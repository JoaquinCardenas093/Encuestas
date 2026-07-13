# Dashed-Box Callout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the AI-suggest-layout wrap an analysis in a dashed-border, no-fill box (a callout variant), via a new `LayoutBox.box_style="dashed"`. Blank/None = current behavior.

**Architecture:** `LayoutBox` gains `box_style: Literal["dashed"] | None`. `_add_analyses_textboxes` dispatches `box_style=="dashed"` → new `_add_dashed_box` (rectangle, no fill, dashed gray border). The `/suggest-slide-layout` endpoint propagates `box_style` from the AI's element output; the `correct_slide_layout` prompt learns it can set it. Additive — existing `callout` (filled rounded) unchanged.

**Tech Stack:** Python (FastAPI, python-pptx, pytest).

## Global Constraints

- Backend tests: `cd backend && arch -arm64 .venv/bin/python -m pytest <path> -v` (arm64 venv prefix).
- If a command hits ENOSPC / `/private/tmp ... full`, prefix: `export TMPDIR="$HOME/.cache/cc-tmp" && mkdir -p "$TMPDIR" &&`.
- `box_style` only valid value is `"dashed"`; None/absent ⇒ current behavior. Invalid value ⇒ treated as None.
- `box_style=="dashed"` takes precedence over `callout` if both are set.
- Dashed border: gray `#404040`, ~1pt, `a:prstDash val="dash"`, NO fill (`fill.background()`) — mirror the existing dashed-line XML pattern in `pptx_generator.py` (~lines 290-296).
- Ephemeral/AI-only: no frontend/user control; only the AI emits `box_style`.
- There is an UNRELATED uncommitted change in `backend/aurum_encuestas/llm_client.py` (env var `REACT_APP_ANTHROPIC_API_KEY`) — do NOT revert or touch that line. When Task 2 edits llm_client.py (the prompt), `git add` will include the file; the implementer MUST leave the env-var line as-is (it currently reads `ANTHROPIC_API_KEY` in the committed base) and only add the prompt text, so no env-var change enters the commit.
- Work on the branch the controller creates; do NOT switch branches inside a task.

---

### Task 1: `box_style` model + `_add_dashed_box` render + dispatch

**Files:**
- Modify: `backend/aurum_encuestas/models.py` (`LayoutBox`)
- Modify: `backend/aurum_encuestas/pptx_generator.py` (`_add_dashed_box` + dispatch)
- Test: `backend/tests/test_pptx_generator.py`

**Interfaces:**
- Produces: `LayoutBox.box_style: Literal["dashed"] | None`; `_add_dashed_box(slide, text, el, font_name=None, font_pt=None)`.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_pptx_generator.py` (read the file's existing imports/helpers first; you need a blank slide — create one via `python-pptx` `Presentation().slides.add_slide(prs.slide_layouts[6])` if no helper exists):

```python
def test_add_dashed_box_has_dashed_border_and_no_fill():
    from pptx import Presentation
    from aurum_encuestas.pptx_generator import _add_dashed_box
    from pptx.oxml.ns import qn
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    n0 = len(slide.shapes)
    el = {"x": 500000, "y": 1200000, "cx": 8000000, "cy": 3000000}
    _add_dashed_box(slide, "Texto de análisis", el)
    assert len(slide.shapes) == n0 + 1
    shape = slide.shapes[-1]
    # dashed border present
    ln = shape.line._get_or_add_ln()
    dashes = ln.findall(qn("a:prstDash"))
    assert dashes and dashes[0].get("val") == "dash"
    # no solid fill (noFill)
    assert shape.fill.type is None or str(shape.fill.type).endswith("BACKGROUND")
    # text made it in
    assert "Texto de análisis" in shape.text_frame.text


def test_analyses_textboxes_uses_dashed_box_when_box_style_dashed(valid_template_path, valid_xlsx_path, monkeypatch):
    # Build a slide_def with one slide-analysis and an AI layout whose LayoutBox
    # has box_style="dashed"; assert _add_dashed_box is chosen (a shape with prstDash exists).
    # Reuse whatever ProjectState/Slide construction the existing pptx_generator tests use;
    # if none, spy on the dispatch by monkeypatching _add_dashed_box to record the call.
    from aurum_encuestas import pptx_generator
    called = {}
    monkeypatch.setattr(pptx_generator, "_add_dashed_box",
                        lambda *a, **k: called.setdefault("dashed", True))
    monkeypatch.setattr(pptx_generator, "_add_callout",
                        lambda *a, **k: called.setdefault("callout", True))
    # Minimal: construct a slide with one analysis + an ai layout box_style=dashed and
    # invoke _add_analyses_textboxes directly. See models.Slide/Analysis/SlideLayout/LayoutBox.
    from pptx import Presentation
    from aurum_encuestas.models import Slide, Analysis, SlideLayout, LayoutBox
    prs = Presentation(); slide = prs.slides.add_slide(prs.slide_layouts[6])
    an = Analysis(id="a1", scope="slide", target_id=None, text="X", ai_generated=True, edited=False)
    layout = SlideLayout(positions={"a1": LayoutBox(x_emu=1, y_emu=1, cx_emu=100, cy_emu=100, box_style="dashed")})
    slide_def = Slide(id="s1", type="shell", title="T", charts=[], analyses=[an], layout=layout)
    pptx_generator._add_analyses_textboxes(slide, slide_def, {"x":0,"y":0,"cx":100,"cy":100}, None)
    assert called.get("dashed") and not called.get("callout")
