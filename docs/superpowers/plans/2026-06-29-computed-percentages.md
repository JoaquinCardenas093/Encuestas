# Computed Percentages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute every chart/table percentage as `count / column_total` from an auto-detected Total row (col B == "Total", overridable in the mapper), replacing the pre-computed `%row`/`%col` block reads.

**Architecture:** `ParsedDB` gains `total_row` (1-based sheet row of column totals); the parser auto-detects it. Both extractors take `total_row` and compute `pct = count / cell(total_row, col)`. The visual mapper drops the `%row`/`%col` paint roles and adds a `Total` row role; the field editor exposes `total_row` as an editable number.

**Tech Stack:** Python (openpyxl, pytest, FastAPI), React + TypeScript (vitest, Zustand).

## Global Constraints

- Backend tests run: `cd backend && arch -arm64 .venv/bin/python -m pytest <path> -v` (arm64 venv prefix required).
- Frontend tests run: `cd frontend && npx vitest run <path>`; typecheck `cd frontend && npx tsc --noEmit`.
- If a command hits ENOSPC / `/private/tmp ... full`, prefix with `export TMPDIR="$HOME/.cache/cc-tmp" && mkdir -p "$TMPDIR" &&`.
- `total_row` is **1-based** (openpyxl sheet row), `None` when no Total row found.
- `pct = count / total` only when `total` is a number and `!= 0`; otherwise `pct = None`. Missing count → `count = 0`.
- The pre-computed `%row`/`%col` blocks are NO LONGER read for extraction. `data_blocks.pct_row_cols`/`pct_col_cols` remain in the serialized model (carried through unchanged) but are unused.
- Work on a feature branch (controller creates it); do NOT switch branches inside a task.

---

### Task 1: `total_row` model field + parser detection

**Files:**
- Modify: `backend/aurum_encuestas/models.py` (`ParsedDB`)
- Modify: `backend/aurum_encuestas/xlsx_parser.py` (`_detect_total_row`, `parse_xlsx`)
- Test: `backend/tests/test_xlsx_parser.py`

**Interfaces:**
- Produces: `ParsedDB.total_row: int | None`; `_detect_total_row(ws) -> int | None`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_xlsx_parser.py`:

```python
def test_parse_detects_total_row(valid_xlsx_path):
    from aurum_encuestas.xlsx_parser import parse_xlsx
    db = parse_xlsx(str(valid_xlsx_path))
    # Fixture writes "Total" at row 3, col B
    assert db.total_row == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_xlsx_parser.py::test_parse_detects_total_row -v`
Expected: FAIL (`ParsedDB` has no `total_row`, or it's missing/None).

- [ ] **Step 3: Add the model field**

In `backend/aurum_encuestas/models.py`, `class ParsedDB` — add after `data_blocks`:

```python
    total_row: int | None = None
```

- [ ] **Step 4: Add detection + wire into parse_xlsx**

In `backend/aurum_encuestas/xlsx_parser.py`, add the helper (near `_detect_sample_size`):

```python
def _detect_total_row(ws) -> int | None:
    """Row whose column B is 'Total' — holds the per-column totals (denominators)."""
    for r in range(1, ws.max_row + 1):
        v = ws.cell(r, 2).value
        if v is not None and str(v).strip() == "Total":
            return r
    return None
```

In `parse_xlsx`, after `data_blocks = _detect_data_blocks(ws)`:

```python
    total_row = _detect_total_row(ws)
```

and add `total_row=total_row,` to the `ParsedDB(...)` constructor call.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_xlsx_parser.py -v`
Expected: PASS (new test + existing parser tests).

- [ ] **Step 6: Commit**

```bash
git add backend/aurum_encuestas/models.py backend/aurum_encuestas/xlsx_parser.py backend/tests/test_xlsx_parser.py
git commit -m "feat(parser): detect Total row (col B == 'Total') into ParsedDB.total_row"
```

---

### Task 2: Compute pct = count / column_total in extraction

