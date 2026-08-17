# Free-Mode Layout AI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the user gives an explicit `user_hint`, let the layout AI redesign a slide with total freedom — free position/size, per-element color/font/size on text, hide elements, and create new textboxes/shapes/lines — while the no-hint path stays exactly as today.

**Architecture:** A "free mode" is toggled by a non-empty `user_hint`. In free mode `correct_slide_layout` uses a new `LAYOUT_FREE_SYSTEM` prompt and the endpoint parses extra per-element overrides (`color`, `font`, `hidden`) plus a `created` array of new elements. The model gains `LayoutBox.color/font_name/hidden` and widens `LayoutExtra.kind` to `line|textbox|rect`. The renderer applies those overrides (skip hidden, color/font on text, render created shapes; hidden charts are filtered before the chart pipeline). Frontend just widens the TS types.

**Tech Stack:** FastAPI + Pydantic + python-pptx (backend, `arch -arm64 .venv/bin/pytest`); React + TypeScript + Vitest (frontend).

## Global Constraints

- Free mode triggers ONLY when `(user_hint or "").strip()` is non-empty. With no hint, behavior is 100% unchanged (existing `LAYOUT_CORRECTOR_SYSTEM`, safe area, enforce, caps).
- Charts: may be moved/resized/hidden, but their internal series colors are NOT changed by the layout AI.
- Color/font overrides apply only to TEXT elements (analysis, subtitle, created textboxes). Colors are hex strings without `#`.
- Backend tests run with `arch -arm64 .venv/bin/pytest` (plain pytest hits an x86_64/arm64 mismatch).
- Old ProjectState/SlideLayout must still validate (new fields default: color=None, font_name=None, hidden=False; `LayoutExtra.kind` "line" still valid).
- Known pre-existing failures (do NOT fix; "no new failures" is the bar): backend test_generate_analysis_truncates_long_response, test_build_pptx_with_chart, test_load_active_returns_file_when_present; frontend AddChartModal (4), ConfigPanel (1), AddAnalysisModal (1).

---

### Task 1: Backend model — LayoutBox + LayoutExtra new fields

**Files:**
- Modify: `backend/aurum_encuestas/models.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `LayoutBox` += `color: str | None = None`, `font_name: str | None = None`, `hidden: bool = False`. `LayoutExtra.kind: Literal["line","textbox","rect"]`, += `id: str | None = None`, `font_name: str | None = None`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_models.py`:

```python
def test_layout_box_new_fields_default():
    from aurum_encuestas.models import LayoutBox
    b = LayoutBox(x_emu=0, y_emu=0, cx_emu=100, cy_emu=100)
    assert b.color is None and b.font_name is None and b.hidden is False


def test_layout_box_accepts_overrides():
    from aurum_encuestas.models import LayoutBox
    b = LayoutBox(x_emu=0, y_emu=0, cx_emu=1, cy_emu=1, color="C00000", font_name="Georgia", hidden=True)
    assert b.color == "C00000" and b.font_name == "Georgia" and b.hidden is True


def test_layout_extra_textbox_kind():
    from aurum_encuestas.models import LayoutExtra
    e = LayoutExtra(kind="textbox", id="free_1", x_emu=1, y_emu=1, cx_emu=10, cy_emu=2,
                    text="Hola", font_name="Arial", color="404040", fill="D9D9D9")
    assert e.kind == "textbox" and e.id == "free_1" and e.text == "Hola"


def test_layout_extra_line_still_valid():
    from aurum_encuestas.models import LayoutExtra
    e = LayoutExtra(kind="line", x_emu=0, y_emu=0, cx_emu=100, cy_emu=0, style="dotted", color="D9D9D9")
    assert e.kind == "line"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && arch -arm64 .venv/bin/pytest tests/test_models.py::test_layout_box_accepts_overrides tests/test_models.py::test_layout_extra_textbox_kind -v`
Expected: FAIL — new fields / kinds not accepted.

- [ ] **Step 3: Write minimal implementation**

