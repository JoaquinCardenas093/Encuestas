# TABLE_WITH_MINIBARS per Breakdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the user picks `TABLE_WITH_MINIBARS` as `chart_type` for a `Chart` with `breakdown_id != "general"`, render a single-panel segmented table (group header + category header + counts row + option rows with minibars) instead of a chart shape. Each selected breakdown produces its own table; layout reuses the matched pattern's position (no new patterns).

**Architecture:** A small dispatch hook in `pattern_renderer.render_pattern` peeks at `slide_config.charts[chart_ref_index].chart_type` before invoking element_renderers; when the value is `TABLE_WITH_MINIBARS` it synthesizes a `kind: table, structure: segmented_breakdowns` element targeting just that one `breakdown_id` and routes to `table_renderer`. `_render_segmented_breakdowns` gains a single-panel codepath with image-faithful style overrides; `_set_cell` learns to accept raw hex so option rows can render white text. Frontend modals filter `TABLE_WITH_MINIBARS` out of the chart_type dropdown when no real breakdown is selected.

**Tech Stack:** Python 3.11 + python-pptx, pydantic v2 schemas, React + TypeScript + Zustand frontend, pytest + vitest.

## Global Constraints

- Backend Python target: `3.11`. Tests: `cd backend && arch -arm64 .venv/bin/pytest -q` from repo root.
- Frontend: vitest via `cd frontend && npm test -- --run`. TypeScript clean (`npx tsc --noEmit`).
- `BUILTIN_STYLE_GUIDE` stays pure-literal Python (no env reads).
- Existing palette role mapping in `color_resolver.build_render_context`: `role_names = ["primary","secondary","background","accent","dark","light"]` → palette indexes [0..5]. Palette is `["#7F7F7F","#404040","#EEC245","#C00000","#FFC000"]` (post-prior-plan Task 5). Effective role hexes: primary=#7F7F7F, secondary=#404040, background=#EEC245, accent=#C00000, dark=#FFC000, light=#7F7F7F (palette wraps via `idx % len`).
- Spanish UI strings stay in es-MX neutral tone.
- All hex literals in code must be `#RRGGBB` uppercase 7-char form.
- Slide dimensions: 12192000 × 6858000 EMU (unchanged from prior plan).
- TABLE_WITH_MINIBARS is already in `BUILTIN_STYLE_GUIDE.available_chart_types` (Task 5 of prior plan).
- Branch base: `main` at `bc385c0` (post-prior plan).

---

## File Structure

**Files modified, none created:**

| File | Responsibility | Touched in |
|---|---|---|
| `backend/aurum_encuestas/pattern_renderer.py` | Dispatch hook + `_synthesize_table_element` helper | Task 1 |
| `backend/aurum_encuestas/element_renderers/table_renderer.py` | N=1 single-panel branch + hex-text support + image-faithful style overrides | Task 2 |
| `frontend/src/pages/Editor/modals/AddChartModal.tsx` | Filter TABLE_WITH_MINIBARS from dropdown when no breakdown picked | Task 3 |
| `frontend/src/pages/Editor/ConfigPanel.tsx` | Same filter on per-chart chart_type dropdown | Task 3 |
| `backend/tests/test_pattern_renderer.py` | New: dispatch routes to table_renderer | Task 1 |
| `backend/tests/test_table_renderer.py` | New: single-panel render + counts + minibar config | Task 2 |
| `frontend/tests/AddChartModal.test.tsx` | New: TABLE_WITH_MINIBARS hidden when no breakdown | Task 3 |
| `backend/tests/test_render_e2e.py` | Append: end-to-end 1-breakdown table assertion | Task 4 |

---

### Task 1: Render-time dispatch hook in pattern_renderer

**Files:**
- Modify: `backend/aurum_encuestas/pattern_renderer.py:35-92` (render_pattern loop) — add `_synthesize_table_element` private helper and per-element peek
- Test: `backend/tests/test_pattern_renderer.py` — new test fn

