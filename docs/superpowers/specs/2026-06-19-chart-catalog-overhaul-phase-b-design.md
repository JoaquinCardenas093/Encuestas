# Chart Catalog Overhaul — Fase B Design Spec

**Date:** 2026-06-19
**Status:** Approved (brainstorming) → ready for writing-plans
**Branch base:** `main` at `fd24232` (post Fase A merge)
**Phase:** B of 3 — render grouped chart_types + legend visuals + multi-breakdown table image-faithful style.

## Goal

Render the two grouped chart_types added to the schema in Fase A: `PIE_GROUPED` (N-pie grid) and `BAR_HORIZONTAL_GROUPED` (clustered multi-series horizontal bars). Expose all 5 chart_types in the UI dropdown (Fase A capped at 3). Wire the previously-dormant per-chart fields `show_legend`, `grid_cols`, `title`, and a new `cat_titles: dict` into the UI and the renderers. Apply image-faithful style overrides to BOTH single-panel and multi-panel `TABLE_WITH_MINIBARS` so a user-provided "Rango de edad" / multi-breakdown table renders identically to the reference screenshots. Add a left external legend block for `TABLE_WITH_MINIBARS` when `show_legend=True`.

No OLE Excel embedded tables — that is Fase C.

## Non-Goals (deferred to Fase C)

- OLE Excel embedded tables (double-click-to-edit data inside python-pptx tables).
- AI training prompt updates for grouped chart_types.
- Pattern auto-classification recompute to surface grouped types as AI suggestions.

## Locked decisions (from grilling)

1. **PIE_GROUPED auto grid** when `grid_cols=None`: `rows = 1 if N≤3 else 2 if N≤6 else 3`; `cols = ceil(N/rows)`.
2. **Per-pie title source**: `Chart.cat_titles: dict[str, str] | None` overrides; default = breakdown category label.
3. **BAR_HORIZONTAL_GROUPED series colors**: `chart.colors[i]` overrides; palette fallback (primary, secondary, accent, …) cycles.
4. **show_legend UI**: visible only when `chart_type ∈ {BAR_HORIZONTAL_GROUPED, TABLE_WITH_MINIBARS}`. Default `false`.
5. **grid_cols UI**: free numeric input, backend validator `ge=1`. Visible only when `chart_type == PIE_GROUPED`.
6. **title input UI**: visible for all 5 chart_types. Default `null`.
7. **TABLE_WITH_MINIBARS legend semantic**:
   - `show_legend=True` → move row labels (Observaciones / Sí / No / …) to a left external block; panels render without internal label column.
   - `show_legend=False` → panels render without internal label column AND without external block (no row labels visible at all).
8. **cat_titles UI**: AddChartModal AND ConfigPanel show N text inputs (one per breakdown category) when `chart_type == PIE_GROUPED` AND `nReal == 1`.
9. **PIE_GROUPED render orchestration**: `chart_renderer.render()` detects the type and creates N pie shapes internally — no pattern fan-out.

**Implicit UI constraint**: PIE_GROUPED and BAR_HORIZONTAL_GROUPED require exactly one real breakdown to make semantic sense. Dropdown filter:
- `nReal == 0` → hide TABLE_WITH_MINIBARS, PIE_GROUPED, BAR_HORIZONTAL_GROUPED.
- `nReal == 1` → show all 5.
- `nReal ≥ 2` → lock to TABLE_WITH_MINIBARS only.

## Architecture overview

