# TABLE_WITH_MINIBARS per Breakdown — Design Spec

**Date:** 2026-06-18
**Status:** Approved (brainstorming) → ready for writing-plans
**Branch base:** `main` at `bc385c0` (post-Bug #1/#2/#3 plan)

## Goal

When the user picks `TABLE_WITH_MINIBARS` as `chart_type` in `AddChartModal` for a chart whose `breakdown_id` is a real dimension (Sexo, NSE, Edad, etc.), render a single-panel segmented table — header with the breakdown label, a sub-header row of category names, a counts row, and one option row per question option with horizontal minibars and percentages — INSTEAD of a chart shape. Selecting 3 breakdowns must yield 3 separate tables, one per breakdown, laid out by the same N-charts-grid mechanism that handles 3-chart slides.

Reference output (single Rango de edad table from user-provided screenshot):

```
┌────────────────────────────────────┐
│            Rango de edad           │  ← group_header (merged across cats)
├──────────┬─────────────┬───────────┤
│          │ De 18 a 39  │ De 40 a 59│  ← category_header (yellow on dark)
├──────────┼─────────────┼───────────┤
│          │     250     │    250    │  ← counts_row (yellow on dark)
├──────────┼─────────────┼───────────┤
│    Sí    │ 92.0% ■■■■  │ 91.2% ■■■■│  ← option_row (% + minibar)
├──────────┼─────────────┼───────────┤
│    No    │ 8.0%  ▪     │ 8.8%  ▪   │  ← option_row
└──────────┴─────────────┴───────────┘
```

## Non-Goals

- No new `Pattern` entries in `BUILTIN_STYLE_GUIDE`. Layout (position, size) keeps coming from the matched pattern (`binary_general` / `multi_choice_small` / `comparison_two_charts` / `n_charts_grid`).
- No multi-breakdown packing into one table. The legacy `segmented_breakdowns` with side-by-side mini-panels stays available via the `breakdown_groups: "all_except_general"` path (used by `binary_with_demographics`) but is NOT what the new flow produces — each `Chart` record renders as its own single-panel table.
- No frontend redesign of `AddChartModal` UX beyond filtering the chart_type dropdown.

## Architecture

### Render-time element dispatch hook

`pattern_renderer.render_pattern()` already iterates `ordered_elements` after fan-out and dispatches each by `element["kind"]` via `_KIND_RENDERERS`. We add a single pre-dispatch step: for any element where `kind == "chart"`, peek at `slide_config.charts[data_source.chart_ref_index].chart_type`. If that string equals `"TABLE_WITH_MINIBARS"`, synthesize a `kind: table` element (`structure: segmented_breakdowns`, `breakdown_groups: [source_chart.breakdown_id]`, inheriting `position` and `id` from the original chart element) and route it to `table_renderer.render` instead of `chart_renderer.render`.

```
┌─────────────────────────────────────────────┐
│ pattern_renderer.render_pattern             │
│  for each element in ordered_elements:      │
│    if kind == "chart":                      │
│      sc = slide_config.charts[chart_ref]    │
│      if sc.chart_type == "TABLE_WITH_MINI": │  ← NEW
│        el = _synthesize_table_element(el,   │
│                                       sc)   │
│    renderer = _KIND_RENDERERS[el.kind]      │
│    renderer.render(slide, el, ctx)          │
└─────────────────────────────────────────────┘
```

`_synthesize_table_element` is a new private helper in `pattern_renderer.py`:

```python
def _synthesize_table_element(chart_el: dict, source_chart) -> dict:
    """Convert a chart element to a single-panel segmented_breakdowns table."""
    return {
        "kind": "table",
        "id": chart_el.get("id"),
        "position": chart_el.get("position"),
        "structure": "segmented_breakdowns",
        "data_source": {
            "chart_ref_index": chart_el.get("data_source", {}).get("chart_ref_index", 0),
            "breakdown_groups": [source_chart.breakdown_id],
        },
        # Use the binary_with_demographics cells defaults — pulled from style_guide
        # at runtime via ctx.style_guide (no new hardcoded styling).
    }
```

When `cells` is absent on the synthesized element, `table_renderer` uses its existing defaults plus the active style guide's palette (the only change needed in `table_renderer` — see below).

### Routing decision: why pattern_renderer, not pattern_classifier

Pattern matching is `chart_type`-agnostic (triggers only know `question_type`, `n_breakdowns`, `n_charts_in_slide`). Doing the swap at classification time means the matched pattern wouldn't know if the eventual render is a chart or a table — fine for layout. But it would require either (a) emitting two different patterns for the same trigger or (b) running the swap in `_KIND_RENDERERS` itself. Both are noisier than a one-line peek in `render_pattern`. The pattern stays pure layout intent; the renderer decides the kind from the UI selection. Matches the chart_type-UI-wins philosophy from Bug #1.

### single-panel mode in `_render_segmented_breakdowns`

Currently `_render_segmented_breakdowns` (table_renderer.py:143-295) packs N breakdowns into a single table with side-by-side mini-panels. For N=1 it must:
- Render group_header as a single merged cell across the breakdown's categories (not across multiple breakdowns).
- Drop the panel-separator divider.
- Use full width of the bbox for the single panel.

Audit needed: verify it already handles N=1 correctly. If not, the implementation plan adds a minimal `if len(breakdown_keys) == 1: ...` branch.

### Color sourcing

`_TableCells` defaults in `BUILTIN_STYLE_GUIDE.patterns["binary_with_demographics"]` already use role-names (`primary`, `secondary`, `background`). `color_resolver.resolve` maps these to the active palette. The new flow does not introduce hex strings — it relies on the role→palette mapping:

| Cell | Fill role | Text role | Notes |
|------|-----------|-----------|-------|
| `group_header` | `palette[1]` ≡ `secondary` | `palette[2]` ≡ `accent` | merged across cats |
| `category_header` | `palette[0]` ≡ `primary` | `palette[2]` ≡ `accent` | bold |
| `counts_row` | `palette[0]` ≡ `primary` | `palette[2]` ≡ `accent` | sum of option counts per cat |
| `option_row` label col | `palette[0]` ≡ `primary` | `background` (white) | left-aligned |
| `option_row` value cells | `palette[0]` ≡ `primary` | `background` (white) | pct text `left_of_bar` |
| minibar fill | `secondary` (#404040) | — | track: none |

Requires confirming `color_resolver` exposes role names `primary`/`secondary`/`accent`/`background` in this exact mapping. If `accent` is currently named `tertiary` or otherwise, the design uses whatever the resolver already calls index 2.

### Counts row source

For each breakdown category, the counts cell value = sum of `count` over all question options in that category. For binary (Sí/No), `Sí.count + No.count` = n per cat. The data lives in `EnrichedChart.all_breakdowns_data[breakdown_id]["categories"][cat][opt]["count"]`. If the sum is 0 (missing data), fall back to `parsed_db.sample_size / n_cats` — never render an empty counts row.

Implemented in `table_renderer._compute_counts_for_breakdown` (new private helper).

### Edge case — TABLE_WITH_MINIBARS + breakdown=general

The frontend filters the dropdown:
- `AddChartModal.tsx`: derive `chartTypes` from `styleGuide.available_chart_types`, then filter out `TABLE_WITH_MINIBARS` when `breakdownIds` is empty or contains only `"general"`.
- `ConfigPanel.tsx`: same filter on the per-chart chart_type dropdown — disable the option if the chart's `breakdown_id === "general"`.

This makes the invalid combination unselectable in UI. Backend has a defensive fallback: if a Chart with `breakdown_id == "general"` and `chart_type == "TABLE_WITH_MINIBARS"` somehow reaches the renderer (legacy project files), `_synthesize_table_element` logs a warning and the renderer falls back to chart-mode with `chart_type = "BAR_HORIZONTAL"`.

## Components changed

| File | Change |
|---|---|
| `backend/aurum_encuestas/pattern_renderer.py` | Add `_synthesize_table_element`. Call it inside `render_pattern` loop before dispatching `kind == "chart"` elements. |
| `backend/aurum_encuestas/element_renderers/table_renderer.py` | Audit `_render_segmented_breakdowns` for N=1. Add `_compute_counts_for_breakdown` helper. No structural rewrite. |
| `backend/aurum_encuestas/element_renderers/chart_renderer.py` | None (TABLE routing happens before chart_renderer is called). |
| `backend/aurum_encuestas/style_guide.py` | If `binary_with_demographics` cells defaults aren't already palette-role-based, swap hex literals for role names. |
| `frontend/src/pages/Editor/modals/AddChartModal.tsx` | Filter `TABLE_WITH_MINIBARS` from dropdown when no real breakdown selected. |
| `frontend/src/pages/Editor/ConfigPanel.tsx` | Same filter on per-chart chart_type dropdown. |
| `backend/tests/test_table_renderer.py` | New: `test_segmented_breakdowns_single_panel`. |
| `backend/tests/test_pattern_renderer.py` | New: `test_chart_with_table_type_routes_to_table_renderer`. |
| `frontend/tests/AddChartModal.test.tsx` | Append: TABLE_WITH_MINIBARS hidden when no breakdown picked. |

## Testing strategy

- **Backend unit**: `test_segmented_breakdowns_single_panel` builds an `EnrichedChart` with `all_breakdowns_data["edad"]` (2 cats × 2 options × {count,pct}), runs `table_renderer.render` directly with a synthesized element, asserts on `slide.shapes[0].has_table is True`, exactly 4 rows × 3 cols, group_header text == breakdown label, counts row values == sum of option counts.
- **Backend integration**: `test_chart_with_table_type_routes_to_table_renderer` builds a `SlideConfig` with one chart `chart_type="TABLE_WITH_MINIBARS"`, runs `pattern_renderer.render_pattern` with the `binary_general` pattern, asserts the resulting slide has `has_table` not `has_chart`.
- **Frontend**: 1 vitest case in `AddChartModal.test.tsx` — render the modal with no breakdown selected, query the dropdown options, assert `TABLE_WITH_MINIBARS` is absent.

## Open risks / out-of-scope follow-ups

- `_render_segmented_breakdowns` may have hidden assumptions about ≥2 breakdowns. The plan audits this in Step 1 and either confirms or adds a minimal N=1 branch.
- N-charts-grid pattern was sized for chart shapes (h_rel=0.74). Tables of identical bbox may look cramped — flag if visual review on real data shows it. Out-of-scope for this spec; addressable as a Minor adjustment later.
- "MAF Mayo 2026" deck never used this 1-panel layout (it stayed with chart per cat); the visual reference is the user-provided screenshot only. No corpus to validate against; visual diff post-merge is the verification.
