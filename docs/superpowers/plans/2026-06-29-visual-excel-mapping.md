# Visual Excel Mapping (Paint Mode) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a third wizard view that renders the raw Excel sheet as a grid and lets the user paint mapping roles onto cells (heuristic pre-paints), deterministically rebuilding `ParsedDB` on save.

**Architecture:** A new read-only `/api/sheet-grid` endpoint returns the raw cell values. A pure frontend module `sheetPaint.ts` converts between a per-cell paint map and `ParsedDB` (forward build + inverse pre-paint). A `SheetGrid` component does the paint UI; the wizard gains a 3-view switch. All views edit the same `parsed_db` (text-based) via the existing `setParsedDb`.

**Tech Stack:** Python (FastAPI, openpyxl, pytest, TestClient), React + TypeScript (Zustand, vitest).

## Global Constraints

- Backend tests run: `cd backend && arch -arm64 .venv/bin/python -m pytest <path> -v` (arm64 venv prefix required).
- Frontend tests run: `cd frontend && npx vitest run <path>`.
- If a command hits ENOSPC / `/private/tmp ... full`, prefix it with `export TMPDIR="$HOME/.cache/cc-tmp" && mkdir -p "$TMPDIR" &&`.
- `data_blocks` column ranges are **1-based** `[start, end]` (matches the existing `ParsedDB.data_blocks` convention).
- The `general` breakdown (`id="general"`) is implicit — never painted; the rebuild carries `prev`'s general breakdown through unchanged.
- Paint values stay TEXT-based: the rebuilt `ParsedDB` feeds the existing text/label extraction; no coordinate storage.
- Grid cap: 200 rows × 120 cols; beyond that the endpoint sets `truncated: true`.
- Work on a feature branch (the controller creates it); do NOT switch branches inside a task.

---

### Task 1: Backend `/api/sheet-grid` endpoint

**Files:**
- Modify: `backend/aurum_encuestas/api.py` (add request model + route)
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Produces: `POST /api/sheet-grid` body `{ "db_path": str | null }` → `{ n_rows, n_cols, cells: string[][], truncated: bool }` or `{ error, n_rows:0, n_cols:0, cells:[] }`.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_api.py`:

```python
def test_sheet_grid_endpoint(valid_xlsx_path):
    r = client.post("/api/sheet-grid", json={"db_path": str(valid_xlsx_path)})
    assert r.status_code == 200
    body = r.json()
    assert body["n_rows"] > 0 and body["n_cols"] > 0
    assert body["truncated"] is False
    # Row 1 col D (index [0][3]) is the "Rango de edad" breakdown header
    assert body["cells"][0][3] == "Rango de edad"
    # Row 18 col A (index [17][0]) is the question marker
    assert body["cells"][17][0] == "$p1.recordacion"


def test_sheet_grid_bad_path():
    r = client.post("/api/sheet-grid", json={"db_path": "/no/such/file.xlsx"})
    assert r.status_code == 200
    assert "error" in r.json()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_api.py::test_sheet_grid_endpoint tests/test_api.py::test_sheet_grid_bad_path -v`
Expected: FAIL (404 Not Found — route doesn't exist yet).

- [ ] **Step 3: Add the request model + route**

In `backend/aurum_encuestas/api.py`, add the model near the other `BaseModel`
request classes:

```python
class SheetGridRequest(BaseModel):
    db_path: str | None = None
```

And add the endpoint (place it next to the other `@app.post` routes):

```python
@app.post("/api/sheet-grid")
async def sheet_grid_endpoint(req: SheetGridRequest):
    """Return the raw cells of the first worksheet (read-only) for the visual
    mapping grid. Bounded to MAX_ROWS x MAX_COLS."""
    from openpyxl import load_workbook
    MAX_ROWS, MAX_COLS = 200, 120
    path = (req.db_path or "").strip()
    if not path:
        return {"error": "db_path requerido", "n_rows": 0, "n_cols": 0, "cells": []}
    try:
        wb = load_workbook(path, data_only=True)
    except Exception as e:  # noqa: BLE001 — surface any open error to the UI
        return {"error": f"No se pudo abrir: {e}", "n_rows": 0, "n_cols": 0, "cells": []}
    ws = wb.worksheets[0]
    full_rows, full_cols = ws.max_row or 0, ws.max_column or 0
    n_rows, n_cols = min(full_rows, MAX_ROWS), min(full_cols, MAX_COLS)
    truncated = full_rows > MAX_ROWS or full_cols > MAX_COLS
    cells = []
    for r in range(1, n_rows + 1):
        row = []
        for c in range(1, n_cols + 1):
            v = ws.cell(r, c).value
            row.append("" if v is None else str(v))
        cells.append(row)
    return {"n_rows": n_rows, "n_cols": n_cols, "cells": cells, "truncated": truncated}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_api.py -v`
Expected: PASS (new tests + existing api tests; the synth fixture is small so `truncated` is False).

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/api.py backend/tests/test_api.py
git commit -m "feat(api): /api/sheet-grid returns raw sheet cells for visual mapping"
```

