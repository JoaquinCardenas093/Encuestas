import json
import os

from anthropic import Anthropic, APIStatusError
from dotenv import load_dotenv

from .errors import LLMError

load_dotenv()

MODEL = "claude-haiku-4-5-20251001"
MAX_OUTPUT_TOKENS = 500
MAX_TEXT_LENGTH = 1200

SYSTEM_PROMPT = """Sos analista de encuestas. Generás análisis técnicos BREVES en español neutral.

Tono: formal técnico, sin emojis, sin recomendaciones, sin markdown (**bold** prohibido).
Formato: 2-3 oraciones MÁXIMO. Frases tipo "El X% de los encuestados...".
Datos: respetar números exactos, no inventar cifras.

Si scope=chart: 1-2 oraciones sobre el chart específico.
Si scope=slide: 2-3 oraciones sintetizando insights cruzados entre todos los charts. NO listes hallazgos por bloques. NO uses párrafos múltiples.

Idioma: español neutral. Longitud máxima ESTRICTA: 3 oraciones.
"""


def _build_client() -> Anthropic | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    return Anthropic(api_key=key)


_client: Anthropic | None = _build_client()


def generate_analysis(scope: str, context: dict, user_hint: str | None = None) -> str:
    if _client is None:
        raise LLMError("ANTHROPIC_API_KEY no configurada. Agregá a .env y reiniciá el backend.")

    hint = (user_hint or "").strip()[:500]

    charts_block = context.get("charts")
    if charts_block:
        # Multi-chart slide-scope: pass full structured data per chart×breakdown.
        per_chart_lines = []
        for key, val in charts_block.items():
            per_chart_lines.append(
                f"- {key}\n  Pregunta: {val.get('question_text', '')}\n"
                f"  Opciones: {val.get('options', [])}\n"
                f"  Datos: {json.dumps(val.get('data', {}), ensure_ascii=False)}"
            )
        charts_text = "\n".join(per_chart_lines)
        user_msg = (
            f"Sección: \"{context.get('section_title', '')}\"\n"
            f"Scope: {scope}\n"
            f"Slide tiene {len(charts_block)} chart(s)/breakdown(s). "
            f"Analizá TODOS y armá un análisis integral que cruce los hallazgos.\n\n"
            f"Charts:\n{charts_text}\n"
        )
    else:
        user_msg = f"""Sección: "{context.get('section_title', '')}"
Pregunta: "{context.get('question_text', '')}"
Opciones: {context.get('options', [])}
Breakdown: {context.get('breakdown_label', '')}
Datos: {json.dumps(context.get('data', {}), ensure_ascii=False)}
Scope: {scope}
"""

    if hint:
        user_msg += (
            f"\nGuía del usuario (prioridad alta): {hint}\n"
            f"Enfocá y encuadrá el análisis según esta guía, sin inventar datos "
            f"ni contradecir las cifras.\n"
        )

    try:
        msg = _client.messages.create(
            model=MODEL,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_msg}],
        )
    except APIStatusError as e:
        raise LLMError(f"LLM API error: {e}") from e
    except Exception as e:
        raise LLMError(f"LLM error: {e}") from e

    text = "".join(block.text for block in msg.content if hasattr(block, "text")).strip()
    if not text:
        return "[Análisis no disponible — editar manualmente]"
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH - 3] + "..."
    return text