```

(If the `Analysis`/`Slide`/`LayoutBox` constructor field names differ, READ `models.py` and adjust — do not invent fields.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_pptx_generator.py::test_add_dashed_box_has_dashed_border_and_no_fill tests/test_pptx_generator.py::test_analyses_textboxes_uses_dashed_box_when_box_style_dashed -v`
Expected: FAIL (`_add_dashed_box` not defined / `box_style` unexpected).

- [ ] **Step 3: Add the model field**

In `backend/aurum_encuestas/models.py`, `class LayoutBox` — add after `callout`:

```python
    box_style: Literal["dashed"] | None = None  # dashed-border box wrapping analysis (AI-only)
```

(`Literal` is already imported at the top of models.py.)

- [ ] **Step 4: Add `_add_dashed_box`**

In `backend/aurum_encuestas/pptx_generator.py`, next to `_add_callout`, add:

```python
def _add_dashed_box(slide, text: str, el: dict, font_name: str | None = None, font_pt: float | None = None) -> None:
    """Render analysis inside a dashed-border rectangle with NO fill (AI box_style='dashed')."""
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_AUTO_SIZE
    from pptx.dml.color import RGBColor
    from pptx.oxml.ns import qn
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                   Emu(el["x"]), Emu(el["y"]), Emu(el["cx"]), Emu(el["cy"]))
    shape.fill.background()
    shape.line.color.rgb = RGBColor(0x40, 0x40, 0x40)
    shape.line.width = Pt(1)
    ln = shape.line._get_or_add_ln()
    prst = ln.makeelement(qn("a:prstDash"), {"val": "dash"})
    for old in ln.findall(qn("a:prstDash")):
        ln.remove(old)
    ln.append(prst)
    tf = shape.text_frame
    tf.word_wrap = True
    try:
        tf.auto_size = MSO_AUTO_SIZE.NONE
    except Exception:
        pass
    p = tf.paragraphs[0]
    for run in list(p.runs):
        run.text = ""
    run = p.add_run()
    run.text = text or ""
    if font_name:
        run.font.name = font_name
    if font_pt:
        run.font.size = Pt(font_pt)
    run.font.color.rgb = RGBColor(0x40, 0x40, 0x40)
```

(`Emu` and `Pt` are already imported/used in this module — confirm; `_add_callout` uses them.)

- [ ] **Step 5: Dispatch in `_add_analyses_textboxes`**

In `_add_analyses_textboxes`, read `box_style` alongside `callout`:

After `callout = box.callout` (the `if a.id in ai_positions:` branch), add:
```python
            box_style = getattr(box, "box_style", None)
```
And initialize `box_style = None` near the top where `callout = False` is initialized (so the non-AI branch has it defined).

Change the dispatch from:
```python
            if callout:
                _add_callout(slide, a.text, el, font_override, font_pt=font_pt)
            else:
                _add_textbox(slide, a.text, el, font_override, font_pt=font_pt)
```
to:
```python
            if box_style == "dashed":
                _add_dashed_box(slide, a.text, el, font_override, font_pt=font_pt)
            elif callout:
                _add_callout(slide, a.text, el, font_override, font_pt=font_pt)
            else:
                _add_textbox(slide, a.text, el, font_override, font_pt=font_pt)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_pptx_generator.py -v`
Expected: PASS (new 2 + existing).

- [ ] **Step 7: Commit**

```bash
git add backend/aurum_encuestas/models.py backend/aurum_encuestas/pptx_generator.py backend/tests/test_pptx_generator.py
git commit -m "feat(layout): dashed-box render for analysis (box_style=dashed)"
```

---

### Task 2: propagate `box_style` from AI + prompt

**Files:**
- Modify: `backend/aurum_encuestas/api.py` (layout parse → `box_style` on the LayoutBox)
- Modify: `backend/aurum_encuestas/llm_client.py` (`correct_slide_layout` prompt)
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `LayoutBox.box_style` (Task 1).
- Produces: the `/suggest-slide-layout` response's per-analysis position includes `box_style` when the AI set it.

- [ ] **Step 1: Write the failing test**

In `backend/aurum_encuestas/api.py`, the suggest-slide-layout handler parses `raw["elements"]` into a `positions` dict (the block around `positions[key] = {"x_emu":..., "callout":...}`, ~lines 720-727). The propagation is: for analysis elements, copy `box_style` through. READ that handler to find the exact function and whether it is unit-testable directly, OR test via the endpoint.

Add to `backend/tests/test_api.py` a test that drives the parse. If the parse is inline in the endpoint and needs the LLM, prefer monkeypatching `correct_slide_layout` to return a canned `raw` with an analysis element carrying `box_style: "dashed"`, then assert the endpoint response's `positions[<analysis_id>]` (or `extras`/positions structure the endpoint returns) includes `box_style == "dashed"`:

