# Fix Chart-Type / Breakdown-Split / Layout + PPTX Training Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make chart_type fully user-selectable (UI wins), split each breakdown into a separate chart (no multi-series merging), fix general slide layout to match Aurora reference proportions, and bake real Aurora/MAF training data into both `BUILTIN_STYLE_GUIDE` patterns and the LLM layout system prompt.

**Architecture:** Bugs all live in the render pipeline `pattern_classifier → pattern_renderer → chart_renderer → pptx_generator`. We fix the pipeline so (a) `source_chart.chart_type` from the UI overrides any pattern-side `chart_type`, (b) each `Chart` record is rendered as a single-series chart for its own `breakdown_id` (multi_series feature is removed), and (c) pattern positions match the EMU geometry observed in the Aurora reference deck. Training is hardened by updating the built-in style guide palette and adding few-shot examples to the LLM layout prompt.

**Tech Stack:** Python 3.11 + python-pptx for backend rendering, pydantic v2 schemas, FastAPI for `/api/*`, React + TypeScript + Zustand for frontend, pytest + Playwright for tests.

## Global Constraints

- Backend Python target: `3.11`. Backend tests run via `pytest backend/tests -q` from repo root.
- Frontend Node: `>=18`. Frontend tests run via `pnpm test` from `frontend/`. Component tests use vitest.
- All Spanish-facing strings must stay in es-MX neutral tone (matches existing prompts).
- `BUILTIN_STYLE_GUIDE` must remain pure-literal Python (no env reads, no dynamic data) — it is loaded at import time.
- python-pptx `XL_CHART_TYPE` integer values: PIE=5, DOUGHNUT=?, BAR_CLUSTERED=57, BAR_HORIZONTAL ≡ BAR_CLUSTERED in our map, COLUMN_CLUSTERED=51.
- Slide dimensions in target template: `12192000 x 6858000 EMU` (= 13.33" × 7.5"); `free_area` height is typically `~6,200,000 EMU` after subtracting top title band and bottom notes band.
- Aurora reference colors (verbatim from `PPT Aurora ejemplo.pptx`): PIE highlight palette `["#C00000", "#FFC000"]`, BAR neutral `["#595959"]`.
- MAF observed palette (verbatim from `Aurum - Encuestas - Precancelaciones - MAF - Mayo 2026.pptx`): grey-emphasis `["#7F7F7F","#404040","#EEC245"]` with last bar highlighted yellow.
- Pattern matching is cached via `pattern_classifier._cache` — clear cache (`clear_cache()`) when modifying `BUILTIN_STYLE_GUIDE` in tests.
- Frontend `ChartType` literal must stay in sync with backend `models.py` `ChartType`.

---

## File Structure

**New files:** none. All work modifies existing modules.

**Modified files (per task):**

| File | Responsibility | Touched in |
|---|---|---|
| `backend/aurum_encuestas/element_renderers/chart_renderer.py` | Single source of truth for chart rendering (XL_CHART_TYPE, labels, position) | Task 1, Task 2 |
| `backend/aurum_encuestas/style_guide.py` | Pattern schema + `BUILTIN_STYLE_GUIDE` (5 baseline patterns) | Task 1, Task 3, Task 4, Task 5 |
| `backend/aurum_encuestas/style_guide_analyzer.py` | Auto-repair of AI-generated style guides | Task 1 |
| `backend/aurum_encuestas/pattern_classifier.py` | Trigger evaluation + pattern matching | Task 4 |
| `backend/aurum_encuestas/pattern_renderer.py` | Element fan-out + position resolution | Task 4 |
| `backend/aurum_encuestas/pptx_generator.py` | Legacy `_add_chart` path + CHART_TYPE_MAP fallback | Task 2 |
| `backend/aurum_encuestas/models.py` | `Chart` model (kill `multi_series`) | Task 2 |
| `backend/aurum_encuestas/llm_client.py` | `LAYOUT_SYSTEM` prompt + few-shot examples | Task 6 |
| `frontend/src/pages/Editor/modals/AddChartModal.tsx` | Drop multi_series checkbox | Task 2 |
| `frontend/src/store/project.ts` | `addCharts()` signature (drop multiSeries param) | Task 2 |
| `frontend/src/types/index.ts` | `Chart` interface (drop `multi_series`) | Task 2 |
| `backend/tests/test_element_renderers.py` | Regression: UI chart_type override + per-breakdown rendering | Task 1, Task 2, Task 7 |
| `backend/tests/test_pattern_classifier.py` | Test 3-chart pattern triggers | Task 4 |

---