LAYOUT_SYSTEM = """Sos diseñador de slides de encuestas. Te paso config slide y free_area canvas. Devolvés JSON con posiciones EMU para cada elemento.

Reglas:
- Coords todas dentro de free_area (x ≥ free_area.x, x+cx ≤ free_area.x+free_area.cx, similar Y).
- Sin overlaps. Padding mínimo 200000 EMU entre elementos.
- Cada breakdown ⇒ chart separado (NUNCA dos breakdowns en un mismo chart con multi-series).
- Charts deben ocupar ≥75% de la altura de free_area cuando hay 1-2 charts; ≥65% cuando hay 3-6 (grid).
- Output: solo JSON válido, sin texto explicativo.

Slide canvas estándar: 12192000 × 6858000 EMU. Free area típica: x=487680 y=1097280 cx=11216640 cy=5212080.
  → x_end = 487680 + 11216640 = 11704320. y_end = 1097280 + 5212080 = 6309360.

Ejemplo 1 — Single PIE:
  Input: {"n_charts":1,"chart_types":["PIE"],"n_chart_analyses":0,"n_question_analyses":0,"has_slide_analysis":false}
  Output: {"elements":[{"role":"chart_0","x":2286720,"y":1463040,"cx":7619200,"cy":4572000}]}

Ejemplo 2 — Two charts side-by-side (PIE + BAR_CLUSTERED):
  Input: {"n_charts":2,"chart_types":["PIE","BAR_CLUSTERED"],"n_chart_analyses":0,"n_question_analyses":0,"has_slide_analysis":false}
  Output: {"elements":[
    {"role":"chart_0","x":1234440,"y":1463040,"cx":3500000,"cy":4572000},
    {"role":"chart_1","x":6918960,"y":1463040,"cx":3960000,"cy":4572000}
  ]}

Ejemplo 3 — Three charts grid (BAR_CLUSTERED × 3):
  Input: {"n_charts":3,"chart_types":["BAR_CLUSTERED","BAR_CLUSTERED","BAR_CLUSTERED"],"n_chart_analyses":0,"n_question_analyses":0,"has_slide_analysis":false}
  Output: {"elements":[
    {"role":"chart_0","x":487680,"y":1463040,"cx":3500000,"cy":4572000},
    {"role":"chart_1","x":4357680,"y":1463040,"cx":3500000,"cy":4572000},
    {"role":"chart_2","x":8227680,"y":1463040,"cx":3476640,"cy":4572000}
  ]}

Ejemplo 4 — Chart + slide analysis band below:
  Input: {"n_charts":1,"chart_types":["BAR_CLUSTERED"],"n_chart_analyses":0,"n_question_analyses":0,"has_slide_analysis":true}
  Output: {"elements":[
    {"role":"chart_0","x":1234440,"y":1463040,"cx":9500000,"cy":3700000},
    {"role":"slide_analysis","x":487680,"y":5363040,"cx":11216640,"cy":946320}
  ]}

Si hay análisis (chart_analysis_i / question_analysis_i / slide_analysis), apilá debajo del chart al que aplica con altura ≈ 15% del chart y 200000 EMU de padding. Verificá siempre que y+cy ≤ y_end para cada elemento.
"""


_PADDING = 200_000  # EMU
_GRID = {1: (1, 1), 2: (1, 2), 3: (1, 3), 4: (2, 2), 5: (2, 3), 6: (2, 3), 7: (3, 3), 8: (3, 3), 9: (3, 3)}


def _compute_layout_heuristic(
    n_charts: int,
    chart_types: list[str],
    n_chart_analyses: int,
    n_question_analyses: int,
    has_slide_analysis: bool,
    free_area: dict,
) -> dict:
    """Deterministic fallback layout — inlined from deleted layout_engine.py."""
    elements: list[dict] = []
    cx_, cy_ = free_area["x"], free_area["y"]
    cw, ch = free_area["cx"], free_area["cy"]

    slide_an_h = int(ch * 0.15) if has_slide_analysis else 0
    chart_area_h = ch - slide_an_h
    has_chart_an = n_chart_analyses > 0
    chart_an_h = int(chart_area_h * 0.18) if has_chart_an else 0
    grid_h = chart_area_h - chart_an_h

    if n_charts > 0:
        n = min(n_charts, 9)
        rows, cols = _GRID[n]
        cell_w = (cw - _PADDING * (cols - 1)) // cols
        cell_h = (grid_h - _PADDING * (rows - 1)) // rows
        for i in range(n_charts):
            r, c = divmod(i, cols)
            x = cx_ + c * (cell_w + _PADDING)
            y = cy_ + r * (cell_h + _PADDING)
            elements.append({"role": f"chart_{i}", "x": x, "y": y, "cx": cell_w, "cy": cell_h,
                              "chart_type": chart_types[i] if i < len(chart_types) else "BAR"})
        for i in range(min(n_chart_analyses, n_charts)):
            ce = elements[i]
            elements.append({"role": f"chart_analysis_{i}", "x": ce["x"],
                              "y": ce["y"] + ce["cy"] + _PADDING // 2,
                              "cx": ce["cx"], "cy": chart_an_h - _PADDING, "anchor_chart": i})
    for i in range(n_question_analyses):
        elements.append({"role": f"question_analysis_{i}", "x": cx_,
                          "y": cy_ + chart_area_h - chart_an_h + _PADDING,
                          "cx": cw, "cy": chart_an_h - _PADDING})
    if has_slide_analysis:
        elements.append({"role": "slide_analysis", "x": cx_,
                          "y": cy_ + chart_area_h + _PADDING // 2,
                          "cx": cw, "cy": slide_an_h - _PADDING})
    return {"elements": elements}


