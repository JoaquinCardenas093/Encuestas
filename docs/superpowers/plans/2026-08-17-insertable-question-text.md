# Insertable Question-Text Subtitles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the automatic `@Subtitulo` question text with user-inserted, editable, removable question texts per slide (`Slide.subtitles`), rendered as textboxes and positioned by the existing layout AI.

**Architecture:** A subtitle is a lightweight `{id, text}` element mirroring analyses: rendered as a PPTX textbox, positioned via `SlideLayout.positions[<subtitle id>]` when the layout AI placed it (using a `subtitle_` id prefix), else stacked in a top fallback band. The auto `@Subtitulo` derivation is removed. Frontend adds a slide-level "Textos de pregunta" section in ConfigPanel with insert/edit/remove.

**Tech Stack:** FastAPI + Pydantic + python-pptx (backend, tests run with `arch -arm64 .venv/bin/pytest`); React + TypeScript + Zustand + Vitest (frontend).

## Global Constraints

- Backend tests MUST run with `arch -arm64 .venv/bin/pytest` (plain pytest hits an x86_64/arm64 dlopen mismatch).
- The auto `@Subtitulo` derivation (pptx_generator.py:134-140) is REMOVED; `@Subtitulo` is substituted with `""`.
- Subtitle text is plain (no callout/dashed box). Inserted text auto-derives `"{code}. {text}"` from the slide's chart questions, then is freely editable (a snapshot; editing never touches `parsed_db`).
- `Slide.subtitles` defaults to `[]`; loading an old ProjectState without the field must validate.
- Frontend ids use the existing `uid("...")` helper in `store/project.ts`.
- Known pre-existing test failures (do NOT try to fix; "no NEW failures" is the bar): backend test_generate_analysis_truncates_long_response, test_build_pptx_with_chart (`assert 0 == 1` — build itself runs fine, only its assertion fails), test_load_active_returns_file_when_present; frontend AddChartModal (4), ConfigPanel (1), AddAnalysisModal (1).

---

### Task 1: Backend model — Subtitle + Slide.subtitles

**Files:**
- Modify: `backend/aurum_encuestas/models.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `Subtitle(BaseModel)` with `id: str`, `text: str`; `Slide.subtitles: list[Subtitle] = []`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_models.py`:

```python
def test_slide_subtitles_default_empty():
    from aurum_encuestas.models import Slide
    s = Slide(id="s1", type="shell")
    assert s.subtitles == []


def test_slide_accepts_subtitles():
    from aurum_encuestas.models import Slide, Subtitle
    s = Slide(id="s1", type="shell", subtitles=[Subtitle(id="sub1", text="P1. ¿Conoce la marca?")])
    assert len(s.subtitles) == 1
    assert s.subtitles[0].id == "sub1"
    assert s.subtitles[0].text == "P1. ¿Conoce la marca?"


def test_old_slide_without_subtitles_validates():
    from aurum_encuestas.models import Slide
    s = Slide.model_validate({"id": "s1", "type": "shell", "title": "T", "charts": [], "analyses": []})
    assert s.subtitles == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && arch -arm64 .venv/bin/pytest tests/test_models.py::test_slide_accepts_subtitles -v`
Expected: FAIL — `Subtitle` does not exist / `subtitles` is not a field.

- [ ] **Step 3: Write minimal implementation**

In `backend/aurum_encuestas/models.py`, add the `Subtitle` model just before `class Slide`:

```python
class Subtitle(BaseModel):
    id: str
    text: str
```

Add the field to `Slide` (alongside `analyses`):

```python
    subtitles: list[Subtitle] = []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && arch -arm64 .venv/bin/pytest tests/test_models.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/models.py backend/tests/test_models.py
git commit -m "feat(subtitle): add Subtitle model + Slide.subtitles"
```

---

### Task 2: Backend PPTX render — drop auto @Subtitulo, render subtitles as textboxes