### Task 1: Bug #1 — `source_chart.chart_type` overrides pattern chart_type

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/chart_renderer.py:45-70`
- Modify: `backend/aurum_encuestas/style_guide.py` — make `ElementChart.chart_type` optional (`str | None = None`)
- Modify: `backend/aurum_encuestas/style_guide.py` — strip `"chart_type": "..."` from the 5 patterns in `BUILTIN_STYLE_GUIDE` (lines 331, 364, 429, 461, 488, 509)
- Modify: `backend/aurum_encuestas/style_guide_analyzer.py:306` — remove auto-repair `→ "BAR_HORIZONTAL"` fallback
- Test: `backend/tests/test_element_renderers.py` (new test fn)

**Interfaces:**
- Consumes: `EnrichedChart.chart_type: str` (from `pattern_classifier.build_slide_config`)
- Produces: `chart_renderer.render(slide, element, ctx)` now reads `source_chart.chart_type` first, falls back to `element["chart_type"]`, then to `"BAR_HORIZONTAL"` as last resort (kept for backwards-compat with legacy specs).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_element_renderers.py — append after existing tests
def test_render_chart_respects_source_chart_chart_type(tmp_path):
    """UI-selected chart_type must override the pattern's chart_type."""
    from pptx import Presentation
    from aurum_encuestas.element_renderers.chart_renderer import render
    from aurum_encuestas.element_renderers.render_context import RenderContext
    from types import SimpleNamespace

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    q = SimpleNamespace(options=["Sí", "No"])
    source_chart = SimpleNamespace(
        question=q,
        data={"General": {"Sí": {"pct": 0.6, "count": 60}, "No": {"pct": 0.4, "count": 40}}},
        chart_type="COLUMN_CLUSTERED",  # ← UI choice
        colors=[],
    )
    slide_config = SimpleNamespace(charts=[source_chart])
    ctx = RenderContext(
        slide_config=slide_config,
        chart_colors=["#7F7F7F"],
        free_area={"x": 0, "y": 0, "cx": 6_000_000, "cy": 4_000_000},
        typography={"label_size": 9},
        resolved_anchors={},
    )

    element = {
        "kind": "chart", "id": "main_pie",
        "chart_type": "PIE",  # ← pattern said PIE
        "position": {"x_rel": 0.1, "y_rel": 0.1, "w_rel": 0.8, "h_rel": 0.8},
        "data_source": {"chart_ref_index": 0, "value_field": "pct"},
    }
    render(slide, element, ctx)

    # Verify the rendered chart is COLUMN_CLUSTERED (51), not PIE (5)
    from pptx.enum.chart import XL_CHART_TYPE
    chart_shape = next(sh for sh in slide.shapes if sh.has_chart)
    assert chart_shape.chart.chart_type == XL_CHART_TYPE.COLUMN_CLUSTERED
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest backend/tests/test_element_renderers.py::test_render_chart_respects_source_chart_chart_type -v
```

Expected: FAIL — assertion `XL_CHART_TYPE.PIE != XL_CHART_TYPE.COLUMN_CLUSTERED` (current code at `chart_renderer.py:65` uses `element["chart_type"]`).

- [ ] **Step 3: Implement override in chart_renderer.py**

Replace `chart_renderer.py:60-70` with:

```python
    source_chart = charts_list[chart_ref_index]
    # UI selection wins: source_chart.chart_type comes from AddChartModal and
    # is the authoritative type. The pattern's chart_type is now layout-only
    # advice — fall back to it only if the UI didn't pick anything (legacy charts).
    ui_chart_type = (getattr(source_chart, "chart_type", None) or "").strip()
    pattern_chart_type = (element.get("chart_type") or "").strip()
    chart_type_str = ui_chart_type or pattern_chart_type or "BAR_HORIZONTAL"
    xl_chart_type = _CHART_TYPE_MAP.get(chart_type_str)
    if xl_chart_type is None:
        log.warning("Unknown chart_type %r — falling back to BAR_CLUSTERED", chart_type_str)
        xl_chart_type = XL_CHART_TYPE.BAR_CLUSTERED
    is_pie = chart_type_str in ("PIE", "DONUT")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest backend/tests/test_element_renderers.py::test_render_chart_respects_source_chart_chart_type -v
```

Expected: PASS.

- [ ] **Step 5: Strip `chart_type` from `BUILTIN_STYLE_GUIDE` patterns**

In `backend/aurum_encuestas/style_guide.py`, delete the `"chart_type": "..."` key from every chart element in the 5 patterns:
- `binary_general` → remove line 331 `"chart_type": "PIE"`
- `binary_with_demographics` → remove line 364 `"chart_type": "PIE"`
- `multi_choice_small` → remove line 429 `"chart_type": "BAR_HORIZONTAL"`
- `multi_choice_large` → remove line 461 `"chart_type": "COLUMN_CLUSTERED"`
- `comparison_two_charts` → remove line 488 `"chart_type": "PIE"` and line 509 `"chart_type": "PIE"`

Then make the schema field optional. In `style_guide.py:106`:

```python
class ElementChart(_Base):
    kind: Literal["chart"]
    id: str
    position: Position | PositionAnchored
    chart_type: str | None = None   # ← layout-only; UI's source_chart.chart_type wins at render
    data_source: _DataSourceChart
    labels: _Labels | None = None
    legend: Literal["none", "right", "bottom", "top", "left"] = "none"
    title: str | None = None
    sort: Literal["none", "desc_by_value", "asc_by_value", "category_order"] = "none"
```

- [ ] **Step 6: Remove auto-repair fallback in style_guide_analyzer.py**

At `style_guide_analyzer.py:306` (current line — verify with grep `BAR_HORIZONTAL`), replace the auto-repair block. Current likely shape:

```python
if element.get("chart_type") not in CHART_TYPES:
    element["chart_type"] = "BAR_HORIZONTAL"
```

Change to:

```python
# chart_type is now optional (UI wins). If AI emits an unknown type, drop it
# rather than rewriting to BAR_HORIZONTAL — render_chart will use the UI's pick.
if element.get("chart_type") and element["chart_type"] not in CHART_TYPES:
    element.pop("chart_type", None)
```

- [ ] **Step 7: Run full backend test suite**

```bash
cd backend && pytest -q
```

Expected: All tests pass. If any test asserted `chart_type == "PIE"` on a pattern, update it to assert `chart_type is None`.

- [ ] **Step 8: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/chart_renderer.py \
        backend/aurum_encuestas/style_guide.py \
        backend/aurum_encuestas/style_guide_analyzer.py \
        backend/tests/test_element_renderers.py
git commit -m "fix(chart_type): UI source_chart.chart_type overrides pattern hardcode

Patterns now express layout-only intent; the chart_type a user picks in
AddChartModal is the authoritative type. Stripped hardcoded chart_type
from the 5 built-in patterns and made the field optional in the schema.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Bug #2 — One chart per breakdown, kill `multi_series`

**Files:**
- Modify: `backend/aurum_encuestas/models.py` — remove `Chart.multi_series`
- Modify: `backend/aurum_encuestas/pptx_generator.py:315-329` — simplify to single-series only
- Modify: `backend/aurum_encuestas/element_renderers/chart_renderer.py:_build_chart_data` — pick correct breakdown row based on `source_chart.breakdown_id`
- Modify: `frontend/src/types/index.ts` — drop `multi_series` from `Chart`
- Modify: `frontend/src/pages/Editor/modals/AddChartModal.tsx` — remove multi-series checkbox + state
- Modify: `frontend/src/store/project.ts:163-179` — drop `multiSeries` param from `addCharts`
- Test: `backend/tests/test_element_renderers.py` (new fn)