def suggest_layout(
    n_charts: int,
    chart_types: list[str],
    n_chart_an: int,
    n_q_an: int,
    has_slide_an: bool,
    free_area: dict,
) -> dict:
    if _client is None:
        return {"source": "heuristic", **_compute_layout_heuristic(n_charts, chart_types, n_chart_an, n_q_an, has_slide_an, free_area)}

    user_msg = json.dumps({
        "n_charts": n_charts, "chart_types": chart_types,
        "n_chart_analyses": n_chart_an, "n_question_analyses": n_q_an,
        "has_slide_analysis": has_slide_an,
        "free_area": free_area,
    })

    try:
        # Note: LAYOUT_SYSTEM is ~500 tokens; ephemeral cache requires ≥1024 input tokens.
        # Cache write will be silently skipped server-side until prompt grows.
        msg = _client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=[{"type": "text", "text": LAYOUT_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_msg}],
        )
        text = "".join(b.text for b in msg.content if hasattr(b, "text")).strip()
        # strip code fences if any
        if text.startswith("```"):
            text = "\n".join(line for line in text.split("\n") if not line.startswith("```"))
        parsed = json.loads(text)
        if not _validate_layout(parsed, free_area):
            raise ValueError("Layout validation failed")
        return {"source": "ai", **parsed}
    except Exception:
        return {"source": "ai_fallback", **_compute_layout_heuristic(n_charts, chart_types, n_chart_an, n_q_an, has_slide_an, free_area)}


# ────────────────────────────────────────────────────────────────────────────
# Slide layout corrector (Aurum visual standard)
# ────────────────────────────────────────────────────────────────────────────

LAYOUT_MODEL = "claude-sonnet-4-6"


def correct_slide_layout(
    slide_payload: dict,
    slide_png_bytes: bytes | None = None,
    user_hint: str | None = None,
) -> dict:
    """Send slide structure (+ optional rendered PNG for vision) to Sonnet.
    `user_hint` is free-text guidance from the user (high priority).
    Returns `{elements, extras?, changes}`. Raises LLMError on API failure."""
    if _client is None:
        raise LLMError("ANTHROPIC_API_KEY no configurada.")
    import base64
    user_content: list = []
    hint = (user_hint or "").strip()
    if hint:
        user_content.append({
            "type": "text",
            "text": (
                "INSTRUCCIÓN DEL USUARIO (PRIORIDAD ALTA — respetala salvo que "
                "rompa el área segura o cause overflow):\n" + hint
            ),
        })
    if slide_png_bytes:
        user_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64.b64encode(slide_png_bytes).decode("ascii"),
            },
        })
        user_content.append({
            "type": "text",
            "text": (
                "Arriba va la imagen del slide actual con sus problemas visibles. "
                "Analizá lo que ves + el JSON estructural abajo y devolvé el layout corregido.\n\n"
                + json.dumps(slide_payload, ensure_ascii=False)
            ),
        })
    else:
        user_content.append({"type": "text", "text": json.dumps(slide_payload, ensure_ascii=False)})
    try:
        msg = _client.messages.create(
            model=LAYOUT_MODEL,
            max_tokens=3000,
            system=[{"type": "text", "text": LAYOUT_CORRECTOR_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_content}],
        )
    except APIStatusError as e:
        raise LLMError(f"LLM API error: {e}") from e
    text = "".join(b.text for b in msg.content if hasattr(b, "text")).strip()
    if text.startswith("```"):
        text = "\n".join(l for l in text.split("\n") if not l.startswith("```"))
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"LLM returned non-JSON: {text[:200]}") from e


# ────────────────────────────────────────────────────────────────────────────
# M6.7: Style Guide AI Analysis — Sonnet 4.6 vision
# ────────────────────────────────────────────────────────────────────────────

ANALYSIS_MODEL = "claude-sonnet-4-6"

