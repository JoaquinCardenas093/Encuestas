# Chart Catalog Overhaul — Fase A Design Spec

**Date:** 2026-06-19
**Status:** Approved (brainstorming) → ready for writing-plans
**Branch base:** `main` at `20becd1` (post-table-with-minibars merge)
**Phase:** A of 3 — schema + UI foundation for the new 5-type chart catalog. Render of grouped charts deferred to Fase B. OLE Excel-backed tables deferred to Fase C.

## Goal

Reduce the user-facing chart catalog from 10+ types down to a fixed family of 5: `PIE`, `PIE_GROUPED`, `BAR_HORIZONTAL`, `BAR_HORIZONTAL_GROUPED`, `TABLE_WITH_MINIBARS`. Replace `Chart.breakdown_id: str` with `Chart.breakdown_ids: list[str]` so a single chart can target multiple demographic dimensions. Add three new per-chart fields (`show_legend`, `grid_cols`, `title`) that Fase B will consume. Enforce a hard cut on legacy types and the legacy field — Pydantic rejects stored projects that carry either, with a clear migration message.

The user-visible behavior change in Fase A is intentionally minimal: dropdown now shows 3 chart types (Fase B unlocks the two `_GROUPED` variants), AddChartModal creates ONE `Chart` record per Apply (current single-breakdown-per-Chart fan-out goes away in favor of a list), and selecting 2+ real breakdowns auto-locks the chart_type to `TABLE_WITH_MINIBARS`. Rendering reuses today's pipeline: PIE/BAR_HORIZONTAL/TABLE_WITH_MINIBARS work as they do post-merge (single-panel for 1 breakdown, multi-panel for 2+, since `_render_segmented_breakdowns` already supports both).

## Non-Goals (deferred)

- **Fase B**: rendering of `PIE_GROUPED` (N-pie grid) and `BAR_HORIZONTAL_GROUPED` (clustered multi-series), visual tuning of multi-breakdown `TABLE_WITH_MINIBARS` to match the reference screenshots (img 12/13/18), UI for `show_legend`/`grid_cols`/`title`, legend rendering for tables (lateral left layout) and grouped bars (bottom).
- **Fase C**: OLE-embedded Excel under each `TABLE_WITH_MINIBARS` so the user can double-click to edit table data as a spreadsheet.
- This spec covers ONLY Fase A.

## Architecture overview

```
┌──────────────────────┐  schema  ┌──────────────────────┐
│ frontend types/index │ ◀──────▶ │ backend models.py    │
│   Chart interface    │          │   ChartType (5)      │
│   ChartType union    │          │   Chart fields       │
└─────────┬────────────┘          │   reject_legacy val. │
          │                       └──────────────────────┘
          │                                 ▲
          │                                 │
┌─────────▼────────────┐   addChart   ┌─────┴────────────┐
│ AddChartModal +      │ ─────────▶   │ project.ts store │
│ ConfigPanel          │   single     │   addChart(...)  │
│   - filter dropdown  │   record     └──────────────────┘
│   - auto-lock to     │
│     TABLE on ≥2 real │
│     breakdowns       │
└──────────────────────┘

backend render pipeline (unchanged shape, adapted to list):

  pattern_classifier.build_slide_config
     └─ EnrichedChart.breakdown_ids: list[str]
     └─ extract_chart_data(db_path, q, bds[0] or "general", ...)
  pattern_renderer.render_pattern
     └─ peek source_chart.chart_type == TABLE_WITH_MINIBARS AND
        any real bd in source_chart.breakdown_ids
        → synthesize {kind: table, structure: segmented_breakdowns,
                      data_source.breakdown_groups: real_bds}
     └─ dispatch chart_renderer | table_renderer
```

The schema is the contract; UI and renderer both adapt to the same `breakdown_ids: list[str]`. There is no compatibility shim — stored projects that still have `breakdown_id: str` or any removed `chart_type` value raise at load with a clear migration message (decisions Q-A1 hard fail + Q2 hard fail from grilling).

## Data model

### `backend/aurum_encuestas/models.py`

