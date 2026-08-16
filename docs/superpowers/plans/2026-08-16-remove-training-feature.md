# Remove Training Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the training feature (corpus upload + AI style-guide generation) from backend and frontend without changing anything else.

**Architecture:** This is a deletion, not a feature build. Each task removes one coherent area, then verifies nothing dangles: backend imports clean (`import aurum_encuestas.api`) and pytest stays green; frontend `tsc --noEmit` is clean and vitest stays green. The render engine (`style_guide.py`, `pattern_classifier.py`, `pptx_generator.py`) is untouched and keeps falling back to `BUILTIN_STYLE_GUIDE`.

**Tech Stack:** FastAPI/pytest (backend, run with `arch -arm64 .venv/bin/pytest`), React/TypeScript/Vitest (frontend).

## Global Constraints

- Do NOT touch the render engine: `style_guide.py`, `pattern_classifier.py`, `pattern_renderer.py`, `pptx_generator.py`, `element_renderers/`, `llm_client.py`.
- Keep `migrate_legacy_files` imported and called in the `lifespan` (api.py) — it lives in `style_guide.py`, which stays.
- Do NOT edit `config.py` (dead helpers left in place on purpose).
- Do NOT delete VPS data — code only.
- Backend tests run with `arch -arm64 .venv/bin/pytest` (plain `pytest` hits an x86_64/arm64 mismatch).
- "No new failures": the baseline already has pre-existing failures (test_style_guide, test_pattern_classifier LRU, test_pptx_generator, some frontend AddChartModal/ConfigPanel/AddAnalysisModal). Removing training also removes `test_get_style_guide_returns_saved_guide` (one of the pre-existing backend failures).

---

### Task 1: Backend — remove training endpoints, request models, and imports from api.py

**Files:**
- Modify: `backend/aurum_encuestas/api.py`
- Modify: `backend/tests/test_api.py`

**Interfaces:**
- Produces: `api.py` with no `/api/training/*` routes and no imports of `training_sets`/`style_guide_analyzer`/training-only `style_guide` symbols. `import aurum_encuestas.api` still succeeds.

- [ ] **Step 1: Delete the endpoint functions and their request models in `api.py`**

Delete each of these blocks entirely (the decorated function plus, where noted, its Pydantic model):
- `@app.post("/api/training/corpus/add")` → `async def corpus_add(...)`
- `@app.get("/api/training/corpus/list")` → `async def corpus_list(...)`
- `class CorpusDeleteRequest(BaseModel)` and `@app.post("/api/training/corpus/delete")` → `async def corpus_delete(...)`
- `_analysis_jobs: dict[str, dict] = {}` (the module-level jobs dict) and `@app.post("/api/training/analyze-with-ai")` → `async def analyze_with_ai(...)`
- `@app.get("/api/training/analysis-status/{job_id}")` → `async def analysis_status(...)`
- `@app.get("/api/training/style-guide")` → `async def get_style_guide(...)`
- `class PatternUpdateRequest(BaseModel)` and `@app.put("/api/training/style-guide/pattern/{pattern_id}")` → `async def update_style_guide_pattern(...)`
- `class ClearCacheRequest(BaseModel)` and `@app.post("/api/training/clear-cache")` → `async def clear_cache(...)`

Leave everything between them that is NOT training (e.g. `_estimate_analysis_band_cm`, the suggest-layout endpoints, font logic) exactly as-is.

- [ ] **Step 2: Fix the imports in `api.py`**

Change the config import (drop the two training-only helpers):
```python
from .config import add_recent, load_recents
```
Change the style_guide import to keep only what the lifespan uses:
```python
from .style_guide import migrate_legacy_files
```
(Delete the multi-line import of `BUILTIN_STYLE_GUIDE`, `Pattern`, `load_active_style_guide`, `save_style_guide`.) The local imports inside the deleted functions (`from .style_guide_analyzer import run_full_analysis_pipeline`, `from .style_guide import load_active_style_guide`) disappear with those functions.

- [ ] **Step 3: Delete the training tests in `test_api.py`**

