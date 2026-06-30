# "Seleccionar conteos" — Count-Cell Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A "Seleccionar conteos" button in the Excel editor that highlights every detected count cell (option×category) using the existing `counts` paint role, so the user can corroborate the system read the counts correctly.

**Architecture:** A new fallback-safe backend endpoint `POST /api/count-cells` reuses the extractor's `_find_question_rows` + `_resolve_breakdown_cols` over all questions × all breakdowns to return 1-based `(row,col)` coordinates of every count cell. The frontend fetches them, converts to 0-based, filters to the visible 200×120 window via a pure `paintCountCells` helper, and paints the `counts` role into the `SheetGrid`'s `PaintMap`. No change to the extraction model or data shapes.

**Tech Stack:** Python (FastAPI, openpyxl, pytest/TestClient), React + TypeScript (vitest, Zustand).

## Global Constraints

- Backend tests run: `cd backend && arch -arm64 .venv/bin/python -m pytest <path> -v` (arm64 venv prefix required).
- Frontend tests run: `cd frontend && npx vitest run <path>`; typecheck `cd frontend && npx tsc --noEmit`.
- If a command hits ENOSPC / `/private/tmp ... full`, prefix with: `export TMPDIR="$HOME/.cache/cc-tmp" && mkdir -p "$TMPDIR" &&`.
- Coordinates from the backend are **1-based** (openpyxl convention). The frontend converts to 0-based (`row-1, col-1`).
- The visible grid window is **200 rows × 120 cols** (`MAX_ROWS, MAX_COLS` in `/api/sheet-grid`). Count cells outside the window are dropped and counted.
- Reuse the existing `counts` paint role — do NOT add a new role or change the extraction model (`paintToParsedDb` still derives `counts_cols` from min/max column).
- Endpoints must be fallback-safe: any failure returns `{error: <str>, cells: []}` with HTTP 200, never raises to the client (same pattern as `/api/cell-values`, `/api/sheet-grid`).
- There is an UNRELATED uncommitted change in `backend/aurum_encuestas/llm_client.py` (env var rename). Do NOT stage, commit, revert, or touch it. Each commit stages ONLY the files its task lists.
- Work on a feature branch (the controller creates it); do NOT switch branches inside a task.

---

### Task 1: `POST /api/count-cells` endpoint

**Files:**
- Modify: `backend/aurum_encuestas/api.py` (request model + route)
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `ParsedDB.questions`, `ParsedDB.breakdowns`, `ParsedDB.data_blocks["counts_cols"]`; extractor helpers `_find_question_rows(ws, question)` and `_resolve_breakdown_cols(ws, breakdown_id, block_start_col)` (in `backend/aurum_encuestas/data_extractor.py`).
- Produces: `POST /api/count-cells` body `{state}` → `{cells: [{row, col}]}` (1-based, deduped) or `{error, cells: []}`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_api.py` (the `_minimal_state(db, path)` helper already exists at the bottom of the file — reuse it):

```python
def test_count_cells_endpoint(valid_xlsx_path):
    from aurum_encuestas.xlsx_parser import parse_xlsx
    from aurum_encuestas.data_extractor import _find_question_rows, _resolve_breakdown_cols
    from openpyxl import load_workbook
    db = parse_xlsx(str(valid_xlsx_path))
    state = _minimal_state(db, str(valid_xlsx_path))
    r = client.post("/api/count-cells", json={"state": state})
    assert r.status_code == 200
    body = r.json()
    assert body.get("error") is None
    cells = body["cells"]
    assert len(cells) > 0
    # No duplicate coordinates
    pairs = [(c["row"], c["col"]) for c in cells]
    assert len(pairs) == len(set(pairs))
    # A known count cell (P1 "Sí" / general / Total) is present and holds 458
    ws = load_workbook(str(valid_xlsx_path), data_only=True).worksheets[0]
    q1 = db.questions[0]
    rows = _find_question_rows(ws, q1)
    cols = _resolve_breakdown_cols(ws, "general", db.data_blocks["counts_cols"][0])
    expected = {"row": rows["Sí"], "col": cols["Total"]}
    assert expected in cells
    assert ws.cell(expected["row"], expected["col"]).value == 458


