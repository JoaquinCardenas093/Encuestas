# Computed Percentages (count ÷ column total) — Design

Date: 2026-06-29
Status: Approved

## Problem

Charts and tables currently read percentages from a pre-computed `%row`/`%col`
column block in the XLSX (`data_blocks.pct_row_cols`). The real source data does
not reliably carry those blocks; the percentage that matters is **count ÷
column total** — e.g. P1 "Sí" = 458 out of a General total of 500 → 91.6%; within
"De 18 a 39 años", 230 of 250 → 92%. The column totals live in a dedicated
**Total row** (the row whose column B is `"Total"`, image reference: row 3 of the
sample sheet).

## Goal

Compute every percentage as `count / column_total`, where `column_total` comes
from the Total row at the category's column. Stop reading the pre-computed `%`
blocks. The Total row is auto-detected (col B == `"Total"`) and overridable in the
visual mapper.

## Decisions (from brainstorming)

- **Replace, not fallback:** the app ALWAYS computes `count / column_total`; the
  pre-computed `%` blocks are no longer read for extraction.
- **Total row:** auto-detected by `col B == "Total"`, with a mapper override (a new
  `Total` paint role) and an editable field in the field editor.
- Division by zero / missing total → `pct = None`; missing count → `count = 0`.

## Non-goals

- No removal of `data_blocks.pct_row_cols`/`pct_col_cols` from the serialized model
  (kept for backward compatibility, but unused by extraction).
- No change to how counts themselves are located (still the `counts_cols` block +
  `_resolve_breakdown_cols`).

## Architecture

### 1. Data model — `total_row`

`backend/aurum_encuestas/models.py` — `ParsedDB` gains:
```python
total_row: int | None = None   # 1-based sheet row holding per-column totals
```
`frontend/src/types/index.ts` — `ParsedDB` gains `total_row?: number | null`.

`total_row` is the sheet row (1-based, openpyxl convention) whose cells, at each
category column, are the denominators.

### 2. Parser — detect the Total row

`backend/aurum_encuestas/xlsx_parser.py`:
- New `_detect_total_row(ws) -> int | None`: scan rows from 1; return the first row
  whose `str(ws.cell(r, 2).value).strip() == "Total"` (column B). `None` if absent.
- `parse_xlsx` sets `ParsedDB.total_row = _detect_total_row(ws)`.

### 3. Extraction — compute `pct = count / column_total`

`backend/aurum_encuestas/data_extractor.py`:
- `extract_chart_data(xlsx_path, question, breakdown_id, data_blocks,
  allowed_categories=None, total_row=None)`:
  - Resolve category columns from the **counts** block (`counts_cols[0]`) as today.
  - For each (option_row, category_col): `count = ws.cell(option_row, col).value or 0`;
    `total = ws.cell(total_row, col).value if total_row else None`;
    `pct = float(count) / float(total) if total else None` (guard `total == 0` → `None`).
  - Remove the `pct_breakdown_cols` / `pct_start` lookups entirely.
- `extract_all_breakdowns_data(xlsx_path, question, breakdowns, data_blocks,
  total_row=None)`: same change — compute `pct` from `total_row` instead of the pct
  block.
- Callers pass `total_row=parsed_db.total_row` (or `state.parsed_db.total_row`):
  `pattern_classifier.build_slide_config`, `pptx_generator._add_chart`,
  `api._build_analysis_context`.

The returned shape is unchanged: `{category: {option: {count, pct}}}` — only the
`pct` source changes.

### 4. Visual mapper — `Total` role, drop `%row`/`%col`

`frontend/src/pages/Wizard/sheetPaint.ts`:
- `Role` drops `"pctRow"` and `"pctCol"`, adds `"total"`.
- `paintToParsedDb`: cells painted `total` → `total_row = min(painted row, 0-based) + 1`
  (1-based). If none painted, carry `prev.total_row`. `counts` role unchanged. The
  data-block ranges for counts still come from painted `counts` cells (or `prev`).
- `parsedDbToPaint`: pre-paint the `total_row` (paint that row across the counts
  columns) and the counts block; no longer pre-paint `%row`/`%col`.
- Result `db` includes `total_row`.

`frontend/src/pages/Wizard/SheetGrid.tsx`:
- Toolbar role list drops `%Row`/`%Col`, adds `Total` (a distinct color).

### 5. Field editor + edge handling

`frontend/src/pages/Wizard/XlsxVerifyWizard.tsx`:
- The field editor (`mode === "fields"`) shows `total_row` as an editable number
  (override of the auto-detected value). A new `mappingDraft` helper
  `setTotalRow(db, n)` (pure) backs it.
- The Lista view shows the detected `total_row` (read-only).

Edge cases:
- `total_row` is `None`/0 → all `pct` are `None` (charts/tables omit the value);
  surface a wizard note "No se detectó la fila Total — los porcentajes quedarán vacíos".
- `total == 0` for a column → `pct = None` for that column.
- Existing extraction tests that asserted `pct` values from the old pct block must be
  updated to the computed values (or assert counts only).

## Testing

- Backend: `_detect_total_row` returns 3 for the synth fixture (col B row 3 ==
  "Total"); `extract_chart_data(..., total_row=3)` yields `pct == 458/500` for
  General "Sí" and `229/250` for a sexo column; `total_row=None` → `pct is None`.
- Frontend (`sheetPaint.test.ts`): `paintToParsedDb` maps a painted `total` row →
  `total_row`; round-trip `parsedDbToPaint`→`paintToParsedDb` preserves `total_row`;
  `mappingDraft.setTotalRow` is pure.

## Affected files

- `backend/aurum_encuestas/models.py` (`ParsedDB.total_row`)
- `backend/aurum_encuestas/xlsx_parser.py` (`_detect_total_row`, set in `parse_xlsx`)
- `backend/aurum_encuestas/data_extractor.py` (compute pct; `total_row` param on both extractors)
- `backend/aurum_encuestas/pattern_classifier.py`, `pptx_generator.py`, `api.py` (pass `total_row`)
- `backend/tests/test_data_extractor.py`, `test_xlsx_parser.py` (computed-pct + detect tests)
- `frontend/src/types/index.ts` (`total_row`)
- `frontend/src/pages/Wizard/sheetPaint.ts` (+ `.test.ts`) (`total` role, drop pct roles)
- `frontend/src/pages/Wizard/SheetGrid.tsx` (toolbar roles)
- `frontend/src/pages/Wizard/mappingDraft.ts` (+ `.test.ts`) (`setTotalRow`)
- `frontend/src/pages/Wizard/XlsxVerifyWizard.tsx` (total_row field)
