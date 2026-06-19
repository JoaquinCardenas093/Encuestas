# Chart Catalog Overhaul Fase B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the two grouped chart_types added to the schema in Fase A (`PIE_GROUPED` as an N-pie grid, `BAR_HORIZONTAL_GROUPED` as a clustered multi-series bar) and expose all 5 chart_types to the UI dropdown. Wire `show_legend`, `grid_cols`, `title`, and a new `cat_titles: dict` into both UI and renderers. Apply image-faithful style overrides to BOTH single-panel AND multi-panel `TABLE_WITH_MINIBARS`, drop the internal label column, and add a left external legend block when `show_legend=True`.

**Architecture:** `chart_renderer.render` gains an internal PIE_GROUPED branch that fans out N pie shapes itself (decision Q9). Single-shape types reuse the existing path with two additions: `chart.title` writes the chart title; `show_legend=True` on BAR_HORIZONTAL_GROUPED enables a bottom legend. `table_renderer` extracts a module-level `_SEGMENTED_CELLS_FASE_B` style override and applies it uniformly to single-panel AND multi-panel branches; `_render_panel` learns to render without a label column when `label_col_width_rel <= 0`. A new `_render_external_legend_block` helper renders the left labels block when `show_legend=True`.

**Tech Stack:** Python 3.11 + python-pptx, pydantic v2, React + TypeScript + Zustand, pytest + vitest.

## Global Constraints

- Backend Python target: `3.11`. Test command: `cd backend && arch -arm64 .venv/bin/pytest -q` from repo root.
- Frontend: `cd frontend && npx vitest run`. TypeScript clean (`npx tsc --noEmit`).
- `BUILTIN_STYLE_GUIDE` stays pure-literal Python.
- Spanish UI strings es-MX neutral tone, no emoji.
- `ChartType` literal stays at exactly 5 values: `PIE`, `PIE_GROUPED`, `BAR_HORIZONTAL`, `BAR_HORIZONTAL_GROUPED`, `TABLE_WITH_MINIBARS` (no change from Fase A).
- `BUILTIN_STYLE_GUIDE.available_chart_types` Fase B = exactly `["PIE", "PIE_GROUPED", "BAR_HORIZONTAL", "BAR_HORIZONTAL_GROUPED", "TABLE_WITH_MINIBARS"]` (expanded from 3 to 5).
- `Chart.grid_cols: int | None = Field(default=None, ge=1)` — backend validator rejects 0 or negative.
- `Chart.cat_titles: dict[str, str] | None = None` — keys are breakdown category labels (exact match), values are user-override titles per pie.
- PIE_GROUPED auto-grid rule when `grid_cols is None`: `rows = 1 if N<=3 else 2 if N<=6 else 3`; `cols = ceil(N / rows)`.
- `TABLE_WITH_MINIBARS` legend semantic (Q7 lock):
  - `show_legend=True` → render external left block (~10% width) with row labels (`Observaciones` + question options); panels rendered WITHOUT internal label column.
  - `show_legend=False` → no external block, panels still WITHOUT internal label column (labels not visible anywhere).
- AddChartModal dropdown filter (Fase B):
  - `nReal == 0` → hide `TABLE_WITH_MINIBARS`, `PIE_GROUPED`, `BAR_HORIZONTAL_GROUPED`.
  - `nReal == 1` → show all 5.
  - `nReal >= 2` → lock to `["TABLE_WITH_MINIBARS"]`.
- Branch base: `main` at `fd24232` (post Fase A merge). New branch: `feat/chart-catalog-phase-b`.

---

## File Structure

No new files. Modified:

| File | Touched in | Responsibility |
|---|---|---|
| `backend/aurum_encuestas/models.py` | Task 1 | `Chart.cat_titles` field; `Chart.grid_cols` validator `ge=1` |
| `backend/aurum_encuestas/style_guide.py` | Task 2 | `available_chart_types` extended to the 5-item Fase B list |
| `backend/aurum_encuestas/pattern_classifier.py` | Task 3 | `EnrichedChart` carries `show_legend`, `grid_cols`, `title`, `cat_titles` |
| `backend/aurum_encuestas/element_renderers/chart_renderer.py` | Tasks 4+5 | T4: title + show_legend wiring; remove Fase B warning. T5: `_render_pie_grouped` + helpers |
| `backend/aurum_encuestas/element_renderers/table_renderer.py` | Tasks 6+7 | T6: `_SEGMENTED_CELLS_FASE_B`; `_render_panel` no-label-col branch; weight recalc. T7: `_render_external_legend_block`; show_legend wiring |
| `frontend/src/types/index.ts` | Task 8 | `Chart.cat_titles` field |
| `frontend/src/store/project.ts` | Task 8 | `addChart` opts param; `updateChartField` action |
| `frontend/src/pages/Editor/modals/AddChartModal.tsx` | Task 8 | Filter + new inputs + 5-item BUILTIN |
| `frontend/src/pages/Editor/ConfigPanel.tsx` | Task 8 | Per-chart inputs + 5-item BUILTIN |
| `backend/tests/test_models.py` | Task 1 | cat_titles + grid_cols validator |
| `backend/tests/test_style_guide.py` | Task 2 | 5-item list assertion |
| `backend/tests/test_pattern_classifier.py` | Task 3 | EnrichedChart propagation |
| `backend/tests/test_element_renderers.py` | Tasks 4+5 | Title, legend, grouped fallback warning removed, PIE_GROUPED render |
| `backend/tests/test_table_renderer.py` | Tasks 6+7 | Image-style cells uniform, no-label-col, external legend block |
| `frontend/tests/AddChartModal.test.tsx` | Task 8 | Filter for 5 types + conditional inputs + apply payload |
| `frontend/tests/ConfigPanel.test.tsx` | Task 8 | Per-chart inputs + updateChartField |
| `frontend/tests/store.test.ts` | Task 8 | addChart opts + updateChartField |

---

### Task 1: `Chart.cat_titles` + `grid_cols` validator

**Files:**
- Modify: `backend/aurum_encuestas/models.py`
- Modify: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: nothing new (depends on pydantic).
- Produces:
  - `Chart.cat_titles: dict[str, str] | None = None`
  - `Chart.grid_cols: int | None = Field(default=None, ge=1)` (validator added)

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_models.py`:

```python
def test_chart_accepts_cat_titles_dict():
    from aurum_encuestas.models import Chart
    c = Chart.model_validate({
        "id": "c1", "question_id": "q1", "breakdown_ids": ["edad"],
        "chart_type": "PIE_GROUPED",
        "cat_titles": {"18-39": "Jóvenes", "40-59": "Adultos"},
    })
    assert c.cat_titles == {"18-39": "Jóvenes", "40-59": "Adultos"}


def test_chart_cat_titles_default_none():
    from aurum_encuestas.models import Chart
    c = Chart.model_validate({"id":"c1","question_id":"q1","breakdown_ids":[],"chart_type":"PIE"})
    assert c.cat_titles is None


def test_chart_grid_cols_rejects_zero():
    import pytest
    from pydantic import ValidationError
    from aurum_encuestas.models import Chart
    with pytest.raises(ValidationError):
        Chart.model_validate({"id":"c1","question_id":"q1","breakdown_ids":[],
                              "chart_type":"PIE_GROUPED","grid_cols":0})


def test_chart_grid_cols_rejects_negative():
    import pytest
    from pydantic import ValidationError
    from aurum_encuestas.models import Chart
    with pytest.raises(ValidationError):
        Chart.model_validate({"id":"c1","question_id":"q1","breakdown_ids":[],
                              "chart_type":"PIE_GROUPED","grid_cols":-3})


def test_chart_grid_cols_accepts_positive():
    from aurum_encuestas.models import Chart
    c = Chart.model_validate({"id":"c1","question_id":"q1","breakdown_ids":[],
                              "chart_type":"PIE_GROUPED","grid_cols":3})
    assert c.grid_cols == 3
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_models.py -k "cat_titles or grid_cols_rejects or grid_cols_accepts" -v
```

Expected: FAIL — `cat_titles` field doesn't exist; `grid_cols=0/-3` currently accepted.

- [ ] **Step 3: Update `Chart` model**

In `backend/aurum_encuestas/models.py`, find the `Chart` class. Update the field definitions:

```python
class Chart(BaseModel):
    id: str
    question_id: str
    breakdown_ids: list[str] = Field(default_factory=list)
    chart_type: ChartType
    show_legend: bool = False
    grid_cols: int | None = Field(default=None, ge=1)
    title: str | None = None
    cat_titles: dict[str, str] | None = None
    colors: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _reject_legacy(cls, data):
        # (unchanged from Fase A)
        ...
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_models.py -k "cat_titles or grid_cols_rejects or grid_cols_accepts" -v
```

Expected: PASS.

- [ ] **Step 5: Run full suite to catch regressions**

```bash
cd backend && arch -arm64 .venv/bin/pytest -q 2>&1 | tail -3
```

Expected: 288+ pass, 0 fail.

- [ ] **Step 6: Commit**

```bash
git add backend/aurum_encuestas/models.py backend/tests/test_models.py
git commit -m "feat(schema): Chart.cat_titles + grid_cols ge=1 validator

cat_titles dict[str, str] | None enables per-pie title overrides in
PIE_GROUPED. grid_cols gains a positive-integer validator to reject
0 and negative values at the schema layer.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `available_chart_types` Fase B = 5 items