---

### Task 2: `sheetPaint.ts` core — types, paint helpers, forward build

**Files:**
- Create: `frontend/src/pages/Wizard/sheetPaint.ts`
- Test: `frontend/src/pages/Wizard/sheetPaint.test.ts`

**Interfaces:**
- Produces: `Role`, `PaintMap`, `cellKey(r,c)`, `colLetter(c)`,
  `paintRect(map,r0,c0,r1,c1,role|null)`,
  `paintToParsedDb(cells, paint, prev) -> { db: ParsedDB, warnings: string[] }`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/pages/Wizard/sheetPaint.test.ts`:

```ts
import { it, expect } from "vitest"
import { cellKey, colLetter, paintRect, paintToParsedDb, type PaintMap } from "./sheetPaint"
import type { ParsedDB } from "../../types"

const prev: ParsedDB = {
  questions: [{ id: "q1", code: "P1", text: "$p1.rec", options: ["Sí", "No"], confidence: 1 }],
  breakdowns: [
    { id: "general", label: "General", categories: ["Total"] },
    { id: "sexo", label: "Sexo", categories: ["Hombre", "Mujer"] },
  ],
  sample_size: 500,
  data_blocks: { counts_cols: [3, 5], pct_row_cols: [7, 9], pct_col_cols: [11, 13] },
}

// cells grid (row-major, 0-based). Row0=sheet row1.
const cells: string[][] = [
  ["", "", "Sexo", "Sexo", "", "", "", "", ""],          // row0: breakdown header at cols 2,3
  ["General", "", "Hombre", "Mujer", "", "", "", "", ""], // row1: categories at cols 2,3
  ["$p1.rec", "Sí", "458", "230", "228", "x", "x", "x", "x"], // row2: question + option Sí
  ["", "No", "42", "20", "22", "x", "x", "x", "x"],       // row3: option No
]

it("colLetter + cellKey", () => {
  expect(colLetter(0)).toBe("A")
  expect(colLetter(26)).toBe("AA")
  expect(cellKey(2, 1)).toBe("2,1")
})

it("paintRect fills and clears a rectangle", () => {
  let m: PaintMap = {}
  m = paintRect(m, 2, 1, 3, 1, "option")
  expect(m["2,1"]).toBe("option")
  expect(m["3,1"]).toBe("option")
  m = paintRect(m, 2, 1, 2, 1, null)
  expect(m["2,1"]).toBeUndefined()
})

it("paintToParsedDb rebuilds questions, breakdowns, data blocks", () => {
  let p: PaintMap = {}
  p = paintRect(p, 2, 0, 2, 0, "question")     // $p1.rec
  p = paintRect(p, 2, 1, 3, 1, "option")        // Sí, No
  p = paintRect(p, 0, 2, 0, 3, "breakdown")     // Sexo header (cols 2,3 same label)
  p = paintRect(p, 1, 2, 1, 3, "category")      // Hombre, Mujer
  p = paintRect(p, 2, 2, 2, 4, "counts")        // counts cols 2..4 -> [3,5]
  const { db, warnings } = paintToParsedDb(cells, p, prev)
  expect(warnings).toEqual([])
  expect(db.questions).toHaveLength(1)
  expect(db.questions[0].options).toEqual(["Sí", "No"])
  // general carried through + the painted Sexo breakdown
  expect(db.breakdowns.map((b) => b.id)).toEqual(["general", "sexo"])
  expect(db.breakdowns[1].categories).toEqual(["Hombre", "Mujer"])
  expect(db.data_blocks.counts_cols).toEqual([3, 5])
  // untouched blocks keep prev
  expect(db.data_blocks.pct_row_cols).toEqual([7, 9])
})