In `models.py`, extend `LayoutBox` (add after `box_style`):
```python
    color: str | None = None      # hex without # — font color (text elements only)
    font_name: str | None = None  # font family (text elements only)
    hidden: bool = False          # true = do not render this element
```
Widen `LayoutExtra`:
```python
class LayoutExtra(BaseModel):
    """AI-created extra visual shape: line separator, or (free mode) textbox / rect."""
    kind: Literal["line", "textbox", "rect"]
    id: str | None = None
    x_emu: int
    y_emu: int
    cx_emu: int = 0
    cy_emu: int = 0
    text: str | None = None
    font_pt: float | None = None
    font_name: str | None = None
    bold: bool = False
    style: str | None = None
    color: str | None = None
    fill: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && arch -arm64 .venv/bin/pytest tests/test_models.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/models.py backend/tests/test_models.py
git commit -m "feat(free-layout): LayoutBox color/font/hidden + LayoutExtra textbox/rect kinds"
```

---

### Task 2: Backend prompt — LAYOUT_FREE_SYSTEM selected by user_hint

**Files:**
- Modify: `backend/aurum_encuestas/llm_client.py`
- Test: `backend/tests/test_llm_client.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: module constant `LAYOUT_FREE_SYSTEM`; `correct_slide_layout` picks `LAYOUT_FREE_SYSTEM` when `(user_hint or "").strip()` is non-empty, else `LAYOUT_CORRECTOR_SYSTEM`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_llm_client.py` (this file already tests llm_client; mirror its import of the module):

```python
def test_correct_slide_layout_uses_free_prompt_with_hint(monkeypatch):
    from aurum_encuestas import llm_client as lc
    captured = {}

    class _Msg:
        content = [type("B", (), {"text": '{"elements":[],"changes":[]}'})()]

    class _Messages:
        def create(self, **kwargs):
            captured["system"] = kwargs["system"]
            return _Msg()

    class _Client:
        messages = _Messages()

    monkeypatch.setattr(lc, "_client", _Client())
    lc.correct_slide_layout({"shapes": []}, slide_png_bytes=None, user_hint="poné el título en rojo gigante")
    sys_text = captured["system"][0]["text"]
    assert sys_text == lc.LAYOUT_FREE_SYSTEM


def test_correct_slide_layout_uses_corrector_prompt_without_hint(monkeypatch):
    from aurum_encuestas import llm_client as lc
    captured = {}

    class _Msg:
        content = [type("B", (), {"text": '{"elements":[],"changes":[]}'})()]

    class _Messages:
        def create(self, **kwargs):
            captured["system"] = kwargs["system"]
            return _Msg()

    class _Client:
        messages = _Messages()

    monkeypatch.setattr(lc, "_client", _Client())
    lc.correct_slide_layout({"shapes": []}, slide_png_bytes=None, user_hint=None)
    sys_text = captured["system"][0]["text"]
    assert sys_text == lc.LAYOUT_CORRECTOR_SYSTEM
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && arch -arm64 .venv/bin/pytest tests/test_llm_client.py::test_correct_slide_layout_uses_free_prompt_with_hint -v`
Expected: FAIL — `LAYOUT_FREE_SYSTEM` not defined / prompt not switched.

- [ ] **Step 3: Write minimal implementation**