```
chart_renderer.render(slide, element, ctx)
   │
   ├─ chart_type == "PIE_GROUPED"
   │    └─ _render_pie_grouped()  ← NEW
   │         compute grid (rows, cols) from chart.grid_cols or auto rule
   │         for each cat in breakdown.categories:
   │            build single-series CategoryChartData
   │            add_chart(PIE, cell_bbox, ...)
   │            set per-pie title via cat_titles[cat] or cat
   │            apply colors / rotation / labels
   │
   ├─ chart_type ∈ {"PIE","BAR_HORIZONTAL","BAR_HORIZONTAL_GROUPED"}
   │    └─ existing single-shape path with two additions:
   │         - Chart.title → chart.has_title + chart_title.text
   │         - BAR_HORIZONTAL_GROUPED + show_legend=True → bottom legend
   │
   └─ chart_type == "TABLE_WITH_MINIBARS"
        (routed earlier by pattern_renderer dispatch peek)

table_renderer.render(slide, element, ctx)
   structure == "segmented_breakdowns"
   └─ _render_segmented_breakdowns()
        if show_legend: _render_external_legend_block() to the left
        for each panel: _render_panel() with _SEGMENTED_CELLS_FASE_B style
                        and label_col_width_rel=0 (NO internal label col)
```

The Fase A dispatch hook in `pattern_renderer.render_pattern` is unchanged — it already swaps `kind=chart` to `kind=table` when `chart_type == "TABLE_WITH_MINIBARS"` and `breakdown_ids` has real entries.

## Data model

### `backend/aurum_encuestas/models.py`

```python
class Chart(BaseModel):
    id: str
    question_id: str
    breakdown_ids: list[str] = Field(default_factory=list)
    chart_type: ChartType
    show_legend: bool = False
    grid_cols: int | None = Field(default=None, ge=1)    # CHANGED: ge=1 validator
    title: str | None = None
    cat_titles: dict[str, str] | None = None              # NEW
    colors: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _reject_legacy(cls, data):
        # (unchanged from Fase A)
```

### `frontend/src/types/index.ts`

```typescript
export interface Chart {
  id: string
  question_id: string
  breakdown_ids: string[]
  chart_type: ChartType
  show_legend: boolean
  grid_cols: number | null
  title: string | null
  cat_titles: Record<string, string> | null    // NEW
  colors: string[]
}
```

## Backend wiring

### `backend/aurum_encuestas/style_guide.py`

`StyleGuide.available_chart_types` default factory + `BUILTIN_STYLE_GUIDE["available_chart_types"]` literal both extend to the 5-item Fase B list:

```python
["PIE", "PIE_GROUPED", "BAR_HORIZONTAL", "BAR_HORIZONTAL_GROUPED", "TABLE_WITH_MINIBARS"]
```

`style_guide_analyzer.py` repair logic stays identical — it drops unknown chart_types via `el.pop("chart_type", None)`. Since `PIE_GROUPED` and `BAR_HORIZONTAL_GROUPED` are now in the allowed set, they pass through.

### `backend/aurum_encuestas/pattern_classifier.py`

`EnrichedChart` propagates the new fields:

```python
@dataclass
class EnrichedChart:
    id: str
    question_id: str
    breakdown_ids: list[str]
    chart_type: str
    colors: list
    question: Any = None
    data: dict = field(default_factory=dict)
    all_breakdowns_data: dict = field(default_factory=dict)
    show_legend: bool = False        # NEW
    grid_cols: int | None = None     # NEW
    title: str | None = None         # NEW
    cat_titles: dict | None = None   # NEW
```

`build_slide_config` reads the new fields from `chart.show_legend`, `chart.grid_cols`, `chart.title`, `chart.cat_titles` and populates EnrichedChart accordingly.

### `backend/aurum_encuestas/element_renderers/chart_renderer.py`

**Remove** the `"Fase B"` warning block added in Fase A T4. Grouped types now render real output (PIE_GROUPED via dedicated helper; BAR_HORIZONTAL_GROUPED via existing multi-series path).

**Dispatch addition** at top of `render()`:

```python
if chart_type_str == "PIE_GROUPED":
    _render_pie_grouped(slide, element, source_chart, ctx)
    return
```

**New helpers** (full bodies in plan):

```python
def _render_pie_grouped(slide, element, source_chart, ctx) -> None
def _compute_grid_dims(n: int, grid_cols: int | None) -> tuple[int, int]
def _add_title_textbox(slide, x: int, y: int, w: int, h: int, text: str, ctx) -> None
```