**Files:**
- Modify: `backend/aurum_encuestas/style_guide.py`
- Modify: `backend/tests/test_style_guide.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `StyleGuide.available_chart_types` default + `BUILTIN_STYLE_GUIDE["available_chart_types"]` return `["PIE","PIE_GROUPED","BAR_HORIZONTAL","BAR_HORIZONTAL_GROUPED","TABLE_WITH_MINIBARS"]`.

- [ ] **Step 1: Failing test**

Append to `backend/tests/test_style_guide.py`:

```python
def test_builtin_available_chart_types_phase_b_is_five():
    from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE
    assert BUILTIN_STYLE_GUIDE.available_chart_types == [
        "PIE", "PIE_GROUPED",
        "BAR_HORIZONTAL", "BAR_HORIZONTAL_GROUPED",
        "TABLE_WITH_MINIBARS",
    ]


def test_style_guide_default_available_chart_types_phase_b_is_five():
    from aurum_encuestas.style_guide import StyleGuide
    sg = StyleGuide()
    assert sg.available_chart_types == [
        "PIE", "PIE_GROUPED",
        "BAR_HORIZONTAL", "BAR_HORIZONTAL_GROUPED",
        "TABLE_WITH_MINIBARS",
    ]
```

The Fase A test `test_builtin_available_chart_types_phase_a_is_three` will start failing — DELETE it (it asserted the now-superseded 3-item list).

- [ ] **Step 2: Run, expect failing**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_style_guide.py::test_builtin_available_chart_types_phase_b_is_five tests/test_style_guide.py::test_style_guide_default_available_chart_types_phase_b_is_five -v
```

Expected: FAIL.

- [ ] **Step 3: Update both list sites**

In `backend/aurum_encuestas/style_guide.py`, update `StyleGuide.available_chart_types` default factory:

```python
    available_chart_types: list[str] = Field(
        default_factory=lambda: [
            "PIE", "PIE_GROUPED",
            "BAR_HORIZONTAL", "BAR_HORIZONTAL_GROUPED",
            "TABLE_WITH_MINIBARS",
        ]
    )
```

And `BUILTIN_STYLE_GUIDE["available_chart_types"]`:

```python
    "available_chart_types": [
        "PIE", "PIE_GROUPED",
        "BAR_HORIZONTAL", "BAR_HORIZONTAL_GROUPED",
        "TABLE_WITH_MINIBARS",
    ],
```

Delete the Fase A test `test_builtin_available_chart_types_phase_a_is_three` from `test_style_guide.py` if present.

Adapt `test_builtin_palette_matches_aurora_reference` if it asserts the now-stale 3-item shape: update its assertion to check for any of the 5 types instead.

- [ ] **Step 4: Run tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_style_guide.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/style_guide.py backend/tests/test_style_guide.py
git commit -m "feat(style_guide): expose 5 chart types in Fase B

available_chart_types extended to include PIE_GROUPED and
BAR_HORIZONTAL_GROUPED. Fase A's 3-item assertion test deleted in
favor of the new 5-item assertion.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `EnrichedChart` propagates new fields

**Files:**
- Modify: `backend/aurum_encuestas/pattern_classifier.py`
- Modify: `backend/tests/test_pattern_classifier.py`

**Interfaces:**
- Consumes (from Task 1): `Chart` model with the new fields.
- Produces: `EnrichedChart` dataclass carries `show_legend: bool`, `grid_cols: int | None`, `title: str | None`, `cat_titles: dict | None`. `build_slide_config` propagates them from each `Chart`.

- [ ] **Step 1: Failing test**

Append to `backend/tests/test_pattern_classifier.py`:

```python
def test_enriched_chart_propagates_phase_b_fields():
    from aurum_encuestas.pattern_classifier import build_slide_config
    from aurum_encuestas.models import Chart, Question, Breakdown, ParsedDB
    from types import SimpleNamespace

    chart = Chart(
        id="c1", question_id="q1", breakdown_ids=["edad"],
        chart_type="PIE_GROUPED",
        show_legend=True, grid_cols=2,
        title="Plazo del crédito",
        cat_titles={"18-39": "Jóvenes", "40-59": "Adultos"},
    )
    slide_def = SimpleNamespace(charts=[chart], analyses=[])
    parsed = ParsedDB(
        questions=[Question(id="q1", code="Q1", text="t", options=["Sí","No"], confidence=0.9)],
        breakdowns=[Breakdown(id="edad", label="Edad", categories=["18-39","40-59"])],
        sample_size=500, data_blocks={"counts_cols":[],"pct_row_cols":[],"pct_col_cols":[]},
    )
    cfg = build_slide_config(slide_def, parsed_db=parsed, db_path=None)
    ec = cfg.charts[0]
    assert ec.show_legend is True
    assert ec.grid_cols == 2
    assert ec.title == "Plazo del crédito"
    assert ec.cat_titles == {"18-39": "Jóvenes", "40-59": "Adultos"}
```

- [ ] **Step 2: Run, expect failing**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_pattern_classifier.py::test_enriched_chart_propagates_phase_b_fields -v
```

Expected: FAIL — `EnrichedChart` lacks the new fields.

- [ ] **Step 3: Update `EnrichedChart` and `build_slide_config`**

In `backend/aurum_encuestas/pattern_classifier.py`, find the nested `EnrichedChart` dataclass (around line 453) and update it:

```python
    @dataclass
    class EnrichedChart:
        id: str
        question_id: str
        breakdown_ids: list[str]
        chart_type: str
        colors: list
        question: _Any = None
        data: dict = field(default_factory=dict)
        all_breakdowns_data: dict = field(default_factory=dict)
        show_legend: bool = False
        grid_cols: int | None = None
        title: str | None = None
        cat_titles: dict | None = None
```

Find the `EnrichedChart(...)` construction in `build_slide_config` (around line 493) and pass the new fields:

```python
            EnrichedChart(
                id=chart.id,
                question_id=chart.question_id,
                breakdown_ids=list(chart.breakdown_ids),
                chart_type=chart.chart_type,
                colors=getattr(chart, "colors", []),
                question=question,
                data=chart_data,
                all_breakdowns_data=all_bds,
                show_legend=getattr(chart, "show_legend", False),
                grid_cols=getattr(chart, "grid_cols", None),
                title=getattr(chart, "title", None),
                cat_titles=getattr(chart, "cat_titles", None),
            )
```

- [ ] **Step 4: Run tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_pattern_classifier.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/pattern_classifier.py backend/tests/test_pattern_classifier.py
git commit -m "feat(classifier): EnrichedChart propagates Fase B fields

show_legend, grid_cols, title, cat_titles now flow from Chart through
build_slide_config to the renderers.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `chart_renderer` — chart title + show_legend + remove Fase B warning

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/chart_renderer.py`
- Modify: `backend/tests/test_element_renderers.py`

**Interfaces:**
- Consumes (from Task 3): `source_chart.title`, `source_chart.show_legend`.
- Produces: For single-shape chart_types (PIE, BAR_HORIZONTAL, BAR_HORIZONTAL_GROUPED), `render()` writes `chart.chart_title.text_frame.text = title` when `source_chart.title` set; sets `chart.legend.position = BOTTOM` when `chart_type == BAR_HORIZONTAL_GROUPED` and `show_legend=True`; suppresses legend otherwise for BAR_HORIZONTAL_GROUPED. The Fase A warning block emitting "Fase B" is REMOVED.

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_element_renderers.py`:

```python
def test_chart_title_renders_on_chart_when_set():
    from pptx import Presentation
    from types import SimpleNamespace
    from aurum_encuestas.element_renderers.chart_renderer import render
    from aurum_encuestas.element_renderers.render_context import RenderContext

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    q = SimpleNamespace(options=["A","B"])
    src = SimpleNamespace(
        question=q, breakdown_ids=[], chart_type="BAR_HORIZONTAL",
        title="Plazo del crédito",
        colors=[], show_legend=False, grid_cols=None, cat_titles=None,
        data={"General": {"A":{"pct":0.5},"B":{"pct":0.5}}},
    )
    ctx = RenderContext(
        slide_config=SimpleNamespace(charts=[src]),
        chart_colors=["#7F7F7F","#404040","#EEC245","#C00000","#FFC000"],
        resolved_colors={"primary":"#7F7F7F","secondary":"#404040","background":"#EEC245"},
        free_area={"x":0,"y":0,"cx":12_192_000,"cy":6_858_000},
        typography={"label_size":9,"body_size":10,"title_size":16,"font_family":"Calibri"},
        style_guide=None, resolved_anchors={},
    )
    render(slide, {"kind":"chart","id":"c","position":{"x_rel":0,"y_rel":0,"w_rel":1,"h_rel":1},
                   "data_source":{"chart_ref_index":0,"value_field":"pct"}}, ctx)
    chart_shape = next(sh for sh in slide.shapes if sh.has_chart)
    assert chart_shape.chart.has_title is True
    assert "Plazo del crédito" in chart_shape.chart.chart_title.text_frame.text


def test_bar_horizontal_grouped_legend_bottom_when_show_legend():
    from pptx import Presentation
    from pptx.enum.chart import XL_LEGEND_POSITION
    from types import SimpleNamespace
    from aurum_encuestas.element_renderers.chart_renderer import render
    from aurum_encuestas.element_renderers.render_context import RenderContext

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    q = SimpleNamespace(options=["A","B"])
    src = SimpleNamespace(
        question=q, breakdown_ids=["entidad"], chart_type="BAR_HORIZONTAL_GROUPED",
        show_legend=True, title=None, grid_cols=None, cat_titles=None,
        colors=[],
        data={
            "General": {"A":{"pct":0.5},"B":{"pct":0.5}},
            "Banco":   {"A":{"pct":0.4},"B":{"pct":0.6}},
            "MAF":     {"A":{"pct":0.7},"B":{"pct":0.3}},
        },
    )
    ctx = RenderContext(
        slide_config=SimpleNamespace(charts=[src]),
        chart_colors=["#7F7F7F","#404040","#EEC245","#C00000","#FFC000"],
        resolved_colors={"primary":"#7F7F7F","secondary":"#404040","background":"#EEC245"},
        free_area={"x":0,"y":0,"cx":12_192_000,"cy":6_858_000},
        typography={"label_size":9,"body_size":10,"title_size":16,"font_family":"Calibri"},
        style_guide=None, resolved_anchors={},
    )
    render(slide, {"kind":"chart","id":"c","position":{"x_rel":0,"y_rel":0,"w_rel":1,"h_rel":1},
                   "data_source":{"chart_ref_index":0,"value_field":"pct"}}, ctx)
    chart_shape = next(sh for sh in slide.shapes if sh.has_chart)
    assert chart_shape.chart.has_legend is True
    assert chart_shape.chart.legend.position == XL_LEGEND_POSITION.BOTTOM