**Interfaces:**
- Consumes (from Task 1): `chart_renderer.render` reads `source_chart.chart_type` from `EnrichedChart`.
- Produces: `EnrichedChart` no longer carries `multi_series`. `_build_chart_data(source_chart, value_field, sort)` now selects the breakdown row by matching `source_chart.breakdown_id` against the data keys (case-insensitive), falling back to first non-empty row.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_element_renderers.py — append
def test_render_chart_for_breakdown_creates_two_series():
    from pptx import Presentation
    from aurum_encuestas.element_renderers.chart_renderer import render
    from aurum_encuestas.element_renderers.render_context import RenderContext
    from types import SimpleNamespace

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    q = SimpleNamespace(options=["Sí", "No"])
    source_chart = SimpleNamespace(
        question=q,
        breakdown_id="sexo",
        chart_type="BAR_CLUSTERED",
        data={
            "General": {"Sí": {"pct": 0.55}, "No": {"pct": 0.45}},
            "Hombre":  {"Sí": {"pct": 0.80}, "No": {"pct": 0.20}},
            "Mujer":   {"Sí": {"pct": 0.30}, "No": {"pct": 0.70}},
        },
        colors=[],
    )
    ctx = RenderContext(
        slide_config=SimpleNamespace(charts=[source_chart]),
        chart_colors=["#7F7F7F","#404040"],
        free_area={"x":0,"y":0,"cx":6_000_000,"cy":4_000_000},
        typography={"label_size":9},
        resolved_anchors={},
    )
    render(slide, {
        "kind":"chart","id":"c","position":{"x_rel":0,"y_rel":0,"w_rel":1,"h_rel":1},
        "data_source":{"chart_ref_index":0,"value_field":"pct"},
    }, ctx)

    chart_shape = next(sh for sh in slide.shapes if sh.has_chart)
    series = list(chart_shape.chart.series)
    # Expect 2 series (Hombre, Mujer), each with 2 points (Sí, No)
    assert len(series) == 2, f"expected 2 series, got {len(series)}"
    names = {s.name for s in series}
    assert names == {"Hombre", "Mujer"}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest backend/tests/test_element_renderers.py::test_render_chart_for_breakdown_creates_two_series -v
```

Expected: FAIL — current `_build_chart_data` always picks the General row → 1 series.

- [ ] **Step 3: Rewrite `_build_chart_data` to use breakdown_id**

Replace `chart_renderer.py:244-284` (`_build_chart_data`) with:

```python
def _build_chart_data(source_chart, value_field: str, sort: str):
    """Extract CategoryChartData from a chart for its breakdown_id.

    Single-series mode (breakdown_id in {"general", "", None}): plot the
    General/Total row.

    Multi-series mode (any other breakdown_id): one series per breakdown
    category (e.g. Hombre/Mujer for sexo). General row is excluded so we
    never double-plot it alongside the breakdown categories.
    """
    cd = CategoryChartData()
    question = getattr(source_chart, "question", None)
    options = list(question.options) if question else []
    data = getattr(source_chart, "data", {}) or {}
    breakdown_id = (getattr(source_chart, "breakdown_id", "") or "").lower()

    is_general = breakdown_id in ("", "general")

    if is_general:
        primary = data.get("General") or data.get("Total") or (next(iter(data.values())) if data else {})
        if not options and primary:
            options = list(primary.keys())
        if sort in ("desc_by_value", "asc_by_value") and primary:
            reverse = sort == "desc_by_value"
            options = sorted(options, key=lambda o: (primary.get(o) or {}).get(value_field, 0), reverse=reverse)
        cd.categories = options
        values = [float((primary.get(o) or {}).get(value_field, 0) or 0) for o in options]
        cd.add_series("", values)
        return cd, values

    # Breakdown chart: every row except General becomes a series.
    cats = [k for k in data.keys() if k.lower() not in ("general", "total")]
    if not cats:
        cats = list(data.keys())

    # Sort options by the FIRST category's value so all series share an axis order.
    if options and sort in ("desc_by_value", "asc_by_value") and cats:
        reverse = sort == "desc_by_value"
        first = data.get(cats[0]) or {}
        options = sorted(options, key=lambda o: (first.get(o) or {}).get(value_field, 0), reverse=reverse)
    cd.categories = options

    all_values: list[float] = []
    for cat in cats:
        row = data.get(cat) or {}
        series_values = [float((row.get(o) or {}).get(value_field, 0) or 0) for o in options]
        cd.add_series(cat, series_values)
        all_values.extend(series_values)
    return cd, all_values
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest backend/tests/test_element_renderers.py::test_render_chart_for_breakdown_creates_two_series -v
```

Expected: PASS.

- [ ] **Step 5: Remove `multi_series` from backend `Chart`**

In `backend/aurum_encuestas/models.py:45-52`, replace:

```python
class Chart(BaseModel):
    id: str
    question_id: str
    breakdown_id: str
    chart_type: ChartType
    multi_series: bool = False
    colors: list[str] = []
```

with:

```python
class Chart(BaseModel):
    id: str
    question_id: str
    breakdown_id: str
    chart_type: ChartType
    colors: list[str] = []
```

- [ ] **Step 6: Update `pptx_generator._add_chart` (legacy path)**

Replace `pptx_generator.py:315-329` block with:

```python
    options = _find_question(state, chart_def.question_id).options
    cd.categories = options

    is_general = chart_def.breakdown_id in (None, "", "general")
    if is_general or len(data) <= 1:
        primary_cat = next((c for c in data if c.lower() in ("total", "general")), None) or (next(iter(data), None) if data else None)
        series = [_value(data.get(primary_cat, {}).get(opt, {})) for opt in options] if primary_cat else [0.0] * len(options)
        cd.add_series("Total", series)
    else:
        cats_to_plot = [c for c in data if c.lower() not in ("total", "general")] or list(data.keys())
        for cat in cats_to_plot:
            values = [_value(data[cat].get(opt, {})) for opt in options]
            cd.add_series(cat, values)