Remove the training test block — every test function hitting `/api/training/*`:
`test_analyze_with_ai_returns_job_id`, `test_analysis_status_unknown_job`, `test_corpus_add_pptx`, `test_corpus_add_rejects_non_pptx`, `test_corpus_list_returns_pptxs`, `test_corpus_list_empty_when_no_corpus`, `test_corpus_delete_removes_file`, `test_corpus_delete_missing_file_still_ok`, `test_analyze_with_ai_endpoint_returns_job_id` (and its status-poll companion), `test_get_style_guide_returns_builtin_when_none_exists`, `test_get_style_guide_returns_saved_guide`, `test_put_style_guide_pattern_updates_pattern`, `test_put_style_guide_pattern_404_when_not_found`, `test_clear_cache_render`, `test_clear_cache_classifier`, `test_clear_cache_all`, `test_clear_cache_invalid_type_returns_422`.
Also remove any now-unused module-level fixtures/constants used only by them (e.g. a `MINIMAL_STYLE_GUIDE` dict) if it is referenced nowhere else.

- [ ] **Step 4: Verify import is clean**

Run: `cd backend && arch -arm64 .venv/bin/python -c "import aurum_encuestas.api; print('OK')"`
Expected: prints `OK` (no ImportError, no NameError from a leftover symbol).

- [ ] **Step 5: Verify no training route remains**

Run: `cd backend && grep -rn "api/training" aurum_encuestas/api.py tests/test_api.py || echo "NONE"`
Expected: `NONE`.

- [ ] **Step 6: Run the api test file**

Run: `cd backend && arch -arm64 .venv/bin/pytest tests/test_api.py -q`
Expected: passes except pre-existing non-training failures; no error about missing training routes.

- [ ] **Step 7: Commit**

```bash
git add backend/aurum_encuestas/api.py backend/tests/test_api.py
git commit -m "refactor(training): remove /api/training endpoints and their tests"
```

---

### Task 2: Backend — delete the training-only modules

**Files:**
- Delete: `backend/aurum_encuestas/style_guide_analyzer.py`
- Delete: `backend/aurum_encuestas/training_sets.py`
- Delete: `backend/tests/test_style_guide_analyzer.py`

**Interfaces:**
- Consumes: Task 1 removed the only importers of these modules.
- Produces: modules gone; nothing imports them.

- [ ] **Step 1: Confirm nothing still imports them**

Run: `cd backend && grep -rn "style_guide_analyzer\|training_sets" aurum_encuestas || echo "NONE"`
Expected: `NONE` (Task 1 removed the api.py references).

- [ ] **Step 2: Delete the files**

```bash
git rm backend/aurum_encuestas/style_guide_analyzer.py backend/aurum_encuestas/training_sets.py backend/tests/test_style_guide_analyzer.py
```

- [ ] **Step 3: Verify import + full backend suite**

Run: `cd backend && arch -arm64 .venv/bin/python -c "import aurum_encuestas.api; print('OK')" && arch -arm64 .venv/bin/pytest -q`
Expected: `OK`; suite green except the known pre-existing failures (which now number one fewer, since `test_get_style_guide_returns_saved_guide` was removed in Task 1). No new failures, no collection error from the deleted test file.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(training): delete style_guide_analyzer and training_sets modules"
```

---

### Task 3: Frontend — decouple ColorPicker from the styleGuide store

Do this BEFORE deleting the store (Task 4), so ColorPicker never imports a missing module.

**Files:**
- Modify: `frontend/src/components/ColorPicker/ColorPicker.tsx`
- Modify: `frontend/tests/ColorPicker.test.tsx`

**Interfaces:**
- Produces: `ColorPicker` with no dependency on `useStyleGuideStore`; `suggestedPalette` becomes `[]`.

- [ ] **Step 1: Remove the store usage in `ColorPicker.tsx`**

Delete the import `import { useStyleGuideStore } from "../../store/styleGuide"` and the two lines that read it:
```tsx
const styleGuide = useStyleGuideStore(...)
const suggestedPalette = styleGuide?.global.suggested_palette ?? []
```
Replace with:
```tsx
const suggestedPalette: string[] = []
```
Leave the rest (recent-colors fetch, DEFAULT_COLORS, render) unchanged. Since `suggestedPalette` is empty, the "Sugeridas del training" row renders nothing (or guard it with `suggestedPalette.length > 0` if it currently always renders a header).

- [ ] **Step 2: Update `ColorPicker.test.tsx`**

Remove the `vi.mock("../src/store/styleGuide", ...)` block and delete the test that clicks a suggested-palette swatch (the `#7F7F7F` case), since suggested palette is now always empty. Keep the other ColorPicker tests.