def test_bar_horizontal_grouped_no_legend_when_show_legend_false():
    from pptx import Presentation
    from types import SimpleNamespace
    from aurum_encuestas.element_renderers.chart_renderer import render
    from aurum_encuestas.element_renderers.render_context import RenderContext

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    q = SimpleNamespace(options=["A","B"])
    src = SimpleNamespace(
        question=q, breakdown_ids=["entidad"], chart_type="BAR_HORIZONTAL_GROUPED",
        show_legend=False, title=None, grid_cols=None, cat_titles=None,
        colors=[],
        data={"General":{"A":{"pct":0.5},"B":{"pct":0.5}},
              "Banco":{"A":{"pct":0.4},"B":{"pct":0.6}}},
    )
    ctx = RenderContext(
        slide_config=SimpleNamespace(charts=[src]),
        chart_colors=["#7F7F7F","#404040","#EEC245","#C00000","#FFC000"],
        resolved_colors={"primary":"#7F7F7F","secondary":"#404040","background":"#EEC245"},
        free_area={"x":0,"y":0,"cx":12_192_000,"cy":6_858_000},
        typography={"label_size":9,"body_size":10,"title_size":16,"font_family":"Calibri"},
        style_guide=None, resolved_anchors={},
    )
    render(slide, {"kind":"chart","id":"c","position":{"x_rel":0,"y_rel":0,"w_rel":1,"h_rel":1},
                   "data_source":{"chart_ref_index":0,"value_field":"pct"}}, ctx)
    chart_shape = next(sh for sh in slide.shapes if sh.has_chart)
    assert chart_shape.chart.has_legend is False


def test_grouped_fallback_warning_removed(caplog):
    import logging
    from pptx import Presentation
    from types import SimpleNamespace
    from aurum_encuestas.element_renderers.chart_renderer import render
    from aurum_encuestas.element_renderers.render_context import RenderContext

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    q = SimpleNamespace(options=["A","B"])
    src = SimpleNamespace(
        question=q, breakdown_ids=["entidad"], chart_type="BAR_HORIZONTAL_GROUPED",
        show_legend=False, title=None, grid_cols=None, cat_titles=None, colors=[],
        data={"Banco":{"A":{"pct":0.4},"B":{"pct":0.6}}},
    )
    ctx = RenderContext(
        slide_config=SimpleNamespace(charts=[src]),
        chart_colors=["#7F7F7F","#404040","#EEC245","#C00000","#FFC000"],
        resolved_colors={"primary":"#7F7F7F","secondary":"#404040","background":"#EEC245"},
        free_area={"x":0,"y":0,"cx":12_192_000,"cy":6_858_000},
        typography={"label_size":9,"body_size":10,"title_size":16,"font_family":"Calibri"},
        style_guide=None, resolved_anchors={},
    )
    with caplog.at_level(logging.WARNING):
        render(slide, {"kind":"chart","id":"c","position":{"x_rel":0,"y_rel":0,"w_rel":1,"h_rel":1},
                       "data_source":{"chart_ref_index":0,"value_field":"pct"}}, ctx)
    assert not any("Fase B" in r.message for r in caplog.records), \
        f"unexpected Fase B warning still emitted: {[r.message for r in caplog.records]}"
```

The Fase A test `test_grouped_chart_type_logs_warning_and_falls_back` will start failing because the warning is removed. DELETE it.

- [ ] **Step 2: Run, expect failing**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_element_renderers.py -k "chart_title or grouped_legend or grouped_fallback_warning_removed" -v
```

Expected: FAIL.

- [ ] **Step 3: Update `render()` — remove Fase B warning, add title/legend wiring**

In `backend/aurum_encuestas/element_renderers/chart_renderer.py`, find the `render()` function. Locate and DELETE the Fase A warning block:

```python
    if chart_type_str in ("PIE_GROUPED", "BAR_HORIZONTAL_GROUPED"):
        log.warning(
            "chart_type %s grouped render is Fase B — emitting single-series fallback",
            chart_type_str,
        )
```

After the existing chart_shape creation block (`chart_shape = slide.shapes.add_chart(...)`) and before any existing legend handling, add the Fase B wiring. Locate the existing legend block (it currently sets `chart.has_legend = False` for pie/donut) and REPLACE it with:

```python
    # Chart title (all single-shape types)
    title_str = (getattr(source_chart, "title", None) or "").strip()
    if title_str:
        chart.has_title = True
        chart.chart_title.text_frame.text = title_str
    else:
        chart.has_title = False

    # Legend (Fase B):
    show_legend = bool(getattr(source_chart, "show_legend", False))
    if is_pie:
        chart.has_legend = False
    elif chart_type_str == "BAR_HORIZONTAL_GROUPED" and show_legend:
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
    else:
        chart.has_legend = False
```

Replace the existing element-driven legend block (`legend_str = element.get("legend", "none")` etc) with the Fase B form above. The pattern's `legend` element field is now informational — `Chart.show_legend` is authoritative.

- [ ] **Step 4: Run tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_element_renderers.py -k "chart_title or grouped_legend or grouped_fallback_warning_removed" -v
```

Expected: PASS for the new tests.

- [ ] **Step 5: Run full file to confirm no regressions**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_element_renderers.py -v 2>&1 | tail -10
```

Expected: only the deleted `test_grouped_chart_type_logs_warning_and_falls_back` is gone; everything else passes.

- [ ] **Step 6: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/chart_renderer.py backend/tests/test_element_renderers.py
git commit -m "feat(chart_renderer): chart.title + BAR_HORIZONTAL_GROUPED legend

Single-shape chart_types now render Chart.title via has_title +
chart_title.text. BAR_HORIZONTAL_GROUPED with show_legend=True
enables a bottom legend; otherwise no legend. PIE always no legend.
The Fase A 'Fase B' fallback warning is removed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `chart_renderer` — `_render_pie_grouped` + helpers

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/chart_renderer.py`
- Modify: `backend/tests/test_element_renderers.py`

**Interfaces:**
- Consumes (from Task 4): chart title + legend pipelines stay intact for single-shape types.
- Produces:
  - `_render_pie_grouped(slide, element, source_chart, ctx) -> None`
  - `_compute_grid_dims(n: int, grid_cols: int | None) -> tuple[int, int]` — returns `(rows, cols)`.
  - `_add_title_textbox(slide, x, y, w, h, text, ctx) -> None` — centered title text-box above the grid.
  - `render()` dispatches to `_render_pie_grouped` early when `chart_type_str == "PIE_GROUPED"`.

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_element_renderers.py`:

