# Per-Cell Count Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the set of marked count cells (`counts` role) authoritative for extraction — an option×category whose cell is not marked reads as count 0 — while staying backward-compatible (no marks ⇒ read everything as today).

**Architecture:** A new `ParsedDB.count_cells: list[[row,col]]` (1-based) is consumed by both extractors: when non-empty, any `(option_row, category_col)` not in the set is forced to count 0 (before value-overrides, which still apply on top). The frontend's `paintToParsedDb` emits `count_cells` from the painted `counts` cells, with a truncation guard that keeps the legacy read-all behavior on truncated sheets.

**Tech Stack:** Python (FastAPI, openpyxl, pytest/TestClient), React + TypeScript (vitest, Zustand).

## Global Constraints

- Backend tests run: `cd backend && arch -arm64 .venv/bin/python -m pytest <path> -v` (arm64 venv prefix required).
- Frontend tests run: `cd frontend && npx vitest run <path>`; typecheck `cd frontend && npx tsc --noEmit`.
- If a command hits ENOSPC / `/private/tmp ... full`, prefix with: `export TMPDIR="$HOME/.cache/cc-tmp" && mkdir -p "$TMPDIR" &&`.
- `count_cells` entries are **1-based** `[row, col]` (openpyxl convention), same as `/api/count-cells`.
- Empty/absent `count_cells` ⇒ NO filter (read all). This preserves existing projects and is the backward-compat contract.
- The per-cell filter runs BEFORE the existing `value_overrides` block in each extractor — an explicit override can re-raise an excluded (0) count.
- Reuse the existing `counts` paint role; `counts_cols` derivation in `paintToParsedDb` stays unchanged (it provides column geometry).
- There is an UNRELATED uncommitted change in `backend/aurum_encuestas/llm_client.py` (env var rename). Do NOT stage, commit, revert, or touch it. Each commit stages ONLY the files its task lists.
- Work on the existing feature branch (`feat-count-cells`); do NOT switch branches inside a task.

---

### Task 1: `count_cells` model + per-cell filter in extraction

**Files:**
- Modify: `backend/aurum_encuestas/models.py` (`ParsedDB`)
- Modify: `backend/aurum_encuestas/data_extractor.py` (`_count_cell_set` + filter in both extractors)
- Modify: `backend/aurum_encuestas/pattern_classifier.py`, `pptx_generator.py`, `api.py` (pass `count_cells`)
- Test: `backend/tests/test_data_extractor.py`

**Interfaces:**
- Produces: `ParsedDB.count_cells: list`; `_count_cell_set(count_cells) -> set[tuple[int,int]] | None`; `extract_chart_data(..., count_cells=None)` and `extract_all_breakdowns_data(..., count_cells=None)` apply the filter.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_data_extractor.py` (mirror the existing override tests' style; they already import `parse_xlsx` and use `valid_xlsx_path`):

```python
def test_count_cells_filter_excludes_unmarked(valid_xlsx_path):
    from aurum_encuestas.data_extractor import _find_question_rows, _resolve_breakdown_cols
    from openpyxl import load_workbook
    db = parse_xlsx(str(valid_xlsx_path))
    q1 = db.questions[0]
    ws = load_workbook(str(valid_xlsx_path), data_only=True).worksheets[0]
    rows = _find_question_rows(ws, q1)
    cols = _resolve_breakdown_cols(ws, "general", db.data_blocks["counts_cols"][0])
    si_cell = [rows["Sí"], cols["Total"]]          # mark ONLY "Sí"
    data = extract_chart_data(str(valid_xlsx_path), q1, "general", db.data_blocks,
                              total_row=db.total_row, count_cells=[si_cell])
    assert data["Total"]["Sí"]["count"] == 458     # marked → read
    assert data["Total"]["No"]["count"] == 0       # unmarked → 0
    assert data["Total"]["No"]["pct"] == 0.0