```

(This removes the `chart_def.multi_series` flag — multi-series is now implied by `breakdown_id != general`.)

- [ ] **Step 7: Update `pattern_classifier.EnrichedChart` and `build_slide_config`**

In `pattern_classifier.py:399-451`, remove the `multi_series` field from `EnrichedChart`:

```python
    @dataclass
    class EnrichedChart:
        id: str
        question_id: str
        breakdown_id: str
        chart_type: str
        colors: list
        question: _Any = None
        data: dict = field(default_factory=dict)
        all_breakdowns_data: dict = field(default_factory=dict)
```

And in `enriched_charts.append(...)` at line 439-450, remove `multi_series=...`.

- [ ] **Step 8: Frontend — drop `multi_series` from types**

`frontend/src/types/index.ts` — find the `Chart` interface (look for `multi_series` to locate it) and remove the field.

- [ ] **Step 9: Frontend — drop checkbox from AddChartModal**

`frontend/src/pages/Editor/modals/AddChartModal.tsx`:
- Delete `multiSeries` state at line 34.
- Delete the checkbox block at lines 160-167.
- Drop `multiSeries` from `ApplyResult` interface at lines 10-16.
- Drop `multiSeries` from the `onApply({...})` call at lines 82-88.

- [ ] **Step 10: Frontend — drop param from `addCharts`**

`frontend/src/store/project.ts:163-179` — remove the `multiSeries` parameter from `addCharts` and from the `newCharts` map.

Find the call site (in `Editor.tsx` or wherever) and remove the extra argument.

```bash
grep -rn "addCharts(" frontend/src --include="*.ts" --include="*.tsx"
```

Update each caller.

- [ ] **Step 11: Run all tests**

```bash
cd backend && pytest -q
cd ../frontend && pnpm test
```

Expected: all green.

- [ ] **Step 12: Commit**

```bash
git add backend/aurum_encuestas/models.py \
        backend/aurum_encuestas/pptx_generator.py \
        backend/aurum_encuestas/element_renderers/chart_renderer.py \
        backend/aurum_encuestas/pattern_classifier.py \
        frontend/src/types/index.ts \
        frontend/src/pages/Editor/modals/AddChartModal.tsx \
        frontend/src/store/project.ts \
        backend/tests/test_element_renderers.py
git commit -m "fix(breakdown): one chart per breakdown_id, drop multi_series flag

multi_series is now implicit: charts with breakdown_id='general' plot the
Total row as a single series; any other breakdown_id plots one series per
breakdown category. UI no longer exposes the multi_series toggle.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Bug #3a — Retune pattern layouts to Aurora EMU proportions

**Files:**
- Modify: `backend/aurum_encuestas/style_guide.py` — `BUILTIN_STYLE_GUIDE` patterns
- Test: `backend/tests/test_style_guide.py` (new)

**Interfaces:**
- Consumes: nothing new.
- Produces: pattern Position dicts that match Aurora reference (heights ~0.76 instead of 0.65; y_rel ~0.16 instead of 0.20 for full-height single-chart cases).

**Aurora reference geometry (extracted from slides 13/14/19 of `PPT Aurora ejemplo.pptx`):**
- Slide is 13.33" × 7.5". Free area ≈ `x_rel=0.04, y_rel=0.13, w_rel=0.92, h_rel=0.83` (after title band 0.08-0.13 and notes band 0.92-0.95).
- Slide 13 (Sexo PIE + Edad BAR side-by-side): PIE at L=1.38 T=1.22 W=3.83 H=5.72 → relative to FA: `x_rel≈0.10, y_rel≈0.12, w_rel≈0.29, h_rel≈0.76`. BAR at L=7.57 T=1.23 W=4.33 H=5.67 → `x_rel≈0.57, y_rel≈0.12, w_rel≈0.33, h_rel≈0.75`.
- Slide 14 (NSE BAR + Lugar BAR): both H≈5.69 → h_rel≈0.76.
- Slide 19 (single BAR): L=2.30 T=2.68 W=8.72 H=4.19 → `x_rel≈0.17, y_rel≈0.36, w_rel≈0.65, h_rel≈0.56` (text above squeezed top).

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_style_guide.py — new file (or append if exists)
def test_builtin_patterns_use_aurora_proportions():
    from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE
    patterns = {p.id: p for p in BUILTIN_STYLE_GUIDE.patterns}

    # comparison_two_charts: each chart should be tall (h_rel >= 0.70)
    p = patterns["comparison_two_charts"]
    chart_els = [e for e in p.implementation.elements if e.kind == "chart"]
    assert len(chart_els) == 2
    for el in chart_els:
        assert el.position.h_rel >= 0.70, f"{el.id}: h_rel={el.position.h_rel} too short vs Aurora (0.75)"

    # multi_choice_small: full-width bar with h_rel >= 0.70
    el = next(e for e in patterns["multi_choice_small"].implementation.elements if e.kind == "chart")
    assert el.position.h_rel >= 0.65

    # binary_general: large centred pie
    el = next(e for e in patterns["binary_general"].implementation.elements if e.kind == "chart")
    assert el.position.h_rel >= 0.70
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest backend/tests/test_style_guide.py::test_builtin_patterns_use_aurora_proportions -v
```

Expected: FAIL — current heights 0.58–0.68.

- [ ] **Step 3: Update positions**

In `style_guide.py`, change these position dicts (keep all other keys intact):

- `binary_general` → `"position": {"x_rel": 0.12, "y_rel": 0.12, "w_rel": 0.76, "h_rel": 0.76}` (was 0.15/0.20/0.70/0.65)
- `binary_with_demographics` → main_pie `"position": {"x_rel": 0.04, "y_rel": 0.12, "w_rel": 0.30, "h_rel": 0.76}` (was 0.03/0.22/0.30/0.58); demographics_table `"position": {"x_rel": 0.38, "y_rel": 0.12, "w_rel": 0.58, "h_rel": 0.76}` (was 0.38/0.22/0.58/0.58)
- `multi_choice_small` → `"position": {"x_rel": 0.17, "y_rel": 0.20, "w_rel": 0.65, "h_rel": 0.65}` (was 0.05/0.20/0.90/0.65). Note: Aurora slide 19 has analysis text band above the chart; narrower width and y_rel=0.20 leaves room.
- `multi_choice_large` → `"position": {"x_rel": 0.03, "y_rel": 0.14, "w_rel": 0.94, "h_rel": 0.74}` (was 0.03/0.18/0.94/0.68)
- `comparison_two_charts` → left_chart `"position": {"x_rel": 0.04, "y_rel": 0.12, "w_rel": 0.42, "h_rel": 0.76}`; center_divider `"position": {"x_rel": 0.495, "y_rel": 0.10, "w_rel": 0.002, "h_rel": 0.78}`; right_chart `"position": {"x_rel": 0.54, "y_rel": 0.12, "w_rel": 0.42, "h_rel": 0.76}` (was 0.02/0.20/0.46/0.65 and 0.52/0.20/0.46/0.65)

- [ ] **Step 4: Run test to verify pass**

```bash
pytest backend/tests/test_style_guide.py::test_builtin_patterns_use_aurora_proportions -v
```

Expected: PASS.

- [ ] **Step 5: Smoke-render a sample slide and inspect**

```bash
cd backend && python3 -c "
from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE
for p in BUILTIN_STYLE_GUIDE.patterns:
    print(p.id)
    for e in p.implementation.elements:
        if hasattr(e.position, 'h_rel'):
            print(f'  {e.id}: x={e.position.x_rel} y={e.position.y_rel} w={e.position.w_rel} h={e.position.h_rel}')