**Interfaces:**
- Consumes: `slide_config.charts[i].chart_type`, `.breakdown_id` from `EnrichedChart` (already present).
- Produces: `_synthesize_table_element(chart_el: dict, source_chart) -> dict` — returns a `kind="table"` element with `structure="segmented_breakdowns"`, `breakdown_groups=[source_chart.breakdown_id]`, inheriting `id` and `position` from `chart_el`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pattern_renderer.py — append at end of file
def test_chart_with_table_type_routes_to_table_renderer():
    """When source_chart.chart_type == TABLE_WITH_MINIBARS, the dispatch hook
    must produce a table shape (has_table True) instead of a chart shape."""
    from pptx import Presentation
    from types import SimpleNamespace
    from aurum_encuestas.pattern_renderer import render_pattern
    from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE
    from aurum_encuestas.element_renderers.render_context import RenderContext

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    q = SimpleNamespace(options=["Sí", "No"])
    source_chart = SimpleNamespace(
        question=q,
        breakdown_id="edad",
        chart_type="TABLE_WITH_MINIBARS",
        colors=[],
        data={"General": {"Sí": {"pct": 0.92, "count": 460}, "No": {"pct": 0.08, "count": 40}}},
        all_breakdowns_data={
            "edad": {
                "label": "Rango de edad",
                "categories": {
                    "De 18 a 39 años": {"Sí": {"pct": 0.92, "count": 230}, "No": {"pct": 0.08, "count": 20}},
                    "De 40 a 59 años": {"Sí": {"pct": 0.912, "count": 228}, "No": {"pct": 0.088, "count": 22}},
                },
            },
        },
    )
    slide_config = SimpleNamespace(charts=[source_chart], analyses=[], n_charts=1)
    ctx = RenderContext(
        slide_config=slide_config,
        chart_colors=["#7F7F7F", "#404040", "#EEC245", "#C00000", "#FFC000"],
        resolved_colors={
            "primary": "#7F7F7F", "secondary": "#404040", "background": "#EEC245",
            "accent": "#C00000", "dark": "#FFC000", "light": "#7F7F7F",
        },
        free_area={"x": 487680, "y": 1097280, "cx": 11216640, "cy": 5212080},
        typography={"label_size": 9, "body_size": 10, "title_size": 16, "font_family": "Calibri"},
        style_guide=BUILTIN_STYLE_GUIDE,
        resolved_anchors={},
    )

    # binary_general matches: 1 chart, binary question, no breakdowns
    pattern = next(p for p in BUILTIN_STYLE_GUIDE.patterns if p.id == "binary_general")
    render_pattern(pattern, slide, ctx, BUILTIN_STYLE_GUIDE, list(BUILTIN_STYLE_GUIDE.patterns))

    has_table = any(sh.has_table for sh in slide.shapes)
    has_chart = any(sh.has_chart for sh in slide.shapes)
    assert has_table, f"expected a table shape, got shapes: {[str(sh.shape_type) for sh in slide.shapes]}"
    assert not has_chart, "expected NO chart shape when chart_type is TABLE_WITH_MINIBARS"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_pattern_renderer.py::test_chart_with_table_type_routes_to_table_renderer -v
```

Expected: FAIL — current `render_pattern` routes by `element["kind"]` only; `chart_type` is ignored.

- [ ] **Step 3: Add `_synthesize_table_element` helper and call site**

In `backend/aurum_encuestas/pattern_renderer.py`, after the `render_pattern` function block (or wherever helpers live — append near `resolve_position`), add:

```python
def _synthesize_table_element(chart_el: dict, source_chart) -> dict:
    """Convert a chart element to a single-panel segmented_breakdowns table.

    Called by render_pattern when source_chart.chart_type == TABLE_WITH_MINIBARS.
    Inherits id/position from the original chart element so layout stays
    pattern-driven; targets only the source_chart's own breakdown_id.
    """
    bd_id = getattr(source_chart, "breakdown_id", None)
    return {
        "kind": "table",
        "id": chart_el.get("id"),
        "position": chart_el.get("position", {}),
        "structure": "segmented_breakdowns",
        "data_source": {
            "chart_ref_index": chart_el.get("data_source", {}).get("chart_ref_index", 0),
            "breakdown_groups": [bd_id] if bd_id and bd_id.lower() != "general" else [],
        },
    }
```

Then in the `render_pattern` function, inside the `for element in ordered_elements:` loop, add a peek before `renderer_module_path = _KIND_RENDERERS.get(kind)`. Find the existing loop body (around line 59-72) — currently:

```python
    for element in ordered_elements:
        kind = element.get("kind")
        renderer_module_path = _KIND_RENDERERS.get(kind)