`_compute_grid_dims`:
```python
def _compute_grid_dims(n: int, grid_cols: int | None) -> tuple[int, int]:
    if grid_cols and grid_cols >= 1:
        cols = grid_cols
        rows = (n + cols - 1) // cols
        return rows, cols
    rows = 1 if n <= 3 else (2 if n <= 6 else 3)
    cols = (n + rows - 1) // rows
    return rows, cols
```

**Title rendering** (single-shape path, after `chart_shape` is created):
```python
title_str = (getattr(source_chart, "title", None) or "").strip()
if title_str:
    chart.has_title = True
    chart.chart_title.text_frame.text = title_str
```

**show_legend handling** for BAR_HORIZONTAL_GROUPED:
```python
show_legend = bool(getattr(source_chart, "show_legend", False))
if chart_type_str == "BAR_HORIZONTAL_GROUPED" and show_legend:
    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout = False
elif chart_type_str == "BAR_HORIZONTAL_GROUPED":
    chart.has_legend = False
```

PIE / BAR_HORIZONTAL single: existing behavior (no legend).

### `backend/aurum_encuestas/element_renderers/table_renderer.py`

**New module-level constant** `_SEGMENTED_CELLS_FASE_B`:

```python
_SEGMENTED_CELLS_FASE_B = {
    "group_header": {
        "style": {"fill": "secondary", "text_color": "background",
                  "font_size": 11, "bold": True, "align_h": "center"},
    },
    "category_header": {
        "style": {"fill": "primary", "text_color": "background",
                  "font_size": 10, "bold": True, "align_h": "center"},
    },
    "counts_row": {
        "style": {"fill": "primary", "text_color": "background",
                  "font_size": 11, "bold": True, "align_h": "center"},
        "label_first_col": "",
    },
    "option_row": {
        "style": {"fill": "primary", "text_color": "#FFFFFF",
                  "font_size": 10, "align_h": "center"},
        "label_col_width_rel": 0.0,    # zero = no internal label col
        "value_format": "percentage",
        "value_decimals": 1,
        "minibar": {
            "enabled": True,
            "color_role": "secondary",
            "height_rel_to_cell": 0.25,
            "show_percent_text": True,
            "percent_text_position": "left_of_bar",
        },
    },
}
```

`_render_segmented_breakdowns` overrides per-pattern `cells_cfg` with `_SEGMENTED_CELLS_FASE_B` for BOTH single-panel and multi-panel branches. The `len(panels) == 1` short-circuit retains the bbox-full-width logic but uses the shared cells config.

**Multi-panel weight recalculation**: with `label_col_width_rel=0` there is no label column, so `weight = len(cats)` (was `1 + len(cats)`). Update `_pack_panels_into_rows` weight calc to read `label_col_width_rel` from the cells config — when zero, weight is cats-only; when positive, weight stays `1 + len(cats)` for back-compat with patterns that still set a positive label col width.

**`_render_panel`** gains a branch on `label_col_width_rel`:

```python
label_col_w_rel = option_cfg.get("label_col_width_rel", 0.18)
if label_col_w_rel <= 0.001:
    n_cols = n_cat
    label_w = 0
else:
    n_cols = 1 + n_cat
    label_w = max(MIN_LABEL_EMU, int(label_col_w_rel * cx))
```

All subsequent column-indexed writes shift accordingly: cat headers, counts, option values start at column 0 (not column 1) when `label_w == 0`. The label-col writes (`_set_cell(tbl.cell(row_idx, 0), option_label, ...)`) only fire when `label_w > 0`.

**New helper** `_render_external_legend_block(slide, x, y, w, h, options, label_first, ctx)`:
Creates a 1-column tall table with rows aligned to the panel layout:
- Row 0: spacer matching group_header (fill=secondary).
- Row 1: spacer matching category_header (fill=primary).
- Row 2: `label_first` (e.g. "Observaciones"), right-aligned.
- Rows 3+: each option label (e.g. "Sí", "No"), right-aligned, with same font/color/fill as option rows in the panel (primary fill, white text via raw `#FFFFFF`).