**Files:**
- Modify: `backend/aurum_encuestas/pptx_generator.py`
- Test: `backend/tests/test_pptx_generator.py`

**Interfaces:**
- Consumes: `Slide.subtitles` (Task 1); existing `_add_textbox`, `SlideLayout.positions`, `free_area`.
- Produces: `_add_subtitle_textboxes(slide, slide_def, free_area, font_override)`; `@Subtitulo` always `""`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_pptx_generator.py` (the file already has `_state`, `valid_xlsx_path`, `valid_template_path`, and `from aurum_encuestas.models import ...`; add `Subtitle` to that import):

```python
def test_subtitle_text_renders_in_pptx(tmp_path, valid_xlsx_path, valid_template_path):
    from aurum_encuestas.models import Subtitle
    slides = [
        Slide(id="s1", type="separator", title="Sec"),
        Slide(id="s2", type="shell", title="Sec", charts=[], analyses=[],
              subtitles=[Subtitle(id="sub1", text="P1. Texto de la pregunta")]),
    ]
    state = _state(slides, valid_xlsx_path, valid_template_path)
    out = tmp_path / "out.pptx"
    build_pptx(state, str(out))
    prs = Presentation(str(out))
    texts = [sh.text_frame.text for sh in prs.slides[1].shapes if sh.has_text_frame]
    assert any("Texto de la pregunta" in t for t in texts)


def test_no_auto_subtitle_from_chart_question(tmp_path, valid_xlsx_path, valid_template_path):
    # A shell slide with a single-question chart and NO subtitles must NOT auto-insert
    # the question text (old @Subtitulo behavior is removed).
    slides = [
        Slide(id="s1", type="separator", title="Sec"),
        Slide(id="s2", type="shell", title="Sec",
              charts=[Chart(id="c1", question_id="q1", breakdown_ids=[], chart_type="PIE")],
              analyses=[], subtitles=[]),
    ]
    state = _state(slides, valid_xlsx_path, valid_template_path)
    out = tmp_path / "out.pptx"
    build_pptx(state, str(out))
    prs = Presentation(str(out))
    texts = [sh.text_frame.text for sh in prs.slides[1].shapes if sh.has_text_frame]
    assert not any("$p1.recordacion" in t for t in texts)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && arch -arm64 .venv/bin/pytest tests/test_pptx_generator.py::test_subtitle_text_renders_in_pptx tests/test_pptx_generator.py::test_no_auto_subtitle_from_chart_question -v`
Expected: `test_subtitle_text_renders_in_pptx` FAILS (subtitle not rendered); `test_no_auto_subtitle` FAILS (question text still auto-inserted via @Subtitulo).

- [ ] **Step 3: Write minimal implementation**

In `backend/aurum_encuestas/pptx_generator.py`, replace the auto-derivation block (currently ~lines 133-140) so `subtitle_text` is always empty:

```python
            # @Subtitulo is no longer auto-filled; question texts are user-inserted
            # subtitles rendered as textboxes (see _add_subtitle_textboxes).
            subtitle_text = ""
            title_text = slide_def.title or ""
```
(Delete the `unique_q_ids` / `q` lookup that computed `subtitle_text`.)

Add the subtitle render call in `_add_slide_content`, right after the analyses call (pptx_generator.py:260):

```python
    _add_subtitle_textboxes(slide, slide_def, free_area, state.inputs.font_override if state.inputs else None)