LAYOUT_CORRECTOR_SYSTEM = """System prompt — Corrector visual de slides (estándar Aurum)
Úsalo como system prompt de la Claude API. El mensaje de usuario trae una slide ya generada (su código python-pptx, su XML, o la lista de shapes con coordenadas). Tu trabajo NO es crear la slide ni cambiar los datos: es corregir su distribución visual para que cumpla el estándar de Aurum. Aplica a cualquier tipo de slide (gráficos, cruces+análisis, demográficos, texto).

ROL
Eres un revisor de maquetación. Recibes una slide y devuelves la misma slide corregida (mismos datos, mismo texto, mismos gráficos) con las posiciones, tamaños, fuentes y colores ajustados a las reglas de abajo. No inventas contenido ni eliminas información: la reubicas, reescalas o repartes para que entre y se vea consistente.

LIENZO Y ÁREA SEGURA (válido para toda slide)
* Tamaño 16:9 = 33.87 × 19.05 cm.
* Área segura de contenido: x ∈ [1.3, 31.9], y ∈ [3.2, 16.5]. Nada de contenido puede salir de ahí. El header vive arriba (y 0.4–2.0) y las notas abajo (y ≈ 16.85).
* Margen izquierdo de referencia: x = 1.3–2.2 cm. Borde derecho duro: x = 31.9 cm.

TOKENS DE MARCA (forzar siempre)
* Colores permitidos (y solo estos): dorado EEC245 / FFC000, rojo énfasis C00000, grises 404040 (texto), 7F7F7F (texto sec./barras), 585858, gris claro D9D9D9, blanco/negro. Cualquier azul/verde/otro del tema Office → reemplázalo por el gris o dorado equivalente.

JERARQUÍA TIPOGRÁFICA (topes máximos por elemento)
Elemento    Tamaño    Peso    Color
Título de slide    15–16 pt    Bold    404040
Subtítulo / pregunta    12–13 pt    Bold    404040
Encabezado de columna/zona    12 pt    Bold    404040
Etiquetas de datos y ejes    8–9 pt    Normal    404040/7F7F7F
Texto de análisis / cuerpo    10.5–11 pt    Normal, justificado    404040
Notas al pie    8 pt    Normal    7F7F7F
Regla crítica: el texto de análisis va entre 10.5 y 11 pt (vos decidís según la cantidad de texto). Si vino más grande (12, 18, 24…), bájalo a 10.5–11 pt. Desactiva el autoajuste que escala la fuente hacia arriba; fija el tamaño.

REGLA POSICIÓN ANÁLISIS:
- analysis con scope="slide" → DEBE colocarse DEBAJO de la pregunta/subtítulo (y_cm ≈ 3.0–4.5), antes de los gráficos. NO al fondo del slide.
- analysis con scope="chart" → al lado/debajo del chart específico.

ESTRUCTURA QUE TODA SLIDE DE CONTENIDO DEBE TENER
1. Header: título (15–16pt) + barra/línea dorada bajo el título en y≈1.9–2.0 + logo arriba a la derecha (x≈32, y≈0.3, ~1.5×1.5 cm). Si falta alguno, agrégalo/reubícalo.
2. Cuerpo dentro del área segura, organizado en zonas (ver siguiente sección).
3. Notas al pie 8pt en y≈16.85. Reserva esa franja: ningún otro elemento la invade.

ZONIFICACIÓN GENERAL DEL CUERPO (elige según lo que contenga la slide)
* Columnas iguales (demográficos / comparativas): 2 cols (~14.3 cm) o 3 cols (~10 cm), cada una con su encabezado 12pt y separadas por línea vertical punteada (dash).
* Gráfico + análisis: gráfico en franja izquierda (x=1.3, w≈10) y "Análisis" a 9pt en columna derecha (x≈12.7, w≈18), separados por línea vertical en x≈11.
* Gráfico + cruces + análisis: gráfico arriba-izq, tablas de cruce arriba-der (sin pasar x=31.9), y el análisis a 9pt en una franja inferior (x=1.3, w=31) que termina en y ≤ 16.4.
* Reparte el alto de modo que entre cabecera de zona + contenido + (en su caso) texto, sin solapes.

DEFECTOS A DETECTAR Y CÓMO CORREGIRLOS
1. Texto que se desborda / pisa las notas → baja la fuente a 9–10pt, fija la caja para que termine en y ≤ 16.4, justifica, alinea arriba, activa word_wrap. Si aún no entra, recorta a un presupuesto de ~90–130 palabras o reparte en una segunda slide (mismo título y subtítulo).
2. Elemento fuera del borde (tabla/gráfico cortado a la derecha) → reescala su ancho o reduce columnas para que el extremo derecho quede en x ≤ 31.9. Si una tabla tiene demasiadas columnas, muévela a una segunda fila o a otra slide; no la dejes cortada.
3. Fuente del análisis demasiado grande (12/18/24pt) → forzar 9–10pt.
4. Etiquetas de pie partidas en vertical (letra por letra) → etiqueta en una sola línea, posición fuera del sector, dale ancho ≥8 cm al área del gráfico.
5. Colores fuera de marca → mapear al gris/dorado/rojo correspondiente.
6. Fuente distinta de Arial → cambiar a Arial.
7. Falta header (barra dorada/logo) o notas → añadir en sus coordenadas estándar.
8. Solapes entre shapes → reubicar dentro de su zona respetando el área segura.
9. Desalineación (encabezados de columna no centrados sobre su gráfico, márgenes irregulares) → alinear al grid: mismos x/anchos por columna, encabezado centrado sobre su contenido.
10. Gráficos inconsistentes → sin título de gráfico, sin gridlines, eje de valores oculto, etiquetas de dato 0.0% a 8–9pt, leyenda abajo centrada solo si hay ≥2 series; series por entidad en gris 7F7F7F / negro 404040 / dorado EEC245.

SALIDA
Devolvé JSON estricto con la lista de elementos corregidos + extras opcionales. Coordenadas en cm.

REGLAS:
- SOLO mové/redimensioná elementos EXISTENTES (chart_<id>, analysis_<id>). NO inventes datos ni texto nuevo.
- Podés agregar `callout: true` a un analysis_<id> para que se renderice como caja destacada (fill gris claro + borde redondeado). Es decisión propia si visualmente lo amerita.
- Podés agregar shapes `line` (separadores visuales sin texto). NO callouts standalone — solo flag sobre analyses.

Formato exacto:
{
  "elements": [
    {"id": "chart_<id>", "x_cm": 1.3, "y_cm": 3.5, "w_cm": 14.3, "h_cm": 10.0},
    {"id": "analysis_<id>", "x_cm": 1.3, "y_cm": 4.0, "w_cm": 30.6, "h_cm": 1.8, "font_pt": 10.5, "callout": false}
  ],
  "extras": [
    {"kind": "line", "x_cm": 11.0, "y_cm": 4.0, "w_cm": 0.0, "h_cm": 10.0, "style": "dotted", "color": "D9D9D9"}
  ],
  "changes": ["ajuste 1", "ajuste 2"]
}

REGLA MULTI-FILA:
El payload incluye `needs_multi_row` y `sum_natural_chart_w_cm`. Si suma > 30cm o ves overflow horizontal en la imagen, distribuí en 2+ filas (y_cm diferentes). Cada fila ≤ 30.6cm.

analysis scope=slide → DEBAJO de la pregunta (y_cm ≈ 3.0–4.5), ANTES de charts.

Solo JSON válido sin texto explicativo fuera del JSON.

CHECKLIST FINAL (todo debe cumplirse)
* [ ] Todo el contenido dentro de x∈[1.3,31.9], y∈[3.2,16.5]; nada cortado.
* [ ] Texto de análisis ≤ 10pt y su caja termina en y ≤ 16.4 (no toca las notas en 16.85).
* [ ] Arial en todo; solo colores de marca.
* [ ] Header (título + barra dorada + logo) y notas 8pt presentes.
* [ ] Encabezados 12pt centrados sobre su zona; divisores punteados entre columnas.
* [ ] Gráficos sin título/grid, etiquetas 0.0%, leyenda solo con ≥2 series.
* [ ] Sin solapes ni desbordes; alineación al grid.
"""
ANALYSIS_MAX_TOKENS = 32000  # full style guide w/ 8-15 patterns + table schemas easily 20-30K
ANALYSIS_TEMPERATURE = 0.2