```python
def test_compute_grid_dims_auto_rule():
    from aurum_encuestas.element_renderers.chart_renderer import _compute_grid_dims
    assert _compute_grid_dims(1, None) == (1, 1)
    assert _compute_grid_dims(2, None) == (1, 2)
    assert _compute_grid_dims(3, None) == (1, 3)
    assert _compute_grid_dims(4, None) == (2, 2)
    assert _compute_grid_dims(5, None) == (2, 3)
    assert _compute_grid_dims(6, None) == (2, 3)
    assert _compute_grid_dims(7, None) == (3, 3)
    assert _compute_grid_dims(9, None) == (3, 3)


def test_compute_grid_dims_user_override():
    from aurum_encuestas.element_renderers.chart_renderer import _compute_grid_dims
    assert _compute_grid_dims(6, 2) == (3, 2)
    assert _compute_grid_dims(6, 3) == (2, 3)
    assert _compute_grid_dims(5, 1) == (5, 1)


def _make_pie_grouped_ctx(n_cats=3):
    from types import SimpleNamespace
    from aurum_encuestas.element_renderers.render_context import RenderContext
    q = SimpleNamespace(options=["Sí","No"])
    cats = {f"cat{i}": {"Sí":{"pct":0.5,"count":50},"No":{"pct":0.5,"count":50}} for i in range(n_cats)}
    src = SimpleNamespace(
        question=q, breakdown_ids=["entidad"], chart_type="PIE_GROUPED",
        show_legend=False, title=None, grid_cols=None, cat_titles=None, colors=[],
        data={}, all_breakdowns_data={"entidad":{"label":"Entidad","categories":cats}},
    )
    ctx = RenderContext(
        slide_config=SimpleNamespace(charts=[src]),
        chart_colors=["#7F7F7F","#404040","#EEC245","#C00000","#FFC000"],
        resolved_colors={"primary":"#7F7F7F","secondary":"#404040","background":"#EEC245"},
        free_area={"x":0,"y":0,"cx":12_192_000,"cy":6_858_000},
        typography={"label_size":9,"body_size":10,"title_size":16,"font_family":"Calibri"},
        style_guide=None, resolved_anchors={},
    )
    return src, ctx


def test_pie_grouped_renders_n_pie_shapes():
    from pptx import Presentation
    from pptx.enum.chart import XL_CHART_TYPE
    from aurum_encuestas.element_renderers.chart_renderer import render
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _src, ctx = _make_pie_grouped_ctx(n_cats=3)
    render(slide, {"kind":"chart","id":"c","position":{"x_rel":0,"y_rel":0,"w_rel":1,"h_rel":1},
                   "data_source":{"chart_ref_index":0,"value_field":"pct"}}, ctx)
    chart_shapes = [sh for sh in slide.shapes if sh.has_chart]
    assert len(chart_shapes) == 3
    for sh in chart_shapes:
        assert sh.chart.chart_type == XL_CHART_TYPE.PIE


def test_pie_grouped_user_grid_cols_overrides_auto():
    from pptx import Presentation
    from aurum_encuestas.element_renderers.chart_renderer import render
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    src, ctx = _make_pie_grouped_ctx(n_cats=6)
    src.grid_cols = 2
    render(slide, {"kind":"chart","id":"c","position":{"x_rel":0,"y_rel":0,"w_rel":1,"h_rel":1},
                   "data_source":{"chart_ref_index":0,"value_field":"pct"}}, ctx)
    chart_shapes = [sh for sh in slide.shapes if sh.has_chart]
    assert len(chart_shapes) == 6
    # Row 1 has 2 shapes at same Y; Row 2 same; Row 3 same → 3 distinct Y values.
    y_set = {sh.top for sh in chart_shapes}
    assert len(y_set) == 3


def test_pie_grouped_cat_titles_override():
    from pptx import Presentation
    from aurum_encuestas.element_renderers.chart_renderer import render
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    src, ctx = _make_pie_grouped_ctx(n_cats=2)
    src.cat_titles = {"cat0": "Banco", "cat1": "MAF"}
    render(slide, {"kind":"chart","id":"c","position":{"x_rel":0,"y_rel":0,"w_rel":1,"h_rel":1},
                   "data_source":{"chart_ref_index":0,"value_field":"pct"}}, ctx)
    chart_shapes = [sh for sh in slide.shapes if sh.has_chart]
    titles = {sh.chart.chart_title.text_frame.text for sh in chart_shapes}
    assert titles == {"Banco", "MAF"}


def test_pie_grouped_chart_title_renders_textbox_above_grid():
    from pptx import Presentation
    from aurum_encuestas.element_renderers.chart_renderer import render
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    src, ctx = _make_pie_grouped_ctx(n_cats=2)
    src.title = "Plazo del crédito"
    render(slide, {"kind":"chart","id":"c","position":{"x_rel":0,"y_rel":0,"w_rel":1,"h_rel":1},
                   "data_source":{"chart_ref_index":0,"value_field":"pct"}}, ctx)
    textboxes = [sh for sh in slide.shapes if sh.has_text_frame and not sh.has_chart]
    assert any("Plazo del crédito" in tb.text_frame.text for tb in textboxes)


def test_pie_grouped_empty_breakdown_warns(caplog):
    import logging
    from pptx import Presentation
    from types import SimpleNamespace
    from aurum_encuestas.element_renderers.chart_renderer import render
    from aurum_encuestas.element_renderers.render_context import RenderContext

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    q = SimpleNamespace(options=["Sí","No"])
    src = SimpleNamespace(
        question=q, breakdown_ids=["edad"], chart_type="PIE_GROUPED",
        show_legend=False, title=None, grid_cols=None, cat_titles=None, colors=[],
        data={}, all_breakdowns_data={},   # ← missing breakdown
    )
    ctx = RenderContext(
        slide_config=SimpleNamespace(charts=[src]),
        chart_colors=["#7F7F7F"], resolved_colors={},
        free_area={"x":0,"y":0,"cx":12_192_000,"cy":6_858_000},
        typography={"label_size":9,"body_size":10,"title_size":16,"font_family":"Calibri"},
        style_guide=None, resolved_anchors={},
    )
    with caplog.at_level(logging.WARNING):
        render(slide, {"kind":"chart","id":"c","position":{"x_rel":0,"y_rel":0,"w_rel":1,"h_rel":1},
                       "data_source":{"chart_ref_index":0,"value_field":"pct"}}, ctx)
    assert not any(sh.has_chart for sh in slide.shapes)
    assert any("PIE_GROUPED" in r.message and "empty" in r.message.lower() for r in caplog.records)
```

- [ ] **Step 2: Run, expect failing**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_element_renderers.py -k "compute_grid_dims or pie_grouped" -v
```

Expected: FAIL.

- [ ] **Step 3: Implement helpers + dispatch**

In `backend/aurum_encuestas/element_renderers/chart_renderer.py`, add the helpers (near the top, after `_LEGEND_POSITION_MAP`):

```python
def _compute_grid_dims(n: int, grid_cols: int | None) -> tuple[int, int]:
    """Return (rows, cols) for PIE_GROUPED grid.

    User-set grid_cols overrides auto rule (rows=1 if N<=3 else 2 if N<=6 else 3).
    """
    if grid_cols and grid_cols >= 1:
        cols = grid_cols
        rows = (n + cols - 1) // cols
        return rows, cols
    rows = 1 if n <= 3 else (2 if n <= 6 else 3)
    cols = (n + rows - 1) // rows
    return rows, cols


def _add_title_textbox(slide, x: int, y: int, w: int, h: int, text: str, ctx) -> None:
    """Centered bold title text-box above a PIE_GROUPED grid."""
    from pptx.enum.text import PP_ALIGN
    tb = slide.shapes.add_textbox(Emu(x), Emu(y), Emu(w), Emu(h))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = text
    run.font.size = Pt(ctx.typography.get("title_size", 16))
    run.font.bold = True
    run.font.name = ctx.typography.get("font_family", "Calibri")


def _render_pie_grouped(slide, element: dict, source_chart, ctx) -> None:
    """Render PIE_GROUPED as N pie chart shapes inside a grid bbox.

    Each cat of source_chart.breakdown_ids[0] becomes one pie. Per-pie title
    uses cat_titles[cat] or cat label. Optional chart.title renders as a
    text-box above the grid.
    """
    x, y, cx, cy = _resolve_position(element.get("position", {}), ctx)

    bds = list(getattr(source_chart, "breakdown_ids", []) or [])
    primary_bd = bds[0] if bds else None
    all_bds = getattr(source_chart, "all_breakdowns_data", {}) or {}
    bd_data = all_bds.get(primary_bd, {}) if primary_bd else {}
    categories = bd_data.get("categories", {}) or {}

    if not categories:
        log.warning("PIE_GROUPED with empty breakdown — skipping render")
        return

    cat_list = list(categories.keys())
    n = len(cat_list)
    rows, cols = _compute_grid_dims(n, getattr(source_chart, "grid_cols", None))
    cat_titles = getattr(source_chart, "cat_titles", None) or {}
    question = getattr(source_chart, "question", None)
    options = list(question.options) if question else []

    title_str = (getattr(source_chart, "title", None) or "").strip()
    title_band_h = 400_000 if title_str else 0
    if title_str:
        _add_title_textbox(slide, x, y, cx, title_band_h, title_str, ctx)

    grid_y = y + title_band_h
    grid_h = cy - title_band_h
    gap_x = int(0.02 * cx)
    gap_y = int(0.06 * grid_h)
    cell_w = (cx - gap_x * (cols - 1)) // cols
    cell_h = (grid_h - gap_y * (rows - 1)) // rows

    fallback_colors = list(ctx.chart_colors or [])
    per_chart_colors = list(getattr(source_chart, "colors", []) or [])

    for i, cat in enumerate(cat_list):
        r, c = divmod(i, cols)
        cell_x = x + c * (cell_w + gap_x)
        cell_y = grid_y + r * (cell_h + gap_y)

        cd = CategoryChartData()
        cd.categories = options
        values = [float((categories[cat].get(opt) or {}).get("pct", 0) or 0) for opt in options]
        cd.add_series("", values)

        try:
            chart_shape = slide.shapes.add_chart(
                XL_CHART_TYPE.PIE,
                Emu(cell_x), Emu(cell_y),
                Emu(cell_w), Emu(cell_h),
                cd,
            )
        except Exception as exc:
            log.error("PIE_GROUPED: add_chart failed for cat %r: %s", cat, exc)
            continue
        sub_chart = chart_shape.chart
        sub_chart.has_legend = False

        # Per-slice colors
        n_pts = len(options)
        effective_colors: list[str] = []
        for j in range(max(n_pts, len(per_chart_colors), len(fallback_colors))):
            if j < len(per_chart_colors) and per_chart_colors[j]:
                effective_colors.append(per_chart_colors[j])
            elif fallback_colors:
                effective_colors.append(fallback_colors[j % len(fallback_colors)])
            else:
                effective_colors.append("#7F7F7F")
        _apply_series_colors(sub_chart, effective_colors)

        # Labels: category + percentage inside slice
        _apply_labels(sub_chart, {
            "show_category_name": True, "show_percentage": True,
            "show_value": False, "format": "0.0%",
            "position": "outside_end",
        }, ctx)

        # Per-pie title via cat_titles override
        sub_title = cat_titles.get(cat) or cat
        sub_chart.has_title = True
        sub_chart.chart_title.text_frame.text = sub_title

        # Pie rotation (existing rule)
        sorted_vals = sorted(values, reverse=True)
        if sorted_vals:
            total = sum(v for v in sorted_vals if v) or 1.0
            dom = (sorted_vals[0] or 0) / total
            angle = 180 if abs(dom - 0.5) < 0.05 else int(round(-90 - dom * 180)) % 360
            _set_pie_first_slice_angle(sub_chart, angle)
```

In `render()`, immediately after `chart_type_str` is resolved (and before `xl_chart_type = _CHART_TYPE_MAP.get(...)` is read), add the dispatch:

```python
    if chart_type_str == "PIE_GROUPED":
        _render_pie_grouped(slide, element, source_chart, ctx)
        return
```

- [ ] **Step 4: Run tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_element_renderers.py -k "compute_grid_dims or pie_grouped" -v
```