"
```

Expected: heights ≥ 0.65 for all chart elements.

- [ ] **Step 6: Commit**

```bash
git add backend/aurum_encuestas/style_guide.py backend/tests/test_style_guide.py
git commit -m "fix(layouts): retune pattern positions to Aurora EMU proportions

Charts were rendering ~25% shorter than Aurora reference (h_rel=0.58
vs 0.76). Updated all 5 built-in patterns to match observed Aurora
deck geometry (slides 13/14/19 of 'PPT Aurora ejemplo.pptx').

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Bug #3b — Dynamic N-charts pattern (handle 3+)

**Files:**
- Modify: `backend/aurum_encuestas/style_guide.py` — add `n_charts_grid` pattern with priority 5
- Modify: `backend/aurum_encuestas/pattern_renderer.py` — fan-out chart elements based on `slide_config.charts` count when pattern has a single `"_repeat": "per_chart"` chart element
- Test: `backend/tests/test_pattern_classifier.py` (new fn)
- Test: `backend/tests/test_pattern_renderer.py` (new fn)

**Interfaces:**
- Consumes: `slide_config.charts: list[EnrichedChart]`.
- Produces: a new pattern `n_charts_grid` whose first chart element carries `"_repeat": "per_chart"` and `position` describes the FIRST cell — the renderer auto-tiles into a grid (1-row for n≤3, 2-row for n=4-6, 3-row for n=7-9).

- [ ] **Step 1: Failing test for classifier**

```python
# backend/tests/test_pattern_classifier.py — append
def test_three_charts_matches_n_charts_grid_pattern():
    from aurum_encuestas.pattern_classifier import classify_slide
    from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE
    from types import SimpleNamespace

    slide_config = SimpleNamespace(
        charts=[
            SimpleNamespace(question_id="q1", breakdown_id="sexo", chart_type="PIE"),
            SimpleNamespace(question_id="q2", breakdown_id="general", chart_type="BAR_CLUSTERED"),
            SimpleNamespace(question_id="q3", breakdown_id="general", chart_type="BAR_CLUSTERED"),
        ],
        n_charts=3,
        analyses=[],
    )
    pattern = classify_slide(slide_config, BUILTIN_STYLE_GUIDE)
    assert pattern is not None and pattern.id == "n_charts_grid"
```

- [ ] **Step 2: Run, expect fail**

```bash
pytest backend/tests/test_pattern_classifier.py::test_three_charts_matches_n_charts_grid_pattern -v
```

Expected: FAIL — no `n_charts_grid` pattern exists.

- [ ] **Step 3: Add `n_charts_grid` pattern to `BUILTIN_STYLE_GUIDE`**

Append after `comparison_two_charts` (before the closing `]` of `patterns`):

```python
        # ── 5: n_charts_grid ──────────────────────────────────────────────
        # 3+ charts in one slide → auto-tile (1×3, 2×3, etc.).
        # The single chart element below is replicated by pattern_renderer
        # based on slide_config.charts count; position is the FIRST cell.
        {
            "id": "n_charts_grid",
            "priority": 5,
            "trigger": {"field": "n_charts_in_slide", "$gte": 3},
            "why_picked": "3+ charts — auto grid de N celdas iguales.",
            "implementation": {
                "elements": [
                    {
                        "kind": "chart",
                        "id": "grid_chart",
                        "position": {"x_rel": 0.03, "y_rel": 0.14, "w_rel": 0.30, "h_rel": 0.74},
                        "data_source": {"chart_ref_index": 0, "value_field": "pct"},
                        "labels": {
                            "show_percentage": True,
                            "position": "outside_end",
                            "format": "0.0%",
                            "font_size": 8,
                        },
                        "legend": "none",
                        "sort": "desc_by_value",
                        "_repeat": "per_chart",
                    },
                ]
            },
        },
```

- [ ] **Step 4: Run classifier test, expect pass**