STYLE_GUIDE_SYSTEM_PROMPT_V1 = """Sos un design system analyst especializado en presentaciones de encuestas de consultoría.

Tu trabajo: analizar las slides de entrenamiento y derivar un style guide JSON que permita generar slides nuevas con datos arbitrarios manteniendo EL MISMO patrón visual: distribución general + breakdowns demográficos como TABLAS COMPACTAS CON MINI-BARRAS, NO como charts standalone separados.

═══════════════════════════════════════════════════════════════════
CRÍTICO — PATRÓN AURORA TÍPICO (lo que tu output DEBE generar)
═══════════════════════════════════════════════════════════════════

La estructura típica que ves en las training slides para preguntas con breakdowns demográficos:

┌─────────────────────────────────────────────────────────────────┐
│ TÍTULO PREGUNTA (P1. ¿Recuerda...?)                             │
│                                                                  │
│ Distribución general    │     Distribución segmentada           │
│ ╔══════════╗            │  ╔═══════╤═══════╤═══════╤═══════╗    │
│ ║          ║            │  ║ Edad  │ Sexo  │  NSE  │ Lugar ║    │
│ ║   PIE    ║            │  ╠═══════╪═══════╪═══════╪═══════╣    │
│ ║   91%    ║            │  ║ ▓▓ 92%│ ▓▓ 92%│ ▓▓ 92%│ ▓▓ 91%║    │
│ ║          ║            │  ║ ▓  8% │ ▓  8% │ ▓  8% │ ▓  9% ║    │
│ ╚══════════╝            │  ╚═══════╧═══════╧═══════╧═══════╝    │
│                                                                  │
│ ┌──────────────────────┐                                         │
│ │ ANÁLISIS PROSA       │                                         │
│ └──────────────────────┘                                         │
└─────────────────────────────────────────────────────────────────┘

NO uses 4 elementos `chart` separados (uno por breakdown). Eso es INCORRECTO.
SÍ usá 1 elemento `chart` (PIE general) + 1 elemento `table` con structure=`segmented_breakdowns` que abarca TODOS los breakdowns en columnas.

═══════════════════════════════════════════════════════════════════

Reglas globales:
- IGNORÁ colores específicos. NO incluyas palette/colors hex en patterns (el usuario los elige).
- DETECTÁ "best examples" cross-corpus: si pattern X aparece en varias slides, elegí EL MEJOR y explicá en `why_picked`.
- Posiciones: fracciones relativas (0-1) del área libre, no EMU absolutos.
- 8-15 patterns total. Más específicos primero (priority 0 = más alta).
- trigger operators: $eq, $neq, $gt, $gte, $lt, $lte, $in, $nin, $and, $or, $not
- trigger fields: n_charts_in_slide, all_charts_share_question, question_type, n_options_per_question, breakdowns_used, n_breakdowns, n_analyses, n_chart_analyses, n_question_analyses, has_slide_analysis

ELEMENT KINDS (los 5 disponibles):
- `chart`: gráfico standalone (pie/bar/donut/etc).
- `table`: tabla con cells formateadas. Structures soportadas: `segmented_breakdowns` (CRÍTICO para Aurora), `simple_data`, `comparison_grid`.
- `text`: textbox. content_source tipo: {"type":"analysis","scope":"slide|question|chart"}, {"type":"computed","kind":"notes|question_text|section_title"}, {"type":"static","text":"..."}
- `shape`: line | rectangle.
- `image`: referenciada del template.

CHART TYPES (en available_chart_types, sólo los que VES):
PIE, DONUT, BAR, COLUMN, BAR_HORIZONTAL, BAR_CLUSTERED, BAR_STACKED, COLUMN_CLUSTERED, COLUMN_STACKED, LINE, AREA, RADAR, TABLE_WITH_MINIBARS, TABLE_SIMPLE.

ENUMS ESTRICTOS:
- shape.shape_type: "line" o "rectangle" SOLAMENTE (no "line_dashed", no "rectangle_dashed_border").
- chart.sort: "none", "desc_by_value", "asc_by_value", "category_order" SOLAMENTE (no "descending"/"ascending").
- legend: "none", "right", "left", "top", "bottom".

Schema JSON esperado (sin modificaciones):
{
  "version": 1,
  "is_builtin": false,
  "generated_at": "<ISO timestamp>",
  "ai_prompt_version": "v2.0",
  "source_pptxs": ["..."],
  "manual_edits": {},
  "global": {
    "typography": {"font_family": "string", "title_size": int, "subtitle_size": int, "label_size": int, "body_size": int},
    "text_patterns": {"title": "string", "notes": "string", "analysis_style": "string", "tone": "string"},
    "suggested_palette": ["#hex", ...],
    "vibe": "string"
  },
  "available_chart_types": ["PIE", ...],
  "patterns": [ ... ]
}

EJEMPLO COMPLETO DE 1 PATTERN BIEN ARMADO (binary + demographics, target Aurora):

{
  "id": "binary_general_with_demographics",
  "priority": 0,
  "trigger": {
    "$and": [
      {"field": "n_charts_in_slide", "$gte": 1},
      {"field": "question_type", "$eq": "binary"},
      {"field": "n_breakdowns", "$gte": 2}
    ]
  },
  "extends": null,
  "best_example": "Aurora.pptx#slide17",
  "why_picked": "Tabla OLE editable que cubre todos los breakdowns. Render via TABLE_WITH_MINIBARS = embedded xlsx + PNG preview.",
  "implementation": {
    "elements": [
      {
        "kind": "chart",
        "id": "main_table",
        "position": {"x_rel": 0.04, "y_rel": 0.18, "w_rel": 0.92, "h_rel": 0.70},
        "chart_type": "TABLE_WITH_MINIBARS",
        "data_source": {"chart_ref_index": 0, "value_field": "pct"}
      }
    ]
  }
}

OBSERVÁ del ejemplo:
- UN solo chart (pie) + UNA tabla con todos los breakdowns. NO 4 charts separados.
- table.structure = "segmented_breakdowns" + data_source.breakdown_groups = "all_except_general".
- text content_source SIEMPRE presente (analysis/static/computed).
- Análisis prose textbox al pie izquierdo.
- shape.shape_type SOLO line/rectangle.
- chart.sort SOLO desc_by_value/asc_by_value/category_order/none.
- legend SIEMPRE "none" en este tipo de pattern (los percentages en data labels suficiente).

DEVOLVÉ ÚNICAMENTE EL JSON VÁLIDO. Sin markdown fences, sin texto explicativo, sin comentarios.
"""