```python
from pydantic import BaseModel, Field, model_validator

ChartType = Literal[
    "PIE", "PIE_GROUPED",
    "BAR_HORIZONTAL", "BAR_HORIZONTAL_GROUPED",
    "TABLE_WITH_MINIBARS",
]

_ALLOWED_CHART_TYPES = {
    "PIE", "PIE_GROUPED",
    "BAR_HORIZONTAL", "BAR_HORIZONTAL_GROUPED",
    "TABLE_WITH_MINIBARS",
}


class Chart(BaseModel):
    id: str
    question_id: str
    breakdown_ids: list[str] = Field(default_factory=list)  # [] = general; 1 = single bd; 2+ = multi-bd
    chart_type: ChartType
    show_legend: bool = False
    grid_cols: int | None = None   # PIE_GROUPED only; None = auto (Fase B uses)
    title: str | None = None       # user override; None = no title
    colors: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _reject_legacy(cls, data):
        if not isinstance(data, dict):
            return data
        if "breakdown_id" in data:
            raise ValueError(
                "Chart.breakdown_id (str) was removed in 2026-06-19 catalog overhaul. "
                "Migrate to breakdown_ids: list[str]. "
                "Example: breakdown_id='edad' → breakdown_ids=['edad']; "
                "breakdown_id='general' → breakdown_ids=[]."
            )
        ct = data.get("chart_type")
        if ct is not None and ct not in _ALLOWED_CHART_TYPES:
            raise ValueError(
                f"chart_type {ct!r} was removed from the catalog. "
                f"Allowed types: {sorted(_ALLOWED_CHART_TYPES)}."
            )
        return data
```

`AnalysisScope`, `SlideType`, and all other model fields stay untouched.

### `frontend/src/types/index.ts`

```typescript
export type ChartType =
  | "PIE" | "PIE_GROUPED"
  | "BAR_HORIZONTAL" | "BAR_HORIZONTAL_GROUPED"
  | "TABLE_WITH_MINIBARS"

export interface Chart {
  id: string
  question_id: string
  breakdown_ids: string[]    // [] = general
  chart_type: ChartType
  show_legend: boolean       // default false; UI not exposed in Fase A
  grid_cols: number | null   // default null; UI not exposed in Fase A
  title: string | null       // default null; UI not exposed in Fase A
  colors: string[]
}
```

## Frontend behavior

### `frontend/src/store/project.ts`

Rename `addCharts(slideId, questionId, breakdownIds, chartType)` → `addChart(slideId, questionId, breakdownIds, chartType)`. Single `Chart` record per call:

```typescript
addChart(slideId, questionId, breakdownIds, chartType) {
  const newChart: Chart = {
    id: uid("ch"),
    question_id: questionId,
    breakdown_ids: breakdownIds,
    chart_type: chartType,
    show_legend: false,
    grid_cols: null,
    title: null,
    colors: [],
  }
  // append to slide.charts
}
```

The `multiSeries` parameter is already gone (previous merge). Color picker stays single-chart-scoped.

### `frontend/src/pages/Editor/modals/AddChartModal.tsx`

Derived state:
```typescript
const realBreakdownIds = Array.from(breakdownIds).filter((b) => b !== "general")
const nReal = realBreakdownIds.length

// chartType filter
const chartTypes = useMemo(() => {
  if (nReal === 0) {
    return allChartTypes.filter((t) => t !== "TABLE_WITH_MINIBARS")
  }
  if (nReal === 1) {
    return allChartTypes  // PIE + BAR_HORIZONTAL + TABLE_WITH_MINIBARS
  }
  // nReal >= 2 → only TABLE
  return ["TABLE_WITH_MINIBARS"]
}, [allChartTypes, nReal])

// auto-lock on 2+
useEffect(() => {
  if (!chartTypes.includes(chartType)) {
    setChartType(chartTypes[0] as ChartType)
  }
}, [chartTypes.join(","), chartType])
```

Dropdown is `disabled={nReal >= 2}` with a hint text `"Con 2+ breakdowns solo se permite tabla"`. Apply calls `addChart(slideId, questionId, realBreakdownIds, chartType)` — single record.