```

Add the function near `_add_analyses_textboxes`:

```python
def _add_subtitle_textboxes(slide, slide_def: Slide, free_area: dict, font_override: str | None) -> None:
    """Append user-inserted question-text subtitles as plain textboxes.
    Uses AI layout positions when present, else stacks in a top band of free_area."""
    if not slide_def.subtitles:
        return
    ai_positions = slide_def.layout.positions if (slide_def.layout and slide_def.layout.positions) else {}

    fa_x = free_area.get("x", 0)
    fa_y = free_area.get("y", 0)
    fa_cx = free_area.get("cx", 1)
    fa_cy = free_area.get("cy", 1)

    # Fallback band along the TOP of free_area (analyses use the bottom band).
    band_h_frac = 0.15
    band_x = fa_x + int(fa_cx * 0.04)
    band_cx = int(fa_cx * 0.92)
    band_cy = int(fa_cy * band_h_frac)

    no_ai = [s for s in slide_def.subtitles if s.id not in ai_positions]
    per_cy = band_cy // len(no_ai) if no_ai else band_cy
    no_ai_index = 0
    for sub in slide_def.subtitles:
        if sub.id in ai_positions:
            box = ai_positions[sub.id]
            el = {"x": box.x_emu, "y": box.y_emu, "cx": box.cx_emu, "cy": box.cy_emu}
            font_pt = box.font_pt
        else:
            el = {"x": band_x, "y": fa_y + no_ai_index * per_cy, "cx": band_cx, "cy": per_cy}
            font_pt = None
            no_ai_index += 1
        try:
            _add_textbox(slide, sub.text, el, font_override, font_pt=font_pt)
        except Exception as exc:
            _log.warning("_add_subtitle_textboxes: failed subtitle %s: %s", sub.id, exc)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && arch -arm64 .venv/bin/pytest tests/test_pptx_generator.py -q`
Expected: the two new tests PASS. Pre-existing `test_build_pptx_with_chart` may still fail (unrelated) — no NEW failures.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/pptx_generator.py backend/tests/test_pptx_generator.py
git commit -m "feat(subtitle): render inserted subtitles as textboxes; drop auto @Subtitulo"
```

---

### Task 3: Backend layout AI — include subtitles in payload + parse subtitle_ positions

**Files:**
- Modify: `backend/aurum_encuestas/api.py` (the `suggest_slide_layout` endpoint: `payload_shapes` build ~561-608 and the position parse loop ~640-658)
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `Slide.subtitles` (Task 1).
- Produces: `payload_shapes` contains a `{"id": f"subtitle_{sub.id}", "kind": "subtitle", ...}` per subtitle; the parse loop maps `subtitle_<x>` → `positions["<x>"]`.

- [ ] **Step 1: Write the failing test**

First locate the endpoint name/URL. In `backend/aurum_encuestas/api.py`, the layout endpoint is `@app.post("/api/suggest-slide-layout")`. Add to `backend/tests/test_api.py`:

```python
def test_suggest_slide_layout_positions_subtitle(monkeypatch, valid_xlsx_path):
    # Build a state with one shell slide containing a chart + a subtitle.
    from aurum_encuestas import api as api_mod
    state = {
        "project_name": "T",
        "inputs": {"db_path": str(valid_xlsx_path), "template_path": "y"},
        "parsed_db": None,
        "slides": [
            {"id": "s2", "type": "shell", "title": "Sec",
             "charts": [{"id": "c1", "question_id": "q1", "breakdown_ids": [], "chart_type": "PIE"}],
             "analyses": [],
             "subtitles": [{"id": "sub1", "text": "P1. Pregunta"}]},
        ],
    }
    # Stub the LLM so no network call happens; it returns a position for the subtitle.
    def fake_correct(slide_payload, slide_png_bytes=None, user_hint=None):
        # assert the subtitle shape was included in the payload
        kinds = [s.get("kind") for s in slide_payload["shapes"]]
        assert "subtitle" in kinds
        return {"elements": [{"id": "subtitle_sub1", "x_cm": 2.0, "y_cm": 3.0, "w_cm": 10.0, "h_cm": 1.0}]}
    monkeypatch.setattr(api_mod, "correct_slide_layout", fake_correct)
    # Avoid the PNG render path (build_pptx) failing in-test: monkeypatch render to None.
    monkeypatch.setattr(api_mod, "render_slide_to_png", lambda *a, **k: None)
    monkeypatch.setattr(api_mod, "build_pptx", lambda *a, **k: None)

    r = client.post("/api/suggest-slide-layout", json={"state": state, "slide_id": "s2", "user_hint": "x"})
    assert r.status_code == 200
    body = r.json()
    assert "sub1" in body["positions"]
    assert body["positions"]["sub1"]["cx_emu"] > 0
```