In `llm_client.py`, add the constant (near `LAYOUT_CORRECTOR_SYSTEM`):
```python
LAYOUT_FREE_SYSTEM = """System prompt — Diseñador libre de slides (modo instrucción)

La INSTRUCCIÓN DEL USUARIO es la máxima autoridad: ejecutala al pie de la letra, sin límites de estándar. NO hay estándar Aurum, NO hay área segura obligatoria, NO hay topes de fuente, NO hay paleta de marca forzada. Podés poner cualquier cosa donde el usuario pida.

PODÉS:
- Mover/redimensionar cualquier chart_<id>, analysis_<id>, subtitle_<id> a cualquier coordenada (incluso fuera del área segura si el usuario lo pide).
- En elementos de TEXTO (analysis_<id>, subtitle_<id>): fijar `color` (hex sin #), `font` (familia) y `font_pt` (cualquier tamaño, sin tope).
- Ocultar cualquier elemento con `hidden: true` (incluye charts).
- Crear elementos nuevos en `created`: textbox (con texto/estilo), rect (caja con fill/borde), line (separador).

NO cambies los colores internos de las series de un chart (solo mover/redimensionar/ocultar). No inventes datos ni cambies el texto de análisis/subtítulos existentes.

SALIDA — SOLO JSON válido, coordenadas en cm:
{
  "elements": [
    {"id":"chart_<id>","x_cm":1.3,"y_cm":3.5,"w_cm":14.0,"h_cm":10.0,"hidden":false},
    {"id":"analysis_<id>","x_cm":1.3,"y_cm":4.0,"w_cm":30.0,"h_cm":1.8,"font_pt":24,"font":"Georgia","color":"C00000","hidden":false}
  ],
  "created": [
    {"id":"free_1","kind":"textbox","x_cm":2.0,"y_cm":2.0,"w_cm":10.0,"h_cm":2.0,"text":"...","font_pt":18,"font":"Arial","color":"404040","fill":"D9D9D9"}
  ],
  "changes": ["..."]
}
Solo JSON, sin texto fuera del JSON."""
```
In `correct_slide_layout`, choose the system prompt by hint. Find where it calls `_client.messages.create(... system=[{"type":"text","text": LAYOUT_CORRECTOR_SYSTEM, ...}])` and replace the hardcoded constant with a variable set at the top of the function:
```python
    system_prompt = LAYOUT_FREE_SYSTEM if (user_hint or "").strip() else LAYOUT_CORRECTOR_SYSTEM
```
and use `system_prompt` in the `system=[{"type":"text","text": system_prompt, "cache_control": {"type":"ephemeral"}}]` list.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && arch -arm64 .venv/bin/pytest tests/test_llm_client.py -q`
Expected: the two new tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/llm_client.py backend/tests/test_llm_client.py
git commit -m "feat(free-layout): LAYOUT_FREE_SYSTEM prompt selected when user_hint present"
```

---

### Task 3: Backend parse — free-mode overrides + created elements

**Files:**
- Modify: `backend/aurum_encuestas/api.py` (the `/api/suggest-slide-layout` parse block: the `for el in raw.get("elements", ...)` loop ~647-679 and the extras loop ~698+)
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (model fields are dicts here; the endpoint returns plain dicts that Pydantic later validates on save).
- Produces: in free mode, each `positions[key]` dict also carries `color`, `font_name`, `hidden`; and `raw["created"]` is parsed into the returned `extras` list with `kind` in `line|textbox|rect`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_api.py` (reuse the stub pattern from the existing subtitle layout test — monkeypatch `correct_slide_layout`, `render_slide_to_png`, `build_pptx` on `aurum_encuestas.api`):

```python
def test_suggest_slide_layout_free_mode_overrides(monkeypatch, valid_xlsx_path):
    from aurum_encuestas import api as api_mod
    state = {
        "project_name": "T",
        "inputs": {"db_path": str(valid_xlsx_path), "template_path": "y"},
        "parsed_db": None,
        "slides": [
            {"id": "s2", "type": "shell", "title": "Sec",
             "charts": [{"id": "c1", "question_id": "q1", "breakdown_ids": [], "chart_type": "PIE"}],
             "analyses": [{"id": "a1", "scope": "slide", "text": "T"}],
             "subtitles": []},
        ],
    }

    def fake_correct(slide_payload, slide_png_bytes=None, user_hint=None):
        return {
            "elements": [
                {"id": "analysis_a1", "x_cm": 1.0, "y_cm": 2.0, "w_cm": 10.0, "h_cm": 2.0,
                 "font_pt": 30, "font": "Georgia", "color": "C00000", "hidden": True},
            ],
            "created": [
                {"id": "free_1", "kind": "textbox", "x_cm": 2.0, "y_cm": 2.0, "w_cm": 8.0, "h_cm": 1.5,
                 "text": "NUEVO", "font": "Arial", "font_pt": 18, "color": "404040", "fill": "D9D9D9"},
            ],
            "changes": ["x"],
        }
    monkeypatch.setattr(api_mod, "correct_slide_layout", fake_correct)
    monkeypatch.setattr(api_mod, "render_slide_to_png", lambda *a, **k: None)
    monkeypatch.setattr(api_mod, "build_pptx", lambda *a, **k: None)

    r = client.post("/api/suggest-slide-layout", json={"state": state, "slide_id": "s2", "user_hint": "hacelo rojo gigante"})
    assert r.status_code == 200
    body = r.json()
    pos = body["positions"]["a1"]
    assert pos["color"] == "C00000"
    assert pos["font_name"] == "Georgia"
    assert pos["hidden"] is True
    assert pos["font_pt"] == 30.0  # no cap
    created = [e for e in body["extras"] if e.get("kind") == "textbox"]
    assert len(created) == 1 and created[0]["text"] == "NUEVO"
