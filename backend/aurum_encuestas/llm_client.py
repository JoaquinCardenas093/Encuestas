import json
import os

from anthropic import Anthropic, APIStatusError
from dotenv import load_dotenv

from .errors import LLMError

load_dotenv()

MODEL = "claude-haiku-4-5-20251001"
MAX_OUTPUT_TOKENS = 400
MAX_TEXT_LENGTH = 500

SYSTEM_PROMPT = """Sos analista de encuestas. Generás análisis técnicos breves en español neutral.

Tono: formal técnico, sin emojis, sin recomendaciones de acción salvo pedido.
Formato: 2-4 oraciones. Frases tipo "El X% de los encuestados...".
Datos: respetar números exactos provistos, no inventar cifras.

Si scope=chart: analizás SOLO ese chart específico (distribución, mayoría, contraste por categoría).
Si scope=question: te paso TODOS los charts de la slide que pertenecen a esa pregunta. Comparás entre breakdowns, identificás patrones cruzados de esa pregunta.
Si scope=slide: te paso TODOS los charts de la slide (de cualquier pregunta). Sintetizás insights cruzados entre charts y preguntas.

Idioma: español neutral. Longitud máxima: 4 oraciones.
"""


def _build_client() -> Anthropic | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    return Anthropic(api_key=key)


_client: Anthropic | None = _build_client()


def generate_analysis(scope: str, context: dict) -> str:
    if _client is None:
        raise LLMError("ANTHROPIC_API_KEY no configurada. Agregá a .env y reiniciá el backend.")

    user_msg = f"""Sección: "{context.get('section_title', '')}"
Pregunta: "{context.get('question_text', '')}"
Opciones: {context.get('options', [])}
Breakdown: {context.get('breakdown_label', '')}
Datos: {json.dumps(context.get('data', {}), ensure_ascii=False)}
Scope: {scope}
"""

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


LAYOUT_SYSTEM = """Sos diseñador de slides. Te paso config slide y free_area canvas. Devolvés JSON con posiciones EMU para cada elemento (charts y análisis).

Reglas:
- Coords todas dentro de free_area (x ≥ free_area.x, x+cx ≤ free_area.x+free_area.cx, similar Y).
- Sin overlaps.
- Padding mínimo 200000 EMU entre elementos.
- Output: solo JSON válido, sin texto explicativo, formato:
  {"elements": [{"role": "chart_0", "x": ..., "y": ..., "cx": ..., "cy": ...}, ...]}
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
# M6.7: Style Guide AI Analysis — Sonnet 4.6 vision
# ────────────────────────────────────────────────────────────────────────────

ANALYSIS_MODEL = "claude-sonnet-4-6"
ANALYSIS_MAX_TOKENS = 32000  # full style guide w/ 8-15 patterns + table schemas easily 20-30K
ANALYSIS_TEMPERATURE = 0.2

STYLE_GUIDE_SYSTEM_PROMPT_V1 = """Sos un design system analyst especializado en presentaciones de encuestas.

Tu trabajo: analizar las slides de entrenamiento provistas y derivar un style guide ESTRUCTURADO en JSON que permita generar slides nuevas con datos arbitrarios manteniendo el estilo, jerarquía visual y patrones de presentación de las training slides.

Reglas:
- IGNORÁ colores específicos. El usuario elegirá colores aparte. NO incluyas palette/colors hex en patterns.
- IDENTIFICÁ patterns de presentación: cómo se presenta cada tipo de pregunta (binaria, múltiple, ranking), cómo se muestran breakdowns demográficos (tablas con mini-bars vs charts agrupados), dónde van los análisis.
- IDENTIFICÁ tipos de gráfico/elemento usados (PIE, BAR_HORIZONTAL, TABLE_WITH_MINIBARS, etc). Lista en available_chart_types SOLO los que VES.
- DETECTÁ "best examples" cross-corpus: si pattern X tiene 3 ejemplos en distintas slides, elegí EL MEJOR (más limpio, jerarquía más clara, más legible) y explicá por qué en why_picked.
- Posiciones: usá fracciones relativas (0-1) del área libre, no EMU absolutos.
- 8-15 patterns total. Más específicos primero (menor priority number = mayor prioridad).
- trigger operators soportados: $eq, $neq, $gt, $gte, $lt, $lte, $in, $nin, $and, $or, $not
- trigger fields: n_charts_in_slide, all_charts_share_question, question_type, n_options_per_question, breakdowns_used, n_breakdowns, n_analyses, n_chart_analyses, n_question_analyses, has_slide_analysis

Schema JSON esperado:
{
  "version": 1,
  "is_builtin": false,
  "generated_at": "<ISO timestamp>",
  "ai_prompt_version": "v1.0",
  "source_pptxs": ["..."],
  "manual_edits": {},
  "global": {
    "typography": {"font_family": "string", "title_size": int, "subtitle_size": int, "label_size": int, "body_size": int},
    "text_patterns": {"title": "string", "notes": "string", "analysis_style": "string", "tone": "string"},
    "suggested_palette": ["#hex", ...],
    "vibe": "string"
  },
  "available_chart_types": ["PIE", "DONUT", "BAR_HORIZONTAL", "BAR_CLUSTERED", "COLUMN_CLUSTERED", "TABLE_WITH_MINIBARS"],
  "patterns": [
    {
      "id": "unique_snake_case_id",
      "priority": 0,
      "trigger": {"$and": [{"field": "n_charts_in_slide", "$eq": 1}, {"field": "question_type", "$eq": "binary"}]},
      "extends": null,
      "best_example": "file.pptx#slideN",
      "why_picked": "string",
      "implementation": {
        "elements": [
          {"kind": "chart", "id": "el_id", "position": {"x_rel": 0.05, "y_rel": 0.1, "w_rel": 0.4, "h_rel": 0.7}, "chart_type": "PIE", "data_source": {"chart_ref_index": 0, "value_field": "pct"}, "labels": {"show_percentage": true, "position": "outside_end", "format": "0.0%"}, "legend": "none", "sort": "none"}
        ]
      }
    }
  ]
}

Devolvé ÚNICAMENTE el JSON válido. Sin markdown fences, sin comentarios fuera del JSON, sin texto explicativo.
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