**Files:**
- Modify: `backend/aurum_encuestas/data_extractor.py` (`extract_chart_data`, `extract_all_breakdowns_data`)
- Modify: `backend/aurum_encuestas/pattern_classifier.py`, `pptx_generator.py`, `api.py` (pass `total_row`)
- Test: `backend/tests/test_data_extractor.py`

**Interfaces:**
- Consumes: `ParsedDB.total_row` (Task 1).
- Produces: `extract_chart_data(xlsx_path, question, breakdown_id, data_blocks, allowed_categories=None, total_row=None)` and `extract_all_breakdowns_data(xlsx_path, question, breakdowns, data_blocks, total_row=None)` — `pct` is computed from `total_row`.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_data_extractor.py`:

```python
def test_extract_chart_data_computes_pct(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    q1 = db.questions[0]
    data = extract_chart_data(str(valid_xlsx_path), q1, "general", db.data_blocks, total_row=db.total_row)
    assert data["Total"]["Sí"]["count"] == 458
    assert abs(data["Total"]["Sí"]["pct"] - 458 / 500) < 1e-9


def test_extract_chart_data_no_total_row_pct_none(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    q1 = db.questions[0]
    data = extract_chart_data(str(valid_xlsx_path), q1, "general", db.data_blocks, total_row=None)
    assert data["Total"]["Sí"]["pct"] is None
    assert data["Total"]["Sí"]["count"] == 458
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_data_extractor.py::test_extract_chart_data_computes_pct tests/test_data_extractor.py::test_extract_chart_data_no_total_row_pct_none -v`
Expected: FAIL (`unexpected keyword argument 'total_row'`).

- [ ] **Step 3: Rewrite `extract_chart_data`**

Replace the `extract_chart_data` body in `backend/aurum_encuestas/data_extractor.py` with:

```python
def extract_chart_data(xlsx_path: str, question: Question, breakdown_id: str,
                       data_blocks: dict, allowed_categories: list[str] | None = None,
                       total_row: int | None = None) -> dict:
    """Returns {breakdown_category: {option: {count, pct}}}.
    pct = count / column_total, where column_total = cell(total_row, col)."""
    wb = load_workbook(xlsx_path, data_only=True)
    ws = wb.worksheets[0]
    q_rows = _find_question_rows(ws, question)
    counts_start = data_blocks["counts_cols"][0]
    breakdown_cols = _resolve_breakdown_cols(ws, breakdown_id, counts_start)
    if allowed_categories is not None:
        breakdown_cols = {c: breakdown_cols[c] for c in allowed_categories if c in breakdown_cols}

    result: dict[str, dict[str, dict]] = {}
    for cat, col in breakdown_cols.items():
        result[cat] = {}
        total = ws.cell(total_row, col).value if total_row else None
        try:
            total_v = float(total) if total is not None else None
        except (TypeError, ValueError):
            total_v = None
        for opt, row in q_rows.items():
            count = ws.cell(row, col).value or 0
            try:
                count_v = int(count)
            except (TypeError, ValueError):
                count_v = 0
            pct_v = (count_v / total_v) if (total_v and total_v != 0) else None
            result[cat][opt] = {"count": count_v, "pct": pct_v}
    return result
```

- [ ] **Step 4: Rewrite `extract_all_breakdowns_data`**

In the same file, change the signature to add `total_row: int | None = None` and replace its inner column loop so `pct` is computed the same way. The body becomes:

```python
    wb = load_workbook(xlsx_path, data_only=True)
    ws = wb.worksheets[0]
    q_rows = _find_question_rows(ws, question)
    counts_start = data_blocks["counts_cols"][0]

    result: dict[str, dict] = {}
    for bd in breakdowns:
        cnt_cols = _resolve_breakdown_cols(ws, bd.id, counts_start)
        cats: dict[str, dict] = {}
        for cat in bd.categories:  # preserve declared order
            col = cnt_cols.get(cat)
            if col is None:
                continue
            total = ws.cell(total_row, col).value if total_row else None
            try:
                total_v = float(total) if total is not None else None
            except (TypeError, ValueError):
                total_v = None
            cell_map: dict[str, dict] = {}
            for opt, row in q_rows.items():
                count = ws.cell(row, col).value or 0
                try:
                    count_v = int(count)
                except (TypeError, ValueError):
                    count_v = 0
                pct_v = (count_v / total_v) if (total_v and total_v != 0) else None
                cell_map[opt] = {"count": count_v, "pct": pct_v}
            cats[cat] = cell_map
        result[bd.id] = {"label": bd.label, "categories": cats}
    return result
```

(Remove the now-unused `pct_start` / `pct_cols` / `allowed` lines.)

- [ ] **Step 5: Pass `total_row` from all callers**

Read each call site and add `total_row=...`:
- `pattern_classifier.py` (~line 494 `extract_chart_data(...)` and ~line 499 `extract_all_breakdowns_data(...)`): pass `total_row=getattr(parsed_db, "total_row", None)`.
- `api.py` (~line 266 `extract_chart_data(...)` inside `_build_analysis_context`, and ~line 560 `extract_all_breakdowns_data(...)`): pass `total_row=state.parsed_db.total_row`.
- `pptx_generator.py` (~line 419 `extract_chart_data(...)`): pass `total_row=state.parsed_db.total_row`.

Read the surrounding lines first to confirm the local variable holding the parsed db (`parsed_db` vs `state.parsed_db`).

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_data_extractor.py tests/test_pattern_classifier.py -v`
Expected: PASS. (Existing tests assert `count` and key presence, not pct values, so they remain green.)

- [ ] **Step 7: Commit**

```bash
git add backend/aurum_encuestas/data_extractor.py backend/aurum_encuestas/pattern_classifier.py backend/aurum_encuestas/pptx_generator.py backend/aurum_encuestas/api.py backend/tests/test_data_extractor.py
git commit -m "feat(extractor): compute pct = count / column-total from Total row"
```

---

### Task 3: Frontend `total_row` type + sheetPaint `total` role

**Files:**
- Modify: `frontend/src/types/index.ts` (`ParsedDB`)
- Modify: `frontend/src/pages/Wizard/sheetPaint.ts`
- Modify: `frontend/src/pages/Wizard/sheetPaint.test.ts`

**Interfaces:**
- Consumes: `paintToParsedDb`, `parsedDbToPaint`, `cellKey`, `Role`, `PaintMap` (existing).
- Produces: `Role` now includes `"total"` and drops `"pctRow"`/`"pctCol"`; `paintToParsedDb`/`parsedDbToPaint` handle `total_row`.

- [ ] **Step 1: Add the type field**

In `frontend/src/types/index.ts`, `interface ParsedDB` — add after `data_blocks`:

```ts
  total_row?: number | null
```

- [ ] **Step 2: Update the existing tests (red)**

In `frontend/src/pages/Wizard/sheetPaint.test.ts`:
- In the `prev` fixture add `total_row: 3,` (after `sample_size`).
- In the "paintToParsedDb rebuilds..." test: replace the line that paints `counts` with the same plus a `total` row, and drop any `pctRow`/`pctCol` paint. Concretely change the data-block paint lines to:

```ts
  p = paintRect(p, 2, 2, 2, 4, "counts")   // counts cols 2..4 -> [3,5]
  p = paintRect(p, 1, 2, 1, 4, "total")     // total row = sheet row 2
```

and add `expect(db.total_row).toBe(2)` to that test's assertions. Remove any assertion referencing `pctRow`/`pctCol` roles. Keep `counts_cols` assertion. Change the `pct_row_cols` assertion to expect it carried from prev: `expect(db.data_blocks.pct_row_cols).toEqual([7, 9])` (unchanged from prev).
- In the round-trip test: add `expect(db.total_row).toBe(prev.total_row)`.

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/pages/Wizard/sheetPaint.test.ts`
Expected: FAIL (`"total"` not assignable to `Role`; `db.total_row` undefined).

- [ ] **Step 4: Update `sheetPaint.ts`**

- Change the `Role` union: remove `"pctRow" | "pctCol"`, add `"total"`:

```ts
export type Role =
  | "question" | "option" | "breakdown" | "category"
  | "counts" | "total"
```

- In `paintToParsedDb`, replace the data-block section with counts-only + total_row:

```ts
  // --- Data blocks (counts only; pct_* carried from prev, no longer read) ---
  const countsCols = entries.filter((e) => e.role === "counts").map((e) => e.c)
  const counts_cols = countsCols.length
    ? [Math.min(...countsCols) + 1, Math.max(...countsCols) + 1]
    : prev.data_blocks.counts_cols
  const data_blocks = {
    counts_cols,
    pct_row_cols: prev.data_blocks.pct_row_cols,
    pct_col_cols: prev.data_blocks.pct_col_cols,
  }

  // --- Total row (1-based) ---
  const totalRows = entries.filter((e) => e.role === "total").map((e) => e.r)
  const total_row = totalRows.length ? Math.min(...totalRows) + 1 : (prev.total_row ?? null)
```

and change the return to include `total_row`:

```ts
  return { db: { ...prev, questions, breakdowns, data_blocks, sample_size: prev.sample_size, total_row }, warnings }
```

- In `parsedDbToPaint`, replace the data-block pre-paint block (the `paintCols(...)` for counts/pctRow/pctCol) with counts + total:

```ts
  // Counts block: paint an indicator row across the counts columns.
  const baseRow = Math.min(2, Math.max(0, cells.length - 1))
  const cc = db.data_blocks.counts_cols
  if (cc && cc.length >= 2) {
    for (let c = cc[0] - 1; c <= cc[1] - 1; c++) paint[cellKey(baseRow, c)] = "counts"
  }
  // Total row across the counts columns.
  if (db.total_row && db.total_row >= 1) {
    const r = db.total_row - 1
    if (cc && cc.length >= 2) for (let c = cc[0] - 1; c <= cc[1] - 1; c++) paint[cellKey(r, c)] = "total"
  }
```

(Remove the old `markerRow`/`paintCols` helper and its three calls.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/pages/Wizard/sheetPaint.test.ts && npx tsc --noEmit`
Expected: tests PASS; tsc exit 0. (If `SheetGrid.tsx` references the removed roles, that's Task 5 — but tsc here may flag it; if so, leave SheetGrid for Task 5 and note the expected error rather than editing it. To keep tsc green now, Task 5 should run before final integration — see note.) If tsc fails ONLY due to `SheetGrid.tsx` role references, that is expected and resolved in Task 5; record it in the report.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/pages/Wizard/sheetPaint.ts frontend/src/pages/Wizard/sheetPaint.test.ts
git commit -m "feat(wizard): sheetPaint total role + total_row (drop pct roles)"
```

---

### Task 4: `mappingDraft.setTotalRow`

**Files:**
- Modify: `frontend/src/pages/Wizard/mappingDraft.ts`
- Modify: `frontend/src/pages/Wizard/mappingDraft.test.ts`

**Interfaces:**
- Produces: `setTotalRow(db, n) -> ParsedDB` (pure).

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/pages/Wizard/mappingDraft.test.ts`:

```ts
it("setTotalRow is pure and sets total_row", () => {
  const out = D.setTotalRow(base, 7)
  expect(out.total_row).toBe(7)
  expect(base.total_row).toBeUndefined()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/Wizard/mappingDraft.test.ts`
Expected: FAIL (`D.setTotalRow` is not a function).

- [ ] **Step 3: Implement the helper**

Append to `frontend/src/pages/Wizard/mappingDraft.ts`:

```ts
export const setTotalRow = (db: ParsedDB, n: number): ParsedDB => ({ ...db, total_row: n })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/Wizard/mappingDraft.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Wizard/mappingDraft.ts frontend/src/pages/Wizard/mappingDraft.test.ts
git commit -m "feat(wizard): mappingDraft.setTotalRow helper"
```

---

### Task 5: SheetGrid `Total` role + wizard `total_row` field

**Files:**
- Modify: `frontend/src/pages/Wizard/SheetGrid.tsx` (toolbar roles)
- Modify: `frontend/src/pages/Wizard/XlsxVerifyWizard.tsx` (total_row field)

**Interfaces:**
- Consumes: `Role` (now includes `total`, no pct roles — Task 3), `mappingDraft.setTotalRow` (Task 4).

UI wiring; verify with `tsc --noEmit` + manual browser check.

- [ ] **Step 1: Update the SheetGrid toolbar roles**

In `frontend/src/pages/Wizard/SheetGrid.tsx`, change the `ROLES` array — remove the `pctRow` and `pctCol` entries, add a `total` entry:

```tsx
const ROLES: { role: Role; label: string; color: string }[] = [
  { role: "question", label: "Pregunta", color: "#2e7d32" },
  { role: "option", label: "Opciones", color: "#1565c0" },
  { role: "breakdown", label: "Breakdown", color: "#e07b00" },
  { role: "category", label: "Categoría", color: "#7b3fb5" },
  { role: "counts", label: "Counts", color: "#616161" },
  { role: "total", label: "Total", color: "#00838f" },
]
```

(The `COLOR` map derives from `ROLES`, so no other change is needed there.)

- [ ] **Step 2: Add the `total_row` field to the wizard**

In `frontend/src/pages/Wizard/XlsxVerifyWizard.tsx`:
- In the Lista (read-only) view, show the detected total row next to the data-blocks line, e.g.:
  `<div>Fila Total: <strong>{view.total_row ?? "—"}</strong></div>`
- In the field editor (`mode === "fields"`), render an editable number bound to the draft via `setTotalRow`:

```tsx
<label className="block text-xs text-neutral-400 mb-1 mt-3">Fila Total (denominadores)</label>
<input
  type="number"
  value={view.total_row ?? ""}
  onChange={(e) => setDraft(D.setTotalRow(draft!, parseInt(e.target.value, 10) || 0))}
  className="w-32 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
/>
```

(`D` is the existing `import * as D from "./mappingDraft"`; `view`/`draft`/`setDraft` already exist.)

- [ ] **Step 3: Verify it type-checks**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit 0 (zero errors — the Task 3 role change + this toolbar change are now consistent).

- [ ] **Step 4: Manual verification**

Run: `cd frontend && npm run dev` (backend already running).
1. Upload `BD Aurora ejemplo.xlsx`, reach the wizard. Lista shows "Fila Total: 3".
2. Generate a preview of a chart → percentages reflect count÷total (e.g. ~91.6% for P1 "Sí").
3. Editar campos → change "Fila Total" to a wrong row, Guardar, preview → percentages change / blank, confirming it's used.
4. Editar en Excel → toolbar shows "Total" (no %Row/%Col); the detected total row is pre-painted; repaint a different row, Guardar → reflected.

Expected: all behave; no console errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Wizard/SheetGrid.tsx frontend/src/pages/Wizard/XlsxVerifyWizard.tsx
git commit -m "feat(wizard): Total paint role + editable total_row field"
```

---

## Self-Review

**Spec coverage:**
- §1 model `total_row` (backend + frontend) → Task 1 (backend), Task 3 (frontend type). ✓
- §2 parser `_detect_total_row` → Task 1. ✓
- §3 extraction computes pct + callers pass total_row → Task 2. ✓
- §4 mapper: `total` role, drop pct roles, build/inverse handle total_row → Task 3 (sheetPaint) + Task 5 (toolbar). ✓
- §5 field editor total_row + edge handling (None/0 → pct None) → Task 5 (field) + Task 2 (pct None). ✓
- Testing (detect, computed pct, total_row round-trip, setTotalRow) → Tasks 1-4 automated, Task 5 manual. ✓

**Type consistency:** `total_row` is `int | None` (Py) / `number | null` (TS) throughout; 1-based everywhere; `Role` adds `"total"` and drops `"pctRow"/"pctCol"` in Task 3, consumed by SheetGrid in Task 5; `setTotalRow` defined Task 4, used Task 5; extractor `total_row=` kwarg defined Task 2 matches the callers updated in the same task.

**Placeholder scan:** no TBD/TODO. Task 2 Step 5 and Task 5 require reading the real call sites / file (judgment) but name the exact line areas and the exact code to add. Task 3 Step 5 explicitly anticipates a transient tsc error from `SheetGrid.tsx` (resolved in Task 5) and tells the implementer to record rather than hack it.