```

(Confirm the endpoint's response key for extras — the existing code returns `extras` as EMU dicts; match whatever the real response calls it. The two must-hold facts: the analysis override carries color/font_name/hidden/uncapped font_pt, and a created textbox appears in the returned extras.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && arch -arm64 .venv/bin/pytest tests/test_api.py::test_suggest_slide_layout_free_mode_overrides -v`
Expected: FAIL — positions lack color/font_name/hidden; created textbox not in extras.

- [ ] **Step 3: Write minimal implementation**

In `api.py`, compute the free flag once, before the positions loop:
```python
    free_mode = bool((req.user_hint or "").strip())
```
Inside the `for el in raw.get("elements", ...)` loop, when building `positions[key]`, add the override fields in free mode (leave font_pt handling as-is — it is already uncapped; just skip the analysis=11 default when the AI provided a value, which it already does):
```python
        entry = {
            "x_emu": int(float(el.get("x_cm", 0)) * EMU),
            "y_emu": int(float(el.get("y_cm", 0)) * EMU),
            "cx_emu": int(float(el.get("w_cm", 0)) * EMU),
            "cy_emu": int(float(el.get("h_cm", 0)) * EMU),
            "font_pt": font_pt,
            "callout": bool(el.get("callout", False)) if is_analysis else False,
            "box_style": (el.get("box_style") if el.get("box_style") == "dashed" else None) if is_analysis else None,
        }
        if free_mode:
            c = el.get("color")
            f = el.get("font")
            entry["color"] = str(c) if c else None
            entry["font_name"] = str(f) if f else None
            entry["hidden"] = bool(el.get("hidden", False))
        positions[key] = entry
```
After the existing extras (`line`) loop, in free mode also parse `created`:
```python
    if free_mode:
        for ex in raw.get("created", []) or []:
            kind = ex.get("kind")
            if kind not in ("textbox", "rect", "line"):
                continue
            extras_emu.append({
                "kind": kind,
                "id": (str(ex.get("id")) if ex.get("id") else None),
                "x_emu": int(float(ex.get("x_cm", 0)) * EMU),
                "y_emu": int(float(ex.get("y_cm", 0)) * EMU),
                "cx_emu": int(float(ex.get("w_cm", 0)) * EMU),
                "cy_emu": int(float(ex.get("h_cm", 0)) * EMU),
                "text": ex.get("text"),
                "font_pt": (float(ex["font_pt"]) if ex.get("font_pt") is not None else None),
                "font_name": (str(ex.get("font")) if ex.get("font") else None),
                "bold": bool(ex.get("bold", False)),
                "style": ex.get("style"),
                "color": ex.get("color"),
                "fill": ex.get("fill"),
            })
```
(Use the existing `extras_emu` list variable name that the endpoint already builds and returns; match it exactly by reading the code.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && arch -arm64 .venv/bin/pytest tests/test_api.py::test_suggest_slide_layout_free_mode_overrides tests/test_api.py::test_suggest_slide_layout_positions_subtitle -v`
Expected: both PASS (the subtitle test confirms non-free parsing still works).

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/api.py backend/tests/test_api.py
git commit -m "feat(free-layout): parse per-element color/font/hidden + created elements in free mode"
```

---

### Task 4: Backend render — apply overrides, hide, create

**Files:**
- Modify: `backend/aurum_encuestas/pptx_generator.py`
- Test: `backend/tests/test_pptx_generator.py`

**Interfaces:**
- Consumes: `LayoutBox.color/font_name/hidden` (Task 1); `LayoutExtra` textbox/rect (Task 1).
- Produces: `_add_textbox` accepts `color`; text elements honor color/font_name/hidden; hidden charts are filtered before the chart pipeline; `_add_layout_extras` renders `textbox`/`rect`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_pptx_generator.py` (add `Subtitle` already imported; add `LayoutBox`, `SlideLayout`, `LayoutExtra` to the models import):

```python
def test_add_textbox_applies_color():
    from pptx import Presentation
    from pptx.util import Inches
    from aurum_encuestas.pptx_generator import _add_textbox
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_textbox(slide, "Hola", {"x": 0, "y": 0, "cx": 1000000, "cy": 500000}, None, font_pt=12, color="C00000")
    tb = [s for s in slide.shapes if s.has_text_frame][-1]
    run = tb.text_frame.paragraphs[0].runs[0]
    assert str(run.font.color.rgb) == "C00000"


def test_hidden_analysis_not_rendered(tmp_path, valid_xlsx_path, valid_template_path):
    from aurum_encuestas.models import Analysis, SlideLayout, LayoutBox
    layout = SlideLayout(positions={"a1": LayoutBox(x_emu=0, y_emu=0, cx_emu=100, cy_emu=100, hidden=True)})
    slides = [
        Slide(id="s1", type="separator", title="Sec"),
        Slide(id="s2", type="shell", title="Sec", charts=[], subtitles=[],
              analyses=[Analysis(id="a1", scope="slide", text="OCULTO_XYZ")], layout=layout),
    ]
    state = _state(slides, valid_xlsx_path, valid_template_path)
    out = tmp_path / "out.pptx"
    build_pptx(state, str(out))
    prs = Presentation(str(out))
    texts = [sh.text_frame.text for sh in prs.slides[1].shapes if sh.has_text_frame]
    assert not any("OCULTO_XYZ" in t for t in texts)


def test_created_textbox_rendered(tmp_path, valid_xlsx_path, valid_template_path):
    from aurum_encuestas.models import SlideLayout, LayoutExtra
    layout = SlideLayout(extras=[LayoutExtra(kind="textbox", id="free_1", x_emu=1000000, y_emu=1000000,
                                             cx_emu=3000000, cy_emu=800000, text="CREADO_XYZ", color="404040")])
    slides = [
        Slide(id="s1", type="separator", title="Sec"),
        Slide(id="s2", type="shell", title="Sec", charts=[], analyses=[], subtitles=[], layout=layout),
    ]
    state = _state(slides, valid_xlsx_path, valid_template_path)
    out = tmp_path / "out.pptx"
    build_pptx(state, str(out))
    prs = Presentation(str(out))
    texts = [sh.text_frame.text for sh in prs.slides[1].shapes if sh.has_text_frame]
    assert any("CREADO_XYZ" in t for t in texts)


def test_hidden_chart_not_rendered(tmp_path, valid_xlsx_path, valid_template_path):
    from aurum_encuestas.models import SlideLayout, LayoutBox
    layout = SlideLayout(positions={"c1": LayoutBox(x_emu=0, y_emu=0, cx_emu=1, cy_emu=1, hidden=True)})
    slides = [
        Slide(id="s1", type="separator", title="Sec"),
        Slide(id="s2", type="shell", title="Sec", subtitles=[], analyses=[],
              charts=[Chart(id="c1", question_id="q1", breakdown_ids=[], chart_type="PIE")], layout=layout),
    ]
    state = _state(slides, valid_xlsx_path, valid_template_path)
    out = tmp_path / "out.pptx"
    build_pptx(state, str(out))
    prs = Presentation(str(out))
    n_charts = sum(1 for sh in prs.slides[1].shapes if getattr(sh, "has_chart", False))
    assert n_charts == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && arch -arm64 .venv/bin/pytest tests/test_pptx_generator.py::test_add_textbox_applies_color tests/test_pptx_generator.py::test_hidden_analysis_not_rendered tests/test_pptx_generator.py::test_created_textbox_rendered tests/test_pptx_generator.py::test_hidden_chart_not_rendered -v`
Expected: all FAIL.

- [ ] **Step 3: Write minimal implementation**

In `pptx_generator.py`:

**(a) `_add_textbox`** — add a `color` param and apply it to the run:
```python
def _add_textbox(slide, text: str, el: dict, font_name: str | None = None, font_pt: int | None = None, color: str | None = None) -> None:
```
After `run.text = text` and the `font_name`/`font_pt` block, add:
```python
    if color:
        from pptx.dml.color import RGBColor
        try:
            run.font.color.rgb = RGBColor.from_string(color)
        except Exception:
            pass
```

**(b) `_add_analyses_textboxes`** — in the loop over analyses, read overrides from the `LayoutBox`. Where it currently sets `font_pt = box.font_pt` etc. in the `a.id in ai_positions` branch, also read `color`/`font_name`/`hidden`, and skip hidden:
```python
        box = ai_positions.get(a.id)
        if box is not None and getattr(box, "hidden", False):
            continue
        override_color = getattr(box, "color", None) if box is not None else None
        override_font = getattr(box, "font_name", None) if box is not None else None
```
Pass them to the render call — for the plain `_add_textbox` branch use `_add_textbox(slide, a.text, el, override_font or font_override, font_pt=font_pt, color=override_color)`. (Leave the callout/dashed branches as they are — those are standard-mode styling.)

**(c) `_add_subtitle_textboxes`** — same pattern: skip if `box.hidden`; pass `box.color` and `box.font_name` (override over `font_override`) to `_add_textbox`.

**(d) Hidden charts** — in `_add_slide_content`, before the classify/render_pattern pipeline, filter out charts whose LayoutBox is hidden, and use the filtered list wherever charts drive the pipeline (read the function to place this correctly — the charts feed `build_slide_config`/`classify`). Compute:
```python
    _pos = slide_def.layout.positions if (slide_def.layout and slide_def.layout.positions) else {}
    _visible_charts = [c for c in slide_def.charts if not (c.id in _pos and getattr(_pos[c.id], "hidden", False))]
```
Use `_visible_charts` in place of `slide_def.charts` for the pattern pipeline. If `_visible_charts` is empty, skip `render_pattern` entirely (guard the classify/render block) so no chart is drawn — the analyses/subtitles/extras still render.

**(e) `_add_layout_extras`** — handle `kind == "textbox"` and `kind == "rect"`. In the `for ex in extras:` loop, after the `if ex.kind == "line":` branch, add:
```python
            elif ex.kind == "textbox":
                el = {"x": ex.x_emu, "y": ex.y_emu, "cx": ex.cx_emu, "cy": ex.cy_emu}
                if ex.fill:
                    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(ex.x_emu), Emu(ex.y_emu), Emu(ex.cx_emu), Emu(ex.cy_emu))
                    shape.fill.solid(); shape.fill.fore_color.rgb = RGBColor.from_string(ex.fill)
                    shape.line.fill.background()
                    tf = shape.text_frame; tf.word_wrap = True
                    tf.text = ex.text or ""
                    if ex.color:
                        for p in tf.paragraphs:
                            for r in p.runs:
                                r.font.color.rgb = RGBColor.from_string(ex.color)
                    if ex.font_pt:
                        for p in tf.paragraphs:
                            for r in p.runs:
                                r.font.size = Pt(ex.font_pt)
                    if ex.font_name:
                        for p in tf.paragraphs:
                            for r in p.runs:
                                r.font.name = ex.font_name
                else:
                    _add_textbox(slide, ex.text or "", el, ex.font_name, font_pt=int(ex.font_pt) if ex.font_pt else None, color=ex.color)
            elif ex.kind == "rect":
                shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(ex.x_emu), Emu(ex.y_emu), Emu(ex.cx_emu), Emu(ex.cy_emu))
                if ex.fill:
                    shape.fill.solid(); shape.fill.fore_color.rgb = RGBColor.from_string(ex.fill)
                else:
                    shape.fill.background()
                if ex.color:
                    shape.line.color.rgb = RGBColor.from_string(ex.color)