When `show_legend=True`, `_render_segmented_breakdowns` calls this helper first with `legend_block_w = int(box_cx * 0.10)`, then shifts the table region to `table_x = box_x + legend_block_w`, `table_cx = box_cx - legend_block_w`.

When `show_legend=False`, no external block; `legend_block_w = 0`.

### `backend/aurum_encuestas/pattern_renderer.py`

No changes. The Fase A dispatch peek + `_synthesize_table_element` already handle TABLE_WITH_MINIBARS routing. PIE_GROUPED stays `kind="chart"` and dispatches to `chart_renderer.render()` which detects the type internally (decision Q9).

### `backend/aurum_encuestas/pptx_generator.py`

No changes. The legacy `_add_chart` path already adapted to `breakdown_ids` list in Fase A T6. It does not render PIE_GROUPED via the legacy path — modern flow uses `pattern_renderer → chart_renderer`.

## Frontend behavior

### `frontend/src/store/project.ts`

`addChart` signature extends to accept an optional opts object:

```typescript
addChart(
  slideId: string,
  questionId: string,
  breakdownIds: string[],
  chartType: ChartType,
  opts?: {
    show_legend?: boolean
    grid_cols?: number | null
    title?: string | null
    cat_titles?: Record<string, string> | null
    colors?: string[]
  },
): void
```

Defaults match the Pydantic schema (`show_legend=false`, `grid_cols=null`, `title=null`, `cat_titles=null`, `colors=[]`).

New action `updateChartField(slideId, chartId, field, value)` — shallow patch one chart field in-place. Used by ConfigPanel per-chart edits.

### `frontend/src/pages/Editor/modals/AddChartModal.tsx`

**Filter rule** (Fase B):
- `nReal == 0` → hide `TABLE_WITH_MINIBARS`, `PIE_GROUPED`, `BAR_HORIZONTAL_GROUPED`.
- `nReal == 1` → show all 5 (no filter).
- `nReal ≥ 2` → lock dropdown to `["TABLE_WITH_MINIBARS"]`.

**New inputs** (conditional on chart_type):
- `title` text input (always visible).
- `show_legend` checkbox (visible only when `chartType ∈ {BAR_HORIZONTAL_GROUPED, TABLE_WITH_MINIBARS}`).
- `grid_cols` number input min=1 (visible only when `chartType == PIE_GROUPED`).
- `cat_titles` per-cat text inputs (visible only when `chartType == PIE_GROUPED` AND `nReal == 1`). Inputs auto-populate placeholders with cat labels; user types overrides.

**handleApply** emits the new fields:

```typescript
onApply({
  questionId,
  breakdownIds: realBreakdownIds,
  chartType,
  show_legend: showLegend,
  grid_cols: gridCols,
  title: title.trim() || null,
  cat_titles: Object.keys(catTitles).length ? catTitles : null,
  colors: finalColors,
})
```

`BUILTIN_CHART_TYPES` constant extends to 5 items: `["PIE", "PIE_GROUPED", "BAR_HORIZONTAL", "BAR_HORIZONTAL_GROUPED", "TABLE_WITH_MINIBARS"]`.

### `frontend/src/pages/Editor/ConfigPanel.tsx`

Per-chart row exposes the same conditional input set as the modal, scoped to that chart's current `chart_type`. Each input dispatches `updateChartField(slide.id, chart.id, "<field>", value)`.

The `BUILTIN_CHART_TYPES` constant in ConfigPanel also extends to 5.

### `frontend/src/pages/Editor/modals/AddAnalysisModal.tsx`

No changes — already reads `breakdown_ids[0] ?? "general"` after Fase A.

## Testing strategy

### Backend

`backend/tests/test_models.py`:
- `test_chart_accepts_cat_titles_dict` — `cat_titles={"Banco":"Bcos","MAF":"MAF"}` parses.
- `test_chart_grid_cols_rejects_zero` — `grid_cols=0` raises ValidationError.
- `test_chart_grid_cols_rejects_negative` — `grid_cols=-1` raises ValidationError.
- `test_chart_grid_cols_accepts_positive` — `grid_cols=3` parses.