(If the endpoint's request/response shape differs, adjust the request keys and the `positions` accessor to match the real endpoint — read the endpoint first. The two assertions that matter: the payload included a `kind:"subtitle"` shape, and a returned `subtitle_sub1` element lands under `positions["sub1"]`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && arch -arm64 .venv/bin/pytest tests/test_api.py::test_suggest_slide_layout_positions_subtitle -v`
Expected: FAIL — no `subtitle` kind in payload; `sub1` not in positions.

- [ ] **Step 3: Write minimal implementation**

In `api.py`, after the `for a in slide.analyses:` payload loop, add:

```python
    for sub in slide.subtitles:
        payload_shapes.append({
            "id": f"subtitle_{sub.id}",
            "kind": "subtitle",
            "text_chars": len(sub.text or ""),
            "text_preview": (sub.text or "")[:100],
        })
```

In the parse loop, extend the prefix handling. Change the branch that computes `key`:

```python
        is_analysis = eid.startswith("analysis_")
        is_subtitle = eid.startswith("subtitle_")
        if eid.startswith("chart_"):
            key = eid[len("chart_"):]
        elif is_analysis:
            key = eid[len("analysis_"):]
        elif is_subtitle:
            key = eid[len("subtitle_"):]
        else:
            key = eid
```

(Leave the `font_pt` default logic keyed on `is_analysis` as-is; subtitles use whatever font_pt the AI returns or `None`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && arch -arm64 .venv/bin/pytest tests/test_api.py::test_suggest_slide_layout_positions_subtitle -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/api.py backend/tests/test_api.py
git commit -m "feat(subtitle): include subtitles in layout AI payload + parse subtitle_ positions"
```

---

### Task 4: Frontend — types + store actions

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/store/project.ts`
- Test: `frontend/tests/store.test.ts`

**Interfaces:**
- Produces: TS `Subtitle { id: string; text: string }`; `Slide.subtitles: Subtitle[]`; store actions `addSubtitle(slideId, text)`, `updateSubtitle(slideId, subId, text)`, `removeSubtitle(slideId, subId)`.

- [ ] **Step 1: Write the failing test**

Add to `frontend/tests/store.test.ts`:

```ts
describe("subtitles", () => {
  it("add/update/remove subtitle on a slide", () => {
    useProjectStore.setState({ state: null, projectName: null })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    useProjectStore.getState().addSeparator("Sec")
    useProjectStore.getState().addShell()
    const slideId = useProjectStore.getState().state!.slides.find((s) => s.type === "shell")!.id

    useProjectStore.getState().addSubtitle(slideId, "P1. Pregunta")
    let sub = useProjectStore.getState().state!.slides.find((s) => s.id === slideId)!.subtitles[0]
    expect(sub.text).toBe("P1. Pregunta")

    useProjectStore.getState().updateSubtitle(slideId, sub.id, "Editado")
    sub = useProjectStore.getState().state!.slides.find((s) => s.id === slideId)!.subtitles[0]
    expect(sub.text).toBe("Editado")

    useProjectStore.getState().removeSubtitle(slideId, sub.id)
    expect(useProjectStore.getState().state!.slides.find((s) => s.id === slideId)!.subtitles).toEqual([])
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/store.test.ts`
Expected: FAIL — `addSubtitle` is not a function / `subtitles` undefined.

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/types/index.ts`, add the type and field:
```ts
export interface Subtitle {
  id: string
  text: string
}
```
Add `subtitles: Subtitle[]` to the `Slide` interface (next to `auto_notes`). If existing code constructs `Slide` objects literally, this is optional-safe because the store seeds it (below); if TS complains about missing `subtitles` in existing literals, add `subtitles: []` there.

In `frontend/src/store/project.ts`:
- Ensure new shells/separators seed `subtitles: []`. In `addSeparator` and `addShell`, add `subtitles: []` to the `Slide` object literal (next to `analyses: []`).
- Add to the `Store` interface: `addSubtitle(slideId: string, text: string): void`, `updateSubtitle(slideId: string, subId: string, text: string): void`, `removeSubtitle(slideId: string, subId: string): void`.
- Implement (mirroring the existing analysis mutators):
```ts
      addSubtitle(slideId, text) {
        const s = get().state
        if (!s) return
        set({ state: { ...s, slides: s.slides.map((sl) =>
          sl.id !== slideId ? sl : { ...sl, subtitles: [...(sl.subtitles ?? []), { id: uid("sub"), text }] }) } })
      },
      updateSubtitle(slideId, subId, text) {
        const s = get().state
        if (!s) return
        set({ state: { ...s, slides: s.slides.map((sl) =>
          sl.id !== slideId ? sl : { ...sl, subtitles: (sl.subtitles ?? []).map((su) => su.id === subId ? { ...su, text } : su) }) } })
      },
      removeSubtitle(slideId, subId) {
        const s = get().state
        if (!s) return
        set({ state: { ...s, slides: s.slides.map((sl) =>
          sl.id !== slideId ? sl : { ...sl, subtitles: (sl.subtitles ?? []).filter((su) => su.id !== subId) }) } })
      },
```
- If a `_migrateProjectState` / migration exists in this file, ensure loaded slides get `subtitles: []` when missing (so old projects don't crash). If the store already tolerates missing arrays via `?? []`, that suffices.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/store.test.ts && npx tsc --noEmit`
Expected: PASS; tsc clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/store/project.ts frontend/tests/store.test.ts
git commit -m "feat(subtitle): frontend Subtitle type + store add/update/remove actions"
```

---

### Task 5: Frontend — ConfigPanel "Textos de pregunta" UI

**Files:**
- Modify: `frontend/src/pages/Editor/ConfigPanel.tsx`
- Test: `frontend/tests/ConfigPanel.test.tsx`

**Interfaces:**
- Consumes: store actions (Task 4); `slide.charts`, `parsed_db.questions` for deriving question text.

- [ ] **Step 1: Write the failing test**

Read `ConfigPanel.tsx` first to match how it accesses the slide, the store, and `parsed_db` (it already renders per-chart config). Add to `frontend/tests/ConfigPanel.test.tsx`, following that file's existing render/setup pattern:

```tsx
it("insert button disabled without charts; inserts derived question text", async () => {
  // Arrange a shell slide with one chart of question q1 (code P1, text "Marca?").
  // (Mirror how the other ConfigPanel tests seed the store/parsed_db in this file.)
  // ... setup per existing pattern, selecting the shell slide ...
  const insertBtn = screen.getByRole("button", { name: /insertar texto de pregunta/i })
  // With a chart present, it is enabled:
  expect(insertBtn).not.toBeDisabled()
  await userEvent.click(insertBtn)
  // A textarea with the derived "P1. Marca?" appears and is editable:
  expect(screen.getByDisplayValue(/P1\. Marca\?/i)).toBeInTheDocument()
})
```

(Match the existing ConfigPanel test harness for seeding `state`/`parsed_db` and rendering with the target slide id. If the file's tests select a slide via a prop or store field, reuse that exact mechanism. The two assertions that matter: the insert control exists and, after clicking, a textarea shows the derived `"{code}. {text}"`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/ConfigPanel.test.tsx`
Expected: FAIL — no "Insertar texto de pregunta" control.

- [ ] **Step 3: Write minimal implementation**

In `ConfigPanel.tsx`, add a slide-level "Textos de pregunta" section (near the slide "Título" field). Pull the store actions and parsed_db:
```tsx
const addSubtitle = useProjectStore((s) => s.addSubtitle)
const updateSubtitle = useProjectStore((s) => s.updateSubtitle)
const removeSubtitle = useProjectStore((s) => s.removeSubtitle)
const parsedDb = useProjectStore((s) => s.state?.parsed_db)
```
Derive the slide's distinct questions from its charts:
```tsx
const slideQuestions = Array.from(new Set(slide.charts.map((c) => c.question_id)))
  .map((qid) => parsedDb?.questions.find((q) => q.id === qid))
  .filter((q): q is NonNullable<typeof q> => !!q)
```
Render (the exact markup should match the file's existing Tailwind/label idiom):
- A header "Textos de pregunta".
- An "Insertar texto de pregunta" control. Simplest form that satisfies the spec and test: a button that is `disabled={slideQuestions.length === 0}`. On click, if exactly one question, insert its text; if multiple, show a small inline menu (e.g. a `<select>`) of the questions and insert the chosen one. Insert with:
  ```tsx
  addSubtitle(slide.id, `${q.code}. ${q.text}`)
  ```
- The list of `slide.subtitles`: each a `<textarea>` bound to `updateSubtitle(slide.id, sub.id, e.target.value)` plus a remove button calling `removeSubtitle(slide.id, sub.id)`.

Keep it consistent with the per-chart controls already in the file (same class names, same small-label style).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/ConfigPanel.test.tsx && npx tsc --noEmit`
Expected: the new test PASSES (pre-existing ConfigPanel failure "shows title (read-only) for shell from separator" may remain — no NEW failures); tsc clean.

- [ ] **Step 5: Run full frontend suite**

Run: `cd frontend && npx vitest run`
Expected: no new failures beyond the known pre-existing set.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Editor/ConfigPanel.tsx frontend/tests/ConfigPanel.test.tsx
git commit -m "feat(subtitle): ConfigPanel section to insert/edit/remove question texts"
```

---

## Self-Review

**Spec coverage:**
- `Subtitle` model + `Slide.subtitles` default [] + old-state validates → Task 1. ✓
- Remove auto `@Subtitulo`; render subtitles as textboxes with top fallback band → Task 2. ✓
- Layout AI: subtitle in payload (`subtitle_` prefix) + parse back → Task 3. ✓
- Frontend types + store add/update/remove → Task 4. ✓
- ConfigPanel insert (auto-derived, editable) / edit / remove; insert disabled without charts → Task 5. ✓
- Inserted text auto-derives "{code}. {text}", editable snapshot → Task 5 (`${q.code}. ${q.text}`). ✓
- Preview untouched → not in any task. ✓
- Plain text (no callout/dashed) → Task 2 uses `_add_textbox`. ✓

**Placeholder scan:** No TBD/TODO. Backend steps carry exact code. Frontend Task 5's test and markup are specified with the two must-hold assertions and the exact store/derive calls; the "match the file's existing harness/idiom" notes are integration guidance, not missing content (the derive expression, the insert call `addSubtitle(slide.id, \`${q.code}. ${q.text}\`)`, and the update/remove wiring are all concrete).

**Type consistency:**
- `Subtitle {id, text}` identical backend (Task 1) and frontend (Task 4). ✓
- `subtitle_` prefix used in payload build and parse (Task 3) matches the render's use of `positions[<bare id>]` (Task 2 reads `slide_def.layout.positions` keyed by bare id; Task 3 strips the prefix to the bare id). ✓
- Store signatures `addSubtitle(slideId, text)`, `updateSubtitle(slideId, subId, text)`, `removeSubtitle(slideId, subId)` defined Task 4, consumed Task 5. ✓
- `uid("sub")` matches the existing `uid(...)` helper convention. ✓
