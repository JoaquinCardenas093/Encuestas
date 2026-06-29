# Visual Excel Mapping (Paint Mode) — Design

Date: 2026-06-29
Status: Approved

## Problem

The manual mapping editor (shipped 2026-06-27) lets the user correct the
heuristic-detected mapping by typing into form fields (question text, options,
breakdown labels/categories, data-block column ranges, sample size). Typing
column indices and matching text is unintuitive and error-prone — the user
cannot see WHERE in the sheet each value lives.

The user wants to select directly in the Excel: render the sheet as a grid and
assign mapping roles to cells visually.

## Goal

Add a third wizard view — "Editar en Excel" — that renders the raw sheet as a
grid and lets the user **paint** roles onto cells (paint mode). The heuristic
pre-paints the grid; the user repaints only what is wrong. On save, the painted
regions are deterministically rebuilt into a `ParsedDB` and stored via the
existing `setParsedDb`, reusing all current extraction.

## Decisions (from brainstorming)

- **Intent:** correct the heuristic (it pre-paints; user fixes), not map from scratch.
- **Output:** the SAME `ParsedDB` (text/label based) — no explicit coordinate
  storage, no change to the coordinate→value extraction path.
- **Interaction:** paint mode — pick a role from a toolbar, then click/drag cells.

## Non-goals

- No coordinate-based extraction (values still read by text/label at preview).
- No editing of cell VALUES/percentages — the grid is read-only data; only role
  assignment is editable.