### `frontend/src/pages/Editor/ConfigPanel.tsx`

Per-chart row exposes:
- chart_type dropdown (same filter logic, scoped to that row's `chart.breakdown_ids`)
- breakdown_ids editor (multi-select checkbox list — adding the 2nd real breakdown auto-switches chart_type to TABLE_WITH_MINIBARS)
- color picker (unchanged)

`show_legend`, `grid_cols`, `title` are NOT exposed in Fase A UI. Schema carries them with their defaults; Fase B adds the inputs.

## Backend wiring

### `backend/aurum_encuestas/style_guide.py`

```python
# StyleGuide.available_chart_types default and BUILTIN_STYLE_GUIDE alike:
available_chart_types: list[str] = Field(
    default_factory=lambda: ["PIE", "BAR_HORIZONTAL", "TABLE_WITH_MINIBARS"],
)
```

Fase B adds `PIE_GROUPED` and `BAR_HORIZONTAL_GROUPED` to this list (the literal type already allows them — they just aren't surfaced to the UI dropdown).

### `backend/aurum_encuestas/style_guide_analyzer.py`

The existing repair logic drops unknown chart_type rather than rewriting (post Bug-#1 plan). Confirm the allowed set is read from `_ALLOWED_CHART_TYPES` or equivalent and matches Fase A. No behavioral change expected.

### `backend/aurum_encuestas/pattern_classifier.py`

```python
@dataclass
class EnrichedChart:
    id: str
    question_id: str
    breakdown_ids: list[str]   # was breakdown_id: str
    chart_type: str
    colors: list
    question: Any = None
    data: dict = field(default_factory=dict)
    all_breakdowns_data: dict = field(default_factory=dict)
    show_legend: bool = False
    grid_cols: int | None = None
    title: str | None = None
```

In `build_slide_config`:
```python
primary_bd = chart.breakdown_ids[0] if chart.breakdown_ids else "general"
chart_data = extract_chart_data(db_path, question, primary_bd, data_blocks)
```

`extract_all_breakdowns_data` still returns the full dict — no change.

`n_breakdowns` in classifier context should be derived from `len(chart.breakdown_ids)`, NOT from a string compare against `"general"`. Adjust the field extractor in `pattern_classifier._extract_field`.

### `backend/aurum_encuestas/data_extractor.py`

Signature unchanged (`extract_chart_data(db_path, question, breakdown_id, data_blocks)` still takes a single str). Callers pass the first element of the list.

### `backend/aurum_encuestas/element_renderers/chart_renderer.py`

`_build_chart_data` adapts:
```python
bds = getattr(source_chart, "breakdown_ids", []) or []
primary = bds[0] if bds else ""
is_general = (not primary) or primary.lower() == "general"
```

`_CHART_TYPE_MAP` gains defensive entries for the grouped types:
```python
"PIE_GROUPED":            XL_CHART_TYPE.PIE,             # fallback render
"BAR_HORIZONTAL_GROUPED": XL_CHART_TYPE.BAR_CLUSTERED,   # fallback render
```

with a log warning the first time each is invoked: `"chart_type X grouped render Fase B — emitting single-series fallback"`. The grouped types are not in `available_chart_types` for Fase A, so the UI cannot select them. The map entries exist only so a hand-crafted JSON does not crash.

### `backend/aurum_encuestas/element_renderers/table_renderer.py`

No changes. `_render_segmented_breakdowns` already supports both N=1 (single-panel branch from prior plan) and N≥2 (existing weight-packing multi-panel). Fase B will tune the multi-panel visual to match img 12/13/18; Fase A relies on the existing render output.

### `backend/aurum_encuestas/pattern_renderer.py`

Dispatch peek adapts to list:
```python
if kind == "chart":
    ds = element.get("data_source", {}) or {}
    ref_idx = ds.get("chart_ref_index", 0)
    charts_list = getattr(ctx.slide_config, "charts", []) or []
    if 0 <= ref_idx < len(charts_list):
        source_chart = charts_list[ref_idx]
        sc_chart_type = (getattr(source_chart, "chart_type", "") or "").strip()
        sc_bds = list(getattr(source_chart, "breakdown_ids", []) or [])
        sc_bds_real = [b for b in sc_bds if b and b.lower() != "general"]
        if sc_chart_type == "TABLE_WITH_MINIBARS" and sc_bds_real:
            element = _synthesize_table_element(element, source_chart)
            kind = "table"
```

`_synthesize_table_element` updates `breakdown_groups` to the full real list:
```python
def _synthesize_table_element(chart_el: dict, source_chart) -> dict:
    bds = [b for b in (getattr(source_chart, "breakdown_ids", []) or [])
           if b and b.lower() != "general"]
    return {
        "kind": "table",
        "id": chart_el.get("id"),
        "position": chart_el.get("position", {}),
        "structure": "segmented_breakdowns",
        "data_source": {
            "chart_ref_index": chart_el.get("data_source", {}).get("chart_ref_index", 0),
            "breakdown_groups": bds,
        },
    }
```

### `backend/aurum_encuestas/pptx_generator.py`

Legacy `_add_chart` reads `chart_def.breakdown_ids[0] if chart_def.breakdown_ids else None`. `is_general` becomes:
```python
primary_bd = chart_def.breakdown_ids[0] if chart_def.breakdown_ids else None
is_general = primary_bd in (None, "", "general")
```

The rest of `_add_chart` is single-series vs multi-series by length of `data` — unchanged.

## Migration / breaking changes

Per Q2 + Q-A1 (hard fail), no compatibility code paths. The `_reject_legacy` validator is the entire migration surface:
- Old JSON with `"breakdown_id": "edad"` → ValueError with migration example.
- Old JSON with `"chart_type": "BAR_CLUSTERED"` (or DONUT / COLUMN_* / LINE / AREA / RADAR / TABLE_SIMPLE / etc.) → ValueError with allowed list.

There is no auto-rewrite, no deprecation period, no warning-only mode. User is expected to edit their stored project JSON by hand or recreate the slides.

The `api/load-project` endpoint passes through the Pydantic error to the frontend, which surfaces a toast/modal: `"No se pudo cargar el proyecto: <error>"`. The user can open the JSON file under `~/.aurum/projects/<id>.json` and fix it.

## Testing strategy

Backend:
- `backend/tests/test_models.py`:
  - `test_chart_rejects_legacy_breakdown_id_field`: JSON with `breakdown_id` raises ValidationError mentioning `breakdown_ids: list[str]`.
  - `test_chart_rejects_removed_chart_type` (parametrize: DONUT, BAR_CLUSTERED, COLUMN_CLUSTERED, COLUMN_STACKED, BAR_STACKED, LINE, AREA, RADAR, TABLE_SIMPLE): each raises ValidationError mentioning the allowed list.
  - `test_chart_accepts_5_chart_types` (parametrize: PIE, PIE_GROUPED, BAR_HORIZONTAL, BAR_HORIZONTAL_GROUPED, TABLE_WITH_MINIBARS): parses cleanly.
  - `test_chart_accepts_empty_breakdown_ids`, `..._single`, `..._multi`: empty list / 1 / 2 strings all parse.
  - `test_chart_defaults_show_legend_false_grid_cols_none_title_none`.
- `backend/tests/test_pattern_classifier.py`:
  - `test_enriched_chart_has_breakdown_ids_list`: built EnrichedChart carries `breakdown_ids: list`, primary extracted to `data` via `extract_chart_data` with first element.
  - `test_n_breakdowns_derived_from_breakdown_ids_length`: trigger context shows correct n_breakdowns for [], ["edad"], ["edad","sexo"].
- `backend/tests/test_chart_renderer.py`:
  - `test_build_chart_data_empty_breakdown_ids_uses_general`.
  - `test_build_chart_data_single_breakdown_uses_first`.
  - `test_grouped_chart_type_falls_back_with_warning` (caplog asserts warning).
- `backend/tests/test_pattern_renderer.py`:
  - `test_table_dispatch_with_multi_breakdown_ids_passes_full_list`: `_synthesize_table_element` returns `breakdown_groups: ["edad","sexo"]` for input `breakdown_ids=["edad","sexo"]`.
  - Existing `test_chart_with_table_type_routes_to_table_renderer` adapted to use `breakdown_ids=["edad"]` instead of `breakdown_id="edad"`.
- `backend/tests/test_style_guide.py`:
  - `test_builtin_available_chart_types_phase_a_is_three`: list equals `["PIE", "BAR_HORIZONTAL", "TABLE_WITH_MINIBARS"]`.
- `backend/tests/test_table_renderer.py`: adapt existing single-panel test to use `breakdown_ids=["edad"]`; no behavioral change.
- `backend/tests/test_render_e2e.py`: adapt the existing TABLE_WITH_MINIBARS e2e to `breakdown_ids=["edad"]`.

Frontend:
- `frontend/tests/store.test.ts`:
  - `test_addChart_creates_one_chart_with_breakdown_ids_list`.
- `frontend/tests/AddChartModal.test.tsx`:
  - `test_no_breakdown_hides_TABLE_WITH_MINIBARS_from_dropdown`.
  - `test_one_real_breakdown_shows_three_types`.
  - `test_two_real_breakdowns_locks_dropdown_to_TABLE`.
  - `test_apply_creates_single_chart_with_breakdown_ids_array`.
- `frontend/tests/ConfigPanel.test.tsx`:
  - `test_per_chart_chart_type_filter_uses_chart_breakdown_ids`.
  - `test_adding_second_breakdown_in_configpanel_auto_switches_to_TABLE`.

Baseline: 255 backend + 116 frontend pass currently. Fase A adds ~15-18 tests; full suites stay green.

## File map

Created: none.

Modified backend:
- `backend/aurum_encuestas/models.py`
- `backend/aurum_encuestas/style_guide.py`
- `backend/aurum_encuestas/style_guide_analyzer.py` (verify only)
- `backend/aurum_encuestas/pattern_classifier.py`
- `backend/aurum_encuestas/element_renderers/chart_renderer.py`
- `backend/aurum_encuestas/pattern_renderer.py`
- `backend/aurum_encuestas/pptx_generator.py`
- `backend/tests/test_models.py`
- `backend/tests/test_pattern_classifier.py`
- `backend/tests/test_chart_renderer.py`
- `backend/tests/test_pattern_renderer.py`
- `backend/tests/test_style_guide.py`
- `backend/tests/test_table_renderer.py`
- `backend/tests/test_render_e2e.py`

Modified frontend:
- `frontend/src/types/index.ts`
- `frontend/src/store/project.ts`
- `frontend/src/pages/Editor/modals/AddChartModal.tsx`
- `frontend/src/pages/Editor/ConfigPanel.tsx`
- `frontend/tests/store.test.ts`
- `frontend/tests/AddChartModal.test.tsx`
- `frontend/tests/ConfigPanel.test.tsx`

## Open risks

1. **`addCharts` call-sites in frontend.** `grep -rn "addCharts(" frontend/src` from prior plan showed 3-4 callers (Editor, ConfigPanel actions). Plan must rename each. TypeScript compile is the safety net.
2. **`pattern_classifier._extract_field` for `n_breakdowns`.** If the current implementation reads a context key like `n_breakdowns` computed from `breakdown_id != "general"`, the field extractor must move to `len(chart.breakdown_ids)`. Plan verifies and rewrites.
3. **`style_guide_analyzer.py` auto-repair.** Prior plan changed it to DROP unknown chart_type. Confirm Fase A's allowed-set is sourced from a single constant (or reload `_ALLOWED_CHART_TYPES`) so removing types from `available_chart_types` doesn't accidentally let an AI-generated style guide carry a removed value.
4. **AI-generated style guides on disk.** `~/.aurum/training/style_guide.json` may reference removed chart_types. Loader path is `style_guide.load_active()` — same validator chain. Hard fail is acceptable here (user re-runs training analyzer with the new prompt).
5. **`addChart` parameter order.** The plan must name the new parameters explicitly to avoid mistaking `breakdownIds` (list) for an old `multiSeries` (bool). Use TypeScript's named-arg discipline at call-sites.