Expected: PASS.

- [ ] **Step 5: Full file run**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_element_renderers.py -v 2>&1 | tail -10
```

Expected: all element_renderers tests green.

- [ ] **Step 6: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/chart_renderer.py backend/tests/test_element_renderers.py
git commit -m "feat(chart_renderer): PIE_GROUPED N-pie grid render

chart_renderer.render dispatches PIE_GROUPED to a dedicated helper
that fans out N pie shapes inside a grid bbox. Grid dims derive from
chart.grid_cols (user override) or the auto rule (rows=1 if N<=3,
2 if N<=6, 3 otherwise). Per-pie title uses cat_titles override or
falls back to the cat label. Chart.title renders as a centered
text-box above the grid.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: `table_renderer` — `_SEGMENTED_CELLS_FASE_B` + no-label-col branch + weight recalc

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/table_renderer.py`
- Modify: `backend/tests/test_table_renderer.py`

**Interfaces:**
- Consumes: nothing new (uses existing pattern_renderer dispatch).
- Produces:
  - Module-level `_SEGMENTED_CELLS_FASE_B: dict` — image-faithful style overrides.
  - `_render_segmented_breakdowns` overrides per-pattern cells with `_SEGMENTED_CELLS_FASE_B` for BOTH single-panel and multi-panel paths.
  - `_render_panel` skips the label column entirely when `option_cfg.get("label_col_width_rel", 0.18) <= 0.001`.
  - `_pack_panels_into_rows` weight excludes label col when label is suppressed.

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_table_renderer.py`:

```python
def test_segmented_breakdowns_single_panel_uses_fase_b_cells(edad_chart, render_ctx):
    """Fase B: single-panel uses _SEGMENTED_CELLS_FASE_B (no label col,
    fill=primary, white text on option rows)."""
    from pptx import Presentation
    from aurum_encuestas.element_renderers.table_renderer import render
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    render(slide, {
        "kind":"table","id":"t","position":{"x_rel":0.1,"y_rel":0.1,"w_rel":0.8,"h_rel":0.8},
        "structure":"segmented_breakdowns",
        "data_source":{"chart_ref_index":0,"breakdown_groups":["edad"]},
    }, render_ctx)
    tbl = next(sh.table for sh in slide.shapes if sh.has_table)
    cols = list(tbl.columns)
    # No label col: 1 label + 2 cats = 3 cols becomes 2 cols (just cats)
    assert len(cols) == 2, f"expected 2 cols (cats only, no label), got {len(cols)}"
    rows = list(tbl.rows)
    assert len(rows) == 5, f"expected 5 rows, got {len(rows)}"


def test_segmented_breakdowns_multi_panel_uses_fase_b_cells():
    """Multi-panel must apply the same Fase B image-faithful styles
    (post-Fase A multi-panel used pattern's defaults)."""
    from pptx import Presentation
    from types import SimpleNamespace
    from aurum_encuestas.element_renderers.table_renderer import render
    from aurum_encuestas.element_renderers.render_context import RenderContext

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    q = SimpleNamespace(options=["Sí","No"])
    src = SimpleNamespace(
        question=q, breakdown_ids=["edad","sexo"], chart_type="TABLE_WITH_MINIBARS",
        show_legend=False, title=None, grid_cols=None, cat_titles=None, colors=[],
        data={},
        all_breakdowns_data={
            "edad": {"label":"Edad","categories":{
                "18-39":{"Sí":{"pct":0.92,"count":230},"No":{"pct":0.08,"count":20}},
                "40-59":{"Sí":{"pct":0.91,"count":228},"No":{"pct":0.09,"count":22}},
            }},
            "sexo": {"label":"Sexo","categories":{
                "F":{"Sí":{"pct":0.91,"count":250},"No":{"pct":0.09,"count":25}},
                "M":{"Sí":{"pct":0.92,"count":230},"No":{"pct":0.08,"count":20}},
            }},
        },
    )
    ctx = RenderContext(
        slide_config=SimpleNamespace(charts=[src]),
        chart_colors=["#7F7F7F","#404040","#EEC245","#C00000","#FFC000"],
        resolved_colors={"primary":"#7F7F7F","secondary":"#404040","background":"#EEC245"},
        free_area={"x":487680,"y":1097280,"cx":11216640,"cy":5212080},
        typography={"label_size":9,"body_size":10,"title_size":16,"font_family":"Calibri"},
        style_guide=None, resolved_anchors={},
    )
    render(slide, {
        "kind":"table","id":"t","position":{"x_rel":0.02,"y_rel":0.05,"w_rel":0.96,"h_rel":0.90},
        "structure":"segmented_breakdowns",
        "data_source":{"chart_ref_index":0,"breakdown_groups":["edad","sexo"]},
    }, ctx)
    tables = [sh.table for sh in slide.shapes if sh.has_table]
    assert len(tables) == 2, f"expected 2 panels (Edad + Sexo), got {len(tables)}"
    for tbl in tables:
        # 2 cats per panel; no label col → 2 cols
        assert len(list(tbl.columns)) == 2


def test_pack_panels_weight_uses_cats_only_when_label_col_zero():
    from aurum_encuestas.element_renderers.table_renderer import (
        _pack_panels_into_rows, _SEGMENTED_CELLS_FASE_B,
    )
    panels = [
        {"group_id":"edad","label":"Edad","cats":[("18-39",{}),("40-59",{})]},
        {"group_id":"sexo","label":"Sexo","cats":[("F",{}),("M",{})]},
        {"group_id":"nse","label":"NSE","cats":[("A",{}),("B",{}),("C",{}),("D",{}),("E",{})]},
    ]
    label_col_w = _SEGMENTED_CELLS_FASE_B["option_row"]["label_col_width_rel"]
    rows = _pack_panels_into_rows(panels, max_row_weight=12, label_col_width_rel=label_col_w)
    # Total weight without label col = 2+2+5 = 9 ≤ 12 → single row.
    assert len(rows) == 1
    assert len(rows[0]) == 3
```

(Assumes `edad_chart` and `render_ctx` fixtures from the existing single-panel test in Fase A's `test_table_renderer.py` are still present.)

- [ ] **Step 2: Run, expect failing**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_table_renderer.py -v 2>&1 | tail -15
```

Expected: FAIL (current cells_cfg has label_col_width_rel=0.18 from Fase A; weight calc uses `1 + len(cats)`).

- [ ] **Step 3: Add `_SEGMENTED_CELLS_FASE_B` constant**

At module level in `backend/aurum_encuestas/element_renderers/table_renderer.py` (after imports):

```python
_SEGMENTED_CELLS_FASE_B: dict = {
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
        "label_col_width_rel": 0.0,
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

- [ ] **Step 4: Update `_render_panel` — no-label-col branch**

Find `_render_panel` in `table_renderer.py`. Locate where `label_col_w_rel` is read and `n_cols` is set. Replace with:

```python
    label_col_w_rel = option_cfg.get("label_col_width_rel", 0.18)
    if label_col_w_rel <= 0.001:
        n_cols = n_cat
        label_w = 0
    else:
        n_cols = 1 + n_cat
        # existing label_w computation:
        label_col_w_rel_pre = label_col_w_rel
        MIN_LABEL_EMU = 500000
        label_w = max(MIN_LABEL_EMU, int(label_col_w_rel_pre * table_w))
        if label_w > table_w * 0.4:
            label_w = int(table_w * 0.4)
```

Throughout the rest of `_render_panel`, every reference to col index 0 for label writes must be guarded by `if label_w > 0`. The column offsets for cat headers, counts, and option values shift to start at 0 when `label_w == 0` (was column 1):

```python
    first_data_col = 1 if label_w > 0 else 0
    # Cat headers
    for c, (cat_label, _) in enumerate(cats):
        _set_cell(tbl.cell(1, first_data_col + c), cat_label, ctx, cat_hdr_style)
    # Counts row
    if label_w > 0:
        _set_cell(tbl.cell(2, 0), counts_cfg.get("label_first_col", ""), ctx, counts_style)
    for c, (_, opt_cells) in enumerate(cats):
        total = sum(int((opt_cells.get(opt) or {}).get("count") or 0) for opt in options)
        _set_cell(tbl.cell(2, first_data_col + c), str(total) if total else "", ctx, counts_style)
    # Option rows
    for row_idx, opt in enumerate(options, start=3):
        if label_w > 0:
            _set_cell(tbl.cell(row_idx, 0), opt, ctx, opt_label_style)
        for c, (_, opt_cells) in enumerate(cats):
            cell_data = opt_cells.get(opt) or {}
            pct = cell_data.get("pct", 0) or 0
            _set_cell(tbl.cell(row_idx, first_data_col + c), f"{pct*100:.1f}%", ctx, opt_value_style)
            # ... existing minibar overlay logic ...
```

(Adapt to the existing `_render_panel` body — preserve the minibar overlay rendering by adjusting its column index to `first_data_col + c`.)

Also: when `label_w == 0`, skip the table column-width-setting branch that sets `tbl.columns[0].width = label_w`.

- [ ] **Step 5: Update `_pack_panels_into_rows` signature for weight calc**

Find `_pack_panels_into_rows` (around line 340). Replace its signature with:

```python
def _pack_panels_into_rows(
    panels: list[dict],
    max_row_weight: int,
    charts_by_bd: dict | None = None,
    label_col_width_rel: float = 0.18,
) -> list[list[dict]]:
    """Greedy row packing by weight.

    Weight per panel:
      - label_col_width_rel > 0: 1 + len(cats)  (label col counts)
      - else (Fase B):           len(cats)
    """
    _ = charts_by_bd  # backward-compat API
    use_label = label_col_width_rel > 0.001

    def weight(p: dict) -> int:
        return (1 + len(p["cats"])) if use_label else len(p["cats"])

    rows: list[list[dict]] = []
    current: list[dict] = []
    current_w = 0
    for p in panels:
        w = weight(p)
        if current and current_w + w > max_row_weight:
            rows.append(current)
            current = [p]
            current_w = w
        else:
            current.append(p)
            current_w += w
    if current:
        rows.append(current)
    return rows
