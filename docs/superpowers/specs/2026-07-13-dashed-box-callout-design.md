# Diseño: cuadro punteado (dashed box) alrededor del análisis vía AI sugiere layout

**Fecha:** 2026-07-13
**Estado:** aprobado, pendiente de plan de implementación

## Problema

El AI-suggest-layout (`correct_slide_layout`) puede destacar un análisis como **callout** (rectángulo redondeado, relleno gris `#D9D9D9`). No puede envolverlo en un **cuadro con borde punteado sin relleno** (estilo "ficha técnica"), que el usuario quiere como opción visual.

## Objetivo

Que el AI-suggest-layout pueda envolver un análisis en un **rectángulo de borde punteado, sin relleno**. Es una variante del callout. Solo el AI lo emite (no hay control manual del usuario). Blanco = comportamiento actual.

## Decisiones (cerradas con el usuario)

- El cuadro **envuelve un análisis** (como el callout), no es un marco vacío standalone.
- Es un **estilo nuevo** (el código no lo dibuja hoy): hay que agregar render + capacidad en el AI.
- Solo lo emite el **AI** (`correct_slide_layout`); sin control manual del usuario.

## No-objetivos

- Marco vacío standalone / que rodee múltiples elementos.
- Control manual del usuario para el cuadro punteado.
- Tocar el mecanismo de `callout` filled existente (se mantiene).

## Arquitectura

Aditivo sobre el pipeline de layout existente: AI → api.py (parseo) → `LayoutBox` → `_add_analyses_textboxes` → renderer.

### 1. Modelo — `LayoutBox` (`backend/aurum_encuestas/models.py`)

Agregar campo (después de `callout`):

```python
    box_style: Literal["dashed"] | None = None  # dashed-border box wrapping the analysis (AI-only)
```

(Importar `Literal` si no está.) `callout: bool` se mantiene (relleno redondeado). Semántica al render: `box_style=="dashed"` gana sobre `callout` si por error vinieran ambos.

### 2. Render — `pptx_generator.py`

Nueva función `_add_dashed_box(slide, text, el, font_name=None, font_pt=None)` — espejo de `_add_callout` pero:
- `shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(el["x"]), Emu(el["y"]), Emu(el["cx"]), Emu(el["cy"]))`
- `shape.fill.background()` (sin relleno)
- Borde punteado: `shape.line.color.rgb = RGBColor(0x40, 0x40, 0x40)`, `shape.line.width = Pt(1)`, y aplicar dash vía XML igual que las líneas dashed existentes (pptx_generator:290-296): obtener `ln = shape.line._get_or_add_ln()`, crear `a:prstDash` con `val="dash"`, remover dashes previos, append.
- Texto adentro: mismo patrón que `_add_callout` (word_wrap, `auto_size = NONE`, run con `font_name`/`font_pt`, color `#404040`).

En `_add_analyses_textboxes` (donde hoy decide `if callout: _add_callout(...) else: _add_textbox(...)`), cambiar a:
```python
if box_style == "dashed":
    _add_dashed_box(slide, a.text, el, font_override, font_pt=font_pt)
elif callout:
    _add_callout(slide, a.text, el, font_override, font_pt=font_pt)
else:
    _add_textbox(slide, a.text, el, font_override, font_pt=font_pt)
```
donde `box_style = getattr(box, "box_style", None)` (leído del `LayoutBox`, junto al `callout` actual).

### 3. Endpoint — `api.py`

En el parseo del layout del AI (donde se arma `positions[key]` con `callout`, ~línea 720-727), propagar `box_style`:
```python
    "box_style": el.get("box_style") if is_analysis else None,
```
(solo para analysis, igual que `callout`). Debe quedar como campo de la `LayoutBox` resultante.

### 4. AI — `correct_slide_layout` prompt (`llm_client.py`)

- Agregar a las reglas (cerca de donde menciona `callout: true`, ~línea 356): que puede setear `box_style: "dashed"` en un `analysis_<id>` para envolverlo en un cuadro de borde punteado sin relleno (útil para fichas técnicas / bloques de contexto destacados). Es mutuamente excluyente con `callout`.
- Ajustar la línea que prohíbe `"rectangle_dashed_border"` (~línea 440) para no contradecir la nueva capacidad (el dashed box es un atributo del analysis, no un `shape_type` nuevo — aclarar que el dash se pide vía `box_style` en el analysis, no como shape).

## Data flow

```
correct_slide_layout (AI) → {id: "analysis_x", box_style: "dashed", x_cm, y_cm, ...}
  → api.py parseo → positions["analysis_x"].box_style = "dashed"  (LayoutBox)
  → _add_analyses_textboxes → box_style=="dashed" → _add_dashed_box
  → shape rectangle, sin fill, borde dash gris, texto adentro
```

## Edge cases

- `box_style` ausente/None → comportamiento actual (callout o textbox).
- `box_style` valor inválido (no "dashed") → tratado como None → textbox normal.
- `callout: true` Y `box_style: "dashed"` → dashed gana (documentado; el prompt los pide mutuamente excluyentes).
- Backward-compat: proyectos/layouts existentes sin `box_style` → default None, sin cambio.

## Componentes y límites

- `_add_dashed_box`: una responsabilidad (renderizar analysis en rectángulo dashed sin fill). Independiente de `_add_callout`.
- `LayoutBox.box_style`: campo aditivo; el resto del pipeline lo ignora si es None.
- api.py: solo propaga el campo; sin lógica nueva.

## Testing

**Backend** (`backend/tests/test_pptx_generator.py` o donde vivan los tests de callout):
- `test_add_dashed_box_no_fill_dashed_border`: llamar `_add_dashed_box` en un slide vacío → se agrega 1 shape; su `<a:prstDash val="dash"/>` está presente en el XML de la línea; el fill es background/none.
- `test_analyses_textboxes_dashed_box`: `_add_analyses_textboxes` con un `LayoutBox(box_style="dashed")` → usa el dashed box (shape con prstDash), no el callout filled.
- `test_analyses_textboxes_box_style_none_unchanged`: sin `box_style` → comportamiento actual (callout si `callout=True`, else textbox).

**Backend** (`backend/tests/test_api.py`, si hay patrón del suggest-slide-layout): el parseo propaga `box_style` a la `LayoutBox` para un elemento analysis con `box_style: "dashed"`.

**Prompt:** no requiere test automático; verificación manual de que el AI puede emitirlo.

## Archivos afectados

- `backend/aurum_encuestas/models.py` — `LayoutBox.box_style`.
- `backend/aurum_encuestas/pptx_generator.py` — `_add_dashed_box` + dispatch en `_add_analyses_textboxes`.
- `backend/aurum_encuestas/api.py` — propagar `box_style` en el parseo del layout.
- `backend/aurum_encuestas/llm_client.py` — regla en el prompt de `correct_slide_layout` + ajuste de la prohibición.
- `backend/tests/test_pptx_generator.py` (o equivalente) — tests del dashed box.