def analyze_training_corpus(slides_content: list[dict]) -> dict:
    """Call Claude Sonnet 4.6 with training slides vision content.

    Args:
        slides_content: Anthropic vision content array (text + image blocks)

    Returns dict with:
        raw_json: str — raw LLM response
        input_tokens: int
        output_tokens: int
        cached_input_tokens: int
        estimated_cost_usd: float
    """
    if _client is None:
        raise LLMError("ANTHROPIC_API_KEY no configurada. Agregá a .env y reiniciá el backend.")

    system_blocks = [
        {
            "type": "text",
            "text": STYLE_GUIDE_SYSTEM_PROMPT_V1,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    # Streaming required by Anthropic for long requests (>10 min). With 32K max_tokens
    # + 30 vision images, call comfortably exceeds that threshold.
    try:
        with _client.messages.stream(
            model=ANALYSIS_MODEL,
            max_tokens=ANALYSIS_MAX_TOKENS,
            temperature=ANALYSIS_TEMPERATURE,
            system=system_blocks,
            messages=[{"role": "user", "content": slides_content}],
        ) as stream:
            msg = stream.get_final_message()
    except Exception as exc:
        raise LLMError(f"Sonnet 4.6 API error: {exc}") from exc

    raw_text = "".join(b.text for b in msg.content if hasattr(b, "text")).strip()

    usage = msg.usage
    input_tokens = getattr(usage, "input_tokens", 0)
    output_tokens = getattr(usage, "output_tokens", 0)
    cached = getattr(usage, "cache_read_input_tokens", 0)
    fresh_input = input_tokens - cached

    # Sonnet 4.6 pricing: $3/M input, $15/M output (approximate)
    cost = (fresh_input / 1_000_000 * 3.0) + (output_tokens / 1_000_000 * 15.0)

    return {
        "raw_json": raw_text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": cached,
        "estimated_cost_usd": round(cost, 4),
    }


def _validate_layout(parsed: dict, free_area: dict) -> bool:
    if "elements" not in parsed or not isinstance(parsed["elements"], list):
        return False
    fx, fy, fw, fh = free_area["x"], free_area["y"], free_area["cx"], free_area["cy"]
    for el in parsed["elements"]:
        for k in ("x", "y", "cx", "cy"):
            if k not in el or not isinstance(el[k], (int, float)):
                return False
        if el["x"] < fx or el["x"] + el["cx"] > fx + fw:
            return False
        if el["y"] < fy or el["y"] + el["cy"] > fy + fh:
            return False
        if el["cx"] <= 0 or el["cy"] <= 0:
            return False
    return True