`backend/tests/test_style_guide.py`:
- `test_builtin_available_chart_types_phase_b_is_five` — list equals the 5-item Fase B set.

`backend/tests/test_pattern_classifier.py`:
- `test_enriched_chart_propagates_show_legend_grid_cols_title_cat_titles` — build_slide_config carries all four fields.

`backend/tests/test_element_renderers.py` (or new `test_chart_renderer.py`):
- `test_pie_grouped_renders_n_pie_shapes` — N=3 cats → exactly 3 chart shapes, each `chart_type == XL_CHART_TYPE.PIE`.
- `test_pie_grouped_auto_grid_rows_for_each_n` — parametrize N=1..9; asserts (rows, cols) match auto rule.
- `test_pie_grouped_user_grid_cols_overrides_auto` — `grid_cols=2`, N=6 → 2 cols × 3 rows.
- `test_pie_grouped_cat_titles_override` — title text of each sub-chart matches `cat_titles` entry or cat label fallback.
- `test_pie_grouped_chart_title_renders_textbox_above_grid` — `chart.title="Plazo del crédito"` produces a centered text-box above the grid.
- `test_pie_grouped_empty_breakdown_logs_skip_warning` — empty `all_breakdowns_data` warns and creates no shapes.
- `test_bar_horizontal_grouped_legend_on_renders_bottom` — chart.legend.position == XL_LEGEND_POSITION.BOTTOM when show_legend=True.
- `test_bar_horizontal_grouped_legend_off_no_legend` — `chart.has_legend == False`.
- `test_bar_horizontal_single_never_renders_legend` — even with show_legend=True (defensive, since UI doesn't expose it).
- `test_chart_title_renders_for_all_single_shape_types` — parametrize PIE / BAR_HORIZONTAL / BAR_HORIZONTAL_GROUPED.
- `test_grouped_fallback_warning_removed` — caplog asserts NO "Fase B" warning for PIE_GROUPED / BAR_HORIZONTAL_GROUPED.

`backend/tests/test_table_renderer.py`:
- `test_segmented_breakdowns_legend_on_renders_external_block` — `show_legend=True` → first shape is the legend block, second+ are panels; block has rows `len(options) + 3`.
- `test_segmented_breakdowns_legend_off_no_block_no_label_col` — `show_legend=False` → only panel shapes; panels have `n_cols == len(cats)` (no label col).
- `test_segmented_breakdowns_multi_panel_image_style_applied` — 2+ breakdowns, every panel uses `_SEGMENTED_CELLS_FASE_B` (assert fill/text/font_size on key cells).
- `test_external_legend_block_has_observaciones_plus_options` — block row count equals `3 + len(options)`; row 2 text == "Observaciones"; rows 3+ texts match `question.options`.
- `test_panel_weight_calc_excludes_label_col_when_zero` — `_pack_panels_into_rows` weight derives from `len(cats)` only when label col is 0.

### Frontend

`frontend/tests/AddChartModal.test.tsx`:
- `no_real_breakdown_hides_grouped_and_table` — dropdown excludes PIE_GROUPED, BAR_HORIZONTAL_GROUPED, TABLE_WITH_MINIBARS when no real bd.
- `one_real_breakdown_shows_all_five` — dropdown contains all 5.
- `two_real_breakdowns_locks_to_TABLE` — dropdown disabled and only TABLE_WITH_MINIBARS.
- `show_legend_checkbox_only_for_grouped_bar_or_table` — checkbox absent for PIE/PIE_GROUPED/BAR_HORIZONTAL.
- `grid_cols_input_only_for_pie_grouped` — input absent for the other 4 types.
- `cat_titles_inputs_appear_for_pie_grouped_single_bd` — N inputs equal to bd categories.
- `apply_sends_new_fields` — onApply receives `show_legend`, `grid_cols`, `title`, `cat_titles`.

`frontend/tests/ConfigPanel.test.tsx`:
- `per_chart_inputs_match_chart_type` — for each chart in a slide, the right inputs render.
- `updateChartField_patches_single_field` — changing show_legend does not touch grid_cols/title.

`frontend/tests/store.test.ts`:
- `addChart_with_opts_persists_new_fields` — opts.show_legend etc. land on the new Chart record.
- `addChart_without_opts_uses_defaults` — defaults match schema.
- `updateChartField_shallow_patches` — only the targeted field changes.

Baseline: backend 288 / frontend 120. Fase B adds ~25 tests; full suites stay green.

## File map

No new files. Modified:

Backend:
- `backend/aurum_encuestas/models.py` — `cat_titles`, `grid_cols` validator.
- `backend/aurum_encuestas/style_guide.py` — 5-item available_chart_types.
- `backend/aurum_encuestas/pattern_classifier.py` — EnrichedChart fields propagate.
- `backend/aurum_encuestas/element_renderers/chart_renderer.py` — `_render_pie_grouped`, `_compute_grid_dims`, `_add_title_textbox`, dispatch + title + legend wiring; remove Fase B warning.
- `backend/aurum_encuestas/element_renderers/table_renderer.py` — `_SEGMENTED_CELLS_FASE_B`, `_render_external_legend_block`, `_render_panel` no-label-col branch, weight calc adjust.

Frontend:
- `frontend/src/types/index.ts` — `cat_titles` field.
- `frontend/src/store/project.ts` — `addChart` opts param, `updateChartField` action.
- `frontend/src/pages/Editor/modals/AddChartModal.tsx` — filter + new inputs + apply payload; BUILTIN_CHART_TYPES → 5.
- `frontend/src/pages/Editor/ConfigPanel.tsx` — per-chart inputs + updateChartField wiring; BUILTIN_CHART_TYPES → 5.

Tests:
- backend: `test_models.py`, `test_style_guide.py`, `test_pattern_classifier.py`, `test_element_renderers.py`, `test_table_renderer.py`.
- frontend: `AddChartModal.test.tsx`, `ConfigPanel.test.tsx`, `store.test.ts`.

## Open risks

1. **`label_col_width_rel=0.0` weight-pack math.** Existing `_pack_panels_into_rows` uses `1 + len(cats)` per panel. When label col is 0, weight should be `len(cats)` only. Plan must update `_pack_panels_into_rows` to read the label col config or accept a weight parameter — otherwise multi-panel proportions skew.
2. **Visual regression for Fase A `TABLE_WITH_MINIBARS` users.** Fase A's single-panel had an internal label col with "Sí"/"No" labels. Fase B drops it unconditionally; user must enable `show_legend=True` to see labels. Acceptable per Q7 grilling decision; users may complain. Mitigation: default a few demo projects with `show_legend=True`.
3. **External legend block row-height alignment.** `_render_external_legend_block` creates its own table with `n_rows = 3 + len(options)` and height = `box_cy`. Rows are auto-sized by python-pptx. The panel rows may be auto-sized differently (depending on font / minibar height), causing visual misalignment. Mitigation: explicitly set row heights in both the block and the panel using the same `MIN_SUBROW_EMU` formula.
4. **PIE_GROUPED with empty `all_breakdowns_data`.** When data is missing, the helper warns and creates no shapes. Slide will look incomplete. No fallback — user fixes data.
5. **`cat_titles` keys must match cat labels exactly.** If a cat label changes upstream (e.g. xlsx rename), `cat_titles` entries go stale and the helper falls back to the new cat label. No migration path — acceptable for this phase.
6. **`addChart` opts ergonomics.** TypeScript signature accepts an optional opts object; defaults populated by the impl. Call sites must use opts to set non-default values (UI only).
7. **`updateChartField` field name typo risk.** Pure-string field key. TypeScript can't fully constrain it without a `keyof Chart` typing. Plan should require typing as `keyof Pick<Chart, "show_legend" | "grid_cols" | "title" | "cat_titles" | "chart_type" | "breakdown_ids" | "colors">` to catch typos at compile time.