- No "map from scratch / clear all" button (intent is correction).
- The `general` breakdown is implicit (the block's Total column) and is never painted.

## Architecture

### 1. Backend — raw-cells endpoint

`backend/aurum_encuestas/api.py`

- New `POST /api/sheet-grid` with body `{ "db_path": str }` (falls back to the
  project's `inputs.db_path` if omitted/empty).
- Loads the workbook (`openpyxl`, `data_only=True`), reads worksheet 0, and
  returns the used range bounded to `ws.max_row` × `ws.max_column`:
  ```json
  { "n_rows": 80, "n_cols": 55, "cells": [["", "Sexo", ...], ...] }
  ```
  `cells[r][c]` is the cell's value rendered as a string (`""` for empty). Row 0
  = sheet row 1. Read-only; the parser is untouched.
- Guard: if the file can't be opened, return `{ "error": "<msg>" }` with 200 so
  the frontend shows a message rather than crashing.
- A hard cap (e.g. 200 rows × 120 cols) prevents pathological sheets from
  ballooning the payload; rows/cols beyond the cap are dropped and a
  `"truncated": true` flag is set.

### 2. Frontend — grid + paint toolbar

New component `frontend/src/pages/Wizard/SheetGrid.tsx`:

- Props: `cells: string[][]`, `initialPaint: PaintMap`, `onChange(paint: PaintMap)`.
- Renders an HTML table: column headers `A, B, C…` (spreadsheet letters), row
  headers `1, 2, 3…`, and each cell showing its string value.
- A role toolbar (the paint palette): `Pregunta`, `Opciones`, `Breakdown`,
  `Categoría`, `Counts`, `%Row`, `%Col`, `Borrar`. Clicking a chip sets the
  active role.
- Painting: `mousedown` on a cell starts a drag; `mouseenter` while pressed
  extends a rectangular selection; `mouseup` commits — every cell in the
  rectangle gets the active role (or is cleared, for `Borrar`). Each cell is
  tinted with the role color.
- `PaintMap` = `Record<string, Role>` keyed by `"r,c"` (0-based). The component
  is controlled: it calls `onChange` with the updated map.

A small pure module `frontend/src/pages/Wizard/sheetPaint.ts` holds the shared
types and helpers (no React):

```ts
export type Role = "question" | "option" | "breakdown" | "category"
  | "counts" | "pctRow" | "pctCol"
export type PaintMap = Record<string, Role>          // "r,c" -> Role
export const cellKey = (r: number, c: number) => `${r},${c}`
export function paintRect(map: PaintMap, r0, c0, r1, c1, role: Role | null): PaintMap
export function colLetter(c: number): string          // 0 -> "A", 26 -> "AA"
```

### 3. Paint → ParsedDB (deterministic build)

`frontend/src/pages/Wizard/sheetPaint.ts` also holds:

```ts
export function paintToParsedDb(
  cells: string[][],
  paint: PaintMap,
  prev: ParsedDB,          // for sample_size + stable ids fallback
): { db: ParsedDB; warnings: string[] }
```

Rules (spatial association):

- **Questions:** each cell painted `question` is a question anchor; its text =
  cell value. Cells painted `option` in rows BELOW the anchor (same/any column,
  but conventionally col B) and ABOVE the next `question` anchor become that
  question's options, in row order. Question `code` reuses the prev question's
  code when text matches, else `P<n>` by anchor order.
- **Breakdowns:** each cell painted `breakdown` is a header; its text = label.
  Cells painted `category` are assigned to the nearest `breakdown` header to
  their LEFT in the same-or-upper row band (row 1 header → row 2 categories);
  categories ordered left→right. A `category` with no breakdown to its left is
  dropped with a warning.
- **Data blocks:** for each of `counts`/`pctRow`/`pctCol`, take the min and max
  COLUMN among painted cells of that role → `[minCol+1, maxCol+1]` (1-based to
  match the existing `data_blocks` convention). A role with no painted cells
  keeps `prev.data_blocks` value.
- **sample_size:** carried from `prev` (not painted).
- Returns a fresh `ParsedDB`; `warnings` lists dropped categories / empty
  questions for inline display.

### 4. Inverse: ParsedDB → initial paint

`frontend/src/pages/Wizard/sheetPaint.ts`:

```ts
export function parsedDbToPaint(cells: string[][], db: ParsedDB): PaintMap
```

Pre-paints the grid so the user sees the heuristic result: find each question
anchor cell (col A whose text == question.text or marker prefix), its option
cells (col B == option text in the rows below), each breakdown header cell (row
1 == label), category cells (row 2 == category text within the block), and the
`data_blocks` column ranges (paint the header/row-2 band of those columns as
counts/pctRow/pctCol). Best-effort: cells it can't locate are simply left
unpainted (the user repaints them).

### 5. Wizard integration

`frontend/src/pages/Wizard/XlsxVerifyWizard.tsx`:

- A view switch with three modes: **Lista** (current read-only), **Editar
  campos** (the existing form editor), **Editar en Excel** (the grid).
- Entering "Editar en Excel": fetch `/api/sheet-grid` once, compute
  `parsedDbToPaint(cells, parsedDb)` as the initial paint, hold `paint` +
  `cells` in state. Edits update `paint` locally (draft).
- **Guardar**: `const {db, warnings} = paintToParsedDb(cells, paint, parsedDb)`;
  show warnings (if any) inline; on confirm call `setParsedDb(db)` and return to
  Lista. **Cancelar**: discard `paint`, return to Lista.
- All three views edit the same `parsed_db` and never write the store before
  Guardar.

## Edge cases

- **Unpainted cell** → ignored by the build.
- **Category with no breakdown to its left** → dropped, warning surfaced.
- **Question anchor with no options below** → question dropped, warning.
- **Sheet larger than the cap** → grid shows the capped window + a "truncated"
  notice; mapping beyond the window isn't possible (acceptable — real sheets fit).
- **`general`** → never painted; extraction's general short-circuit still applies.
- **Empty paint for a data block** → keeps the previous `data_blocks` value
  (so opening + saving without touching blocks is a no-op for them).

## Testing

- Frontend unit (`sheetPaint.test.ts`, vitest): `paintRect` rectangle fill +
  clear; `colLetter`; `paintToParsedDb` for a representative painted sheet
  (questions+options, two breakdowns with categories, three data blocks) →
  expected `ParsedDB`; category-without-breakdown warning; `parsedDbToPaint`
  round-trips a known `ParsedDB` to a paint map that `paintToParsedDb` rebuilds
  to the same `ParsedDB`.
- Backend (`test_api.py`): `/api/sheet-grid` returns correct `n_rows/n_cols` and
  cell values for the synth fixture; truncation flag when over the cap; error
  payload on a bad path.
- `SheetGrid.tsx` interaction (drag-paint) is verified manually (no component
  test harness for pointer drag); the logic it delegates to (`sheetPaint`) is
  fully unit-tested.

## Affected files

- `backend/aurum_encuestas/api.py` (new `/api/sheet-grid` endpoint)
- `backend/tests/test_api.py` (endpoint tests)
- `frontend/src/pages/Wizard/sheetPaint.ts` (types + pure build/inverse helpers) — new
- `frontend/src/pages/Wizard/sheetPaint.test.ts` — new
- `frontend/src/pages/Wizard/SheetGrid.tsx` (grid + paint UI) — new
- `frontend/src/pages/Wizard/XlsxVerifyWizard.tsx` (3-view switch + grid wiring)
- `frontend/src/api/client.ts` (`fetchSheetGrid`)
