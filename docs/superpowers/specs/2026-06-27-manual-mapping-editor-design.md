# Manual Mapping Editor — Design

Date: 2026-06-27
Status: Approved (approach A)

## Problem

The XLSX verify wizard (`frontend/src/pages/Wizard/XlsxVerifyWizard.tsx`) shows what
the heuristic parser detected (questions, breakdowns, data blocks, sample size) but
offers no way to correct mistakes. The "Editar mapping manual (próximamente)" button
is permanently disabled.

Two hard limits exist in the parser/extractor today:

1. **Breakdown detection is hardcoded.** `xlsx_parser._detect_breakdowns` only keeps
   headers whose slug is in `BREAKDOWN_ID_MAP` (edad/sexo/nse/punto). Any other
   breakdown header in row 1 is silently dropped.
2. **Breakdown→column resolution is hardcoded.** `data_extractor._resolve_breakdown_cols`
   uses a fixed `target_label_map = {"edad": "Rango de edad", "sexo": "Sexo",
   "nse": "NSE", "punto": "Punto"}`. Unknown `breakdown_id` → returns `{}` → all
   values extract as 0.

Result: surveys with breakdowns outside those four can't be charted, and the user
has no way to fix any misdetection.

## Goal

Let the user correct the detected mapping (questions, breakdowns, data blocks,
sample size) directly in the wizard, and generalize the backend so any breakdown
header works without code changes.

Approach: **A — Frontend-state editor + label-based backend resolution.** Edits
mutate `state.parsed_db` in the Zustand store; extraction at preview/render time
already reads `parsed_db`, so no new backend endpoint is needed.

## Non-goals

- No live re-parse / validation round-trip to the backend (that was approach B).
- No explicit per-breakdown column-range picker (approach C).
- No editing of the raw XLSX file. The editor only edits the detected mapping.

## Architecture

### 1. Backend — parser generalization

`backend/aurum_encuestas/xlsx_parser.py::_detect_breakdowns`

- Remove the `if slug_key in BREAKDOWN_ID_MAP` filter. Detect **every** non-empty,
  distinct header in row 1 within block 1 (cols `general_col+1 .. block1_max`).
- For each header: `Breakdown(id=_slug(label), label=header_text,
  categories=[row2 sub-headers in the block, excluding "General"])`.
- Keep `BREAKDOWN_ID_MAP` only as an **optional alias**: when a header's slug maps
  to a canonical id (sexo/edad/nse/punto), use that canonical id so existing
  patterns/colors keyed on those ids keep working. Otherwise use `_slug(label)`.
- A breakdown with zero detected categories is skipped (unchanged).

### 2. Backend — resolver generalization

`backend/aurum_encuestas/data_extractor.py::_resolve_breakdown_cols`

- Remove the hardcoded `target_label_map`.
- Resolve generically: scan row 1 headers at/after `block_start_col`; pick the
  header block whose canonical key matches the requested `breakdown_id`. Match rule:
  `breakdown_id == _slug(header)` OR `BREAKDOWN_ID_MAP.get(_slug(header)) == breakdown_id`
  (so a canonical id still resolves a variant header).
- `general` branch unchanged (`{"Total": block_start_col}`).
- Return `{category_label: column}` for row 2 cells in `[start, end)` (unchanged
  block-walking logic).
- `_slug` must be shared/consistent between parser and extractor (import the parser's
  `_slug`, or move it to a shared helper).

### 3. Backend — category consistency for charts

`backend/aurum_encuestas/data_extractor.py::extract_chart_data`

- After resolving `{category: col}`, when the caller supplies the breakdown's
  declared categories, **filter and order** the resolved categories to that list
  (intersection by exact text). Categories the user removed in the editor are
  excluded; reordering is honored.
- Mechanism: `extract_chart_data` gains an optional `allowed_categories: list[str] |
  None = None` param. Callers that have the `Breakdown` object
  (`pattern_classifier.build_slide_config`, `pptx_generator`) pass
  `breakdown.categories`. When `None`, behavior is unchanged (all resolved cats).
- This makes category edits affect charts the same way they already affect tables
  (`extract_all_breakdowns_data` already filters by `bd.categories`).

### 4. Frontend — editor UI

`frontend/src/pages/Wizard/XlsxVerifyWizard.tsx`

- Add `editing` boolean state. The "Editar mapping manual" button is enabled and
  toggles `editing`. A local `draft` copy of `parsedDb` holds in-progress edits.
- In `editing` mode the read-only sections become editable:
  - **Preguntas**: per question — text `<input>`, options list with add/remove/rename
    (text inputs + "＋ opción" + trash per option), trash to delete the question.
  - **Breakdowns**: per breakdown — label `<input>`, category chips with
    add/remove/rename, trash to delete the breakdown. (`general` is not editable.)
  - **Data blocks**: three comma-separated numeric inputs — Counts / %Row / %Col.
    Parsed to `number[]`; invalid entries ignored.
  - **Sample size**: numeric `<input>`.
- Footer in edit mode: **Guardar** (commit `draft` → `state.parsed_db` via store) and
  **Cancelar** (discard `draft`, exit edit mode). Outside edit mode: existing
  **Confirmar** + the now-enabled **Editar** button.
- Editing mutates a draft, not the store, until Guardar — so Cancelar is clean.

### 5. Persistence & data flow

- No new backend endpoint. Guardar writes the edited `ParsedDB` into
  `state.parsed_db` in the Zustand store (same object the rest of the app reads).
- At preview/export, `pattern_classifier.build_slide_config` and `pptx_generator`
  re-extract from the XLSX using the (possibly edited) `parsed_db` — breakdown labels
  locate columns, declared categories filter them, question option texts match rows
  (via the existing `_find_question_rows` prefix + option-text fallback), and
  `data_blocks` drive the column offsets.

## Edge cases

- **Edited label/option not in the sheet** → its column/row won't resolve → that
  breakdown/option extracts empty. Acceptable; surface a lightweight inline note in
  edit mode ("Si el texto no coincide con la hoja, queda sin datos"). No live
  validation call.
- **Renaming a category** to text not present in row 2 → dropped by the intersection
  filter. Primary supported category edits are remove/reorder.
- **Deleting a question/breakdown** removes it from `parsed_db`; charts that
  reference a deleted id simply have no data (existing empty-data handling applies).
- **Invalid data-block input** (non-numeric) → ignored; keep previous value.
- **`general` breakdown** is never editable/deletable.

## Testing

- Backend unit: `_detect_breakdowns` returns a non-hardcoded header as a breakdown;
  `_resolve_breakdown_cols` resolves a generic slug to the right column block;
  `extract_chart_data` honors `allowed_categories` (removal + reorder).
- Backend regression: the four canonical breakdowns (sexo/edad/nse/punto) still
  resolve and extract identically against `BD Aurora ejemplo.xlsx`.
- Frontend: edit mode toggles; Guardar updates the store; Cancelar discards; deleting
  a question/option/breakdown/category updates the draft; data-block parsing.

## Affected files

- `backend/aurum_encuestas/xlsx_parser.py` (`_detect_breakdowns`, share `_slug`)
- `backend/aurum_encuestas/data_extractor.py` (`_resolve_breakdown_cols`,
  `extract_chart_data` + callers)
- `backend/aurum_encuestas/pattern_classifier.py`, `pptx_generator.py` (pass
  `allowed_categories`)
- `frontend/src/pages/Wizard/XlsxVerifyWizard.tsx` (editor UI)
- `frontend/src/store/project.ts` (setter for edited `parsed_db`, if not already
  mutable through existing API)
