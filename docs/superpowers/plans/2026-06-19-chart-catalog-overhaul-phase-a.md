# Chart Catalog Overhaul Fase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the chart catalog to 5 explicit types (`PIE`, `PIE_GROUPED`, `BAR_HORIZONTAL`, `BAR_HORIZONTAL_GROUPED`, `TABLE_WITH_MINIBARS`), expose only 3 to the UI dropdown in Fase A, replace `Chart.breakdown_id: str` with `Chart.breakdown_ids: list[str]`, add `show_legend`/`grid_cols`/`title` schema fields, and hard-reject legacy stored projects via a Pydantic validator.

**Architecture:** Schema-first migration — the new `Chart` model becomes the contract; the validator rejects both legacy `breakdown_id: str` and any removed `chart_type` with a clear error. Backend renderers, classifier, and the legacy pptx_generator path adapt to read `breakdown_ids` as a list (using the first element where the existing code expects a string). Frontend creates ONE `Chart` record per Apply with the full breakdown_ids list, auto-locks the chart_type dropdown to `TABLE_WITH_MINIBARS` when 2+ real breakdowns are selected, and filters `TABLE_WITH_MINIBARS` out when no real breakdown is picked. No new rendering work — current single-panel and multi-panel `_render_segmented_breakdowns` already covers Fase A's render surface.

**Tech Stack:** Python 3.11 + pydantic v2 + python-pptx (backend), React + TypeScript + Zustand + vitest (frontend), pytest (backend tests).

## Global Constraints

- Backend Python target `3.11`. Test command: `cd backend && arch -arm64 .venv/bin/pytest -q`.
- Frontend: `cd frontend && npx vitest run`. TypeScript clean (`npx tsc --noEmit`).
- `BUILTIN_STYLE_GUIDE` stays pure-literal Python (no env reads, no dynamic data).
- Spanish UI strings stay in es-MX neutral tone.
- The new 5-type `ChartType` literal: `PIE`, `PIE_GROUPED`, `BAR_HORIZONTAL`, `BAR_HORIZONTAL_GROUPED`, `TABLE_WITH_MINIBARS`. No other values accepted.
- `BUILTIN_STYLE_GUIDE.available_chart_types` exposes EXACTLY `["PIE", "BAR_HORIZONTAL", "TABLE_WITH_MINIBARS"]` in Fase A. Fase B will add `PIE_GROUPED` and `BAR_HORIZONTAL_GROUPED`.
- Legacy stored projects with `Chart.breakdown_id: str` or any removed chart_type (DONUT, COLUMN_*, BAR_CLUSTERED, BAR_STACKED, LINE, AREA, RADAR, TABLE_SIMPLE) must raise a `ValidationError` with a clear migration message at load. No auto-rewrite, no compat shim.
- `Chart.breakdown_ids: list[str]`: `[]` = general/Total. Length 1 = single breakdown. Length 2+ = multi-breakdown (TABLE only).
- Branch base: `main` at commit `20becd1`. New branch: `feat/chart-catalog-phase-a`.

---

## File Structure

**No new files.** All work modifies existing modules.