it("category with no breakdown to its left is dropped with a warning", () => {
  let p: PaintMap = {}
  p = paintRect(p, 1, 0, 1, 0, "category")  // col 0, no header to the left
  const { warnings } = paintToParsedDb(cells, p, prev)
  expect(warnings.some((w) => w.includes("sin breakdown"))).toBe(true)
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/pages/Wizard/sheetPaint.test.ts`
Expected: FAIL (module `./sheetPaint` not found).

- [ ] **Step 3: Implement `sheetPaint.ts` (core)**

Create `frontend/src/pages/Wizard/sheetPaint.ts`:

```ts
import type { ParsedDB, Question, Breakdown } from "../../types"

export type Role =
  | "question" | "option" | "breakdown" | "category"
  | "counts" | "pctRow" | "pctCol"
export type PaintMap = Record<string, Role>   // key "r,c" (0-based) -> Role

export const cellKey = (r: number, c: number) => `${r},${c}`

export function colLetter(c: number): string {
  let s = ""
  let n = c
  do { s = String.fromCharCode(65 + (n % 26)) + s; n = Math.floor(n / 26) - 1 } while (n >= 0)
  return s
}

export function paintRect(
  map: PaintMap, r0: number, c0: number, r1: number, c1: number, role: Role | null,
): PaintMap {
  const next = { ...map }
  const [ra, rb] = r0 <= r1 ? [r0, r1] : [r1, r0]
  const [ca, cb] = c0 <= c1 ? [c0, c1] : [c1, c0]
  for (let r = ra; r <= rb; r++) {
    for (let c = ca; c <= cb; c++) {
      const k = cellKey(r, c)
      if (role === null) delete next[k]
      else next[k] = role
    }
  }
  return next
}

const slug = (s: string) => s.trim().toLowerCase()

type Cell = { r: number; c: number; role: Role }

export function paintToParsedDb(
  cells: string[][], paint: PaintMap, prev: ParsedDB,
): { db: ParsedDB; warnings: string[] } {
  const warnings: string[] = []
  const text = (r: number, c: number) => (cells[r]?.[c] ?? "").trim()
  const entries: Cell[] = Object.entries(paint).map(([k, role]) => {
    const [r, c] = k.split(",").map(Number)
    return { r, c, role }
  })

  // --- Questions ---
  const anchors = entries.filter((e) => e.role === "question").sort((a, b) => a.r - b.r || a.c - b.c)
  const options = entries.filter((e) => e.role === "option")
  const prevQByText = new Map(prev.questions.map((q) => [q.text, q]))
  const questions: Question[] = []
  anchors.forEach((anchor, i) => {
    const nextRow = i + 1 < anchors.length ? anchors[i + 1].r : Infinity
    const opts = options
      .filter((o) => o.r > anchor.r && o.r < nextRow)
      .sort((a, b) => a.r - b.r || a.c - b.c)
      .map((o) => text(o.r, o.c))
      .filter((t) => t.length > 0)
    const qtext = text(anchor.r, anchor.c)
    if (opts.length === 0) { warnings.push(`Pregunta "${qtext}" sin opciones — descartada`); return }
    const prevQ = prevQByText.get(qtext)
    questions.push({
      id: prevQ?.id ?? `q${i + 1}`,
      code: prevQ?.code ?? `P${i + 1}`,
      text: qtext, options: opts, confidence: 1,
    })
  })

  // --- Breakdowns (carry prev general first) ---
  const headers = entries.filter((e) => e.role === "breakdown").sort((a, b) => a.c - b.c)
  const catCells = entries.filter((e) => e.role === "category")
  const ownerOf = (cat: Cell): Cell | undefined =>
    headers.filter((h) => h.c <= cat.c).sort((a, b) => b.c - a.c)[0]
  const prevBdByLabel = new Map(prev.breakdowns.map((b) => [b.label, b]))
  const general = prev.breakdowns.find((b) => b.id === "general")
  const breakdowns: Breakdown[] = general ? [general] : []
  // dedupe header instances by label (a header label can span >1 painted cell)
  const seenLabels = new Set<string>()
  headers.forEach((h) => {
    const label = text(h.r, h.c)
    if (!label || seenLabels.has(label)) return
    seenLabels.add(label)
    const cats = catCells
      .filter((cat) => { const o = ownerOf(cat); return o && text(o.r, o.c) === label })
      .sort((a, b) => a.c - b.c)
      .map((cat) => text(cat.r, cat.c))
      .filter((t) => t.length > 0)
    const prevBd = prevBdByLabel.get(label)
    breakdowns.push({ id: prevBd?.id ?? slug(label), label, categories: cats })
  })
  catCells.forEach((cat) => {
    if (!ownerOf(cat)) warnings.push(`Categoría "${text(cat.r, cat.c)}" sin breakdown a la izquierda — descartada`)
  })

  // --- Data blocks ---
  const colRange = (role: Role, fallback: number[]): number[] => {
    const cols = entries.filter((e) => e.role === role).map((e) => e.c)
    return cols.length === 0 ? fallback : [Math.min(...cols) + 1, Math.max(...cols) + 1]
  }
  const data_blocks = {
    counts_cols: colRange("counts", prev.data_blocks.counts_cols),
    pct_row_cols: colRange("pctRow", prev.data_blocks.pct_row_cols),
    pct_col_cols: colRange("pctCol", prev.data_blocks.pct_col_cols),
  }

  return { db: { ...prev, questions, breakdowns, data_blocks, sample_size: prev.sample_size }, warnings }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/pages/Wizard/sheetPaint.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Wizard/sheetPaint.ts frontend/src/pages/Wizard/sheetPaint.test.ts
git commit -m "feat(wizard): sheetPaint core — paint map + ParsedDB rebuild"
```

---

### Task 3: `parsedDbToPaint` inverse + round-trip

**Files:**
- Modify: `frontend/src/pages/Wizard/sheetPaint.ts` (append `parsedDbToPaint`)
- Modify: `frontend/src/pages/Wizard/sheetPaint.test.ts` (round-trip test)

**Interfaces:**
- Consumes: `paintToParsedDb`, `cellKey` (Task 2).
- Produces: `parsedDbToPaint(cells, db) -> PaintMap`.

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/pages/Wizard/sheetPaint.test.ts`:

```ts
import { parsedDbToPaint } from "./sheetPaint"

it("parsedDbToPaint round-trips through paintToParsedDb", () => {
  const paint = parsedDbToPaint(cells, prev)
  const { db, warnings } = paintToParsedDb(cells, paint, prev)
  expect(warnings).toEqual([])
  expect(db.questions[0].options).toEqual(["Sí", "No"])
  expect(db.breakdowns.map((b) => b.id)).toEqual(["general", "sexo"])
  expect(db.breakdowns[1].categories).toEqual(["Hombre", "Mujer"])
  expect(db.data_blocks.counts_cols).toEqual([3, 5])
  expect(db.data_blocks.pct_row_cols).toEqual([7, 9])
  expect(db.data_blocks.pct_col_cols).toEqual([11, 13])
})
```

(The `cells` grid in Task 2 already has the `pct_row`/`pct_col` columns 6–8 and
10–12 present as `"x"` placeholders, so the indicator row can paint them.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/Wizard/sheetPaint.test.ts`
Expected: FAIL (`parsedDbToPaint` is not exported).

- [ ] **Step 3: Implement `parsedDbToPaint`**

Append to `frontend/src/pages/Wizard/sheetPaint.ts`:

```ts
export function parsedDbToPaint(cells: string[][], db: ParsedDB): PaintMap {
  const paint: PaintMap = {}
  const norm = (s: string | undefined) => (s ?? "").trim()
  const COL_A = 0, COL_B = 1, HEADER_ROW = 0, CAT_ROW = 1

  db.questions.forEach((q) => {
    let anchorRow = -1
    for (let r = 0; r < cells.length; r++) {
      const a = norm(cells[r]?.[COL_A])
      if (a && (a === q.text || a.startsWith(q.text + ".") || q.text.startsWith(a + "."))) {
        anchorRow = r; break
      }
    }
    if (anchorRow < 0) return
    paint[cellKey(anchorRow, COL_A)] = "question"
    q.options.forEach((opt) => {
      for (let r = anchorRow; r < cells.length; r++) {
        if (norm(cells[r]?.[COL_B]) === opt) { paint[cellKey(r, COL_B)] = "option"; break }
      }
    })
  })

  db.breakdowns.filter((b) => b.id !== "general").forEach((b) => {
    const hrow = cells[HEADER_ROW] ?? []
    for (let c = 0; c < hrow.length; c++) {
      if (norm(hrow[c]) === b.label) { paint[cellKey(HEADER_ROW, c)] = "breakdown"; break }
    }
    const crow = cells[CAT_ROW] ?? []
    b.categories.forEach((cat) => {
      for (let c = 0; c < crow.length; c++) {
        if (norm(crow[c]) === cat) { paint[cellKey(CAT_ROW, c)] = "category"; break }
      }
    })
  })

  // Data blocks: paint an indicator row (first data row that exists) across each
  // column range. Block columns are >= col C, so they never collide with the
  // question/option cells in cols A/B.
  const markerRow = Math.min(2, Math.max(0, cells.length - 1))
  const paintCols = (range: number[] | undefined, role: Role) => {
    if (!range || range.length < 2) return
    for (let c = range[0] - 1; c <= range[1] - 1; c++) paint[cellKey(markerRow, c)] = role
  }
  paintCols(db.data_blocks.counts_cols, "counts")
  paintCols(db.data_blocks.pct_row_cols, "pctRow")
  paintCols(db.data_blocks.pct_col_cols, "pctCol")

  return paint
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/pages/Wizard/sheetPaint.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Wizard/sheetPaint.ts frontend/src/pages/Wizard/sheetPaint.test.ts
git commit -m "feat(wizard): parsedDbToPaint inverse + round-trip test"
```

---

### Task 4: `fetchSheetGrid` client + `SheetGrid` component

**Files:**
- Modify: `frontend/src/api/client.ts` (add `fetchSheetGrid` + `SheetGrid` type)
- Create: `frontend/src/pages/Wizard/SheetGrid.tsx`

**Interfaces:**
- Consumes: `sheetPaint` types/helpers (`Role`, `PaintMap`, `paintRect`, `cellKey`, `colLetter`).
- Produces: `fetchSheetGrid(db_path) -> Promise<SheetGridResponse>`; default-exported
  `SheetGrid({ cells, paint, onChange })` React component.

This task's logic (paint math) is already unit-tested in `sheetPaint`. The drag
interaction is verified by typecheck + manual check; no component test harness
for pointer drag exists.

- [ ] **Step 1: Add the API client function**

In `frontend/src/api/client.ts` add:

```ts
export interface SheetGridResponse {
  n_rows: number
  n_cols: number
  cells: string[][]
  truncated?: boolean
  error?: string
}

export async function fetchSheetGrid(db_path: string): Promise<SheetGridResponse> {
  return request("/sheet-grid", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ db_path }),
  })
}
```

- [ ] **Step 2: Create the `SheetGrid` component**

Create `frontend/src/pages/Wizard/SheetGrid.tsx`:

```tsx
import { useState } from "react"
import { paintRect, cellKey, colLetter, type PaintMap, type Role } from "./sheetPaint"

const ROLES: { role: Role; label: string; color: string }[] = [
  { role: "question", label: "Pregunta", color: "#2e7d32" },
  { role: "option", label: "Opciones", color: "#1565c0" },
  { role: "breakdown", label: "Breakdown", color: "#e07b00" },
  { role: "category", label: "Categoría", color: "#7b3fb5" },
  { role: "counts", label: "Counts", color: "#616161" },
  { role: "pctRow", label: "%Row", color: "#00838f" },
  { role: "pctCol", label: "%Col", color: "#5d4037" },
]
const COLOR: Record<Role, string> = Object.fromEntries(ROLES.map((r) => [r.role, r.color])) as Record<Role, string>

interface Props {
  cells: string[][]
  paint: PaintMap
  onChange(p: PaintMap): void
}

export default function SheetGrid({ cells, paint, onChange }: Props) {
  const [active, setActive] = useState<Role | null>("question")
  const [erase, setErase] = useState(false)
  const [anchor, setAnchor] = useState<{ r: number; c: number } | null>(null)
  const nCols = cells.reduce((m, row) => Math.max(m, row.length), 0)

  const apply = (r0: number, c0: number, r1: number, c1: number) => {
    const role = erase ? null : active
    if (role === undefined) return
    onChange(paintRect(paint, r0, c0, r1, c1, role))
  }

  return (
    <div className="text-xs">
      <div className="flex flex-wrap gap-1.5 mb-2">
        {ROLES.map((r) => (
          <button
            key={r.role}
            onClick={() => { setActive(r.role); setErase(false) }}
            className="px-2 py-1 rounded border"
            style={{
              background: active === r.role && !erase ? r.color : "transparent",
              color: active === r.role && !erase ? "#fff" : r.color,
              borderColor: r.color,
            }}
          >
            {r.label}
          </button>
        ))}
        <button
          onClick={() => setErase((v) => !v)}
          className="px-2 py-1 rounded border"
          style={{ background: erase ? "#b00020" : "transparent", color: erase ? "#fff" : "#b00020", borderColor: "#b00020" }}
        >
          Borrar
        </button>
      </div>

      <div className="overflow-auto max-h-[60vh] border border-neutral-700 rounded" onMouseLeave={() => setAnchor(null)}>
        <table className="border-collapse select-none" style={{ fontFamily: "ui-monospace, monospace" }}>
          <thead>
            <tr>
              <th className="bg-neutral-800 text-neutral-500 px-1 sticky left-0" />
              {Array.from({ length: nCols }, (_, c) => (
                <th key={c} className="bg-neutral-800 text-neutral-400 px-2 py-0.5 border border-neutral-700">{colLetter(c)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cells.map((row, r) => (
              <tr key={r}>
                <th className="bg-neutral-800 text-neutral-500 px-1 border border-neutral-700 sticky left-0">{r + 1}</th>
                {Array.from({ length: nCols }, (_, c) => {
                  const role = paint[cellKey(r, c)]
                  return (
                    <td
                      key={c}
                      onMouseDown={() => setAnchor({ r, c })}
                      onMouseEnter={() => { if (anchor) { /* live preview not required */ } }}
                      onMouseUp={() => { if (anchor) { apply(anchor.r, anchor.c, r, c); setAnchor(null) } }}
                      className="px-2 py-0.5 border border-neutral-700 whitespace-nowrap cursor-cell"
                      style={{ background: role ? COLOR[role] : undefined, color: role ? "#fff" : "#d4d4d4", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis" }}
                      title={row[c] ?? ""}
                    >
                      {row[c] ?? ""}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-neutral-500 mt-1">Elegí un rol y arrastrá sobre las celdas para asignarlo. “Borrar” limpia el rol.</p>
    </div>
  )
}
```

- [ ] **Step 3: Verify it type-checks**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit 0 (zero errors).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/pages/Wizard/SheetGrid.tsx
git commit -m "feat(wizard): fetchSheetGrid client + SheetGrid paint component"
```

---

### Task 5: Wizard 3-view integration

**Files:**
- Modify: `frontend/src/pages/Wizard/XlsxVerifyWizard.tsx`

**Interfaces:**
- Consumes: `fetchSheetGrid` (Task 4), `SheetGrid` (Task 4), `paintToParsedDb`/`parsedDbToPaint` (Tasks 2-3), `useProjectStore().setParsedDb`.

This is UI wiring; verify with typecheck + manual browser check (no component test harness).

- [ ] **Step 1: Add view state + grid loading**

In `XlsxVerifyWizard.tsx`, add imports and state:

```tsx
import SheetGrid from "./SheetGrid"
import { paintToParsedDb, parsedDbToPaint, type PaintMap } from "./sheetPaint"
import { fetchSheetGrid } from "../../api/client"
```

```tsx
const setParsedDb = useProjectStore((s) => s.setParsedDb)
const dbPath = useProjectStore((s) => s.state?.inputs.db_path) ?? ""
const [mode, setMode] = useState<"list" | "fields" | "excel">("list")
const [gridCells, setGridCells] = useState<string[][] | null>(null)
const [paint, setPaint] = useState<PaintMap>({})
const [gridError, setGridError] = useState<string | null>(null)
```

(If Task: the field-editor `editing`/`draft` state from the earlier manual-mapping
feature already exists — keep it; `mode === "fields"` replaces the old `editing`
boolean. Map the existing field-editor UI under `mode === "fields"`.)

- [ ] **Step 2: Enter Excel mode — fetch grid + seed paint**

Add a handler:

```tsx
const enterExcel = async () => {
  setGridError(null)
  const res = await fetchSheetGrid(dbPath)
  if (res.error || !res.cells?.length) { setGridError(res.error ?? "No se pudieron leer las celdas"); return }
  setGridCells(res.cells)
  setPaint(parsedDbToPaint(res.cells, parsedDb!))
  setMode("excel")
}
```

- [ ] **Step 3: Render the mode switch + Excel view**

Add a 3-button switch near the top (only when not mid-edit), e.g.:

```tsx
<div className="flex gap-2 mb-4">
  <button onClick={() => setMode("list")} className={mode === "list" ? "font-semibold" : "text-neutral-400"}>Lista</button>
  <button onClick={() => setMode("fields")} className={mode === "fields" ? "font-semibold" : "text-neutral-400"}>Editar campos</button>
  <button onClick={enterExcel} className={mode === "excel" ? "font-semibold" : "text-neutral-400"}>Editar en Excel</button>
</div>
```

When `mode === "excel"` and `gridCells`, render the grid + footer:

```tsx
{mode === "excel" && gridCells && (
  <div>
    <SheetGrid cells={gridCells} paint={paint} onChange={setPaint} />
    <div className="flex justify-end gap-2 mt-3">
      <button onClick={() => setMode("list")} className="px-4 py-2 text-sm rounded bg-neutral-700">Cancelar</button>
      <button
        onClick={() => {
          const { db, warnings } = paintToParsedDb(gridCells, paint, parsedDb!)
          if (warnings.length && !confirm(`Avisos:\n${warnings.join("\n")}\n\n¿Guardar igual?`)) return
          setParsedDb(db)
          setMode("list")
        }}
        className="px-4 py-2 text-sm rounded bg-accent text-neutral-900 font-semibold"
      >Guardar</button>
    </div>
  </div>
)}
{gridError && <p className="text-xs text-red-400 mt-2">{gridError}</p>}
```

Render the existing Lista sections only when `mode === "list"`, and the existing
field-editor only when `mode === "fields"`. Keep the original `Confirmar` button
available in `list` mode.

- [ ] **Step 4: Verify it type-checks**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit 0.

- [ ] **Step 5: Manual verification**

Run: `cd frontend && npm run dev` (backend already running).
1. Upload `BD Aurora ejemplo.xlsx`, reach the wizard.
2. Click **Editar en Excel** → grid loads, heuristic roles pre-painted (colored cells).
3. Pick a role (e.g. Categoría), drag over a couple cells → they tint.
4. Click **Guardar** → returns to Lista; the edited mapping is reflected (e.g. a removed/added category).
5. Re-enter, edit, click **Cancelar** → no change persisted.
6. Generate a preview → mapping honored.

Expected: all six behave; no console errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Wizard/XlsxVerifyWizard.tsx
git commit -m "feat(wizard): 3-view switch with visual Excel paint mapping"
```

---

## Self-Review

**Spec coverage:**
- §1 raw-cells endpoint → Task 1. ✓
- §2 grid + paint toolbar (`SheetGrid`, `sheetPaint` types/paintRect/colLetter) → Tasks 2, 4. ✓
- §3 paint→ParsedDB build (spatial rules, general carried, data-block min/max col, warnings) → Task 2. ✓
- §4 ParsedDB→initial paint (inverse) → Task 3. ✓
- §5 wizard 3-view integration (fetch, seed, Guardar/Cancelar, warnings) → Task 5. ✓
- Edge cases (unpainted ignored, category w/o breakdown warning, empty data block keeps prev, general never painted) → Task 2 build + tests. ✓
- Testing (sheetPaint unit incl. round-trip; endpoint tests; manual grid) → Tasks 1-3 automated, 4-5 manual. ✓

**Type consistency:** `Role`, `PaintMap`, `cellKey`, `colLetter`, `paintRect`,
`paintToParsedDb`, `parsedDbToPaint` are defined in Task 2/3 and consumed with the
same names/signatures in Tasks 4-5. `SheetGridResponse`/`fetchSheetGrid` defined in
Task 4 and used in Task 5. Endpoint shape (`cells`, `truncated`) matches between
Task 1 and Task 4's type.

**Placeholder scan:** no TBD/TODO; all code blocks concrete. Tasks 4-5 are explicitly
UI tasks gated on `tsc --noEmit` + manual verification (no pointer-drag test harness),
called out rather than left vague.