def test_count_cells_endpoint_bad_state():
    r = client.post("/api/count-cells", json={"state": {"not": "valid"}})
    assert r.status_code == 200
    body = r.json()
    assert body["cells"] == []
    assert body["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_api.py::test_count_cells_endpoint tests/test_api.py::test_count_cells_endpoint_bad_state -v`
Expected: FAIL (404 — route missing).

- [ ] **Step 3: Add the request model**

In `backend/aurum_encuestas/api.py`, near the other request models (e.g. next to `CellValuesRequest`):

```python
class CountCellsRequest(BaseModel):
    state: dict
```

- [ ] **Step 4: Add the route**

In `backend/aurum_encuestas/api.py`, near the `/api/cell-values` route:

```python
@app.post("/api/count-cells")
async def count_cells_endpoint(req: CountCellsRequest):
    """Coordinates (1-based) of every count cell (option×category across all
    questions and breakdowns), so the Excel editor can highlight them for the
    user to corroborate. Reuses the extractor's row/column resolution."""
    from openpyxl import load_workbook
    from .data_extractor import _find_question_rows, _resolve_breakdown_cols
    try:
        state = ProjectState.model_validate(req.state)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e), "cells": []}
    if not state.parsed_db or not state.inputs:
        return {"error": "Sin datos", "cells": []}
    try:
        cc = state.parsed_db.data_blocks.get("counts_cols")
        counts_start = cc[0]
        wb = load_workbook(state.inputs.db_path, data_only=True)
        ws = wb.worksheets[0]
        seen: set[tuple[int, int]] = set()
        for q in state.parsed_db.questions:
            q_rows = _find_question_rows(ws, q)
            for bd in state.parsed_db.breakdowns:
                bd_cols = _resolve_breakdown_cols(ws, bd.id, counts_start)
                for col in bd_cols.values():
                    for row in q_rows.values():
                        seen.add((row, col))
    except Exception as e:  # noqa: BLE001
        return {"error": str(e), "cells": []}
    cells = [{"row": r, "col": c} for (r, c) in sorted(seen)]
    return {"cells": cells}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_api.py::test_count_cells_endpoint tests/test_api.py::test_count_cells_endpoint_bad_state -v`
Expected: PASS.

- [ ] **Step 6: Run the full api test file to confirm no regression**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_api.py -q`
Expected: PASS (pre-existing skips allowed; no new failures).

- [ ] **Step 7: Commit**

```bash
git add backend/aurum_encuestas/api.py backend/tests/test_api.py
git commit -m "feat(api): /api/count-cells returns count-cell coordinates for verification"
```

---

### Task 2: Frontend `paintCountCells` helper + `fetchCountCells` client

**Files:**
- Modify: `frontend/src/pages/Wizard/sheetPaint.ts` (`paintCountCells`)
- Modify: `frontend/src/pages/Wizard/sheetPaint.test.ts` (test)
- Modify: `frontend/src/api/client.ts` (`CountCellsResponse` + `fetchCountCells`)

**Interfaces:**
- Consumes: `PaintMap`, `cellKey` (from `sheetPaint.ts`).
- Produces:
  - `paintCountCells(paint: PaintMap, coords: {row: number; col: number}[], nRows: number, nCols: number): { paint: PaintMap; dropped: number }` — pure; merges the `counts` role for each in-window coord (1-based→0-based), counts out-of-window coords as `dropped`, never mutates the input.
  - `fetchCountCells(state: any): Promise<CountCellsResponse>` where `CountCellsResponse { cells: { row: number; col: number }[]; error?: string }`.

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/pages/Wizard/sheetPaint.test.ts`:

```ts
import { paintCountCells } from "./sheetPaint"

describe("paintCountCells", () => {
  it("paints counts role at 0-based coords and counts out-of-window drops", () => {
    const { paint, dropped } = paintCountCells({}, [
      { row: 5, col: 3 },     // → "4,2"
      { row: 1, col: 200 },   // col 200 > nCols 120 → dropped
      { row: 250, col: 2 },   // row 250 > nRows 200 → dropped
    ], 200, 120)
    expect(paint["4,2"]).toBe("counts")
    expect(dropped).toBe(2)
  })

  it("merges over existing paint without mutating the input", () => {
    const base = { "0,0": "question" } as Record<string, string>
    const { paint } = paintCountCells(base as any, [{ row: 2, col: 2 }], 200, 120)
    expect(paint["0,0"]).toBe("question")   // preserved
    expect(paint["1,1"]).toBe("counts")     // added
    expect(base["1,1"]).toBeUndefined()     // pure
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/Wizard/sheetPaint.test.ts`
Expected: FAIL (`paintCountCells is not a function` / import error).

- [ ] **Step 3: Implement `paintCountCells`**

Append to `frontend/src/pages/Wizard/sheetPaint.ts`:

```ts
export function paintCountCells(
  paint: PaintMap,
  coords: { row: number; col: number }[],
  nRows: number,
  nCols: number,
): { paint: PaintMap; dropped: number } {
  const next = { ...paint }
  let dropped = 0
  for (const { row, col } of coords) {
    const r = row - 1
    const c = col - 1
    if (r < 0 || c < 0 || r >= nRows || c >= nCols) { dropped++; continue }
    next[cellKey(r, c)] = "counts"
  }
  return { paint: next, dropped }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/Wizard/sheetPaint.test.ts`
Expected: PASS.

- [ ] **Step 5: Add the API client function**

In `frontend/src/api/client.ts`, after the `fetchCellValues` block:

```ts
export interface CountCellsResponse {
  cells: { row: number; col: number }[]
  error?: string
}

export async function fetchCountCells(state: any): Promise<CountCellsResponse> {
  return request<CountCellsResponse>("/count-cells", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state }),
  })
}
```

- [ ] **Step 6: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit 0.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/Wizard/sheetPaint.ts frontend/src/pages/Wizard/sheetPaint.test.ts frontend/src/api/client.ts
git commit -m "feat(wizard): paintCountCells helper + fetchCountCells client"
```

---

### Task 3: "Seleccionar conteos" button in the Excel editor

**Files:**
- Modify: `frontend/src/pages/Wizard/XlsxVerifyWizard.tsx` (button + `handleSelectCounts` in the `mode === "excel"` block)

**Interfaces:**
- Consumes: `fetchCountCells` + `CountCellsResponse` (Task 2), `paintCountCells` (Task 2), existing wizard state `gridCells`, `paint`, `setPaint`, `gridError`, `setGridError`, `storeState`.

UI wiring; verify with `tsc --noEmit` + manual browser check (no pointer-test harness for this view).

- [ ] **Step 1: Add the imports**

In `frontend/src/pages/Wizard/XlsxVerifyWizard.tsx`:
- Add `fetchCountCells` to the existing import from `../../api/client` (it already imports `fetchSheetGrid` from there).
- Add `paintCountCells` to the existing import from `./sheetPaint` (the file already imports `parsedDbToPaint`/`paintToParsedDb` from there).

- [ ] **Step 2: Add the handler**

In `XlsxVerifyWizard.tsx`, inside the component (near `enterExcel`), add:

```tsx
  const handleSelectCounts = async () => {
    if (!gridCells) return
    setGridError(null)
    const res = await fetchCountCells(storeState)
    if (res.error) { setGridError(res.error); return }
    const nRows = gridCells.length
    const nCols = gridCells.reduce((m, row) => Math.max(m, row.length), 0)
    const { paint: next, dropped } = paintCountCells(paint, res.cells, nRows, nCols)
    setPaint(next)
    if (res.cells.length === 0) setGridError("No hay conteos para marcar.")
    else if (dropped > 0) setGridError(`${dropped} celdas de conteo quedaron fuera de la vista (hoja truncada a 200×120).`)
  }
```

(`storeState`, `paint`, `setPaint`, `gridCells`, `gridError`/`setGridError` already exist in the component. If `setGridError` is used for both red errors and this amber notice and you want distinct styling, that is optional polish — the spec accepts reusing `gridError`.)

- [ ] **Step 3: Add the button**

In the `mode === "excel" && gridCells` block, above the `<SheetGrid ... />`, add a button row:

```tsx
          <div className="flex justify-end mb-2">
            <button
              onClick={handleSelectCounts}
              className="px-3 py-1 text-sm rounded bg-neutral-700 text-neutral-200 hover:bg-neutral-600"
            >Seleccionar conteos</button>
          </div>
```

- [ ] **Step 4: Verify it type-checks**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit 0.

- [ ] **Step 5: Manual verification**

Run: `cd frontend && npm run dev` (backend already running).
1. Upload `BD Aurora ejemplo.xlsx`, reach the wizard, click **Editar en Excel**.
2. Click **Seleccionar conteos**. Every count cell (each option × each category, all breakdowns) turns grey (`counts` role).
3. Spot-check: the cell holding P1 "Sí" general count (458) is highlighted.
4. Use **Borrar** + drag to remove a wrong mark, or **Counts** + drag to add one — existing tools work on the marks.
5. **Guardar**; the result still extracts (counts_cols from min/max column) — no regression.
6. (If the sheet is large) a truncation notice appears when some count cells fall outside the 200×120 window.

Expected: all behave; no console errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Wizard/XlsxVerifyWizard.tsx
git commit -m "feat(wizard): Seleccionar conteos button highlights detected count cells"
```

---

## Self-Review

**Spec coverage:**
- §Backend endpoint `/api/count-cells` (reuse helpers, 1-based, dedup, fallback-safe) → Task 1. ✓
- §Frontend client `fetchCountCells` + `CountCellsResponse` → Task 2. ✓
- §Pure `paintCountCells` (1-based→0-based, window filter, merge `counts`) + test → Task 2. ✓
- §UI button + `handleSelectCounts` (fetch → paint → avisos) in `mode === "excel"` → Task 3. ✓
- §Edge cases: out-of-window drop notice (Task 3 Step 2), empty cells notice (Task 3 Step 2), endpoint error (Task 1 route + Task 3 handler), counts_cols missing → `{error, cells:[]}` (Task 1 route `cc[0]` inside try). ✓
- §Testing: backend known-cell + dedup + bad-state (Task 1); `paintCountCells` pure/window (Task 2). ✓
- §No extraction-model change: `paintToParsedDb` untouched; `counts` role reused (Task 3 manual Step 5 confirms save still works). ✓

**Placeholder scan:** none — every code/test/command step is concrete.

**Type consistency:** `paintCountCells(paint, coords, nRows, nCols) → {paint, dropped}` defined Task 2 Step 3, used Task 3 Step 2 with matching args. `fetchCountCells(state) → CountCellsResponse {cells:{row,col}[], error?}` defined Task 2 Step 5, used Task 3 Step 2. Backend returns `{cells:[{row,col}]}` (1-based) consumed by `paintCountCells` which converts. Consistent end-to-end.
```