```

Update call site in `_render_segmented_breakdowns` to pass `label_col_width_rel`:

```python
    panel_rows = _pack_panels_into_rows(
        panels, MAX_ROW_WEIGHT,
        label_col_width_rel=_SEGMENTED_CELLS_FASE_B["option_row"]["label_col_width_rel"],
    )
```

And the row weight inside the multi-panel render loop must use the same formula:

```python
        # Inside the multi-panel loop:
        use_label = _SEGMENTED_CELLS_FASE_B["option_row"]["label_col_width_rel"] > 0.001
        row_weight = sum((1 + len(p["cats"])) if use_label else len(p["cats"]) for p in row)
        avail_w = box_cx - H_GAP_EMU * (len(row) - 1)
        cur_x = box_x
        for p in row:
            w = (1 + len(p["cats"])) if use_label else len(p["cats"])
            panel_w = int(avail_w * (w / row_weight)) if row_weight else avail_w
            ...
```

- [ ] **Step 6: Force `_SEGMENTED_CELLS_FASE_B` to apply to BOTH single and multi-panel branches**

In `_render_segmented_breakdowns`, replace the existing per-pattern cells_cfg derivation with the unified Fase B constant. Locate where `group_hdr_cfg`, `cat_hdr_cfg`, `counts_cfg`, `option_cfg` are computed and REPLACE with:

```python
    group_hdr_cfg = _SEGMENTED_CELLS_FASE_B["group_header"]
    cat_hdr_cfg   = _SEGMENTED_CELLS_FASE_B["category_header"]
    counts_cfg    = _SEGMENTED_CELLS_FASE_B["counts_row"]
    option_cfg    = _SEGMENTED_CELLS_FASE_B["option_row"]
```

The single-panel branch (`if len(panels) == 1`) continues to call `_render_panel` with these configs and `font_cap={"group_header":None,"category_header":None,"counts_row":None,"option_row":None}` (already present from Fase A) — no change needed beyond the constant swap.

The multi-panel weight-packing branch ALSO uses these configs in its `_render_panel` calls — pass the same `font_cap` to lift the multi-panel caps (Fase A had them active to keep packed panels compact; Fase B unifies to image-style):

```python
    # Inside multi-panel loop
    _render_panel(
        slide=slide, panel=p, options=options,
        x=cur_x, y=cur_y, cx=panel_w, cy=row_h,
        ctx=ctx,
        group_hdr_cfg=group_hdr_cfg, cat_hdr_cfg=cat_hdr_cfg,
        counts_cfg=counts_cfg, option_cfg=option_cfg,
        font_cap={"group_header": None, "category_header": None,
                  "counts_row": None, "option_row": None},
    )
```

- [ ] **Step 7: Run tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_table_renderer.py -v
```

Expected: PASS for the new tests; existing single-panel test still passes (assertions updated: cols expected = 2 not 3 since label col is gone — adapt the existing assertion if needed).

- [ ] **Step 8: Full backend suite**

```bash
cd backend && arch -arm64 .venv/bin/pytest -q 2>&1 | tail -3
```

Expected: 0 failures.

- [ ] **Step 9: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/table_renderer.py backend/tests/test_table_renderer.py
git commit -m "feat(table): image-style cells uniform + no-label-col branch + weight recalc

_SEGMENTED_CELLS_FASE_B module-level constant becomes the single
source of truth for image-faithful styling; applied to both single-
panel and multi-panel _render_segmented_breakdowns branches.
_render_panel skips the label column when label_col_width_rel<=0
and shifts data column indices accordingly. _pack_panels_into_rows
accepts label_col_width_rel to size weight from cats alone when the
label col is suppressed, preserving correct proportional packing.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: `table_renderer` — `_render_external_legend_block` + show_legend wiring

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/table_renderer.py`
- Modify: `backend/tests/test_table_renderer.py`

**Interfaces:**
- Consumes (from Task 3): `source_chart.show_legend`.
- Produces:
  - `_render_external_legend_block(slide, x: int, y: int, w: int, h: int, options: list[str], label_first: str, ctx) -> None`
  - `_render_segmented_breakdowns` shifts `table_x`/`table_cx` by `legend_block_w = int(box_cx * 0.10)` when `show_legend=True` and renders the block at the left.

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_table_renderer.py`:

```python
def test_segmented_breakdowns_show_legend_renders_external_block(edad_chart, render_ctx):
    """show_legend=True → leftmost shape is the external legend block;
    panel tables shift right."""
    from pptx import Presentation
    from aurum_encuestas.element_renderers.table_renderer import render
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    edad_chart.show_legend = True
    render(slide, {
        "kind":"table","id":"t","position":{"x_rel":0.05,"y_rel":0.1,"w_rel":0.9,"h_rel":0.8},
        "structure":"segmented_breakdowns",
        "data_source":{"chart_ref_index":0,"breakdown_groups":["edad"]},
    }, render_ctx)
    tables = [sh for sh in slide.shapes if sh.has_table]
    assert len(tables) == 2, f"expected legend block + 1 panel = 2 tables, got {len(tables)}"
    # Leftmost table is the legend block
    leftmost = min(tables, key=lambda t: t.left)
    block_tbl = leftmost.table
    # 3 + len(options) rows = 3 + 2 = 5
    assert len(list(block_tbl.rows)) == 5
    # 1 col
    assert len(list(block_tbl.columns)) == 1
    # Row 2 = "Observaciones"
    assert block_tbl.cell(2, 0).text_frame.text.strip() == "Observaciones"
    # Rows 3,4 = options
    assert {block_tbl.cell(3,0).text_frame.text.strip(),
            block_tbl.cell(4,0).text_frame.text.strip()} == {"Sí","No"}


def test_segmented_breakdowns_show_legend_false_no_external_block(edad_chart, render_ctx):
    from pptx import Presentation
    from aurum_encuestas.element_renderers.table_renderer import render
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    edad_chart.show_legend = False
    render(slide, {
        "kind":"table","id":"t","position":{"x_rel":0.05,"y_rel":0.1,"w_rel":0.9,"h_rel":0.8},
        "structure":"segmented_breakdowns",
        "data_source":{"chart_ref_index":0,"breakdown_groups":["edad"]},
    }, render_ctx)
    tables = [sh for sh in slide.shapes if sh.has_table]
    assert len(tables) == 1, f"expected only the panel, got {len(tables)} tables"
```

- [ ] **Step 2: Run, expect failing**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_table_renderer.py -k "show_legend" -v
```

Expected: FAIL.

- [ ] **Step 3: Add `_render_external_legend_block` helper**

Append to `table_renderer.py` (near the other private helpers):

```python
def _render_external_legend_block(
    slide, x: int, y: int, w: int, h: int,
    options: list[str], label_first: str, ctx,
) -> None:
    """Vertical label block left of segmented table.

    Rows (aligned to panel layout):
      0  spacer (matches group_header band, fill=secondary)
      1  spacer (matches category_header band, fill=primary)
      2  label_first (e.g. "Observaciones"), right-aligned
      3+ option labels (Sí, No, ...), right-aligned
    """
    n_rows = 3 + len(options)
    try:
        tbl_shape = slide.shapes.add_table(n_rows, 1, Emu(x), Emu(y), Emu(w), Emu(h))
        tbl = tbl_shape.table
    except Exception as exc:
        log.error("external legend block add_table failed: %s", exc)
        return

    _set_cell(tbl.cell(0, 0), "", ctx, {"fill": "secondary"})
    _set_cell(tbl.cell(1, 0), "", ctx, {"fill": "primary"})
    _set_cell(tbl.cell(2, 0), label_first, ctx, {
        "fill": "primary", "text_color": "background",
        "font_size": 11, "bold": True, "align_h": "right",
    })
    for i, opt in enumerate(options):
        _set_cell(tbl.cell(3 + i, 0), opt, ctx, {
            "fill": "primary", "text_color": "#FFFFFF",
            "font_size": 10, "bold": True, "align_h": "right",
        })
```

- [ ] **Step 4: Wire `show_legend` in `_render_segmented_breakdowns`**

In `_render_segmented_breakdowns`, after `box_x, box_y, box_cx, box_cy` are resolved AND after the `panels` list is built but BEFORE the single/multi panel branching, add:

```python
    # Resolve source_chart for show_legend + question.options
    data_source_local = element.get("data_source", {}) or {}
    chart_ref_index_local = data_source_local.get("chart_ref_index", 0)
    charts_list = getattr(ctx.slide_config, "charts", []) or []
    source_chart_local = charts_list[chart_ref_index_local] if 0 <= chart_ref_index_local < len(charts_list) else None
    show_legend = bool(getattr(source_chart_local, "show_legend", False)) if source_chart_local else False
    question_local = getattr(source_chart_local, "question", None) if source_chart_local else None
    legend_options = list(question_local.options) if question_local else (options if "options" in dir() else [])

    legend_block_w = int(box_cx * 0.10) if show_legend else 0
    if show_legend and legend_options:
        _render_external_legend_block(
            slide, box_x, box_y, legend_block_w, box_cy,
            options=legend_options, label_first="Observaciones", ctx=ctx,
        )

    table_x = box_x + legend_block_w
    table_cx = box_cx - legend_block_w
```

Then replace every reference to `box_x` and `box_cx` in the single-panel and multi-panel rendering blocks BELOW this point with `table_x` and `table_cx`. (Search/replace inside the function only — `box_y` and `box_cy` stay.)

- [ ] **Step 5: Run tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_table_renderer.py -v
```