def test_count_cells_empty_reads_all(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    q1 = db.questions[0]
    full = extract_chart_data(str(valid_xlsx_path), q1, "general", db.data_blocks,
                              total_row=db.total_row, count_cells=None)
    none = extract_chart_data(str(valid_xlsx_path), q1, "general", db.data_blocks,
                              total_row=db.total_row)
    assert full == none                            # None ⇒ no filter
    assert full["Total"]["No"]["count"] != 0       # "No" still read


def test_count_cells_override_wins(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    q1 = db.questions[0]
    key = f"{q1.id}|general|Total|No"
    # "No" is excluded by count_cells (empty marked set for it) but overridden to 5
    data = extract_chart_data(str(valid_xlsx_path), q1, "general", db.data_blocks,
                              total_row=db.total_row, count_cells=[[1, 1]],
                              overrides={key: {"count": 5}})
    assert data["Total"]["No"]["count"] == 5       # override applies after the 0-forcing
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_data_extractor.py::test_count_cells_filter_excludes_unmarked tests/test_data_extractor.py::test_count_cells_empty_reads_all tests/test_data_extractor.py::test_count_cells_override_wins -v`
Expected: FAIL (`unexpected keyword argument 'count_cells'`).

- [ ] **Step 3: Add the model field**

In `backend/aurum_encuestas/models.py`, `class ParsedDB` — add after `value_overrides` (line ~47):

```python
    count_cells: list = Field(default_factory=list)
```

(`Field` is already imported and used by `value_overrides`.)

- [ ] **Step 4: Add `_count_cell_set` + filter in `extract_chart_data`**

In `backend/aurum_encuestas/data_extractor.py`, add the helper near `_override_key`:

```python
def _count_cell_set(count_cells: list | None) -> set[tuple[int, int]] | None:
    """list[[row,col]] → set of (row,col); None/empty → None (no filter)."""
    if not count_cells:
        return None
    return {(int(r), int(c)) for r, c in count_cells}
```

Change `extract_chart_data`'s signature to add `count_cells: list | None = None` (last param, after `overrides`). Near the top of the function (after `breakdown_cols` is resolved) compute:

```python
    cset = _count_cell_set(count_cells)
```

Inside the option loop, right AFTER `count_v` is computed from the cell and BEFORE the `if overrides:` block:

```python
            if cset is not None and (row, col) not in cset:
                count_v = 0
            pct_v = (count_v / total_v) if (total_v and total_v != 0) else None
```

(Move/ensure `pct_v` is computed from the possibly-zeroed `count_v`. If `pct_v` is already computed above from `count_v`, recompute it here after the zeroing so an excluded cell reports pct 0.0. The `overrides` block stays after this, unchanged.)

- [ ] **Step 5: Apply the same filter in `extract_all_breakdowns_data`**

Add `count_cells: list | None = None` to its signature (last param). Compute `cset = _count_cell_set(count_cells)` near the top. In its inner option loop, after reading `count_v` and before the `if overrides:` block:

```python
                if cset is not None and (row, col) not in cset:
                    count_v = 0
                pct_v = (count_v / total_v) if (total_v and total_v != 0) else None
```

- [ ] **Step 6: Pass `count_cells` from all callers**

Add `count_cells=...` next to each existing `overrides=...` argument:
- `pattern_classifier.py:498` and `:503` → `count_cells=getattr(parsed_db, "count_cells", None)`.
- `pptx_generator.py:423` → `count_cells=state.parsed_db.count_cells if state.parsed_db else None`.
- `api.py:198`, `:339`, `:631` → `count_cells=state.parsed_db.count_cells`.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_data_extractor.py tests/test_pattern_classifier.py -v`
Expected: PASS (new tests + existing — existing pass `count_cells=None` by default).

- [ ] **Step 8: Run the api test file to confirm no regression**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_api.py -q`
Expected: PASS (pre-existing skips allowed; no new failures).

- [ ] **Step 9: Commit**

```bash
git add backend/aurum_encuestas/models.py backend/aurum_encuestas/data_extractor.py backend/aurum_encuestas/pattern_classifier.py backend/aurum_encuestas/pptx_generator.py backend/aurum_encuestas/api.py backend/tests/test_data_extractor.py
git commit -m "feat(extractor): per-cell count_cells filter (unmarked option×category → 0)"
```

---

### Task 2: Frontend `count_cells` type + `paintToParsedDb` emits it (with truncation guard)

**Files:**
- Modify: `frontend/src/types/index.ts` (`ParsedDB`)
- Modify: `frontend/src/pages/Wizard/sheetPaint.ts` (`paintToParsedDb`)
- Modify: `frontend/src/pages/Wizard/sheetPaint.test.ts` (tests)
- Modify: `frontend/src/pages/Wizard/XlsxVerifyWizard.tsx` (pass `gridTruncated`)

**Interfaces:**
- Consumes: `PaintMap`, the existing `paintToParsedDb(cells, paint, prev)` shape.
- Produces: `paintToParsedDb(cells, paint, prev, truncated = false)` returns a db whose `count_cells` is the painted `counts` cells (1-based `[row,col]`), or `prev.count_cells` when `truncated`.

- [ ] **Step 1: Add the type field**

In `frontend/src/types/index.ts`, `interface ParsedDB` — add after `value_overrides`:

```ts
  count_cells?: number[][]
```

- [ ] **Step 2: Write the failing tests**

Append to `frontend/src/pages/Wizard/sheetPaint.test.ts` (it already imports `paintToParsedDb` and builds `cells`/`paint`/`prev` fixtures — reuse that style):

```ts
it("paintToParsedDb emits count_cells (1-based) for painted counts cells", () => {
  const cells = [["P1", "", ""], ["", "Sí", ""], ["", "No", ""]]
  const p: PaintMap = {
    "0,0": "question", "1,1": "option", "2,1": "option",
    "1,2": "counts", "2,2": "counts",
  }
  const prev = { questions: [], breakdowns: [], data_blocks: { counts_cols: [3, 3], pct_row_cols: [], pct_col_cols: [] }, sample_size: 0, total_row: null } as any
  const { db } = paintToParsedDb(cells, p, prev)
  expect(db.count_cells).toEqual([[2, 3], [3, 3]])   // (r+1,c+1), sorted
})

it("paintToParsedDb keeps prev.count_cells when truncated", () => {
  const cells = [["P1"]]
  const p: PaintMap = { "0,0": "counts" }
  const prev = { questions: [], breakdowns: [], data_blocks: { counts_cols: [1, 1], pct_row_cols: [], pct_col_cols: [] }, sample_size: 0, total_row: null, count_cells: [[9, 9]] } as any
  const { db } = paintToParsedDb(cells, p, prev, true)
  expect(db.count_cells).toEqual([[9, 9]])           // not re-derived
})
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/pages/Wizard/sheetPaint.test.ts`
Expected: FAIL (`db.count_cells` is undefined / arity).

- [ ] **Step 4: Implement in `paintToParsedDb`**

In `frontend/src/pages/Wizard/sheetPaint.ts`, change the signature to:

```ts
export function paintToParsedDb(
  cells: string[][], paint: PaintMap, prev: ParsedDB, truncated = false,
): { db: ParsedDB; warnings: string[] } {
```

Before the final `return`, compute `count_cells`:

```ts
  const count_cells = truncated
    ? (prev.count_cells ?? [])
    : entries
        .filter((e) => e.role === "counts")
        .map((e) => [e.r + 1, e.c + 1] as number[])
        .sort((a, b) => a[0] - b[0] || a[1] - b[1])
```

(`entries` is the `{r,c,role}[]` array already built at the top of the function.) Add `count_cells` to the returned db:

```ts
  return { db: { ...prev, questions, breakdowns, data_blocks, sample_size: prev.sample_size, total_row, count_cells }, warnings }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/pages/Wizard/sheetPaint.test.ts`
Expected: PASS (new tests + existing round-trip tests; existing 3-arg calls still compile via the `truncated = false` default).

- [ ] **Step 6: Pass `gridTruncated` from the wizard**

In `frontend/src/pages/Wizard/XlsxVerifyWizard.tsx`, the excel-mode **Guardar** button (line ~132) currently calls `paintToParsedDb(gridCells, paint, parsedDb!)`. Change to:

```tsx
                const { db, warnings } = paintToParsedDb(gridCells, paint, parsedDb!, gridTruncated)
                if (gridTruncated) warnings.unshift("Hoja truncada — la exclusión por celda queda deshabilitada (se leen todos los conteos).")
```

(`gridTruncated` already exists in component state. `warnings` is already shown in the existing `confirm(...)` dialog; prepending the note surfaces it. If `warnings` is empty and not truncated, behavior is unchanged.)

- [ ] **Step 7: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit 0.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/pages/Wizard/sheetPaint.ts frontend/src/pages/Wizard/sheetPaint.test.ts frontend/src/pages/Wizard/XlsxVerifyWizard.tsx
git commit -m "feat(wizard): paintToParsedDb emits count_cells (truncation-guarded) + wizard wiring"
```

---

## Self-Review

**Spec coverage:**
- §1 model `count_cells` (backend + frontend type) → Task 1 (backend), Task 2 (type). ✓
- §2 extraction filter (both functions, before overrides, pct from zeroed count) + `_count_cell_set` → Task 1. ✓
- §3 callers pass `count_cells` → Task 1 Step 6. ✓
- §4 `paintToParsedDb` emits `count_cells` + truncation guard + wizard passes `gridTruncated` → Task 2. ✓
- Excluded = count 0 / pct 0.0, option kept → Task 1 test `test_count_cells_filter_excludes_unmarked`. ✓
- Backward-compat empty ⇒ read all → Task 1 `test_count_cells_empty_reads_all`. ✓
- Override wins over exclusion → Task 1 `test_count_cells_override_wins`. ✓
- Truncation guard → Task 2 `keeps prev.count_cells when truncated`. ✓

**Placeholder scan:** none — every step has concrete code/commands.

**Type consistency:** `_count_cell_set(count_cells) -> set[tuple[int,int]] | None` defined Task 1 Step 4, used in both extractors. `count_cells` is `list[[row,col]]` 1-based on both sides; frontend emits `[e.r+1, e.c+1]` matching backend `(row,col)` 1-based lookups (`q_rows`/`breakdown_cols` are 1-based openpyxl). `paintToParsedDb(..., truncated=false)` defined Task 2 Step 4, called with 4 args Task 2 Step 6 and 3 args (default) in existing tests.
```