```bash
pytest backend/tests/test_pattern_classifier.py::test_three_charts_matches_n_charts_grid_pattern -v
```

Expected: PASS.

- [ ] **Step 5: Failing test for renderer fan-out**

```python
# backend/tests/test_pattern_renderer.py — append (or create)
def test_n_charts_grid_renders_three_chart_shapes():
    from pptx import Presentation
    from aurum_encuestas.pattern_renderer import render_pattern
    from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE
    from aurum_encuestas.element_renderers.render_context import RenderContext
    from types import SimpleNamespace

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    q = SimpleNamespace(options=["A","B","C"])
    charts = [
        SimpleNamespace(question=q, breakdown_id="general", chart_type="PIE",
                        data={"General": {"A":{"pct":0.5},"B":{"pct":0.3},"C":{"pct":0.2}}}, colors=[]),
        SimpleNamespace(question=q, breakdown_id="general", chart_type="BAR_CLUSTERED",
                        data={"General": {"A":{"pct":0.4},"B":{"pct":0.4},"C":{"pct":0.2}}}, colors=[]),
        SimpleNamespace(question=q, breakdown_id="general", chart_type="BAR_CLUSTERED",
                        data={"General": {"A":{"pct":0.6},"B":{"pct":0.3},"C":{"pct":0.1}}}, colors=[]),
    ]
    slide_config = SimpleNamespace(charts=charts, analyses=[], n_charts=3)
    ctx = RenderContext(slide_config=slide_config, chart_colors=["#7F7F7F"],
                        free_area={"x":0,"y":0,"cx":12_192_000,"cy":6_858_000},
                        typography={"label_size":9}, resolved_anchors={})

    pattern = next(p for p in BUILTIN_STYLE_GUIDE.patterns if p.id == "n_charts_grid")
    render_pattern(pattern, slide, ctx, BUILTIN_STYLE_GUIDE, list(BUILTIN_STYLE_GUIDE.patterns))

    n_chart_shapes = sum(1 for sh in slide.shapes if sh.has_chart)
    assert n_chart_shapes == 3, f"expected 3 chart shapes, got {n_chart_shapes}"
```

- [ ] **Step 6: Run, expect fail (only 1 chart rendered)**

```bash
pytest backend/tests/test_pattern_renderer.py::test_n_charts_grid_renders_three_chart_shapes -v
```

- [ ] **Step 7: Implement fan-out in `pattern_renderer.render_pattern`**

In `pattern_renderer.py`, after `ordered_elements = _topological_sort(elements)` (around line 53), add expansion:

```python
    # Fan out elements marked with "_repeat": "per_chart" — one copy per
    # chart in slide_config.charts. Used by n_charts_grid pattern.
    charts_list = getattr(ctx.slide_config, "charts", []) or []
    expanded: list[dict] = []
    for el in ordered_elements:
        if el.get("_repeat") == "per_chart" and charts_list:
            n = len(charts_list)
            cols = 3 if n <= 3 else (3 if n <= 6 else 3)  # always 3 cols
            rows = (n + cols - 1) // cols
            base_pos = el.get("position", {})
            base_x = base_pos.get("x_rel", 0.03)
            base_y = base_pos.get("y_rel", 0.14)
            base_w = base_pos.get("w_rel", 0.30)
            base_h = base_pos.get("h_rel", 0.74)
            gap_x = 0.02
            gap_y = 0.04
            # Recompute w/h so the row fits inside free_area horizontally / vertically
            cell_w = (1.0 - 2 * base_x - gap_x * (cols - 1)) / cols
            cell_h = (base_h - gap_y * (rows - 1)) / rows
            for i in range(n):
                r, c = divmod(i, cols)
                new_el = copy.deepcopy(el)
                new_el.pop("_repeat", None)
                new_el["id"] = f"{el['id']}_{i}"
                new_el["position"] = {
                    "x_rel": base_x + c * (cell_w + gap_x),
                    "y_rel": base_y + r * (cell_h + gap_y),
                    "w_rel": cell_w,
                    "h_rel": cell_h,
                }
                ds = dict(new_el.get("data_source", {}))
                ds["chart_ref_index"] = i
                new_el["data_source"] = ds
                expanded.append(new_el)
        else:
            expanded.append(el)
    ordered_elements = expanded
```

(Make sure `import copy` is already at top of the file — it is.)

- [ ] **Step 8: Run test, expect pass**

```bash
pytest backend/tests/test_pattern_renderer.py::test_n_charts_grid_renders_three_chart_shapes -v
```

Expected: PASS.

- [ ] **Step 9: Run full backend tests**

```bash
cd backend && pytest -q
```

Expected: all green.

- [ ] **Step 10: Commit**

```bash
git add backend/aurum_encuestas/style_guide.py \
        backend/aurum_encuestas/pattern_renderer.py \
        backend/tests/test_pattern_classifier.py \
        backend/tests/test_pattern_renderer.py
git commit -m "feat(patterns): add n_charts_grid pattern with per-chart fan-out

Slides with 3+ charts now match a dedicated pattern that auto-tiles
into a 3-col grid. pattern_renderer replicates any element flagged
'_repeat': 'per_chart' once per source chart, with chart_ref_index
auto-incremented and positions computed from the grid geometry.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Training — Update palette + available chart types

**Files:**
- Modify: `backend/aurum_encuestas/style_guide.py` — `GlobalConfig.suggested_palette` default + `BUILTIN_STYLE_GUIDE` palette + `available_chart_types`
- Test: `backend/tests/test_style_guide.py` (append)

**Interfaces:**
- Consumes: `color_resolver` reads `style_guide.global_.suggested_palette`.
- Produces: defaults shift from generic greys to Aurora-reference palette (last color yellow accent).

- [ ] **Step 1: Failing test**

```python
def test_builtin_palette_matches_aurora_reference():
    from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE
    palette = BUILTIN_STYLE_GUIDE.global_.suggested_palette
    # Yellow accent must appear in the palette (Aurora last-bar highlight)
    assert "#EEC245" in palette or "#FFC000" in palette
    # Grey neutrals first
    assert palette[0] in ("#7F7F7F", "#595959", "#404040")
    # All 9 supported chart types must be in available_chart_types
    assert "LINE" in BUILTIN_STYLE_GUIDE.available_chart_types
    assert "DONUT" in BUILTIN_STYLE_GUIDE.available_chart_types
    assert "AREA" in BUILTIN_STYLE_GUIDE.available_chart_types