```

Replace with:

```python
    for element in ordered_elements:
        kind = element.get("kind")
        # Render-time chart_type peek: if the source chart's chart_type is
        # TABLE_WITH_MINIBARS, synthesize a single-panel segmented table
        # element instead of a chart. Layout stays pattern-driven.
        if kind == "chart":
            ds = element.get("data_source", {}) or {}
            ref_idx = ds.get("chart_ref_index", 0)
            charts_list = getattr(ctx.slide_config, "charts", []) or []
            if 0 <= ref_idx < len(charts_list):
                source_chart = charts_list[ref_idx]
                sc_chart_type = (getattr(source_chart, "chart_type", "") or "").strip()
                sc_bd = (getattr(source_chart, "breakdown_id", "") or "").lower()
                if sc_chart_type == "TABLE_WITH_MINIBARS" and sc_bd and sc_bd != "general":
                    element = _synthesize_table_element(element, source_chart)
                    kind = "table"
        renderer_module_path = _KIND_RENDERERS.get(kind)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_pattern_renderer.py::test_chart_with_table_type_routes_to_table_renderer -v
```

Expected: PASS.

- [ ] **Step 5: Run pattern_renderer test file to confirm no regression**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_pattern_renderer.py -v
```

Expected: all tests in file pass (previous tests stay green; new one passes).

- [ ] **Step 6: Commit**

```bash
git add backend/aurum_encuestas/pattern_renderer.py backend/tests/test_pattern_renderer.py
git commit -m "feat(render): route chart_type=TABLE_WITH_MINIBARS to table_renderer

pattern_renderer.render_pattern now peeks at source_chart.chart_type
before dispatching kind=chart elements. When it equals TABLE_WITH_MINIBARS
and breakdown_id != 'general', the element is synthesized into a
kind=table, structure=segmented_breakdowns element targeting only that
breakdown. Layout (position/size) stays pattern-driven.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Single-panel `_render_segmented_breakdowns` + hex-text `_set_cell`

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/table_renderer.py:87-136` (`_set_cell`) — accept raw `#RRGGBB` hex in `text_color`/`fill`
- Modify: `backend/aurum_encuestas/element_renderers/table_renderer.py:143-295` (`_render_segmented_breakdowns`) — add N=1 single-panel branch with image-faithful style overrides
- Test: `backend/tests/test_table_renderer.py` — new test fn `test_segmented_breakdowns_single_panel_image_style`

**Interfaces:**
- Consumes (from Task 1): synthesized element with `breakdown_groups=[bd_id]` (list of length 1).
- Produces: `_render_segmented_breakdowns` renders a single 4-row × 3-col mini-table with `group_header`, `category_header`, `counts_row`, and 2 `option_row`s for a binary question with a 2-category breakdown. Counts row = sum of option counts per category.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_table_renderer.py — create file (or append if exists)
import pytest
from pptx import Presentation
from types import SimpleNamespace

from aurum_encuestas.element_renderers.table_renderer import render
from aurum_encuestas.element_renderers.render_context import RenderContext


@pytest.fixture
def edad_chart():
    q = SimpleNamespace(options=["Sí", "No"])
    return SimpleNamespace(
        question=q,
        breakdown_id="edad",
        chart_type="TABLE_WITH_MINIBARS",
        colors=[],
        data={},
        all_breakdowns_data={
            "edad": {
                "label": "Rango de edad",
                "categories": {
                    "De 18 a 39 años": {"Sí": {"pct": 0.92, "count": 230}, "No": {"pct": 0.08, "count": 20}},
                    "De 40 a 59 años": {"Sí": {"pct": 0.912, "count": 228}, "No": {"pct": 0.088, "count": 22}},
                },
            },
        },
    )


@pytest.fixture
def render_ctx(edad_chart):
    slide_config = SimpleNamespace(charts=[edad_chart], analyses=[], n_charts=1)
    return RenderContext(
        slide_config=slide_config,
        chart_colors=["#7F7F7F", "#404040", "#EEC245", "#C00000", "#FFC000"],
        resolved_colors={
            "primary": "#7F7F7F", "secondary": "#404040", "background": "#EEC245",
            "accent": "#C00000", "dark": "#FFC000", "light": "#7F7F7F",
        },
        free_area={"x": 487680, "y": 1097280, "cx": 11216640, "cy": 5212080},
        typography={"label_size": 9, "body_size": 10, "title_size": 16, "font_family": "Calibri"},
        style_guide=None,
        resolved_anchors={},
    )


