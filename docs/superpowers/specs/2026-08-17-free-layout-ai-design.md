# Layout AI en "modo libre" (instrucción del usuario sin constraints)

Fecha: 2026-08-17

## Objetivo

Cuando el usuario da una instrucción explícita al "AI sugiere layout"
(`user_hint`), el AI debe poder rediseñar la slide con **libertad total**: mover y
redimensionar sin área segura, cambiar color y fuente/tamaño de los elementos de
texto sin topes, ocultar (borrar) elementos, y crear cajas de texto / formas /
líneas nuevas. Sin instrucción, el comportamiento actual (corrector al estándar
Aurum) queda **intacto**.

## Decisiones (acordadas)

1. **Disparador:** el modo libre se activa SOLO cuando `user_hint` está presente.
   Sin `user_hint` → prompt y pipeline actuales, sin cambios.
2. **Dimensiones de libertad (con instrucción):** posición/tamaño sin área segura;
   color por elemento; fuente y tamaño sin topes; crear/ocultar elementos.
3. **Charts:** el AI puede mover/redimensionar/**ocultar** un chart, pero NO cambia
   sus colores internos de serie (eso vive en `Chart.colors` del ConfigPanel).
   Color/fuente libres aplican a **texto** (análisis, subtítulos, textboxes creados).
4. **Todo en un solo spec.**

## Contexto actual (verificado)

- `llm_client.py`: `correct_slide_layout(slide_payload, slide_png_bytes, user_hint)`
  usa el system prompt `LAYOUT_CORRECTOR_SYSTEM` (fuerza estándar Aurum, área segura,
  topes tipográficos, colores de marca; "solo mové/redimensioná existentes").
- `api.py` `/api/suggest-slide-layout`: arma `payload_shapes`, llama
  `correct_slide_layout`, parsea `raw["elements"]` → `positions` (LayoutBox por id) y
  `raw["extras"]` → `LayoutExtra` (solo `line`). Con `user_hint` presente YA saltea
  el enforcement backend (`_enforce_multi_row`, `_reposition_analyses`).
- `models.py`: `LayoutBox {x_emu,y_emu,cx_emu,cy_emu, font_pt?, callout, box_style?}`;
  `LayoutExtra {kind:"line", x_emu,y_emu,cx_emu,cy_emu, text?, font_pt?, bold, style?,
  color?, fill?}`; `SlideLayout {positions: dict[str,LayoutBox], extras: list, changes}`.
- `pptx_generator.py`: charts vía `render_pattern`; `_add_analyses_textboxes` y
  `_add_subtitle_textboxes` leen `layout.positions[id]`; `_add_layout_extras` renderiza
  `extras` (líneas + texto). `_add_textbox(slide, text, el, font_name, font_pt)` ya
  acepta fuente; NO acepta color.
- Frontend: `suggestSlideLayout(state, slide_id, user_hint)` (client.ts) ya existe;
  ConfigPanel:392 lo dispara con `layoutHint` (input de instrucción ya presente). El
  layout devuelto se persiste en `slide.layout` (ProjectState). Tipos TS: `LayoutBox`
  tiene `callout`/`box_style`; falta color/font/hidden.

## Modelo de datos (backend)

`LayoutBox` — override por elemento existente:
```python
class LayoutBox(BaseModel):
    x_emu: int
    y_emu: int
    cx_emu: int
    cy_emu: int
    font_pt: float | None = None
    callout: bool = False
    box_style: Literal["dashed"] | None = None
    color: str | None = None        # NEW hex sin # — color de fuente (solo texto)
    font_name: str | None = None    # NEW nombre de fuente (solo texto)
    hidden: bool = False            # NEW true = no renderizar el elemento
```

`LayoutExtra` — elementos creados (líneas + cajas/rects nuevos):
```python
class LayoutExtra(BaseModel):
    kind: Literal["line", "textbox", "rect"]   # AMPLIADO (antes solo "line")
    id: str | None = None            # NEW id del elemento creado (para trazabilidad)
    x_emu: int
    y_emu: int
    cx_emu: int = 0
    cy_emu: int = 0
    text: str | None = None
    font_pt: float | None = None
    font_name: str | None = None     # NEW
    bold: bool = False
    style: str | None = None         # line: dotted|dashed|solid
    color: str | None = None         # hex sin #
    fill: str | None = None          # hex sin #
```

`SlideLayout` sin cambios de forma (los creados reutilizan `extras`).

## Prompt (llm_client.py)

Nuevo `LAYOUT_FREE_SYSTEM` usado por `correct_slide_layout` **solo cuando hay
`user_hint`**. Contenido:
- Rol: diseñador libre. La instrucción del usuario es la máxima autoridad; ejecutala
  al pie de la letra.
- SIN área segura, SIN topes de fuente, SIN colores de marca forzados, SIN estándar
  Aurum. Puede posicionar donde quiera (incluso fuera del canvas si el usuario lo pide).
- Puede: mover/redimensionar cualquier `chart_<id>`/`analysis_<id>`/`subtitle_<id>`;
  poner `color`/`font`/`font_pt` a elementos de **texto** (analysis/subtitle);
  `hidden: true` para ocultar cualquier elemento (incluye charts); crear elementos en
  `created` (textbox/line/rect con texto/estilo).
- NO cambia colores internos de series de charts (mover/redimensionar/ocultar sí).
- Formato de salida (superset del actual):
```json
{
  "elements": [
    {"id":"chart_<id>","x_cm":..,"y_cm":..,"w_cm":..,"h_cm":..,"hidden":false},
    {"id":"analysis_<id>","x_cm":..,"y_cm":..,"w_cm":..,"h_cm":..,"font_pt":24,"font":"Georgia","color":"C00000","hidden":false}
  ],
  "created": [
    {"id":"free_1","kind":"textbox","x_cm":..,"y_cm":..,"w_cm":..,"h_cm":..,"text":"...","font_pt":18,"font":"Arial","color":"404040","fill":"D9D9D9"}
  ],
  "changes": ["..."]
}
```
`correct_slide_layout` elige el system prompt: `LAYOUT_FREE_SYSTEM` si
`user_hint.strip()` no vacío, `LAYOUT_CORRECTOR_SYSTEM` si no.

## Parse (api.py `/api/suggest-slide-layout`)

- Detectar free mode = `bool((req.user_hint or "").strip())` (mismo criterio que ya usa
  para saltear enforce).
- Por cada `el` en `raw["elements"]`: parsear posición (cm→EMU) **sin clamp**; parsear
  `font_pt` (en free mode sin límite; en modo normal, comportamiento actual);
  en free mode además parsear `color`, `font` (→ `font_name`), `hidden` hacia el
  `LayoutBox`. `callout`/`box_style` solo para analysis (como hoy).
- Parsear `raw["created"]` (free mode) → `LayoutExtra(kind, id, ...)` y agregarlos a la
  lista de extras que ya se devuelve. En modo normal se sigue leyendo `raw["extras"]`
  con `kind:"line"` como hoy.
- Enforcement backend: ya se saltea con `user_hint`; mantener.

## Render (pptx_generator.py)

- `_add_textbox`: agregar parámetro `color: str | None = None`; si viene, setear el
  color de fuente del run (`RGBColor.from_string(color)`).
- `_add_analyses_textboxes` y `_add_subtitle_textboxes`: al leer el `LayoutBox`:
  - si `box.hidden` → **saltear** ese elemento;
  - pasar `box.color` y `box.font_name` (override) a `_add_textbox` (font_name override
    tiene prioridad sobre `font_override` del proyecto).
- **Charts ocultos:** en `_add_slide_content`, antes de `classify`/`render_pattern`,
  calcular `hidden_chart_ids = {cid for cid,box in layout.positions.items() if
  box.hidden}` y construir la lista de charts visibles; pasar solo esos al pipeline de
  render (los charts ocultos no se clasifican ni renderizan). Si quedan 0 charts
  visibles, saltear `render_pattern` sin error.
- `_add_layout_extras`: soportar `kind == "textbox"` (usar `_add_textbox` con
  `text/color/font_name/font_pt`, y `fill` como fondo si está presente → forma
  rectángulo con relleno + texto) y `kind == "rect"` (rectángulo con `fill`/borde
  `color`). `kind == "line"` como hoy.

## Frontend (tipos)

`types/index.ts`:
- `LayoutBox` += `color?: string`, `font_name?: string`, `hidden?: boolean`.
- `LayoutExtra`: `kind` amplía a `"line" | "textbox" | "rect"`; += `id?: string`,
  `font_name?: string`.
No hay UI nueva: el input de instrucción (`layoutHint`) y el disparo
(`suggestSlideLayout`) ya existen. El layout devuelto se persiste tal cual en
`slide.layout` y se re-envía al backend en cada request (ya ocurre).

## Manejo de errores / borde

- Sin `user_hint` → 100% comportamiento actual (prompt corrector, enforce, área segura).
- `color`/`font_name` inválidos → el render los ignora dentro de try/except (patrón ya
  usado en `_add_layout_extras`/textboxes); no rompe el export.
- `hidden` en todos los charts → `render_pattern` se saltea; análisis/subtítulos y
  creados igual se renderizan.
- Elemento creado sin `text` (textbox) → se omite; `rect`/`line` no requieren texto.
- Proyecto viejo: `LayoutBox` nuevos campos default (color=None, hidden=False) →
  carga sin romper; `LayoutExtra.kind` viejo "line" sigue válido.

## Testing

Backend (pytest `arch -arm64`):
1. `correct_slide_layout` elige `LAYOUT_FREE_SYSTEM` cuando hay `user_hint` y
   `LAYOUT_CORRECTOR_SYSTEM` cuando no (monkeypatch `_client.messages.create`,
   inspeccionar el `system` pasado).
2. Parse free mode: un `raw` con un `analysis_<id>` que trae `color`,`font`,`font_pt`
   grande, `hidden` y un `created` textbox → `positions[id]` con esos overrides y un
   `LayoutExtra(kind="textbox")` en extras. Sin clamp de coordenadas.
3. `LayoutBox`/`LayoutExtra` nuevos campos: defaults + validación de un layout viejo.
4. Render: `_add_textbox` con `color` produce un run con ese color; un analysis con
   `hidden=True` no aparece en el PPTX; un chart con `hidden=True` (positions) no se
   renderiza; un `LayoutExtra(kind="textbox", text=..)` aparece como texto en el PPTX.

Frontend (vitest):
5. Tipos: un `SlideLayout` con `LayoutBox` que trae `color/font_name/hidden` y un
   `LayoutExtra` `kind:"textbox"` compila (tsc) y round-trips por el store sin perder
   campos (persist/migrate).

## Fuera de alcance

- Cambiar colores internos de series de charts vía layout AI (queda en ConfigPanel).
- Editar el **texto** de análisis/subtítulos vía layout AI (solo estilo/posición;
  el texto se edita en sus campos). Los textboxes **creados** sí llevan su texto.
- UI nueva de instrucción (ya existe `layoutHint`).
- Undo granular por elemento (el layout se recalcula por instrucción; el Undo global
  existente cubre el estado).