```
(`MSO_SHAPE`, `RGBColor`, `Emu`, `Pt` are already imported at the top of `_add_layout_extras`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && arch -arm64 .venv/bin/pytest tests/test_pptx_generator.py -q`
Expected: the four new tests PASS. Pre-existing `test_build_pptx_with_chart` may still fail (unrelated).

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/pptx_generator.py backend/tests/test_pptx_generator.py
git commit -m "feat(free-layout): apply color/font overrides, hide elements, render created textboxes/rects"
```

---

### Task 5: Frontend — widen layout types

**Files:**
- Modify: `frontend/src/types/index.ts`
- Test: `frontend/tests/store.test.ts`

**Interfaces:**
- Consumes: backend response shape (Tasks 1/3).
- Produces: `LayoutBox` += `color?: string; font_name?: string; hidden?: boolean`; `LayoutExtra.kind: "line" | "textbox" | "rect"`, += `id?: string; font_name?: string`.

- [ ] **Step 1: Write the failing test**

Add to `frontend/tests/store.test.ts`:

```ts
describe("free layout types", () => {
  it("store round-trips a layout with free-mode overrides", () => {
    useProjectStore.setState({ state: null, projectName: null })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    useProjectStore.getState().addSeparator("Sec")
    useProjectStore.getState().addShell()
    const slideId = useProjectStore.getState().state!.slides.find((s) => s.type === "shell")!.id
    const loaded = {
      ...useProjectStore.getState().state!,
      slides: useProjectStore.getState().state!.slides.map((sl) =>
        sl.id !== slideId ? sl : {
          ...sl,
          layout: {
            positions: { a1: { x_emu: 0, y_emu: 0, cx_emu: 1, cy_emu: 1, color: "C00000", font_name: "Georgia", hidden: true } },
            extras: [{ kind: "textbox" as const, id: "free_1", x_emu: 1, y_emu: 1, cx_emu: 10, cy_emu: 2, text: "N", color: "404040" }],
            changes: [],
          },
        }),
    }
    useProjectStore.getState().loadProjectState(loaded)
    const sl = useProjectStore.getState().state!.slides.find((s) => s.id === slideId)!
    expect(sl.layout!.positions.a1.color).toBe("C00000")
    expect(sl.layout!.positions.a1.hidden).toBe(true)
    expect(sl.layout!.extras[0].kind).toBe("textbox")
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/store.test.ts && npx tsc --noEmit`
Expected: `tsc` FAILS (the literal uses `color`/`hidden`/`kind:"textbox"` not yet on the types), or the runtime test fails to compile.

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/types/index.ts`, extend `LayoutBox`:
```ts
export interface LayoutBox {
  x_emu: number
  y_emu: number
  cx_emu: number
  cy_emu: number
  font_pt?: number | null
  callout?: boolean
  box_style?: "dashed" | null
  color?: string
  font_name?: string
  hidden?: boolean
}
```
(Keep the existing fields exactly; only add the three.) Widen `LayoutExtra`:
```ts
export interface LayoutExtra {
  kind: "line" | "textbox" | "rect"
  id?: string
  x_emu: number
  y_emu: number
  cx_emu: number
  cy_emu: number
  text?: string | null
  font_pt?: number | null
  font_name?: string
  bold?: boolean
  style?: string | null
  color?: string | null
  fill?: string | null
}
```
(Match the existing field set; only widen `kind` and add `id`/`font_name`. If the existing `LayoutExtra` already declares some of these, keep them and only add what's missing.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/store.test.ts && npx tsc --noEmit`
Expected: PASS; tsc clean.

- [ ] **Step 5: Run full frontend suite**

Run: `cd frontend && npx vitest run`
Expected: no new failures beyond the known pre-existing set.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/index.ts frontend/tests/store.test.ts
git commit -m "feat(free-layout): widen LayoutBox/LayoutExtra TS types for free-mode overrides"
```

---

## Self-Review

**Spec coverage:**
- Free mode triggered by user_hint; prompt switch → Task 2. ✓
- LayoutBox color/font/hidden + LayoutExtra kinds → Task 1. ✓
- Parse overrides + created (no clamp; font_pt uncapped already) → Task 3. ✓
- Render: color on text, hidden skip (analysis/subtitle), hidden charts filtered, created textbox/rect → Task 4. ✓
- Charts keep series colors (only move/resize/hide) → Task 4 filters/positions charts; no color applied to charts. ✓
- No-hint path unchanged → Tasks 2 (prompt else-branch) & 3 (free_mode gate). ✓
- Frontend types widened, no UI → Task 5. ✓
- Old state validates → Task 1 defaults; Task 5 optional fields. ✓

**Placeholder scan:** No TBD/TODO. Every code step carries concrete code. The "read the function to place X" notes in Tasks 3/4(d) are integration guidance around concrete snippets (the exact filter expression, the exact entry dict, the exact extras append are all given), not missing content.

**Type consistency:**
- `LayoutBox.color/font_name/hidden` — backend (Task 1) and frontend (Task 5) names match; parse writes `color`/`font_name`/`hidden` keys (Task 3) that Pydantic maps to those fields on save. ✓
- `_add_textbox(..., color=None)` defined Task 4(a), used in 4(b)(c)(e). ✓
- `LayoutExtra.kind` values `line|textbox|rect` consistent across model (Task 1), parse (Task 3), render (Task 4e), TS (Task 5). ✓
- `free_mode` gate uses the same `(user_hint or "").strip()` criterion as the prompt switch (Task 2) and the existing enforce-skip. ✓