```

- [ ] **Step 2: Run, expect fail**

```bash
pytest backend/tests/test_style_guide.py::test_builtin_palette_matches_aurora_reference -v
```

- [ ] **Step 3: Update palette + available_chart_types**

In `style_guide.py`, change `GlobalConfig.suggested_palette` default (line 256):

```python
    suggested_palette: list[str] = Field(default_factory=lambda: ["#7F7F7F", "#404040", "#EEC245", "#C00000", "#FFC000"])
```

In `BUILTIN_STYLE_GUIDE` `"global"` block (line 305):

```python
        "suggested_palette": ["#7F7F7F", "#404040", "#EEC245", "#C00000", "#FFC000"],
        "vibe": "Minimalista profesional. Greys dominan, yellow #EEC245 acentúa la barra destacada (último bar). Red+Yellow para PIEs binarios.",
```

In `BUILTIN_STYLE_GUIDE["available_chart_types"]` (line 308):

```python
    "available_chart_types": [
        "PIE", "DONUT",
        "BAR_HORIZONTAL", "BAR_CLUSTERED", "BAR_STACKED",
        "COLUMN_CLUSTERED", "COLUMN_STACKED",
        "LINE", "AREA",
        "TABLE_WITH_MINIBARS",
    ],
```

And on the `StyleGuide.available_chart_types` default (line 273):

```python
    available_chart_types: list[str] = Field(
        default_factory=lambda: [
            "PIE", "DONUT",
            "BAR_HORIZONTAL", "BAR_CLUSTERED", "BAR_STACKED",
            "COLUMN_CLUSTERED", "COLUMN_STACKED",
            "LINE", "AREA",
            "TABLE_WITH_MINIBARS",
        ]
    )
```

- [ ] **Step 4: Test passes**

```bash
pytest backend/tests/test_style_guide.py::test_builtin_palette_matches_aurora_reference -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/style_guide.py backend/tests/test_style_guide.py
git commit -m "feat(training): adopt Aurora palette + expose all 9 chart types

Default palette is now the grey+yellow+red mix observed in Aurora and
MAF reference decks. available_chart_types includes LINE, AREA, DONUT,
BAR_STACKED, COLUMN_STACKED so the UI dropdown shows everything we can
actually render via python-pptx.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Training — Few-shot LAYOUT_SYSTEM examples

**Files:**
- Modify: `backend/aurum_encuestas/llm_client.py` — extend `LAYOUT_SYSTEM` constant with 3 examples
- Test: `backend/tests/test_llm_client.py` (new fn, mocked)

**Interfaces:**
- Consumes: nothing new.
- Produces: LLM-generated layouts that hew closer to Aurora geometry.

- [ ] **Step 1: Failing test (assert prompt mentions all 3 examples)**

```python
# backend/tests/test_llm_client.py — append
def test_layout_system_includes_aurora_few_shot():
    from aurum_encuestas.llm_client import LAYOUT_SYSTEM
    # Must mention three reference cases
    assert "Ejemplo 1" in LAYOUT_SYSTEM
    assert "Ejemplo 2" in LAYOUT_SYSTEM
    assert "Ejemplo 3" in LAYOUT_SYSTEM
    # Must include Aurora-style EMU coords as ballpark
    assert "12192000" in LAYOUT_SYSTEM  # full slide width hint
    # Must mention single-series per breakdown convention
    assert "breakdown" in LAYOUT_SYSTEM.lower()
```

- [ ] **Step 2: Run, expect fail**

```bash
pytest backend/tests/test_llm_client.py::test_layout_system_includes_aurora_few_shot -v
```

- [ ] **Step 3: Replace `LAYOUT_SYSTEM` constant**

In `llm_client.py`, replace the `LAYOUT_SYSTEM` definition with:

```python
LAYOUT_SYSTEM = """Sos diseñador de slides de encuestas. Te paso config slide y free_area canvas. Devolvés JSON con posiciones EMU para cada elemento.

Reglas:
- Coords todas dentro de free_area (x ≥ free_area.x, x+cx ≤ free_area.x+free_area.cx, similar Y).
- Sin overlaps. Padding mínimo 200000 EMU entre elementos.
- Cada breakdown ⇒ chart separado (NUNCA dos breakdowns en un mismo chart con multi-series).
- Charts deben ocupar ≥75% de la altura de free_area cuando hay 1-2 charts; ≥65% cuando hay 3-6 (grid).
- Output: solo JSON válido, sin texto explicativo.

Slide canvas estándar: 12192000 × 6858000 EMU. Free area típica: x=487680 y=1097280 cx=11216640 cy=5212080.

Ejemplo 1 — Single binary PIE (binary_general):
  Input: n_charts=1, question_type=binary, n_breakdowns=0
  Output: {"elements":[{"role":"chart_0","x":1828800,"y":1722120,"cx":7619680,"cy":4114800}]}

Ejemplo 2 — Two charts side-by-side (comparison_two_charts, e.g. Sexo PIE + Edad BAR):
  Input: n_charts=2, breakdowns=["sexo","edad"]
  Output: {"elements":[
    {"role":"chart_0","x":1234440,"y":1463040,"cx":3504000,"cy":5181600},
    {"role":"chart_1","x":6918960,"y":1463040,"cx":3960000,"cy":5181600}
  ]}

Ejemplo 3 — Three charts grid (n_charts_grid, e.g. Sexo/NSE/Edad demographics):
  Input: n_charts=3, breakdowns=["sexo","nse","edad"]
  Output: {"elements":[
    {"role":"chart_0","x":487680,"y":1463040,"cx":3504000,"cy":4965600},
    {"role":"chart_1","x":4357680,"y":1463040,"cx":3504000,"cy":4965600},
    {"role":"chart_2","x":8227680,"y":1463040,"cx":3504000,"cy":4965600}
  ]}

Si hay análisis (chart_analysis_i / question_analysis_i / slide_analysis), apilá debajo del chart al que aplica con altura ≈ 15% del chart y 200000 EMU de padding.
"""
```