Expected: PASS.

- [ ] **Step 6: Full backend suite**

```bash
cd backend && arch -arm64 .venv/bin/pytest -q 2>&1 | tail -3
```

Expected: 0 fail.

- [ ] **Step 7: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/table_renderer.py backend/tests/test_table_renderer.py
git commit -m "feat(table): external legend block when show_legend=True

_render_external_legend_block creates a 1-col table with row labels
(Observaciones + question options) aligned to the panel layout.
_render_segmented_breakdowns renders the block at ~10% width on the
left when source_chart.show_legend=True; otherwise renders only the
panels. When the block renders, panel tables shift right by the
block width.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Frontend — types + addChart opts + UI inputs + tests

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/store/project.ts`
- Modify: `frontend/src/pages/Editor/modals/AddChartModal.tsx`
- Modify: `frontend/src/pages/Editor/ConfigPanel.tsx`
- Modify: `frontend/tests/AddChartModal.test.tsx`
- Modify: `frontend/tests/ConfigPanel.test.tsx`
- Modify: `frontend/tests/store.test.ts`
- Modify: `frontend/tests/AddChartModal.m6.test.tsx` (BUILTIN list expansion)

**Interfaces:**
- Consumes (from Tasks 1-7): backend `Chart` schema with `cat_titles`, `grid_cols ge=1`.
- Produces:
  - `Chart.cat_titles: Record<string, string> | null` in TS.
  - `addChart(slideId, questionId, breakdownIds, chartType, opts?)` — opts carries `show_legend`, `grid_cols`, `title`, `cat_titles`, `colors`.
  - `updateChartField(slideId, chartId, field, value)` — shallow patch.
  - `AddChartModal` filter shows all 5 types when `nReal===1`, hides grouped+TABLE when `nReal===0`, locks TABLE when `nReal>=2`.
  - Conditional inputs `title`, `show_legend`, `grid_cols`, `cat_titles` per Section 4 spec.

- [ ] **Step 1: Failing tests**

In `frontend/tests/store.test.ts`, append:

```typescript
it("addChart with opts persists new fields", () => {
  setStateMinimalSlide()  // helper that seeds one shell slide
  useProjectStore.getState().addChart("s1", "q1", ["edad"], "PIE_GROUPED", {
    show_legend: true, grid_cols: 2,
    title: "Plazo del crédito",
    cat_titles: { "18-39": "Jóvenes", "40-59": "Adultos" },
  })
  const c = useProjectStore.getState().state!.slides[0].charts[0]
  expect(c.chart_type).toBe("PIE_GROUPED")
  expect(c.show_legend).toBe(true)
  expect(c.grid_cols).toBe(2)
  expect(c.title).toBe("Plazo del crédito")
  expect(c.cat_titles).toEqual({ "18-39": "Jóvenes", "40-59": "Adultos" })
})

it("addChart without opts uses schema defaults", () => {
  setStateMinimalSlide()
  useProjectStore.getState().addChart("s1", "q1", [], "PIE")
  const c = useProjectStore.getState().state!.slides[0].charts[0]
  expect(c.show_legend).toBe(false)
  expect(c.grid_cols).toBeNull()
  expect(c.title).toBeNull()
  expect(c.cat_titles).toBeNull()
})

it("updateChartField patches only the targeted field", () => {
  setStateMinimalSlide()
  useProjectStore.getState().addChart("s1", "q1", ["edad"], "PIE_GROUPED", {
    show_legend: false, grid_cols: 3, title: null,
  })
  const cId = useProjectStore.getState().state!.slides[0].charts[0].id
  useProjectStore.getState().updateChartField("s1", cId, "show_legend", true)
  const c2 = useProjectStore.getState().state!.slides[0].charts[0]
  expect(c2.show_legend).toBe(true)
  expect(c2.grid_cols).toBe(3)
  expect(c2.title).toBeNull()
})
```

In `frontend/tests/AddChartModal.test.tsx`, append:

```typescript
it("one real breakdown shows all 5 chart_types", async () => {
  const u = userEvent.setup()
  render(<AddChartModal open={true} onClose={() => {}} onApply={() => {}} db={baseDb as any} />)
  await u.click(screen.getByLabelText(/Rango de edad/i))
  const dropdown = screen.getByLabelText(/Tipo de chart/i) as HTMLSelectElement
  const values = Array.from(dropdown.options).map((o) => o.value)
  expect(values).toEqual([
    "PIE", "PIE_GROUPED",
    "BAR_HORIZONTAL", "BAR_HORIZONTAL_GROUPED",
    "TABLE_WITH_MINIBARS",
  ])
})

it("no real breakdown hides grouped types and TABLE", () => {
  render(<AddChartModal open={true} onClose={() => {}} onApply={() => {}} db={baseDb as any} />)
  const dropdown = screen.getByLabelText(/Tipo de chart/i) as HTMLSelectElement
  const values = Array.from(dropdown.options).map((o) => o.value)
  expect(values).not.toContain("TABLE_WITH_MINIBARS")
  expect(values).not.toContain("PIE_GROUPED")
  expect(values).not.toContain("BAR_HORIZONTAL_GROUPED")
})

it("show_legend checkbox renders only for BAR_HORIZONTAL_GROUPED or TABLE_WITH_MINIBARS", async () => {
  const u = userEvent.setup()
  render(<AddChartModal open={true} onClose={() => {}} onApply={() => {}} db={baseDb as any} />)
  expect(screen.queryByLabelText(/Mostrar leyenda/i)).toBeNull()
  await u.click(screen.getByLabelText(/Rango de edad/i))
  const dropdown = screen.getByLabelText(/Tipo de chart/i) as HTMLSelectElement
  await u.selectOptions(dropdown, "BAR_HORIZONTAL_GROUPED")
  expect(screen.getByLabelText(/Mostrar leyenda/i)).toBeInTheDocument()
  await u.selectOptions(dropdown, "PIE_GROUPED")
  expect(screen.queryByLabelText(/Mostrar leyenda/i)).toBeNull()
})

it("grid_cols input renders only for PIE_GROUPED", async () => {
  const u = userEvent.setup()
  render(<AddChartModal open={true} onClose={() => {}} onApply={() => {}} db={baseDb as any} />)
  await u.click(screen.getByLabelText(/Rango de edad/i))
  const dropdown = screen.getByLabelText(/Tipo de chart/i) as HTMLSelectElement
  await u.selectOptions(dropdown, "PIE_GROUPED")
  expect(screen.getByLabelText(/Columnas por fila/i)).toBeInTheDocument()
  await u.selectOptions(dropdown, "PIE")
  expect(screen.queryByLabelText(/Columnas por fila/i)).toBeNull()
})

it("apply sends new fields", async () => {
  const u = userEvent.setup()
  const applied: any[] = []
  render(<AddChartModal open={true} onClose={() => {}} onApply={(r) => applied.push(r)} db={baseDb as any} />)
  await u.click(screen.getByLabelText(/Rango de edad/i))
  const dropdown = screen.getByLabelText(/Tipo de chart/i) as HTMLSelectElement
  await u.selectOptions(dropdown, "BAR_HORIZONTAL_GROUPED")
  await u.type(screen.getByPlaceholderText(/Ej: Plazo/i), "Plazo del crédito")
  await u.click(screen.getByLabelText(/Mostrar leyenda/i))
  await u.click(screen.getByText(/Aplicar/i))
  expect(applied[0].title).toBe("Plazo del crédito")
  expect(applied[0].show_legend).toBe(true)
  expect(applied[0].chartType).toBe("BAR_HORIZONTAL_GROUPED")
})
```

- [ ] **Step 2: Run, expect failing**

```bash
cd frontend && npx vitest run tests/store.test.ts tests/AddChartModal.test.tsx
```

Expected: FAIL on the new tests; existing ones may or may not still pass (some will need adapting in steps 3-5).

- [ ] **Step 3: Update `frontend/src/types/index.ts`**

Add `cat_titles` to `Chart`:

```typescript
export interface Chart {
  id: string
  question_id: string
  breakdown_ids: string[]
  chart_type: ChartType
  show_legend: boolean
  grid_cols: number | null
  title: string | null
  cat_titles: Record<string, string> | null
  colors: string[]
}
```

- [ ] **Step 4: Update `frontend/src/store/project.ts`**

Update `addChart` signature and implementation:

```typescript
addChart(
  slideId: string, questionId: string, breakdownIds: string[],
  chartType: import("../types").ChartType,
  opts?: {
    show_legend?: boolean
    grid_cols?: number | null
    title?: string | null
    cat_titles?: Record<string, string> | null
    colors?: string[]
  },
): void
```

```typescript
addChart(slideId, questionId, breakdownIds, chartType, opts) {
  const s = get().state
  if (!s) return
  const slides = s.slides.map((sl) => {
    if (sl.id !== slideId) return sl
    const newChart = {
      id: uid("ch"),
      question_id: questionId,
      breakdown_ids: breakdownIds,
      chart_type: chartType,
      show_legend: opts?.show_legend ?? false,
      grid_cols: opts?.grid_cols ?? null,
      title: opts?.title ?? null,
      cat_titles: opts?.cat_titles ?? null,
      colors: opts?.colors ?? [],
    }
    return { ...sl, charts: [...sl.charts, newChart] }
  })
  set({ state: { ...s, slides } })
},
```

Add `updateChartField`:

```typescript
// In Store interface:
updateChartField<K extends keyof import("../types").Chart>(
  slideId: string, chartId: string, field: K,
  value: import("../types").Chart[K],
): void