```python
def test_suggest_slide_layout_propagates_box_style(monkeypatch, valid_xlsx_path):
    import aurum_encuestas.api as api
    monkeypatch.setattr(api, "correct_slide_layout", lambda *a, **k: {
        "elements": [{"id": "analysis_a1", "x_cm": 1.3, "y_cm": 4.0, "w_cm": 20.0, "h_cm": 3.0,
                      "font_pt": 10.0, "box_style": "dashed"}],
        "extras": [], "changes": [],
    })
    # Build a minimal valid state with a slide that has analysis id "a1" (see _minimal_state
    # helper + models.Slide/Analysis). Call client.post("/api/suggest-slide-layout", json={...}).
    # Assert the returned positions for the analysis carry box_style == "dashed".
    ...
```

Fill in the state construction using the existing `_minimal_state` helper pattern in `test_api.py` and the real request shape of `/api/suggest-slide-layout` (read `SuggestSlideLayoutRequest`). If the endpoint returns `positions` keyed by element id, assert `body["positions"]["a1"]["box_style"] == "dashed"` (adjust key to the real response shape).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_api.py::test_suggest_slide_layout_propagates_box_style -v`
Expected: FAIL (`box_style` not in the parsed position).

- [ ] **Step 3: Propagate `box_style` in the parse**

In `backend/aurum_encuestas/api.py`, in the layout-parse block where `positions[key] = {...}` is built with `"callout": ...` (only for analysis elements), add:

```python
            "box_style": (el.get("box_style") if el.get("box_style") == "dashed" else None) if is_analysis else None,
```

Ensure this `box_style` field flows into whatever `LayoutBox`/response the endpoint returns (same path `callout` takes). If the endpoint builds `LayoutBox(**position_dict)` somewhere, `box_style` is now a valid field (Task 1); if it returns the raw dict, the key is present.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_api.py::test_suggest_slide_layout_propagates_box_style -v`
Expected: PASS.

- [ ] **Step 5: Update the `correct_slide_layout` prompt**

In `backend/aurum_encuestas/llm_client.py`, in the `correct_slide_layout` system prompt:
- Near the `callout: true` rule (~line 356), add a line: that it may set `box_style: "dashed"` on an `analysis_<id>` to wrap it in a dashed-border box with NO fill (for a "ficha técnica" / highlighted context block), mutually exclusive with `callout`.
- Adjust the rule that forbids `"rectangle_dashed_border"` (~line 440) so it does not contradict the new `box_style` attribute — clarify the dashed box is requested via `box_style` on the analysis, not as a new `shape_type`.
- Do NOT modify the `_build_client` env-var line (leave `os.environ.get("ANTHROPIC_API_KEY")` as-is in the commit).

- [ ] **Step 6: Run the api + llm test files to confirm no regression**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_api.py tests/test_llm_client.py -q`
Expected: PASS (pre-existing failures `test_generate_analysis_truncates_long_response` and `test_load_active_returns_file_when_present` may remain — they predate this work; no NEW failures).

- [ ] **Step 7: Commit**

```bash
git add backend/aurum_encuestas/api.py backend/aurum_encuestas/llm_client.py backend/tests/test_api.py
git commit -m "feat(ai-layout): AI can emit box_style=dashed to wrap analysis in a dashed box"
```

---

## Self-Review

**Spec coverage:**
- §1 `LayoutBox.box_style` → Task 1 Step 3. ✓
- §2 `_add_dashed_box` (no fill, dashed gray border, text) + dispatch (dashed > callout > textbox) → Task 1 Steps 4-5. ✓
- §3 api.py propagates `box_style` (analysis only, validated to "dashed") → Task 2 Step 3. ✓
- §4 prompt rule + prohibition adjust → Task 2 Step 5. ✓
- Precedence dashed > callout → Task 1 Step 5 dispatch order + test. ✓
- Backward-compat (None ⇒ current) → Task 1 dispatch `elif callout / else`; test `..._box_style_none` behavior implicit in existing tests. ✓
- Invalid value ⇒ None → Task 2 Step 3 guard (`== "dashed" else None`). ✓
- Env-var line untouched in commits → Global Constraints + Task 2 Step 5 note. ✓

**Placeholder scan:** Task 2 Step 1 leaves the state-construction `...` for the implementer to fill from the real `_minimal_state`/request shape — this is a deliberate "read the model and adjust" instruction (the exact ProjectState fields live in models.py), not a code placeholder; the assertion and monkeypatch are concrete. All other steps are complete.

**Type consistency:** `box_style: Literal["dashed"] | None` defined Task 1 Step 3; read via `getattr(box, "box_style", None)` in dispatch (Task 1 Step 5); propagated as `"dashed"|None` in api.py (Task 2 Step 3). `_add_dashed_box(slide, text, el, font_name=None, font_pt=None)` signature matches the `_add_callout` call convention used in the dispatch. Consistent.