| File | Touched in | Responsibility |
|---|---|---|
| `backend/aurum_encuestas/models.py` | Task 1 | `ChartType` literal, `Chart` schema, legacy reject validator |
| `backend/aurum_encuestas/style_guide.py` | Task 2 | `available_chart_types` 3-item default + BUILTIN |
| `backend/aurum_encuestas/style_guide_analyzer.py` | Task 2 (verify only) | Unknown chart_type repair (post-Bug-#1 already drops; confirm no auto-rewrite to removed types) |
| `backend/aurum_encuestas/pattern_classifier.py` | Task 3 | `EnrichedChart.breakdown_ids` list, `n_breakdowns` from len, primary_bd extraction |
| `backend/aurum_encuestas/element_renderers/chart_renderer.py` | Task 4 | `_build_chart_data` reads list, defensive map for grouped types |
| `backend/aurum_encuestas/pattern_renderer.py` | Task 5 | Peek + `_synthesize_table_element` use breakdown_ids list |
| `backend/aurum_encuestas/pptx_generator.py` | Task 6 | Legacy `_add_chart` adapts to list |
| `frontend/src/types/index.ts` | Task 7 | `ChartType` union (5 values), `Chart` interface (new fields) |
| `frontend/src/store/project.ts` | Task 7 | `addCharts` → `addChart`, single record, list arg |
| `frontend/src/pages/Editor/modals/AddChartModal.tsx` | Task 8 | Filter + auto-lock dropdown, addChart call |
| `frontend/src/pages/Editor/ConfigPanel.tsx` | Task 8 | Per-chart filter + addChart rename |
| `backend/tests/test_models.py` | Task 1 | Reject legacy + accept new fields/types |
| `backend/tests/test_pattern_classifier.py` | Task 3 | n_breakdowns derivation, breakdown_ids propagation |
| `backend/tests/test_chart_renderer.py` | Task 4 | breakdown_ids semantics + grouped fallback warning |
| `backend/tests/test_pattern_renderer.py` | Task 5 | TABLE dispatch with multi-bd list |
| `backend/tests/test_style_guide.py` | Task 2 | `available_chart_types` Fase A is 3 |
| `backend/tests/test_table_renderer.py` | Task 9 | Adapt existing tests to breakdown_ids list |
| `backend/tests/test_render_e2e.py` | Task 9 | Adapt e2e to breakdown_ids list |
| `backend/tests/test_pptx_generator.py` | Task 6 | Adapt fixtures to breakdown_ids list |
| `frontend/tests/AddChartModal.test.tsx` | Task 8 | Filter + auto-lock + single-record apply |
| `frontend/tests/AddChartModal.m6.test.tsx` | Task 8 | Adapt to new addChart signature |
| `frontend/tests/store.test.ts` | Task 7 | addChart adds 1 record with list |
| `frontend/tests/ConfigPanel.test.tsx` | Task 8 | Per-chart filter |

---

### Task 1: Schema — `Chart` model + legacy reject validator

**Files:**
- Modify: `backend/aurum_encuestas/models.py`
- Modify: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: nothing new (depends only on pydantic).
- Produces:
  - `ChartType = Literal["PIE","PIE_GROUPED","BAR_HORIZONTAL","BAR_HORIZONTAL_GROUPED","TABLE_WITH_MINIBARS"]`
  - `Chart` BaseModel with fields `id: str`, `question_id: str`, `breakdown_ids: list[str]` (default `[]`), `chart_type: ChartType`, `show_legend: bool = False`, `grid_cols: int | None = None`, `title: str | None = None`, `colors: list[str] = []`.
  - Validator `_reject_legacy` (mode `"before"`) raises `ValueError` on `breakdown_id` key or unknown `chart_type`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_models.py`:

```python
import pytest
from pydantic import ValidationError

from aurum_encuestas.models import Chart


_NEW_CHART_TYPES = ["PIE", "PIE_GROUPED", "BAR_HORIZONTAL", "BAR_HORIZONTAL_GROUPED", "TABLE_WITH_MINIBARS"]
_REMOVED_CHART_TYPES = [
    "DONUT", "BAR_CLUSTERED", "BAR_STACKED",
    "COLUMN_CLUSTERED", "COLUMN_STACKED",
    "LINE", "AREA", "RADAR", "TABLE_SIMPLE", "BAR", "COLUMN",
]


def test_chart_rejects_legacy_breakdown_id_field():
    payload = {
        "id": "c1", "question_id": "q1",
        "breakdown_id": "edad",                    # legacy field
        "chart_type": "PIE",
    }
    with pytest.raises(ValidationError) as ei:
        Chart.model_validate(payload)
    msg = str(ei.value)
    assert "breakdown_id" in msg and "breakdown_ids" in msg


@pytest.mark.parametrize("ct", _REMOVED_CHART_TYPES)
def test_chart_rejects_removed_chart_type(ct):
    payload = {"id": "c1", "question_id": "q1", "breakdown_ids": [], "chart_type": ct}
    with pytest.raises(ValidationError) as ei:
        Chart.model_validate(payload)
    assert ct in str(ei.value)


@pytest.mark.parametrize("ct", _NEW_CHART_TYPES)
def test_chart_accepts_5_new_chart_types(ct):
    c = Chart.model_validate({"id": "c1", "question_id": "q1", "breakdown_ids": [], "chart_type": ct})
    assert c.chart_type == ct


def test_chart_accepts_empty_breakdown_ids():
    c = Chart.model_validate({"id": "c1", "question_id": "q1", "breakdown_ids": [], "chart_type": "PIE"})
    assert c.breakdown_ids == []


def test_chart_accepts_single_breakdown_id_list():
    c = Chart.model_validate({"id": "c1", "question_id": "q1", "breakdown_ids": ["edad"], "chart_type": "BAR_HORIZONTAL"})
    assert c.breakdown_ids == ["edad"]


def test_chart_accepts_multi_breakdown_ids():
    c = Chart.model_validate({
        "id": "c1", "question_id": "q1",
        "breakdown_ids": ["edad", "sexo", "nse"],
        "chart_type": "TABLE_WITH_MINIBARS",
    })
    assert c.breakdown_ids == ["edad", "sexo", "nse"]


def test_chart_default_new_fields():
    c = Chart.model_validate({"id": "c1", "question_id": "q1", "breakdown_ids": [], "chart_type": "PIE"})
    assert c.show_legend is False
    assert c.grid_cols is None
    assert c.title is None


def test_chart_accepts_new_fields_set():
    c = Chart.model_validate({
        "id": "c1", "question_id": "q1", "breakdown_ids": [],
        "chart_type": "PIE_GROUPED",
        "show_legend": True,
        "grid_cols": 2,
        "title": "Plazo del crédito",
    })
    assert c.show_legend is True
    assert c.grid_cols == 2
    assert c.title == "Plazo del crédito"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_models.py -k "chart_rejects_legacy or chart_rejects_removed or chart_accepts_5 or chart_accepts_empty or chart_accepts_single or chart_accepts_multi or chart_default_new or chart_accepts_new_fields" -v
```

Expected: FAIL on every new test — legacy `breakdown_id: str` is still required by the current model, the new chart_types aren't in the literal, the new fields don't exist.

- [ ] **Step 3: Replace `Chart` model + add validator**

In `backend/aurum_encuestas/models.py`, replace the existing `ChartType` literal and `Chart` BaseModel with:

```python
from typing import Literal
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
    breakdown_ids: list[str] = Field(default_factory=list)
    chart_type: ChartType
    show_legend: bool = False
    grid_cols: int | None = None
    title: str | None = None
    colors: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _reject_legacy(cls, data):
        if not isinstance(data, dict):
            return data
        if "breakdown_id" in data:
            raise ValueError(
                "Chart.breakdown_id (str) was removed in the 2026-06-19 catalog "
                "overhaul. Migrate to breakdown_ids: list[str]. Examples: "
                "breakdown_id='edad' → breakdown_ids=['edad']; "
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

Keep `AnalysisScope`, `SlideType`, `Question`, `Breakdown`, `DataBlocks`, `ParsedDB`, `Analysis`, `Slide`, `ProjectInputs`, `ProjectState`, `TemplateInfo`, `LayoutElement`, `LearnedLayout`, `LayoutBank`, `TrainingPPT` untouched.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_models.py -v
```

Expected: all tests pass. Pre-existing tests in this file that use `breakdown_id="edad"` will now fail — that is correct and they will be fixed in Task 9 by switching to `breakdown_ids=["edad"]`. For Task 1's commit, the new tests pass and the failures are listed as concerns.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/models.py backend/tests/test_models.py
git commit -m "feat(schema): 5-type ChartType + breakdown_ids list + legacy reject

ChartType literal reduced to PIE, PIE_GROUPED, BAR_HORIZONTAL,
BAR_HORIZONTAL_GROUPED, TABLE_WITH_MINIBARS. Chart gains breakdown_ids
list (replaces breakdown_id str), show_legend, grid_cols, title fields.
A model_validator rejects stored projects carrying the legacy
breakdown_id field or any removed chart_type and emits a clear
migration message. Pre-existing fixtures using breakdown_id='edad'
will be adapted to breakdown_ids=['edad'] in Task 9.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `style_guide` — `available_chart_types` 3-item Fase A list

**Files:**
- Modify: `backend/aurum_encuestas/style_guide.py`
- Modify: `backend/aurum_encuestas/style_guide_analyzer.py` (verify only — no diff expected)
- Modify: `backend/tests/test_style_guide.py`

**Interfaces:**
- Consumes: `_ALLOWED_CHART_TYPES` from `models.py` (informational; not imported).
- Produces:
  - `StyleGuide.available_chart_types` default factory returns `["PIE", "BAR_HORIZONTAL", "TABLE_WITH_MINIBARS"]`.
  - `BUILTIN_STYLE_GUIDE["available_chart_types"]` literal returns the same 3-item list.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_style_guide.py`:

```python
def test_builtin_available_chart_types_phase_a_is_three():
    """Fase A exposes exactly 3 chart types to the UI. Fase B adds the
    two grouped variants."""
    from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE
    assert BUILTIN_STYLE_GUIDE.available_chart_types == [
        "PIE", "BAR_HORIZONTAL", "TABLE_WITH_MINIBARS",
    ]


def test_style_guide_default_available_chart_types_is_three():
    from aurum_encuestas.style_guide import StyleGuide
    sg = StyleGuide()
    assert sg.available_chart_types == ["PIE", "BAR_HORIZONTAL", "TABLE_WITH_MINIBARS"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_style_guide.py::test_builtin_available_chart_types_phase_a_is_three tests/test_style_guide.py::test_style_guide_default_available_chart_types_is_three -v
```

Expected: FAIL — current default is 10 items including DONUT/BAR_CLUSTERED/etc.

- [ ] **Step 3: Reduce `available_chart_types` to the 3 Fase A types**

In `backend/aurum_encuestas/style_guide.py`, find the `StyleGuide.available_chart_types` field (around line 272-274) and replace its default factory with:

```python
    available_chart_types: list[str] = Field(
        default_factory=lambda: ["PIE", "BAR_HORIZONTAL", "TABLE_WITH_MINIBARS"]
    )
```

Then find `BUILTIN_STYLE_GUIDE["available_chart_types"]` (around line 308-316) and replace with:

```python
    "available_chart_types": ["PIE", "BAR_HORIZONTAL", "TABLE_WITH_MINIBARS"],
```

- [ ] **Step 4: Verify `style_guide_analyzer.py` — no auto-rewrite to removed types**

Run:

```bash
grep -n "BAR_CLUSTERED\|BAR_HORIZONTAL\|chart_type" backend/aurum_encuestas/style_guide_analyzer.py | head -20
```

Confirm the repair block (post-Bug-#1 plan) DROPS unknown chart_type via `el.pop("chart_type", None)` — does NOT rewrite to `"BAR_HORIZONTAL"`. If a rewrite branch still exists, replace it with a drop. Otherwise no change.

If a change is needed (rewrite still present), apply:

```python
# style_guide_analyzer.py — replace the repair block
if el.get("chart_type") and available_chart_types and el["chart_type"] not in available_chart_types:
    el.pop("chart_type", None)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_style_guide.py -v
```

Expected: all style_guide tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/aurum_encuestas/style_guide.py backend/tests/test_style_guide.py
git add -u backend/aurum_encuestas/style_guide_analyzer.py 2>/dev/null || true
git commit -m "feat(style_guide): expose only 3 chart types to UI in Fase A

available_chart_types default + BUILTIN reduced to PIE, BAR_HORIZONTAL,
TABLE_WITH_MINIBARS. ChartType literal in models.py still accepts the
two _GROUPED variants — they just aren't surfaced to the UI dropdown
yet. Fase B adds them back.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `pattern_classifier` — `EnrichedChart.breakdown_ids` + n_breakdowns from len

**Files:**
- Modify: `backend/aurum_encuestas/pattern_classifier.py:108`, `149-153`, `442-489` (line numbers approximate; locate by symbol name)
- Modify: `backend/tests/test_pattern_classifier.py`

**Interfaces:**
- Consumes (from Task 1): `Chart.breakdown_ids: list[str]`.
- Produces:
  - `EnrichedChart.breakdown_ids: list[str]` (was `breakdown_id: str`).
  - `extract_context(...)` produces `n_breakdowns = len({frozenset(c.breakdown_ids or []) for c in charts})` style derivation — see Step 3.
  - `build_slide_config(...)` uses `primary_bd = chart.breakdown_ids[0] if chart.breakdown_ids else "general"` to call `extract_chart_data`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_pattern_classifier.py`:

```python
def test_enriched_chart_carries_breakdown_ids_list():
    """build_slide_config propagates Chart.breakdown_ids list verbatim."""
    from aurum_encuestas.pattern_classifier import build_slide_config
    from aurum_encuestas.models import Chart, ParsedDB, Question, Breakdown
    from types import SimpleNamespace

    chart = Chart(id="c1", question_id="q1", breakdown_ids=["edad", "sexo"], chart_type="TABLE_WITH_MINIBARS")
    slide_def = SimpleNamespace(charts=[chart], analyses=[])
    parsed = ParsedDB(
        questions=[Question(id="q1", code="Q1", text="t", options=["Sí","No"], confidence=0.9)],
        breakdowns=[Breakdown(id="edad", label="Edad", categories=["18-39","40-59"]),
                    Breakdown(id="sexo", label="Sexo", categories=["F","M"])],
        sample_size=500, data_blocks={"counts_cols":[],"pct_row_cols":[],"pct_col_cols":[]},
    )
    cfg = build_slide_config(slide_def, parsed_db=parsed, db_path=None)
    assert len(cfg.charts) == 1
    assert cfg.charts[0].breakdown_ids == ["edad", "sexo"]


def test_n_breakdowns_uses_breakdown_ids_length():
    """Trigger context n_breakdowns reflects total unique non-general breakdown_ids
    across all charts on the slide."""
    from aurum_encuestas.pattern_classifier import extract_context
    cfg = {
        "charts": [
            {"question_id": "q1", "breakdown_ids": ["edad"]},
            {"question_id": "q1", "breakdown_ids": ["sexo", "nse"]},
            {"question_id": "q2", "breakdown_ids": []},
        ],
        "analyses": [],
    }
    ctx = extract_context(cfg, db=None)
    # 3 unique real breakdowns across slide: edad, sexo, nse
    assert ctx["n_breakdowns"] == 3
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_pattern_classifier.py::test_enriched_chart_carries_breakdown_ids_list tests/test_pattern_classifier.py::test_n_breakdowns_uses_breakdown_ids_length -v
```

Expected: FAIL — `EnrichedChart` still has `breakdown_id: str`, and `extract_context` reads `c.get("breakdown_id")` not `c.get("breakdown_ids")`.

- [ ] **Step 3: Update `extract_context` to read breakdown_ids list**

Locate `extract_context` in `backend/aurum_encuestas/pattern_classifier.py` (around line 108). Find the breakdowns extraction (around lines 149-153):

```python
breakdowns_used = list({c.get("breakdown_id") for c in charts if c.get("breakdown_id")})
n_breakdowns = len(breakdowns_used)
```

Replace with:

```python
bd_set: set[str] = set()
for c in charts:
    for bd in (c.get("breakdown_ids") or []):
        if bd and bd.lower() != "general":
            bd_set.add(bd)
breakdowns_used = sorted(bd_set)
n_breakdowns = len(bd_set)
```

Also locate the doc-comment around line 108 (`"charts": [{"question_id": ..., "breakdown_id": ..., ...}, ...]`) and update to:

```python
"charts": [{"question_id": ..., "breakdown_ids": [...], ...}, ...],
```

- [ ] **Step 4: Update `EnrichedChart` dataclass and `build_slide_config`**

Locate `EnrichedChart` (around line 440-450) and replace `breakdown_id: str` with:

```python
        breakdown_ids: list[str] = field(default_factory=list)
```

Locate the call site building EnrichedChart (around line 488):

```python
            EnrichedChart(
                id=chart.id,
                question_id=chart.question_id,
                breakdown_id=chart.breakdown_id,
                chart_type=chart.chart_type,
                ...
            )
```

Replace with:

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
            )
```

Then locate the `extract_chart_data` call (around line 479):

```python
                chart_data = extract_chart_data(
                    db_path, question, chart.breakdown_id, data_blocks,
                )
```

Replace with:

```python
                primary_bd = chart.breakdown_ids[0] if chart.breakdown_ids else "general"
                chart_data = extract_chart_data(
                    db_path, question, primary_bd, data_blocks,
                )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_pattern_classifier.py -v
```

Expected: new tests pass. Some pre-existing tests using `breakdown_id="..."` in chart dicts will fail and be fixed in Task 9.

- [ ] **Step 6: Commit**

```bash
git add backend/aurum_encuestas/pattern_classifier.py backend/tests/test_pattern_classifier.py
git commit -m "feat(classifier): EnrichedChart.breakdown_ids list + n_breakdowns from len

extract_context derives n_breakdowns from the union of breakdown_ids
across all charts on the slide (general/empty excluded). EnrichedChart
carries breakdown_ids: list[str]. build_slide_config passes the first
element to extract_chart_data (Fase A); Fase B will broaden the
extraction surface.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `chart_renderer` — read breakdown_ids list + defensive map

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/chart_renderer.py`
- Modify: `backend/tests/test_element_renderers.py` (or `test_chart_renderer.py` if separate file exists)

**Interfaces:**
- Consumes (from Task 3): `EnrichedChart.breakdown_ids: list[str]`.
- Produces:
  - `_build_chart_data(source_chart, value_field, sort)`: reads `breakdown_ids` list; `is_general` from empty list OR first element == `"general"` (case-insensitive).
  - `_CHART_TYPE_MAP` gains `"PIE_GROUPED": XL_CHART_TYPE.PIE` and `"BAR_HORIZONTAL_GROUPED": XL_CHART_TYPE.BAR_CLUSTERED` as defensive fallback entries.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_element_renderers.py`:

```python
def test_build_chart_data_empty_breakdown_ids_uses_general():
    """breakdown_ids=[] → plot the General/Total row as single series."""
    from aurum_encuestas.element_renderers.chart_renderer import _build_chart_data
    from types import SimpleNamespace

    q = SimpleNamespace(options=["Sí","No"])
    source = SimpleNamespace(
        question=q,
        breakdown_ids=[],
        chart_type="PIE",
        data={"General": {"Sí":{"pct":0.6,"count":60},"No":{"pct":0.4,"count":40}}},
        colors=[],
    )
    cd, values = _build_chart_data(source, "pct", "desc_by_value")
    # General branch: one series of N option values
    assert len(values) == 2
    assert list(cd.categories) == ["Sí", "No"]


def test_build_chart_data_single_breakdown_uses_that_breakdown():
    """breakdown_ids=['edad'] → multi-series, one per Edad category."""
    from aurum_encuestas.element_renderers.chart_renderer import _build_chart_data
    from types import SimpleNamespace

    q = SimpleNamespace(options=["Sí","No"])
    source = SimpleNamespace(
        question=q,
        breakdown_ids=["edad"],
        chart_type="BAR_HORIZONTAL",
        data={
            "General": {"Sí":{"pct":0.5},"No":{"pct":0.5}},
            "18-39":   {"Sí":{"pct":0.9},"No":{"pct":0.1}},
            "40-59":   {"Sí":{"pct":0.3},"No":{"pct":0.7}},
        },
        colors=[],
    )
    cd, all_values = _build_chart_data(source, "pct", "desc_by_value")
    # values from BOTH categories flattened (2 cats × 2 options = 4 entries)
    assert len(all_values) == 4


def test_grouped_chart_type_logs_warning_and_falls_back(caplog):
    """PIE_GROUPED / BAR_HORIZONTAL_GROUPED log a warning and render
    as single-mode fallback (PIE / BAR_CLUSTERED)."""
    import logging
    from pptx import Presentation
    from aurum_encuestas.element_renderers.chart_renderer import render
    from aurum_encuestas.element_renderers.render_context import RenderContext
    from types import SimpleNamespace

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    q = SimpleNamespace(options=["A","B"])
    source = SimpleNamespace(
        question=q, breakdown_ids=[], chart_type="PIE_GROUPED", colors=[],
        data={"General": {"A":{"pct":0.5},"B":{"pct":0.5}}},
    )
    slide_config = SimpleNamespace(charts=[source])
    ctx = RenderContext(
        slide_config=slide_config,
        chart_colors=["#7F7F7F","#404040","#EEC245","#C00000","#FFC000"],
        resolved_colors={"primary":"#7F7F7F","secondary":"#404040","background":"#EEC245"},
        free_area={"x":0,"y":0,"cx":6_000_000,"cy":4_000_000},
        typography={"label_size":9,"body_size":10,"title_size":16,"font_family":"Calibri"},
        style_guide=None, resolved_anchors={},
    )
    with caplog.at_level(logging.WARNING):
        render(slide, {
            "kind":"chart","id":"c",
            "position":{"x_rel":0,"y_rel":0,"w_rel":1,"h_rel":1},
            "data_source":{"chart_ref_index":0,"value_field":"pct"},
        }, ctx)
    assert any("PIE_GROUPED" in r.message and "Fase B" in r.message for r in caplog.records), \
        f"expected PIE_GROUPED Fase B warning; got: {[r.message for r in caplog.records]}"
    # Shape was created (fallback succeeded)
    assert any(sh.has_chart for sh in slide.shapes)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_element_renderers.py::test_build_chart_data_empty_breakdown_ids_uses_general tests/test_element_renderers.py::test_build_chart_data_single_breakdown_uses_that_breakdown tests/test_element_renderers.py::test_grouped_chart_type_logs_warning_and_falls_back -v
```

Expected: FAIL — current `_build_chart_data` reads `source_chart.breakdown_id` (str), and `_CHART_TYPE_MAP` doesn't have `PIE_GROUPED`.

- [ ] **Step 3: Update `_build_chart_data` to read breakdown_ids list**

In `backend/aurum_encuestas/element_renderers/chart_renderer.py`, find `_build_chart_data` (around line 244). Replace the breakdown_id read (around line 247) with:

```python
    question = getattr(source_chart, "question", None)
    options = list(question.options) if question else []
    data = getattr(source_chart, "data", {}) or {}
    bds = list(getattr(source_chart, "breakdown_ids", []) or [])
    primary = bds[0] if bds else ""
    is_general = (not primary) or primary.lower() == "general"
```

Keep the rest of `_build_chart_data` (general vs multi-series branching) intact — it already keys off `is_general`.

- [ ] **Step 4: Add defensive map entries + grouped fallback warning**

Find `_CHART_TYPE_MAP` (around line 18-28). Append entries:

```python
_CHART_TYPE_MAP: dict[str, int] = {
    "PIE":               XL_CHART_TYPE.PIE,
    "DONUT":             XL_CHART_TYPE.DOUGHNUT,
    "BAR_HORIZONTAL":    XL_CHART_TYPE.BAR_CLUSTERED,
    "BAR_CLUSTERED":     XL_CHART_TYPE.BAR_CLUSTERED,
    "BAR_STACKED":       XL_CHART_TYPE.BAR_STACKED,
    "COLUMN_CLUSTERED":  XL_CHART_TYPE.COLUMN_CLUSTERED,
    "COLUMN_STACKED":    XL_CHART_TYPE.COLUMN_STACKED,
    "LINE":              XL_CHART_TYPE.LINE,
    "AREA":              XL_CHART_TYPE.AREA,
    # Fase A defensive: grouped render is Fase B. UI doesn't expose these
    # types yet, but a hand-crafted JSON could carry them. Fall back to
    # single-mode shape so the slide doesn't crash.
    "PIE_GROUPED":             XL_CHART_TYPE.PIE,
    "BAR_HORIZONTAL_GROUPED":  XL_CHART_TYPE.BAR_CLUSTERED,
}
```

Then in `render()` (around line 60-70 where `chart_type_str` is resolved), after `chart_type_str = ui_chart_type or pattern_chart_type or "BAR_HORIZONTAL"`, add a fallback warning:

```python
    if chart_type_str in ("PIE_GROUPED", "BAR_HORIZONTAL_GROUPED"):
        log.warning(
            "chart_type %s grouped render is Fase B — emitting single-series fallback",
            chart_type_str,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_element_renderers.py -v 2>&1 | tail -30
```

Expected: new tests pass. Existing tests that build `SimpleNamespace` with `breakdown_id=...` will fail and be fixed in Task 9.

- [ ] **Step 6: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/chart_renderer.py backend/tests/test_element_renderers.py
git commit -m "feat(chart_renderer): read breakdown_ids list + defensive grouped fallback

_build_chart_data reads source_chart.breakdown_ids (list) and uses
the first element as the primary breakdown. _CHART_TYPE_MAP gains
PIE_GROUPED and BAR_HORIZONTAL_GROUPED entries that fall back to
PIE / BAR_CLUSTERED single-mode shapes, with a warning indicating
the grouped render is Fase B. UI doesn't expose grouped types in
Fase A; the entries exist so hand-crafted JSON doesn't crash.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `pattern_renderer` — peek + synthesize use breakdown_ids list

**Files:**
- Modify: `backend/aurum_encuestas/pattern_renderer.py`
- Modify: `backend/tests/test_pattern_renderer.py`

**Interfaces:**
- Consumes (from Task 3): `EnrichedChart.breakdown_ids: list[str]`.
- Produces:
  - Dispatch peek reads `breakdown_ids` list and computes `sc_bds_real` (filter out empty / general).
  - `_synthesize_table_element(chart_el, source_chart)` returns `breakdown_groups` = the full real list (not a single-element list).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_pattern_renderer.py`:

```python
def test_synthesize_table_element_uses_full_breakdown_ids_list():
    """_synthesize_table_element passes ALL real breakdown_ids as
    breakdown_groups, not just the first."""
    from aurum_encuestas.pattern_renderer import _synthesize_table_element
    from types import SimpleNamespace

    chart_el = {
        "kind": "chart",
        "id": "main",
        "position": {"x_rel": 0.1, "y_rel": 0.1, "w_rel": 0.8, "h_rel": 0.8},
        "data_source": {"chart_ref_index": 0, "value_field": "pct"},
    }
    src = SimpleNamespace(breakdown_ids=["edad", "sexo", "general", "nse"], chart_type="TABLE_WITH_MINIBARS")
    el = _synthesize_table_element(chart_el, src)
    assert el["kind"] == "table"
    assert el["structure"] == "segmented_breakdowns"
    assert el["data_source"]["breakdown_groups"] == ["edad", "sexo", "nse"]


def test_dispatch_does_not_fire_when_breakdown_ids_empty():
    """chart_type=TABLE_WITH_MINIBARS with breakdown_ids=[] (general) must
    NOT route to table_renderer — falls through to chart_renderer (which
    will warn about an unmapped chart_type)."""
    from pptx import Presentation
    from types import SimpleNamespace
    from aurum_encuestas.pattern_renderer import render_pattern
    from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE
    from aurum_encuestas.element_renderers.render_context import RenderContext

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    q = SimpleNamespace(options=["Sí","No"])
    src = SimpleNamespace(
        question=q, breakdown_ids=[], chart_type="TABLE_WITH_MINIBARS", colors=[],
        data={"General": {"Sí":{"pct":0.6},"No":{"pct":0.4}}}, all_breakdowns_data={},
    )
    slide_config = SimpleNamespace(charts=[src], analyses=[], n_charts=1)
    ctx = RenderContext(
        slide_config=slide_config,
        chart_colors=["#7F7F7F","#404040","#EEC245","#C00000","#FFC000"],
        resolved_colors={"primary":"#7F7F7F","secondary":"#404040","background":"#EEC245"},
        free_area={"x":0,"y":0,"cx":12_192_000,"cy":6_858_000},
        typography={"label_size":9,"body_size":10,"title_size":16,"font_family":"Calibri"},
        style_guide=BUILTIN_STYLE_GUIDE, resolved_anchors={},
    )
    pattern = next(p for p in BUILTIN_STYLE_GUIDE.patterns if p.id == "binary_general")
    render_pattern(pattern, slide, ctx, BUILTIN_STYLE_GUIDE, list(BUILTIN_STYLE_GUIDE.patterns))
    assert not any(sh.has_table for sh in slide.shapes), "should not synthesize table for empty breakdown_ids"


def test_dispatch_fires_for_multi_breakdown_ids():
    """chart_type=TABLE_WITH_MINIBARS with breakdown_ids=['edad','sexo']
    → table shape rendered with both breakdowns in breakdown_groups."""
    from pptx import Presentation
    from types import SimpleNamespace
    from aurum_encuestas.pattern_renderer import render_pattern
    from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE
    from aurum_encuestas.element_renderers.render_context import RenderContext

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    q = SimpleNamespace(options=["Sí","No"])
    src = SimpleNamespace(
        question=q, breakdown_ids=["edad","sexo"], chart_type="TABLE_WITH_MINIBARS", colors=[],
        data={"General": {"Sí":{"pct":0.6},"No":{"pct":0.4}}},
        all_breakdowns_data={
            "edad": {"label":"Edad","categories":{
                "18-39":{"Sí":{"pct":0.9,"count":40},"No":{"pct":0.1,"count":5}},
                "40-59":{"Sí":{"pct":0.3,"count":15},"No":{"pct":0.7,"count":35}},
            }},
            "sexo": {"label":"Sexo","categories":{
                "F":{"Sí":{"pct":0.5,"count":30},"No":{"pct":0.5,"count":30}},
                "M":{"Sí":{"pct":0.7,"count":35},"No":{"pct":0.3,"count":15}},
            }},
        },
    )
    slide_config = SimpleNamespace(charts=[src], analyses=[], n_charts=1)
    ctx = RenderContext(
        slide_config=slide_config,
        chart_colors=["#7F7F7F","#404040","#EEC245","#C00000","#FFC000"],
        resolved_colors={"primary":"#7F7F7F","secondary":"#404040","background":"#EEC245"},
        free_area={"x":0,"y":0,"cx":12_192_000,"cy":6_858_000},
        typography={"label_size":9,"body_size":10,"title_size":16,"font_family":"Calibri"},
        style_guide=BUILTIN_STYLE_GUIDE, resolved_anchors={},
    )
    pattern = next(p for p in BUILTIN_STYLE_GUIDE.patterns if p.id == "binary_general")
    render_pattern(pattern, slide, ctx, BUILTIN_STYLE_GUIDE, list(BUILTIN_STYLE_GUIDE.patterns))
    assert any(sh.has_table for sh in slide.shapes), "expected a table for multi-bd TABLE_WITH_MINIBARS"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_pattern_renderer.py::test_synthesize_table_element_uses_full_breakdown_ids_list tests/test_pattern_renderer.py::test_dispatch_does_not_fire_when_breakdown_ids_empty tests/test_pattern_renderer.py::test_dispatch_fires_for_multi_breakdown_ids -v
```

Expected: FAIL — current peek reads `source_chart.breakdown_id` (str), `_synthesize_table_element` puts `[bd_id]` not the full list.

- [ ] **Step 3: Update the peek in `render_pattern`**

In `backend/aurum_encuestas/pattern_renderer.py`, find the dispatch peek inside the `for element in ordered_elements:` loop (after `ordered_elements = _topological_sort(expanded)`):

```python
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
```

Replace with:

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

- [ ] **Step 4: Update `_synthesize_table_element` to pass the full list**

Find `_synthesize_table_element` (near the helpers section, around line 360-380):

```python
def _synthesize_table_element(chart_el: dict, source_chart) -> dict:
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

Replace with:

```python
def _synthesize_table_element(chart_el: dict, source_chart) -> dict:
    """Convert a chart element to a segmented_breakdowns table element
    targeting every real breakdown carried by source_chart.breakdown_ids."""
    bds = [
        b for b in (getattr(source_chart, "breakdown_ids", []) or [])
        if b and b.lower() != "general"
    ]
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

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_pattern_renderer.py -v
```

Expected: new tests pass. The existing `test_chart_with_table_type_routes_to_table_renderer` will fail because its fixture uses `breakdown_id="edad"` — Task 9 fixes that.

- [ ] **Step 6: Commit**

```bash
git add backend/aurum_encuestas/pattern_renderer.py backend/tests/test_pattern_renderer.py
git commit -m "feat(pattern_renderer): dispatch peek + synthesize use breakdown_ids list

render_pattern's TABLE_WITH_MINIBARS peek reads source_chart.breakdown_ids
(list) and routes to table_renderer only when at least one entry is a
real (non-general, non-empty) breakdown. _synthesize_table_element passes
the full real list as data_source.breakdown_groups so multi-breakdown
tables render N panels via the existing _render_segmented_breakdowns
weight-packing path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: `pptx_generator` legacy `_add_chart` adapts to breakdown_ids list

**Files:**
- Modify: `backend/aurum_encuestas/pptx_generator.py`
- Modify: `backend/tests/test_pptx_generator.py`

**Interfaces:**
- Consumes (from Task 1): `Chart.breakdown_ids: list[str]`.
- Produces: `_add_chart(slide, chart_def, ...)` reads `chart_def.breakdown_ids[0]` (or empty → general).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_pptx_generator.py`:

```python
def test_add_chart_handles_empty_breakdown_ids_as_general():
    """Chart with breakdown_ids=[] plots the General row as single series."""
    from pptx import Presentation
    from aurum_encuestas.pptx_generator import _add_chart
    from aurum_encuestas.models import Chart, Question, Breakdown, ParsedDB, ProjectInputs, ProjectState
    from types import SimpleNamespace

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    chart = Chart(id="c1", question_id="q1", breakdown_ids=[], chart_type="PIE")
    parsed = ParsedDB(
        questions=[Question(id="q1", code="Q1", text="t", options=["Sí","No"], confidence=0.9)],
        breakdowns=[Breakdown(id="general", label="General", categories=["Total"])],
        sample_size=100,
        data_blocks={"counts_cols":[],"pct_row_cols":[],"pct_col_cols":[]},
    )
    state = ProjectState(
        project_name="t",
        inputs=ProjectInputs(db_path="", template_path=""),
        parsed_db=parsed,
        slides=[],
    )
    el = {"x": 0, "y": 0, "cx": 5_000_000, "cy": 3_000_000}
    # Monkeypatch extract_chart_data through the import path used by _add_chart
    from aurum_encuestas import data_extractor as de
    orig = de.extract_chart_data
    de.extract_chart_data = lambda *a, **kw: {"General": {"Sí":{"pct":0.6,"count":60},"No":{"pct":0.4,"count":40}}}
    try:
        _add_chart(slide, chart, state, el)
    finally:
        de.extract_chart_data = orig
    assert any(sh.has_chart for sh in slide.shapes)
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_pptx_generator.py::test_add_chart_handles_empty_breakdown_ids_as_general -v
```

Expected: FAIL — current `_add_chart` reads `chart_def.breakdown_id` which no longer exists in the model.

- [ ] **Step 3: Update `_add_chart`**

In `backend/aurum_encuestas/pptx_generator.py`, find `_add_chart` (around line 294). Locate the call to `extract_chart_data` (around line 295-296):

```python
    data = extract_chart_data(state.inputs.db_path, _find_question(state, chart_def.question_id),
                              chart_def.breakdown_id, state.parsed_db.data_blocks if state.parsed_db else {})
```

Replace with:

```python
    primary_bd = chart_def.breakdown_ids[0] if chart_def.breakdown_ids else "general"
    data = extract_chart_data(state.inputs.db_path, _find_question(state, chart_def.question_id),
                              primary_bd, state.parsed_db.data_blocks if state.parsed_db else {})
```

Then find `is_general` (around line 315):

```python
    is_general = chart_def.breakdown_id == "general" or chart_def.breakdown_id is None
```

Replace with:

```python
    is_general = (not chart_def.breakdown_ids) or chart_def.breakdown_ids[0].lower() == "general"
```

- [ ] **Step 4: Run test to verify pass**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_pptx_generator.py::test_add_chart_handles_empty_breakdown_ids_as_general -v
```

Expected: PASS. Other pre-existing pptx_generator tests that use `breakdown_id=...` Chart constructor args will fail — Task 9 fixes them.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/pptx_generator.py backend/tests/test_pptx_generator.py
git commit -m "feat(pptx_generator): _add_chart reads breakdown_ids list

primary_bd = chart_def.breakdown_ids[0] if breakdown_ids else 'general'.
is_general derived from empty list or first element == 'general'.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Frontend types + `addChart` store action

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/store/project.ts`
- Modify: `frontend/tests/store.test.ts`

**Interfaces:**
- Consumes: nothing from backend at TypeScript compile-time.
- Produces:
  - `ChartType` TS union with 5 values.
  - `Chart` interface with `breakdown_ids: string[]`, `show_legend: boolean`, `grid_cols: number | null`, `title: string | null`.
  - `addChart(slideId: string, questionId: string, breakdownIds: string[], chartType: ChartType): void` on the store (replaces `addCharts`).

- [ ] **Step 1: Failing test**

Append to `frontend/tests/store.test.ts`:

```typescript
it("addChart creates ONE chart with breakdown_ids list", () => {
  const { setState, getState } = useProjectStore  // adapt to actual hook
  // Set up a minimal state with one slide
  setState({
    state: {
      version: 1, app_name: "AurumEncuestas", project_name: "t",
      inputs: { db_path: "", template_path: "" },
      parsed_db: null,
      slides: [{ id: "s1", type: "shell", title: "T", charts: [], analyses: [] }],
      history: { past: [], future: [] },
      palette: null,
    },
  } as any)
  getState().addChart("s1", "q1", ["edad", "sexo"], "TABLE_WITH_MINIBARS")
  const slide = getState().state!.slides.find((s) => s.id === "s1")!
  expect(slide.charts.length).toBe(1)
  expect(slide.charts[0].breakdown_ids).toEqual(["edad", "sexo"])
  expect(slide.charts[0].chart_type).toBe("TABLE_WITH_MINIBARS")
  expect(slide.charts[0].show_legend).toBe(false)
  expect(slide.charts[0].grid_cols).toBeNull()
  expect(slide.charts[0].title).toBeNull()
})
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd frontend && npx vitest run tests/store.test.ts -t "addChart creates ONE chart"
```

Expected: FAIL — `addChart` doesn't exist; current method is `addCharts` and creates N records.

- [ ] **Step 3: Update `frontend/src/types/index.ts`**

Find the existing `ChartType` and `Chart` definitions. Replace with:

```typescript
export type ChartType =
  | "PIE"
  | "PIE_GROUPED"
  | "BAR_HORIZONTAL"
  | "BAR_HORIZONTAL_GROUPED"
  | "TABLE_WITH_MINIBARS"

export interface Chart {
  id: string
  question_id: string
  breakdown_ids: string[]    // [] = general
  chart_type: ChartType
  show_legend: boolean
  grid_cols: number | null
  title: string | null
  colors: string[]
}
```

- [ ] **Step 4: Update `frontend/src/store/project.ts`**

Find `addCharts` in the store interface (around line 65):

```typescript
  addCharts(slideId: string, questionId: string, breakdownIds: string[], chartType: import("../types").ChartType): void
```

Replace with:

```typescript
  addChart(slideId: string, questionId: string, breakdownIds: string[], chartType: import("../types").ChartType): void
```

Find the implementation (around line 163):

```typescript
      addCharts(slideId, questionId, breakdownIds, chartType) {
        const s = get().state
        if (!s) return
        const slides = s.slides.map((sl) => {
          if (sl.id !== slideId) return sl
          const newCharts = breakdownIds.map((bid) => ({
            id: uid("ch"),
            question_id: questionId,
            breakdown_id: bid,
            chart_type: chartType,
            colors: [],
          }))
          return { ...sl, charts: [...sl.charts, ...newCharts] }
        })
        set({ state: { ...s, slides } })
      },
```

Replace with:

```typescript
      addChart(slideId, questionId, breakdownIds, chartType) {
        const s = get().state
        if (!s) return
        const slides = s.slides.map((sl) => {
          if (sl.id !== slideId) return sl
          const newChart = {
            id: uid("ch"),
            question_id: questionId,
            breakdown_ids: breakdownIds,
            chart_type: chartType,
            show_legend: false,
            grid_cols: null,
            title: null,
            colors: [] as string[],
          }
          return { ...sl, charts: [...sl.charts, newChart] }
        })
        set({ state: { ...s, slides } })
      },
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd frontend && npx vitest run tests/store.test.ts -t "addChart creates ONE chart"
```

Expected: PASS. Other store tests may fail on the renamed method — Task 9 fixes them.

- [ ] **Step 6: Compile-check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: errors at any remaining `addCharts(` call site (`ConfigPanel.tsx`, possibly elsewhere). Task 8 fixes them next.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/store/project.ts frontend/tests/store.test.ts
git commit -m "feat(frontend): ChartType 5-value + addChart single-record action

ChartType union reduced to 5 values. Chart interface gains
breakdown_ids array (replaces breakdown_id), show_legend, grid_cols,
title. addCharts → addChart: creates ONE Chart record per call with
breakdown_ids: string[]. ConfigPanel call sites updated in Task 8.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: AddChartModal + ConfigPanel filter, auto-lock, addChart call

**Files:**
- Modify: `frontend/src/pages/Editor/modals/AddChartModal.tsx`
- Modify: `frontend/src/pages/Editor/ConfigPanel.tsx`
- Modify: `frontend/tests/AddChartModal.test.tsx`
- Modify: `frontend/tests/ConfigPanel.test.tsx`
- Modify: `frontend/tests/AddChartModal.m6.test.tsx`

**Interfaces:**
- Consumes (from Task 7): `Chart.breakdown_ids: string[]`, `addChart(slideId, questionId, breakdownIds, chartType)`.
- Produces: AddChartModal applies a single `addChart` call with the full real breakdown list; ConfigPanel uses `addChart` too. Both filter `TABLE_WITH_MINIBARS` per the rules in spec § Frontend behavior.

- [ ] **Step 1: Write failing test (filter + auto-lock)**

Append to `frontend/tests/AddChartModal.test.tsx`:

```typescript
import { fireEvent } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

it("no real breakdown hides TABLE_WITH_MINIBARS from dropdown", () => {
  render(<AddChartModal open={true} onClose={() => {}} onApply={() => {}} db={baseDb as any} />)
  const dropdown = screen.getByLabelText(/Tipo de chart/i) as HTMLSelectElement
  const values = Array.from(dropdown.options).map((o) => o.value)
  expect(values).not.toContain("TABLE_WITH_MINIBARS")
})

it("two real breakdowns locks dropdown to TABLE_WITH_MINIBARS", async () => {
  const u = userEvent.setup()
  render(<AddChartModal open={true} onClose={() => {}} onApply={() => {}} db={baseDb as any} />)
  await u.click(screen.getByLabelText(/Rango de edad/i))
  await u.click(screen.getByLabelText(/Sexo/i))
  const dropdown = screen.getByLabelText(/Tipo de chart/i) as HTMLSelectElement
  expect(dropdown.disabled).toBe(true)
  const values = Array.from(dropdown.options).map((o) => o.value)
  expect(values).toEqual(["TABLE_WITH_MINIBARS"])
})

it("apply creates one chart with breakdown_ids list", async () => {
  const u = userEvent.setup()
  const applied: any[] = []
  render(<AddChartModal open={true} onClose={() => {}} onApply={(r) => applied.push(r)} db={baseDb as any} />)
  await u.click(screen.getByLabelText(/Rango de edad/i))
  await u.click(screen.getByLabelText(/Sexo/i))
  await u.click(screen.getByText(/Aplicar/i))
  expect(applied.length).toBe(1)
  expect(applied[0].breakdownIds).toEqual(["edad", "sexo"])
  expect(applied[0].chartType).toBe("TABLE_WITH_MINIBARS")
})
```

(Where `baseDb` has `breakdowns: [{ id:"general"... }, { id:"edad", label:"Rango de edad", ... }, { id:"sexo", label:"Sexo", ... }]`.)

- [ ] **Step 2: Run failing tests**

```bash
cd frontend && npx vitest run tests/AddChartModal.test.tsx
```

Expected: FAIL on the new tests — current code has no auto-lock and creates N records.

- [ ] **Step 3: Update AddChartModal**

In `frontend/src/pages/Editor/modals/AddChartModal.tsx`:

1. Compute `realBreakdownIds` and `chartTypes`:

```typescript
  const allChartTypes = styleGuide?.available_chart_types?.length
    ? styleGuide.available_chart_types
    : BUILTIN_CHART_TYPES
  const realBreakdownIds = useMemo(
    () => Array.from(breakdownIds).filter((b) => b !== "general"),
    [breakdownIds],
  )
  const nReal = realBreakdownIds.length
  const chartTypes = useMemo(() => {
    if (nReal === 0) return allChartTypes.filter((t) => t !== "TABLE_WITH_MINIBARS")
    if (nReal >= 2) return ["TABLE_WITH_MINIBARS"]
    return allChartTypes
  }, [allChartTypes.join(","), nReal])
```

2. Make the dropdown `disabled={nReal >= 2}` and the underlying `useEffect` auto-syncs `chartType`:

```typescript
  useEffect(() => {
    if (!chartTypes.includes(chartType)) {
      setChartType(chartTypes[0] as ChartType)
    }
  }, [chartTypes.join(","), chartType])
```

3. Update `handleApply`:

```typescript
  const handleApply = () => {
    if (!questionId) return
    onApply({
      questionId,
      breakdownIds: realBreakdownIds,
      chartType,
      colors: finalColors,
    })
    onClose()
  }
```

4. Update `ApplyResult` interface to:

```typescript
interface ApplyResult {
  questionId: string
  breakdownIds: string[]
  chartType: ChartType
  colors: string[]
}
```

(Drop `multiSeries` if still present.)

5. Add hint text under the disabled dropdown: `<p className="text-xs text-neutral-500 mt-1">Con 2+ breakdowns solo se permite TABLE_WITH_MINIBARS.</p>` shown when `nReal >= 2`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npx vitest run tests/AddChartModal.test.tsx
```

Expected: all AddChartModal tests pass (the 3 new ones plus the existing 4 may need small adjustments — e.g. the pre-existing `m6.test.tsx` test was already adapted in the prior plan).

- [ ] **Step 5: Update ConfigPanel call sites and per-chart dropdown filter**

`frontend/src/pages/Editor/ConfigPanel.tsx`:

Find the `addCharts(slide.id, r.questionId, r.breakdownIds, r.chartType)` call (around line 170) and replace with `addChart(slide.id, r.questionId, r.breakdownIds, r.chartType)`. Verify the per-chart `chart_type` dropdown filter logic — locate the existing filter (added by prior plan) and confirm it still references `chart.breakdown_id`. Replace with `chart.breakdown_ids`:

```tsx
{slide.charts.map((c) => {
  const realBds = (c.breakdown_ids || []).filter((b) => b !== "general")
  const nReal = realBds.length
  const allCT = styleGuide?.available_chart_types?.length ? styleGuide.available_chart_types : BUILTIN_CHART_TYPES
  const chartTypeOptions =
    nReal === 0 ? allCT.filter((t) => t !== "TABLE_WITH_MINIBARS")
    : nReal >= 2 ? ["TABLE_WITH_MINIBARS"]
    : allCT
  // ... render <select> with chartTypeOptions
})}
```

If ConfigPanel does not currently render a breakdown_ids editor per chart, do not add one in Fase A — that's deferred to a follow-up. ConfigPanel just needs to (a) call `addChart` instead of `addCharts` and (b) filter the chart_type options per-chart.

- [ ] **Step 6: Run frontend full suite**

```bash
cd frontend && npx vitest run 2>&1 | tail -10 && npx tsc --noEmit 2>&1 | tail -5
```

Expected: all tests green; tsc clean.

- [ ] **Step 7: Adapt existing modal tests (m6 fixture)**

Open `frontend/tests/AddChartModal.m6.test.tsx`. Locate any assertion still referencing `multiSeries` or `breakdown_id` (singular) in fixtures and replace with the new shape. The store mock should reflect new types only.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/Editor/modals/AddChartModal.tsx \
        frontend/src/pages/Editor/ConfigPanel.tsx \
        frontend/tests/AddChartModal.test.tsx \
        frontend/tests/AddChartModal.m6.test.tsx \
        frontend/tests/ConfigPanel.test.tsx
git commit -m "feat(ui): AddChartModal + ConfigPanel filter + auto-lock + addChart call

AddChartModal: hides TABLE_WITH_MINIBARS when no real breakdown picked;
locks dropdown to TABLE_WITH_MINIBARS when 2+ real breakdowns selected;
calls addChart (singular) with breakdown_ids list. ConfigPanel adopts
the same per-chart filter scoped to chart.breakdown_ids.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Adapt pre-existing tests to breakdown_ids list

**Files:**
- Modify: `backend/tests/test_models.py` (existing tests using `breakdown_id="..."`)
- Modify: `backend/tests/test_pattern_classifier.py` (existing chart-dict fixtures)
- Modify: `backend/tests/test_element_renderers.py` (existing `SimpleNamespace(breakdown_id=...)`)
- Modify: `backend/tests/test_pattern_renderer.py` (existing `test_chart_with_table_type_routes_to_table_renderer`)
- Modify: `backend/tests/test_table_renderer.py` (existing single-panel test)
- Modify: `backend/tests/test_render_e2e.py` (existing TABLE_WITH_MINIBARS e2e)
- Modify: `backend/tests/test_pptx_generator.py` (existing Chart fixtures)

**Interfaces:**
- Consumes (from Tasks 1-7): every renamed/restructured Chart field and EnrichedChart field.
- Produces: green full backend suite (255 pre-existing + ~16 new minus the ones replaced).

This task contains no new functionality — only test-fixture migration. Search/replace work.

- [ ] **Step 1: Find all `breakdown_id=` references in tests**

```bash
cd backend && grep -rn "breakdown_id" tests/ | grep -v "breakdown_ids"
```

Expected: a list of test fixtures that build `Chart(...)`, `SimpleNamespace(breakdown_id=...)`, or dict literals `{"breakdown_id": "..."}`.

- [ ] **Step 2: Convert each call site**

For each match found in Step 1:

- `Chart(..., breakdown_id="edad", ...)` → `Chart(..., breakdown_ids=["edad"], ...)`
- `Chart(..., breakdown_id="general", ...)` → `Chart(..., breakdown_ids=[], ...)`
- `SimpleNamespace(..., breakdown_id="edad", ...)` → `SimpleNamespace(..., breakdown_ids=["edad"], ...)`
- `{"breakdown_id": "edad", ...}` → `{"breakdown_ids": ["edad"], ...}`

If a test deliberately exercises the legacy field (e.g. `test_chart_rejects_legacy_breakdown_id_field` from Task 1), leave it alone — it must still use `breakdown_id` to trigger the rejection.

- [ ] **Step 3: Find any remaining hardcoded removed chart_types in fixtures**

```bash
cd backend && grep -rn 'chart_type="\(DONUT\|BAR_CLUSTERED\|BAR_STACKED\|COLUMN_CLUSTERED\|COLUMN_STACKED\|LINE\|AREA\|RADAR\|TABLE_SIMPLE\|BAR\|COLUMN\)"' tests/
```

For each match (other than the Task 1 reject-test parametrize): replace with one of the 5 allowed types (typically `PIE` for binary fixtures, `BAR_HORIZONTAL` otherwise) and ensure the test's expected outcome still makes sense.

- [ ] **Step 4: Run full backend suite**

```bash
cd backend && arch -arm64 .venv/bin/pytest -q 2>&1 | tail -5
```

Expected: 0 failures. Count should be roughly 255 (baseline) + 16 (new across Tasks 1-7) = ~271 passed, 3 skipped.

- [ ] **Step 5: Run full frontend suite + tsc**

```bash
cd frontend && npx vitest run 2>&1 | tail -5 && npx tsc --noEmit 2>&1 | tail -5
```

Expected: ~119-120 passed (116 baseline + a handful of new), tsc clean.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/ frontend/tests/
git commit -m "test: migrate fixtures to breakdown_ids list + new chart_types

Bulk fixture rename for the 2026-06-19 catalog overhaul. Any test that
deliberately exercises the legacy field stays unchanged (e.g. the Task 1
reject test). No behavioral changes — pure search/replace.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Spec coverage:**
  - Spec §Architecture: schema-first migration → Task 1 ✅
  - Spec §Data model (Chart fields + validator): Task 1 ✅
  - Spec §Frontend behavior (filter + auto-lock + single-record addChart): Tasks 7+8 ✅
  - Spec §Backend wiring (style_guide, classifier, chart_renderer, table_renderer no-change, pattern_renderer, pptx_generator): Tasks 2-6 ✅
  - Spec §Migration / breaking changes (hard fail, no auto-rewrite): Task 1 validator ✅
  - Spec §Testing strategy (backend + frontend test list): Tasks 1-8 add new tests; Task 9 migrates pre-existing ✅
  - Spec §Open risks (addCharts call-sites): Task 7+8 ✅; (n_breakdowns derivation): Task 3 ✅; (style_guide_analyzer auto-repair): Task 2 verify ✅; (AI-generated style guides): same hard fail path is covered by `load_active` ✅; (addChart param order): Task 7 names parameters explicitly ✅
- **Placeholder scan:** No "TBD" / "implement later" / "similar to Task N" without code. The only conditional language is Task 2 Step 4 ("if a rewrite branch still exists") — that is a verification step with a concrete patch if needed, not a placeholder.
- **Type consistency:** `Chart.breakdown_ids: list[str]` consistent across Tasks 1, 3, 4, 5, 6. Frontend `Chart.breakdown_ids: string[]` consistent across Tasks 7, 8. `addChart(slideId, questionId, breakdownIds, chartType)` signature consistent in Tasks 7 and 8. `EnrichedChart.breakdown_ids: list[str]` consistent in Tasks 3 and 5. `_synthesize_table_element(chart_el, source_chart)` signature stable in Task 5.
- **Open caveat:**
  - Task 4 Step 1's `test_build_chart_data_empty_breakdown_ids_uses_general` checks `values` length, not series count. The general branch returns one series of N option values (`len(values) == 2`); the multi-branch concatenates across series. Both tests pass given the current `_build_chart_data` shape — verify in execution.
  - Task 9 is a search/replace task with no novel code. It is the largest by file count but smallest by complexity. If the implementer finds any test that asserts the OLD signature deliberately (e.g. a regression test for the old behavior), they should report it and leave alone; the test may be removable in a separate cleanup.
