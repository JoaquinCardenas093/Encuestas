# Per-Cell Value Overrides (counts + percentages) — Design

Date: 2026-06-29
Status: Approved

## Problem

Counts and percentages are derived from the XLSX at extraction time. The field
editor ("Editar campos") edits only the mapping (questions, breakdowns, data
blocks, total_row) — it cannot show or edit the actual **counts** per answer, and
there is no way to manually correct a computed **percentage**. Users need to (a)
see the per-cell count and computed pct, and (b) override either value by hand.

## Goal

Add a crosstab value editor inside the field editor: pick a question + breakdown,
see a table (rows = options, columns = categories) of count + pct per cell, and
override either value. Overrides persist in the project and are applied on top of
the computed values everywhere charts/tables/analysis read data.

## Decisions (from brainstorming)

- **Independent overrides:** count and pct are overridden separately; setting one
  does not touch the other (they may diverge — accepted).
- **Surface:** a crosstab per (question × breakdown) — question selector +
  breakdown selector → table rows=options, cols=categories, each cell two inputs.

## Non-goals

- No bulk import/paste of values; cell-by-cell editing only.
- No recompute coupling between count and pct.
- No new chart behavior — charts/tables read the same `{count, pct}` shape; only the
  values change when an override exists.

## Architecture

### 1. Data model — `value_overrides`

`backend/aurum_encuestas/models.py` — `ParsedDB` gains:
```python
value_overrides: dict = {}   # key -> {"count": int|None, "pct": float|None}
```
Key format (string, JSON-friendly): `f"{question_id}|{breakdown_id}|{category}|{option}"`.
`pct` is stored as a **fraction** (e.g. `0.916`, not `91.6`). A field present with a
non-null value overrides that metric; absent/null → use the computed value.

`frontend/src/types/index.ts` — `ParsedDB` gains
`value_overrides?: Record<string, { count?: number | null; pct?: number | null }>`.

### 2. Extraction applies overrides

`backend/aurum_encuestas/data_extractor.py`:
- Both `extract_chart_data(..., overrides: dict | None = None)` and
  `extract_all_breakdowns_data(..., overrides: dict | None = None)` gain the param.
- After computing `{count, pct}` for a `(category, option)` cell, build the key
  `f"{question.id}|{breakdown_id}|{category}|{option}"` (for `extract_all_breakdowns_data`
  the `breakdown_id` is `bd.id`). If `overrides.get(key)` exists, replace `count`
  and/or `pct` with the override's non-null fields.
- Callers pass `overrides=parsed_db.value_overrides` (same three sites already
  passing `total_row`): `pattern_classifier.build_slide_config`,
  `pptx_generator._add_chart`, `api._build_analysis_context`.

A small shared helper `_override_key(question_id, breakdown_id, category, option) -> str`
keeps the key format in one place.

### 3. Cell-values endpoint

`backend/aurum_encuestas/api.py` — `POST /api/cell-values`:
- Body `{ state: <ProjectState>, question_id: str, breakdown_id: str }`.
- Resolves the question + `state.parsed_db` (data_blocks, total_row,
  value_overrides), runs `extract_chart_data(db_path, question, breakdown_id,
  data_blocks, total_row=..., overrides=...)`, and returns:
  ```json
  { "options": ["Sí","No"], "categories": ["Hombre","Mujer"],
    "cells": { "Sí": { "Hombre": {"count": 229, "pct": 0.916}, ... }, ... } }
  ```
  `options` = question.options order; `categories` = the resolved column order
  (`general` → `["Total"]`). On error return `{ "error": "...", "options": [],
  "categories": [], "cells": {} }` with HTTP 200.

### 4. Crosstab editor in the field editor

`frontend/src/pages/Wizard/XlsxVerifyWizard.tsx` (under `mode === "fields"`):
- A "Valores" section with a question `<select>` and a breakdown `<select>`
  (breakdowns include `general`, labelled "General").
- On selection change, `fetchCellValues(state, questionId, breakdownId)` →
  render a table: header row = categories; one row per option; each cell holds two
  small inputs — **conteo** (number) and **%** (number, displayed as
  `pct * 100`, one decimal).
- Editing an input updates the draft via `setValueOverride(draft, key, patch)` where
  `key = `${questionId}|${breakdownId}|${category}|${option}``. The displayed table
  value reflects the draft override immediately (override merged over fetched value).
- A clear ("×") affordance per cell removes that cell's override (revert to computed).

`frontend/src/api/client.ts` — `fetchCellValues(state, question_id, breakdown_id)`
returning the endpoint shape.

### 5. Draft helper + persistence + edges

`frontend/src/pages/Wizard/mappingDraft.ts`:
- `setValueOverride(db, key, patch: { count?: number | null; pct?: number | null }) -> ParsedDB`
  (pure): merges `patch` into `db.value_overrides[key]`; a field set to `null`/empty
  is deleted; if the merged override becomes empty (`{}`), the key is removed.
- The field editor's existing Guardar already calls `setParsedDb(draft)`, persisting
  `value_overrides`; extraction then applies them.

Edges:
- Empty input (`""`) → that metric's override removed → cell shows the computed value
  again. `pct` input parsed as percent → fraction (`/100`); blank → removed.
- Override key for a cell whose category/option no longer exists (after a mapping
  edit) is simply never matched — harmless stale entry.
- `general` breakdown: category key is `"Total"` (matches `extract_chart_data`'s
  general short-circuit).

## Testing

- Backend: `extract_chart_data(..., overrides={key: {"count": 999}})` returns
  `count == 999` with the computed `pct` unchanged; `{"pct": 0.5}` overrides pct
  only; no override → computed. `/api/cell-values` returns the crosstab with an
  override applied.
- Frontend (`mappingDraft.test.ts`): `setValueOverride` sets/merges/clears purely;
  clearing the last field removes the key.

## Affected files

- `backend/aurum_encuestas/models.py` (`ParsedDB.value_overrides`)
- `backend/aurum_encuestas/data_extractor.py` (`_override_key`, `overrides` param on both extractors)
- `backend/aurum_encuestas/pattern_classifier.py`, `pptx_generator.py`, `api.py` (pass `overrides`; new `/api/cell-values`)
- `backend/tests/test_data_extractor.py`, `test_api.py`
- `frontend/src/types/index.ts` (`value_overrides`)
- `frontend/src/api/client.ts` (`fetchCellValues`)
- `frontend/src/pages/Wizard/mappingDraft.ts` (+ `.test.ts`) (`setValueOverride`)
- `frontend/src/pages/Wizard/XlsxVerifyWizard.tsx` (crosstab editor)