def test_segmented_breakdowns_single_panel_image_style(render_ctx):
    """Single breakdown → 1 mini-table with 5 rows × 3 cols:
    group_header / category_header / counts_row / Sí option_row / No option_row."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    element = {
        "kind": "table",
        "id": "edad_table",
        "position": {"x_rel": 0.17, "y_rel": 0.20, "w_rel": 0.65, "h_rel": 0.65},
        "structure": "segmented_breakdowns",
        "data_source": {"chart_ref_index": 0, "breakdown_groups": ["edad"]},
    }
    render(slide, element, render_ctx)

    tables = [sh for sh in slide.shapes if sh.has_table]
    assert len(tables) == 1, f"expected 1 table, got {len(tables)}"
    tbl = tables[0].table
    rows = list(tbl.rows)
    assert len(rows) == 5, f"expected 5 rows (group/cat/counts/Sí/No), got {len(rows)}"
    cols = list(tbl.columns)
    assert len(cols) == 3, f"expected 3 cols (label + 2 cats), got {len(cols)}"

    # group_header row should contain "Rango de edad"
    group_texts = [tbl.cell(0, c).text_frame.text for c in range(3)]
    assert any("Rango de edad" in t for t in group_texts), f"group_header missing label: {group_texts}"

    # category_header row should contain both category labels
    cat_texts = [tbl.cell(1, c).text_frame.text for c in range(3)]
    assert "De 18 a 39 años" in cat_texts
    assert "De 40 a 59 años" in cat_texts

    # counts_row: cells [1] and [2] should be 250 (230+20) and 250 (228+22)
    assert tbl.cell(2, 1).text_frame.text.strip() == "250", f"counts col1: {tbl.cell(2,1).text_frame.text!r}"
    assert tbl.cell(2, 2).text_frame.text.strip() == "250", f"counts col2: {tbl.cell(2,2).text_frame.text!r}"

    # option_row "Sí": label col then values with % suffix
    assert tbl.cell(3, 0).text_frame.text.strip() == "Sí"
    assert "92.0%" in tbl.cell(3, 1).text_frame.text
    assert "91.2%" in tbl.cell(3, 2).text_frame.text

    # option_row "No"
    assert tbl.cell(4, 0).text_frame.text.strip() == "No"
    assert "8.0%" in tbl.cell(4, 1).text_frame.text
    assert "8.8%" in tbl.cell(4, 2).text_frame.text
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_table_renderer.py::test_segmented_breakdowns_single_panel_image_style -v
```

Expected: FAIL — current `_render_segmented_breakdowns` uses pattern cells_cfg which doesn't match image styling AND existing `_render_panel` already handles N≥1 but row counts/values may differ. The exact failure tells us what to fix.

- [ ] **Step 3: Extend `_set_cell` to accept raw hex literals**

Find `_set_cell` in `backend/aurum_encuestas/element_renderers/table_renderer.py` (around line 87-136). Replace the `text_color_role` resolution block and the `fill_role` block with versions that accept either a hex string or a role name:

```python
    text_color_role = style.get("text_color", "primary")
    if isinstance(text_color_role, str) and text_color_role.startswith("#"):
        hex_text = text_color_role
    else:
        hex_text = ctx.resolved_colors.get(text_color_role, "#000000")
    try:
        run.font.color.rgb = RGBColor.from_string(hex_text.lstrip("#"))
    except Exception:
        pass

    fill_role = style.get("fill")
    if fill_role:
        if isinstance(fill_role, str) and fill_role.startswith("#"):
            fill_hex = fill_role
        else:
            fill_hex = ctx.resolved_colors.get(fill_role)
        if fill_hex:
            try:
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor.from_string(fill_hex.lstrip("#"))
            except Exception:
                pass
```

- [ ] **Step 4: Add single-panel branch in `_render_segmented_breakdowns`**

In `_render_segmented_breakdowns`, after `panels` is materialized (around line 211 — right after `if not panels: ... return`), insert:

```python
    # Single-panel image-style mode: when only ONE breakdown was requested,
    # render a single, centered, image-faithful mini-table (matches the
    # 'Rango de edad' reference screenshot). Overrides the multi-panel
    # weight-packing logic below.
    if len(panels) == 1:
        only = panels[0]
        # Image-faithful style overrides (palette role names map to:
        #   primary=#7F7F7F mid grey, secondary=#404040 dark, background=#EEC245 yellow)
        single_group_hdr = {
            "style": {"fill": "secondary", "text_color": "background", "font_size": 11, "bold": True, "align_h": "center"},
        }
        single_cat_hdr = {
            "style": {"fill": "primary", "text_color": "background", "font_size": 10, "bold": True, "align_h": "center"},
        }
        single_counts = {
            "style": {"fill": "primary", "text_color": "background", "font_size": 11, "bold": True, "align_h": "center"},
            "label_first_col": "",
        }
        single_option = {
            "style": {"fill": "primary", "text_color": "#FFFFFF", "font_size": 10, "align_h": "left"},
            "label_style": {"fill": "primary", "text_color": "#FFFFFF", "font_size": 11, "bold": True, "align_h": "center"},
            "label_col_width_rel": 0.18,
            "value_format": "percentage",
            "value_decimals": 1,
            "minibar": {
                "enabled": True,
                "color_role": "secondary",
                "height_rel_to_cell": 0.25,
                "show_percent_text": True,
                "percent_text_position": "left_of_bar",
            },
        }
        _render_panel(
            slide=slide,
            panel=only,
            options=options,
            x=box_x, y=box_y, cx=box_cx, cy=box_cy,
            ctx=ctx,
            group_hdr_cfg=single_group_hdr,
            cat_hdr_cfg=single_cat_hdr,
            counts_cfg=single_counts,
            option_cfg=single_option,
            matching_chart=None,
        )
        return
```

> Note: the value of `counts_row` per category is computed inside `_render_panel`. If the existing implementation sums option counts per category (sum of `count` over options) into the counts cell, no further change is needed. If it uses `sample_size` / fixed labels (e.g. "Observaciones"), Step 5 fixes that.

- [ ] **Step 5: Verify counts-row computation, patch if needed**

Read `_render_panel` (look for `counts_row` cell writes — search for `counts_cfg` and the row index that draws counts). If the existing code writes counts as `bd_count` or similar from `bd.get("counts_per_cat")`, change it to sum from data:

```python
# Inside _render_panel where counts row is rendered:
for col_idx, (cat_label, opt_cells) in enumerate(cats, start=1):
    cat_count = sum(int((cell or {}).get("count") or 0) for cell in opt_cells.values())
    counts_text = str(cat_count) if cat_count else ""
    _set_cell(tbl.cell(counts_row_idx, col_idx), counts_text, ctx, counts_style)
```

If the existing logic already sums counts correctly, skip Step 5 — note it in your report so the reviewer doesn't expect a diff hunk.

- [ ] **Step 6: Run test to verify it passes**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_table_renderer.py::test_segmented_breakdowns_single_panel_image_style -v
```

Expected: PASS. If it fails on a single assertion (e.g. counts text empty), patch _render_panel per Step 5. If it fails on row/col count, the existing `_render_panel` uses different `N_HEADER_ROWS` — confirm 3 (group + cat + counts).

- [ ] **Step 7: Run full table_renderer test file**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_table_renderer.py -v
```

Expected: all tests pass; multi-breakdown tests must NOT regress (the single-panel branch only fires when `len(panels) == 1`).

- [ ] **Step 8: Run integration test from Task 1**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_pattern_renderer.py::test_chart_with_table_type_routes_to_table_renderer -v
```

Expected: PASS. The end-to-end routing (Task 1) + single-panel render (Task 2) work together.

- [ ] **Step 9: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/table_renderer.py backend/tests/test_table_renderer.py
git commit -m "feat(table): single-panel mode for segmented_breakdowns + hex-color cells

When _render_segmented_breakdowns receives exactly one breakdown_group,
it now renders a single image-faithful mini-table (group_header + cat
header + counts row + option rows with minibars) instead of running the
multi-panel weight-packing code path. _set_cell accepts both palette
role names and raw #RRGGBB hex so option rows can render white text.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Frontend filter TABLE_WITH_MINIBARS when no breakdown picked

**Files:**
- Modify: `frontend/src/pages/Editor/modals/AddChartModal.tsx` — derive filtered chartTypes list
- Modify: `frontend/src/pages/Editor/ConfigPanel.tsx` — same filter for per-chart edit
- Test: `frontend/tests/AddChartModal.test.tsx` — new vitest assertion

**Interfaces:**
- Consumes: `breakdownIds: Set<string>` state already in AddChartModal; `chart.breakdown_id` already on each Chart record.
- Produces: derived `availableChartTypes` excluding `TABLE_WITH_MINIBARS` when no real breakdown is in scope.

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/tests/AddChartModal.test.tsx — append after existing tests
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import AddChartModal from '../src/pages/Editor/modals/AddChartModal'

describe('AddChartModal — TABLE_WITH_MINIBARS visibility', () => {
  const baseDb = {
    questions: [{ id: 'q1', code: 'Q1', text: 'Test', options: ['Sí', 'No'], confidence: 0.9 }],
    breakdowns: [
      { id: 'general', label: 'General', categories: ['Total'] },
      { id: 'edad', label: 'Rango de edad', categories: ['18-39', '40-59'] },
    ],
    sample_size: 500,
    data_blocks: { counts_cols: [], pct_row_cols: [], pct_col_cols: [] },
  }

  it('hides TABLE_WITH_MINIBARS when no breakdown is selected', () => {
    render(<AddChartModal open={true} onClose={() => {}} onApply={() => {}} db={baseDb as any} />)
    const dropdown = screen.getByLabelText(/Tipo de chart/i) as HTMLSelectElement
    const optionTexts = Array.from(dropdown.options).map((o) => o.value)
    expect(optionTexts).not.toContain('TABLE_WITH_MINIBARS')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- --run tests/AddChartModal.test.tsx 2>&1 | tail -15
```

Expected: FAIL — current dropdown includes all `styleGuide.available_chart_types`, which now contains TABLE_WITH_MINIBARS.

- [ ] **Step 3: Filter chartTypes in AddChartModal**

Open `frontend/src/pages/Editor/modals/AddChartModal.tsx`. Find the `chartTypes` derivation (around lines 27-29):

```typescript
  const chartTypes = styleGuide?.available_chart_types?.length
    ? styleGuide.available_chart_types
    : BUILTIN_CHART_TYPES
```

Replace with:

```typescript
  const allChartTypes = styleGuide?.available_chart_types?.length
    ? styleGuide.available_chart_types
    : BUILTIN_CHART_TYPES
  const hasRealBreakdown = Array.from(breakdownIds).some((bid) => bid !== 'general')
  const chartTypes = hasRealBreakdown
    ? allChartTypes
    : allChartTypes.filter((t) => t !== 'TABLE_WITH_MINIBARS')
```

Then update the `useEffect` that syncs `chartType` (around lines 42-44) so it also re-runs when `breakdownIds` changes (`chartTypes` derived value changes too — already covered by `chartTypes.join(",")` dep, but `hasRealBreakdown` change must propagate):

```typescript
  useEffect(() => {
    if (!chartTypes.includes(chartType)) {
      setChartType((chartTypes[0] ?? "PIE") as ChartType)
    }
  }, [chartTypes.join(","), chartType])
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm test -- --run tests/AddChartModal.test.tsx 2>&1 | tail -10
```

Expected: PASS for the new test plus all existing AddChartModal tests.

- [ ] **Step 5: Apply same filter to ConfigPanel.tsx**

Open `frontend/src/pages/Editor/ConfigPanel.tsx`. Search for the per-chart `chart_type` `<select>` (likely uses the same `available_chart_types` list). The component renders one row per existing chart, each with a chart_type dropdown.

Find the chart_type dropdown block. Wrap the options list with the same filter, scoped per-chart:

```tsx
{slide.charts.map((chart) => {
  const hasRealBreakdown = chart.breakdown_id !== 'general'
  const chartTypeOptions = hasRealBreakdown
    ? CHART_TYPES
    : CHART_TYPES.filter((t) => t !== 'TABLE_WITH_MINIBARS')
  return (
    // ...existing JSX...
    <select value={chart.chart_type} onChange={(e) => updateChartType(chart.id, e.target.value)}>
      {chartTypeOptions.map((t) => <option key={t} value={t}>{t}</option>)}
    </select>
    // ...
  )
})}
```

(Adapt to the actual JSX shape — if `CHART_TYPES` is named differently, use whatever the file's existing constant is. The transformation is: filter the options array conditionally per chart.)

- [ ] **Step 6: Verify TypeScript compile**

```bash
cd frontend && npx tsc --noEmit 2>&1 | tail -10
```

Expected: clean (no errors).

- [ ] **Step 7: Run full frontend suite**

```bash
cd frontend && npm test -- --run 2>&1 | tail -10
```

Expected: all tests pass (115 + 1 new = 116).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/Editor/modals/AddChartModal.tsx \
        frontend/src/pages/Editor/ConfigPanel.tsx \
        frontend/tests/AddChartModal.test.tsx
git commit -m "feat(ui): hide TABLE_WITH_MINIBARS when no real breakdown selected

AddChartModal and ConfigPanel filter TABLE_WITH_MINIBARS out of the
chart_type dropdown when the chart's breakdown_id is empty or 'general'.
TABLE_WITH_MINIBARS only makes sense when there is at least one real
demographic dimension to render category columns for.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: End-to-end render regression

**Files:**
- Modify: `backend/tests/test_render_e2e.py` — append a second e2e test that exercises the TABLE_WITH_MINIBARS path

**Interfaces:**
- Consumes: everything from Tasks 1-3.
- Produces: an integration assertion that the full pipeline from a `Chart(chart_type="TABLE_WITH_MINIBARS", breakdown_id="<real>")` record produces a table shape, not a chart shape.

- [ ] **Step 1: Append new test**

In `backend/tests/test_render_e2e.py`, after the existing test, append:

```python
def test_e2e_table_with_minibars_renders_single_panel_table(tmp_path):
    """End-to-end: a Chart with chart_type=TABLE_WITH_MINIBARS and breakdown_id=edad
    flows through build_pptx and produces a table shape on the rendered slide."""
    from pptx import Presentation
    from pptx.util import Inches
    from aurum_encuestas.pptx_generator import build_pptx
    from aurum_encuestas.models import (
        ProjectState, ProjectInputs, Slide, Chart, ParsedDB, Question, Breakdown,
    )

    # Synthetic template with one shell slide
    tpl = tmp_path / "tpl.pptx"
    p = Presentation()
    p.slide_width = Inches(13.33)
    p.slide_height = Inches(7.5)
    s = p.slides.add_slide(p.slide_layouts[6])
    s.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(12), Inches(0.6)).text_frame.text = "@Titulo"
    p.save(str(tpl))

    parsed = ParsedDB(
        questions=[Question(id="q1", code="Q1", text="¿Cliente actual?", options=["Sí", "No"], confidence=0.95)],
        breakdowns=[
            Breakdown(id="general", label="General", categories=["Total"]),
            Breakdown(id="edad", label="Rango de edad", categories=["De 18 a 39 años", "De 40 a 59 años"]),
        ],
        sample_size=500,
        data_blocks={"counts_cols": [], "pct_row_cols": [], "pct_col_cols": []},
    )

    state = ProjectState(
        project_name="e2e-table",
        inputs=ProjectInputs(db_path="", template_path=str(tpl)),
        parsed_db=parsed,
        slides=[
            Slide(
                id="s1", type="shell", title="Demografía",
                charts=[Chart(id="c1", question_id="q1", breakdown_id="edad",
                              chart_type="TABLE_WITH_MINIBARS", colors=[])],
                analyses=[],
            ),
        ],
    )

    out = tmp_path / "out.pptx"
    build_pptx(state, str(out))

    prs = Presentation(str(out))
    slides_with_tables = [s for s in prs.slides if any(sh.has_table for sh in s.shapes)]
    assert slides_with_tables, "expected at least one table shape rendered"
    slides_with_charts = [s for s in prs.slides if any(sh.has_chart for sh in s.shapes)]
    assert not slides_with_charts, "expected NO chart shape (TABLE_WITH_MINIBARS routes to table)"
```

- [ ] **Step 2: Run new test**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_render_e2e.py::test_e2e_table_with_minibars_renders_single_panel_table -v
```

Expected: PASS. If `build_pptx` fails to extract data because `db_path=""` is invalid for `extract_chart_data`, the chart will have empty `data` and `all_breakdowns_data`. The renderer should still produce a table (with empty/zero cells) — not skip the whole element. If the test fails because the renderer skips on empty data, that's a latent issue worth flagging in the report; the spec acceptance is that the table shape is created, not that it has correct values.

If the test fails on data loading, modify the test to monkeypatch `extract_chart_data` and `extract_all_breakdowns_data` to return synthetic dicts directly:

```python
def test_e2e_table_with_minibars_renders_single_panel_table(tmp_path, monkeypatch):
    # ... template + parsed setup ...
    def fake_extract(*args, **kwargs):
        return {"General": {"Sí": {"pct": 0.92, "count": 460}, "No": {"pct": 0.08, "count": 40}}}
    def fake_extract_all(*args, **kwargs):
        return {"edad": {"label": "Rango de edad", "categories": {
            "De 18 a 39 años": {"Sí": {"pct": 0.92, "count": 230}, "No": {"pct": 0.08, "count": 20}},
            "De 40 a 59 años": {"Sí": {"pct": 0.912, "count": 228}, "No": {"pct": 0.088, "count": 22}},
        }}}
    monkeypatch.setattr("aurum_encuestas.data_extractor.extract_chart_data", fake_extract)
    monkeypatch.setattr("aurum_encuestas.data_extractor.extract_all_breakdowns_data", fake_extract_all)
    # ... rest of test
```

Use the monkeypatched variant if needed.

- [ ] **Step 3: Run full backend suite**

```bash
cd backend && arch -arm64 .venv/bin/pytest -q 2>&1 | tail -5
```

Expected: 254 passed (252 prior + 2 new) / 3 skipped (or 2 skipped if the e2e test now PASSes with monkeypatch — adjust the prior `test_e2e_three_breakdown_demographics_slide` is still skipif-guarded by xlsx presence).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_render_e2e.py
git commit -m "test(e2e): TABLE_WITH_MINIBARS chart_type renders a table shape

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Spec coverage:**
  - Render-time dispatch hook → Task 1 ✅
  - `_synthesize_table_element` helper → Task 1 ✅
  - Single-panel `_render_segmented_breakdowns` branch → Task 2 ✅
  - `_set_cell` accepts raw hex → Task 2 Step 3 ✅
  - Counts-row source (sum of option counts) → Task 2 Step 5 ✅ (conditional)
  - Color sourcing via palette roles (with `background` mapping to yellow per existing code) → Task 2 Step 4 ✅
  - UI dropdown filter (AddChartModal + ConfigPanel) → Task 3 ✅
  - Tests: backend unit + integration + frontend filter + e2e → Tasks 1/2/3/4 ✅
- **Placeholder scan:** No "TBD" / "implement later" / "similar to Task N" without code. All steps carry concrete commands and code blocks.
- **Type consistency:** `_synthesize_table_element` signature stable across Tasks 1 and 2 (Task 2 doesn't reference it). `Chart.breakdown_id` field is the same `str` throughout. `EnrichedChart.all_breakdowns_data` schema (`{bd_id: {label, categories: {cat: {opt: {count, pct}}}}}`) matches between the Task 2 fixture and the Task 4 monkeypatch return value.
- **Open risks:**
  - `_render_panel`'s existing counts-row logic may already write the label `"Observaciones"` in column 0 instead of leaving it blank. The single-panel override sets `label_first_col=""` to suppress it — verify by reading `_render_panel` in Task 2 Step 4 before patching.
  - `ConfigPanel.tsx` may use a different constant name than `CHART_TYPES`; Task 3 Step 5 instructs the implementer to adapt. The actual constant is derivable from `useStyleGuideStore` or imported from a shared module — `grep -n "available_chart_types\|CHART_TYPES" frontend/src/pages/Editor/ConfigPanel.tsx` to locate.
  - The Task 2 test asserts text strings like `"92.0%"` and `"De 18 a 39 años"`. If `_set_cell` strips Unicode normalization or `_render_panel` uses a different decimal format, adjust the assertions accordingly — the implementer can relax `==` to `in` if format drifts.