- [ ] **Step 3: Verify**

Run: `cd frontend && npx vitest run tests/ColorPicker.test.tsx`
Expected: passes (no reference to the styleGuide store).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ColorPicker/ColorPicker.tsx frontend/tests/ColorPicker.test.tsx
git commit -m "refactor(training): drop ColorPicker dependency on styleGuide store"
```

---

### Task 4: Frontend — remove the Training page, route, nav, api, and store

**Files:**
- Modify: `frontend/src/App.tsx` (remove import + route)
- Modify: `frontend/src/components/Topbar.tsx` (remove NavLink)
- Delete: `frontend/src/pages/Training/` (TrainingPage.tsx, StyleGuideViewer.tsx, AnalysisProgressModal.tsx)
- Delete: `frontend/src/api/training.ts`
- Delete: `frontend/src/store/styleGuide.ts`
- Delete: `frontend/tests/TrainingPage.test.tsx`, `frontend/tests/styleGuide.store.test.ts`, `frontend/tests/training-api.test.ts`

**Interfaces:**
- Consumes: Task 3 (ColorPicker no longer imports the store).
- Produces: no `/training` route, no Training components, no styleGuide store / training api.

- [ ] **Step 1: Remove route + import in `App.tsx`**

Delete `import TrainingPage from "./pages/Training/TrainingPage"` and the line `<Route path="/training" element={<TrainingPage />} />`.

- [ ] **Step 2: Remove the nav link in `Topbar.tsx`**

Delete the line `<NavLink to="/training" className={tabClass}>Entrenamiento</NavLink>`.

- [ ] **Step 3: Delete the files**

```bash
git rm -r frontend/src/pages/Training frontend/src/api/training.ts frontend/src/store/styleGuide.ts \
  frontend/tests/TrainingPage.test.tsx frontend/tests/styleGuide.store.test.ts frontend/tests/training-api.test.ts
```

- [ ] **Step 4: Verify nothing references them**

Run: `cd frontend && grep -rn "pages/Training\|api/training\|store/styleGuide\|useStyleGuideStore\|/training" src tests || echo "NONE"`
Expected: `NONE`.

- [ ] **Step 5: Typecheck + full frontend suite**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: `tsc` clean (catches any dangling import); vitest green except the known pre-existing failures (AddChartModal/ConfigPanel/AddAnalysisModal). No new failures, no "cannot find module" from deleted files.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(training): remove Training page, route, nav, api client and store"
```

---

## Self-Review

**Spec coverage:**
- Delete backend `style_guide_analyzer.py`, `training_sets.py` → Task 2. ✓
- Delete the 8 `/api/training/*` endpoints + request models + imports → Task 1. ✓
- Keep `migrate_legacy_files` in lifespan → Task 1 Step 2 (import kept). ✓
- Keep render engine (style_guide.py/pattern_classifier.py/pptx_generator.py) untouched → not in any task. ✓
- Don't edit config.py → not in any task. ✓
- Delete frontend Training page/api/store + route + NavLink → Task 4. ✓
- Decouple ColorPicker → Task 3. ✓
- Delete tests (backend analyzer; frontend TrainingPage/styleGuide.store/training-api) → Tasks 2 & 4; backend api training tests → Task 1. ✓
- Verification (import clean, pytest, tsc, vitest) → each task's steps. ✓

**Placeholder scan:** No TBD/TODO. Deletion steps name exact symbols/paths; verification steps give exact commands. (Deletion tasks legitimately have no red-green test cycle — the deliverable is "removed + still-green suites + clean import/typecheck," which every task verifies.)

**Type consistency:** No new symbols introduced. The only code addition is `const suggestedPalette: string[] = []` in ColorPicker (Task 3), replacing the store-derived value of the same name and type (`string[]`). ✓

**Ordering:** Task 3 (decouple ColorPicker) precedes Task 4 (delete store), so ColorPicker never imports a deleted module. Task 1 (remove api imports) precedes Task 2 (delete modules), so api.py never imports a deleted module. ✓