- [ ] **Step 4: Test passes**

```bash
pytest backend/tests/test_llm_client.py::test_layout_system_includes_aurora_few_shot -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/llm_client.py backend/tests/test_llm_client.py
git commit -m "feat(prompt): add Aurora 1/2/3-chart few-shot to LAYOUT_SYSTEM

Three reference layouts (binary single-pie, two-chart side-by-side,
three-chart grid) with concrete EMU coordinates extracted from the
Aurora reference deck. Explicitly encodes the 'one chart per breakdown'
contract so the LLM stops emitting multi-series merges.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Verify — End-to-end render and visual diff

**Files:**
- Add: `backend/tests/test_render_e2e.py` (new — uses the actual MAF Excel if available, else skips)
- Add: `e2e/render-verify.spec.ts` (Playwright) — optional, only if time

**Interfaces:**
- Consumes: everything from tasks 1-6.
- Produces: a regression test that renders a 3-breakdown slide and asserts (a) 3 chart shapes exist, (b) each has its UI-selected chart_type, (c) chart heights are ≥ 0.65 of free_area.

- [ ] **Step 1: Write e2e test**

```python
# backend/tests/test_render_e2e.py — new
import pytest
from pathlib import Path
from pptx import Presentation
from pptx.enum.chart import XL_CHART_TYPE

MAF_XLSX = Path.home() / "Downloads" / "Aurum - Encuestas - Precancelaciones - MAF - Mayo 2026.xlsx"

@pytest.mark.skipif(not MAF_XLSX.exists(), reason="MAF reference xlsx not present")
def test_e2e_three_breakdown_demographics_slide(tmp_path):
    """Render a demographics slide with 3 separate single-series charts
    and assert geometry + chart_type fidelity."""
    from aurum_encuestas.xlsx_parser import parse_xlsx
    from aurum_encuestas.render_service import render_project
    from aurum_encuestas.models import ProjectState, ProjectInputs, Slide, Chart

    parsed = parse_xlsx(str(MAF_XLSX))
    inputs = ProjectInputs(db_path=str(MAF_XLSX), template_path="")  # default template

    # Take the first question as a stand-in for demographics
    q_id = parsed.questions[0].id
    bds = [b.id for b in parsed.breakdowns if b.id != "general"][:3]
    if len(bds) < 3:
        pytest.skip("MAF xlsx has <3 non-general breakdowns")

    charts = [Chart(id=f"c{i}", question_id=q_id, breakdown_id=b, chart_type="BAR_CLUSTERED", colors=[])
              for i, b in enumerate(bds)]
    state = ProjectState(
        project_name="e2e", inputs=inputs, parsed_db=parsed,
        slides=[Slide(id="s1", type="shell", title="Demo", charts=charts, analyses=[])],
    )

    out = tmp_path / "out.pptx"
    render_project(state, str(out))

    prs = Presentation(str(out))
    # Find the chart slide
    chart_slides = [s for s in prs.slides if any(sh.has_chart for sh in s.shapes)]
    assert chart_slides, "no chart slides rendered"
    chart_shapes = [sh for sh in chart_slides[0].shapes if sh.has_chart]
    assert len(chart_shapes) == 3, f"expected 3 chart shapes, got {len(chart_shapes)}"
    for sh in chart_shapes:
        assert sh.chart.chart_type == XL_CHART_TYPE.BAR_CLUSTERED
        # Height must be at least 50% of slide height
        assert sh.height >= 0.50 * prs.slide_height
```

- [ ] **Step 2: Run**

```bash
cd backend && pytest tests/test_render_e2e.py -v
```

Expected: PASS (or SKIP if xlsx missing — write the path explicitly in CLAUDE.md if needed).

- [ ] **Step 3: Manual diff against Aurora**

```bash
# Open both PPTX in PowerPoint or Keynote side-by-side. Visually confirm:
# - Slide 1 (Demographics: 3 charts) tiles 3 charts horizontally
# - Heights match Aurora reference
# - Chart types reflect the UI selection (not pattern hardcode)
open /Users/joaquincardenas/Downloads/PPT\ Aurora\ ejemplo.pptx
# Open the generated file from tmp_path
```

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_render_e2e.py
git commit -m "test(e2e): render demographics slide and assert geometry+type fidelity

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Spec coverage:** Bug #1 ⇒ Task 1. Bug #2 ⇒ Task 2. Bug #3 (layout) ⇒ Tasks 3+4. Training improvement ⇒ Tasks 5+6. Verification ⇒ Task 7.
- **Placeholder scan:** None — every code block contains real code or real commands.
- **Type consistency:** `EnrichedChart` loses `multi_series` in Task 2; downstream `chart_renderer._build_chart_data` is updated in the same task. `Chart` model in `models.py` matches frontend `types/index.ts` after Task 2.
- **Open risks:**
  - `style_guide_analyzer.py:306` exact line may have shifted; use `grep -n "BAR_HORIZONTAL" backend/aurum_encuestas/style_guide_analyzer.py` to find the auto-repair block.
  - `addCharts` call sites in the frontend — `grep -rn "addCharts(" frontend/src` covers them, but a TS compile error will flag any miss.
  - `n_charts_grid` fan-out assumes the renderer's existing `topological_sort` doesn't choke on `_repeat`-tagged elements before expansion. The Task 4 implementation places expansion AFTER `_topological_sort` so this is safe.