// Implementation:
updateChartField(slideId, chartId, field, value) {
  const s = get().state
  if (!s) return
  const slides = s.slides.map((sl) => {
    if (sl.id !== slideId) return sl
    return {
      ...sl,
      charts: sl.charts.map((c) =>
        c.id !== chartId ? c : { ...c, [field]: value }
      ),
    }
  })
  set({ state: { ...s, slides } })
},
```

- [ ] **Step 5: Update `AddChartModal.tsx`**

Replace `BUILTIN_CHART_TYPES` constant at top:

```typescript
const BUILTIN_CHART_TYPES = [
  "PIE", "PIE_GROUPED",
  "BAR_HORIZONTAL", "BAR_HORIZONTAL_GROUPED",
  "TABLE_WITH_MINIBARS",
]
```

Replace the `chartTypes` useMemo with the Fase B filter rule:

```typescript
const realBreakdownIds = useMemo(
  () => Array.from(breakdownIds).filter((b) => b !== "general"),
  [breakdownIds],
)
const nReal = realBreakdownIds.length
const chartTypes = useMemo(() => {
  if (nReal === 0) {
    return allChartTypes.filter((t) =>
      t !== "TABLE_WITH_MINIBARS" &&
      t !== "PIE_GROUPED" &&
      t !== "BAR_HORIZONTAL_GROUPED"
    )
  }
  if (nReal >= 2) return ["TABLE_WITH_MINIBARS"]
  return allChartTypes
}, [allChartTypes.join(","), nReal])
```

Add new state hooks below the existing chart_type / multiSeries removals:

```typescript
const [title, setTitle] = useState("")
const [showLegend, setShowLegend] = useState(false)
const [gridCols, setGridCols] = useState<number | null>(null)
const [catTitles, setCatTitles] = useState<Record<string, string>>({})
```

Derive `breakdownCats`:

```typescript
const breakdownCats = useMemo(() => {
  if (nReal !== 1) return [] as string[]
  const bdId = realBreakdownIds[0]
  return db?.breakdowns.find((b) => b.id === bdId)?.categories ?? []
}, [db, realBreakdownIds, nReal])
```

Insert the new JSX inputs (before the existing color picker block) — Spanish strings literal:

```tsx
<label className="block text-xs text-neutral-400 mb-1">Título (opcional)</label>
<input
  type="text"
  value={title}
  onChange={(e) => setTitle(e.target.value)}
  className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
  placeholder="Ej: Plazo del crédito"
/>

{(chartType === "BAR_HORIZONTAL_GROUPED" || chartType === "TABLE_WITH_MINIBARS") && (
  <label className="flex items-center gap-2 text-sm mb-3">
    <input
      type="checkbox"
      checked={showLegend}
      onChange={(e) => setShowLegend(e.target.checked)}
    />
    Mostrar leyenda
  </label>
)}

{chartType === "PIE_GROUPED" && (
  <>
    <label className="block text-xs text-neutral-400 mb-1">
      Columnas por fila (vacío = auto)
    </label>
    <input
      type="number"
      min={1}
      value={gridCols ?? ""}
      onChange={(e) =>
        setGridCols(e.target.value === "" ? null : Math.max(1, parseInt(e.target.value, 10)))
      }
      className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
    />
  </>
)}

{chartType === "PIE_GROUPED" && nReal === 1 && breakdownCats.length > 0 && (
  <div className="mb-3">
    <label className="block text-xs text-neutral-400 mb-2">
      Títulos por categoría (opcional)
    </label>
    {breakdownCats.map((cat) => (
      <div key={cat} className="flex items-center gap-2 mb-1">
        <span className="text-xs text-neutral-500 w-32 truncate">{cat}</span>
        <input
          type="text"
          value={catTitles[cat] ?? ""}
          onChange={(e) => setCatTitles({ ...catTitles, [cat]: e.target.value })}
          className="flex-1 bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs"
          placeholder={cat}
        />
      </div>
    ))}
  </div>
)}
```

Update `ApplyResult` interface:

```typescript
interface ApplyResult {
  questionId: string
  breakdownIds: string[]
  chartType: ChartType
  show_legend: boolean
  grid_cols: number | null
  title: string | null
  cat_titles: Record<string, string> | null
  colors: string[]
}
```

Update `handleApply`:

```typescript
const handleApply = () => {
  if (!questionId) return
  const catTitlesPayload = Object.keys(catTitles).length ? catTitles : null
  onApply({
    questionId,
    breakdownIds: realBreakdownIds,
    chartType,
    show_legend: showLegend,
    grid_cols: gridCols,
    title: title.trim() || null,
    cat_titles: catTitlesPayload,
    colors: finalColors,
  })
  onClose()
}
```

Reset new state in the `useEffect` that fires on `open`:

```typescript
useEffect(() => {
  if (open && db && db.questions.length > 0) {
    setQuestionId(db.questions[0].id)
    setBreakdownIds(new Set())
    setPrimaryColor("")
    setShowAdvanced(false)
    setAdvancedColors([])
    setTitle("")
    setShowLegend(false)
    setGridCols(null)
    setCatTitles({})
  }
}, [open, db])
```

- [ ] **Step 6: Update `ConfigPanel.tsx`**

Update `BUILTIN_CHART_TYPES` constant to the 5-item list (same as modal).

Add the same conditional inputs per chart row, scoped to that chart's `chart_type`. Each input dispatches `updateChartField(slide.id, chart.id, "<field>", value)`. Find the existing chart_type select per-row block and add the new inputs after it. Replicate the Spanish labels.

If ConfigPanel renders an "apply" callback chain that re-invokes `addChart`, replace it with `updateChartField` for each changed property (or keep addChart for new charts only).

- [ ] **Step 7: Update `AddChartModal.m6.test.tsx` BUILTIN list**

Find the `BUILTIN_CHART_TYPES` mock literal in `AddChartModal.m6.test.tsx` (added in prior plans) and update to the 5-item list. Adapt any assertions that hardcoded the 3-item shape.

- [ ] **Step 8: Run frontend tests + tsc**

```bash
cd frontend && npx vitest run 2>&1 | tail -10
cd frontend && npx tsc --noEmit 2>&1 | tail -5
```

Expected: 0 failures, tsc clean.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/types/index.ts \
        frontend/src/store/project.ts \
        frontend/src/pages/Editor/modals/AddChartModal.tsx \
        frontend/src/pages/Editor/ConfigPanel.tsx \
        frontend/tests/store.test.ts \
        frontend/tests/AddChartModal.test.tsx \
        frontend/tests/ConfigPanel.test.tsx \
        frontend/tests/AddChartModal.m6.test.tsx
git commit -m "feat(ui): Fase B inputs + 5-type filter + addChart opts

ChartType TS interface gains cat_titles. addChart accepts an opts
object for show_legend, grid_cols, title, cat_titles, colors.
updateChartField patches one Chart field in-place. AddChartModal
filter shows all 5 types when nReal===1, hides grouped+TABLE when
nReal===0, locks TABLE when nReal>=2. New conditional inputs:
title (all types), show_legend (BAR_HORIZONTAL_GROUPED + TABLE),
grid_cols (PIE_GROUPED), cat_titles (PIE_GROUPED + nReal===1).
ConfigPanel mirrors per-chart. BUILTIN_CHART_TYPES extended to 5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Spec coverage:**
  - Spec § Data model (cat_titles + grid_cols validator) → T1 ✅
  - Spec § Backend wiring (style_guide 5 types, EnrichedChart propagation, chart_renderer title+legend, _render_pie_grouped, table_renderer image-style+no-label-col, external legend block) → T2, T3, T4, T5, T6, T7 ✅
  - Spec § Frontend behavior (filter rule, conditional inputs, addChart opts, updateChartField) → T8 ✅
  - Spec § Testing strategy (~25 tests across backend + frontend) → T1-T8 ✅
  - Spec § Open risks (label_col_width_rel weight calc, visual regression Fase A users, legend block alignment, PIE_GROUPED empty data, cat_titles key drift, addChart opts ergonomics, updateChartField key typing) → addressed by T6 weight refactor + T5 empty warn + T8 generic-typed updateChartField ✅
- **Placeholder scan:** No "TBD" / "implement later". The only conditional language is T6 Step 4 ("Adapt to the existing `_render_panel` body — preserve the minibar overlay rendering by adjusting its column index") — that's a concrete instruction with the offset rule named (`first_data_col`).
- **Type consistency:** `Chart.cat_titles` consistent across T1, T3, T8 (`dict[str, str] | None` py / `Record<string, string> | null` ts). `_compute_grid_dims(n, grid_cols) -> tuple[int, int]` stable across T5. `_render_pie_grouped(slide, element, source_chart, ctx) -> None` stable. `_render_external_legend_block(slide, x, y, w, h, options, label_first, ctx) -> None` stable across T7 spec + impl. `addChart(slideId, questionId, breakdownIds, chartType, opts?)` stable across T8. `updateChartField` uses `K extends keyof Chart` generic at the interface level — typo-safe.
- **Open caveats:**
  - T6 Step 4 changes are extensive within `_render_panel`. Implementer should test single-panel rendering after the diff to confirm minibar overlays still align (no internal label col → column index 0 instead of 1 for minibar overlays).
  - T7 Step 4 inserts a code block that uses `legend_options` derived from `question.options` — but the original `_render_segmented_breakdowns` already has an `options` variable in scope (from `question = getattr(source_chart, "question", None)`). The implementer should reuse the existing `options` variable directly instead of re-deriving via `legend_options` to avoid duplication. The plan example uses a local name to be safe against scope drift.
  - The `_set_cell` helper expects role names OR `#RRGGBB` hex literals (Fase A T2 added the hex path). `_render_external_legend_block` uses both `"primary"` / `"secondary"` / `"background"` role names AND `"#FFFFFF"` hex — both paths are tested in Fase A and Fase B.
