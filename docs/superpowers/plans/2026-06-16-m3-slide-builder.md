# M3 — Slide Builder + Preview Render + Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** User can build slides (separators + shells), add charts with multi-select breakdowns, see live PNG preview via LibreOffice, reorder slides via drag-drop, undo/redo, and export an editable `.pptx` to disk.

**Architecture:** Backend gains pptx generator (clones template shell/separator, substitutes placeholders, inserts charts via python-pptx) + layout engine (heurística A determinística) + render service (libreoffice headless → PNG). Frontend gains full 3-column Editor with SlideRail (dnd-kit drag), Preview (img with bbox overlay), ConfigPanel (chart/analysis lists + modals), Footer (undo/redo/reset), and Export modal.

**Tech Stack adds:** python-pptx chart manipulation, subprocess for libreoffice, base64 for PNG transport, @dnd-kit/sortable for rail reorder.

---

## File Structure

**Create (backend):**
- `backend/aurum_encuestas/layout_engine.py` — heurística A: grid coords
- `backend/aurum_encuestas/pptx_generator.py` — build pptx from project state
- `backend/aurum_encuestas/render_service.py` — libreoffice wrapper
- `backend/aurum_encuestas/data_extractor.py` — pull counts/% from xlsx given (question_id, breakdown_id)
- `backend/tests/test_layout_engine.py`
- `backend/tests/test_pptx_generator.py`
- `backend/tests/test_render_service.py`
- `backend/tests/test_data_extractor.py`

**Modify (backend):**
- `backend/aurum_encuestas/api.py` — endpoints `/api/preview-slide`, `/api/export-pptx`
- `backend/aurum_encuestas/xlsx_parser.py` — expose `parse_xlsx_with_data()` returning workbook handle for downstream extraction
- `backend/tests/test_api.py` — preview + export tests

**Create (frontend):**
- `frontend/src/pages/Editor/SlideRail.tsx`
- `frontend/src/pages/Editor/Preview.tsx`
- `frontend/src/pages/Editor/ConfigPanel.tsx`
- `frontend/src/pages/Editor/EditorFooter.tsx`
- `frontend/src/pages/Editor/modals/AddChartModal.tsx`
- `frontend/src/pages/Editor/modals/AddSeparatorModal.tsx`
- `frontend/src/pages/Editor/modals/ExportModal.tsx`
- `frontend/src/hooks/useDebounce.ts`
- `frontend/src/hooks/useKeyboardShortcuts.ts`
- `frontend/tests/SlideRail.test.tsx`
- `frontend/tests/ConfigPanel.test.tsx`
- `frontend/tests/AddChartModal.test.tsx`
- `frontend/tests/EditorFooter.test.tsx`

**Modify (frontend):**
- `frontend/src/api/client.ts` — `previewSlide()`, `exportPptx()`
- `frontend/src/store/project.ts` — `addChart`, `removeChart`, `updateChart`, `resetSlide`, `resetAll`
- `frontend/src/pages/Editor/EditorPage.tsx` — wire all sub-components

---

### Task 1: data_extractor — pull data for (question, breakdown)

**Files:**
- Create: `backend/aurum_encuestas/data_extractor.py`
- Create: `backend/tests/test_data_extractor.py`

- [ ] **Step 1: Failing tests**

Create `backend/tests/test_data_extractor.py`:

```python
from aurum_encuestas.data_extractor import extract_chart_data
from aurum_encuestas.xlsx_parser import parse_xlsx


def test_extract_chart_data_general(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    q1 = db.questions[0]
    data = extract_chart_data(str(valid_xlsx_path), q1, "general", db.data_blocks)
    assert "Total" in data
    # data is {breakdown_category: {option: {count, pct}}}
    assert data["Total"]["Sí"]["count"] == 458


def test_extract_chart_data_sexo(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    q1 = db.questions[0]
    data = extract_chart_data(str(valid_xlsx_path), q1, "sexo", db.data_blocks)
    assert "Hombre" in data
    assert "Mujer" in data
```

- [ ] **Step 2: Run failing**

Run: `cd backend && .venv/bin/pytest tests/test_data_extractor.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement extractor**

Create `backend/aurum_encuestas/data_extractor.py`:

```python
from openpyxl import load_workbook
from .models import Question


def extract_chart_data(xlsx_path: str, question: Question, breakdown_id: str, data_blocks: dict) -> dict:
    """Returns {breakdown_category: {option: {count, pct}}} for the given question + breakdown."""
    wb = load_workbook(xlsx_path, data_only=True)
    ws = wb.worksheets[0]

    # Find the rows of this question's options
    q_rows = _find_question_rows(ws, question)

    counts_start = data_blocks["counts_cols"][0]
    pct_start = data_blocks["pct_row_cols"][0]

    breakdown_cols = _resolve_breakdown_cols(ws, breakdown_id, counts_start)
    pct_breakdown_cols = _resolve_breakdown_cols(ws, breakdown_id, pct_start)

    result: dict[str, dict[str, dict]] = {}
    for cat, col in breakdown_cols.items():
        result[cat] = {}
        pct_col = pct_breakdown_cols.get(cat)
        for opt, row in q_rows.items():
            count = ws.cell(row, col).value or 0
            pct = ws.cell(row, pct_col).value if pct_col else None
            try:
                count_v = int(count)
            except (TypeError, ValueError):
                count_v = 0
            try:
                pct_v = float(pct) if pct is not None else None
            except (TypeError, ValueError):
                pct_v = None
            result[cat][opt] = {"count": count_v, "pct": pct_v}
    return result


def _find_question_rows(ws, question: Question) -> dict[str, int]:
    """Find rows for this question's options by matching col A marker + col B options."""
    rows: dict[str, int] = {}
    in_question = False
    options_left = list(question.options)

    for r in range(3, ws.max_row + 1):
        a = ws.cell(r, 1).value
        b = ws.cell(r, 2).value
        if a and str(a).strip() == question.text:
            in_question = True
            if b and str(b).strip() in options_left:
                rows[str(b).strip()] = r
                options_left.remove(str(b).strip())
        elif in_question and not a and b and str(b).strip() in options_left:
            rows[str(b).strip()] = r
            options_left.remove(str(b).strip())
        elif in_question and a is not None and str(a).strip():
            break  # next question started
    return rows


def _resolve_breakdown_cols(ws, breakdown_id: str, block_start_col: int) -> dict[str, int]:
    """Map category label → column index for the given breakdown within the column block."""
    row2 = {c.column: (c.value or "") for c in ws[2]}

    if breakdown_id == "general":
        # General column is the first column of the block
        return {"Total": block_start_col}

    # Find which range of cols belong to this breakdown
    row1 = {c.column: (c.value or "") for c in ws[1]}
    target_label_map = {"edad": "Rango de edad", "sexo": "Sexo", "nse": "NSE", "punto": "Punto"}
    target_label = target_label_map.get(breakdown_id)
    if not target_label:
        return {}

    # Find header for this breakdown WITHIN the block (col >= block_start_col)
    sorted_cols = sorted([c for c in row1.keys() if c >= block_start_col])
    group_starts = []
    for c in sorted_cols:
        v = str(row1[c]).strip()
        if v:
            group_starts.append((c, v))

    found = None
    for i, (c, label) in enumerate(group_starts):
        if label == target_label:
            end_col = group_starts[i + 1][0] if i + 1 < len(group_starts) else c + 7
            found = (c, end_col)
            break

    if not found:
        return {}

    start, end = found
    out = {}
    for c in range(start, end):
        cat = str(row2.get(c) or "").strip()
        if cat:
            out[cat] = c
    return out
```

- [ ] **Step 4: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_data_extractor.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/data_extractor.py backend/tests/test_data_extractor.py
git commit -m "feat(backend): data_extractor — pull (counts, pct) by (question, breakdown)"
```

---

### Task 2: layout_engine — heurística A determinística

**Files:**
- Create: `backend/aurum_encuestas/layout_engine.py`
- Create: `backend/tests/test_layout_engine.py`

- [ ] **Step 1: Failing tests**

Create `backend/tests/test_layout_engine.py`:

```python
from aurum_encuestas.layout_engine import compute_layout


FREE_AREA = {"x": 600000, "y": 1200000, "cx": 11000000, "cy": 5000000}


def test_single_chart_full_area():
    layout = compute_layout(
        n_charts=1, chart_types=["PIE"], n_chart_analyses=0, n_question_analyses=0, has_slide_analysis=False,
        free_area=FREE_AREA,
    )
    assert layout["elements"][0]["role"] == "chart_0"
    assert layout["elements"][0]["cx"] >= 9000000  # near full width


def test_two_charts_side_by_side():
    layout = compute_layout(
        n_charts=2, chart_types=["PIE", "BAR"], n_chart_analyses=0, n_question_analyses=0, has_slide_analysis=False,
        free_area=FREE_AREA,
    )
    chart_els = [e for e in layout["elements"] if e["role"].startswith("chart_")]
    assert len(chart_els) == 2
    # both at same Y
    assert chart_els[0]["y"] == chart_els[1]["y"]
    # different X
    assert chart_els[0]["x"] < chart_els[1]["x"]


def test_four_charts_2x2_grid():
    layout = compute_layout(
        n_charts=4, chart_types=["PIE"] * 4, n_chart_analyses=0, n_question_analyses=0, has_slide_analysis=False,
        free_area=FREE_AREA,
    )
    charts = [e for e in layout["elements"] if e["role"].startswith("chart_")]
    assert len(charts) == 4
    # 2 rows, 2 cols
    ys = sorted(set(c["y"] for c in charts))
    xs = sorted(set(c["x"] for c in charts))
    assert len(ys) == 2
    assert len(xs) == 2


def test_with_slide_analysis_reserves_footer():
    layout = compute_layout(
        n_charts=1, chart_types=["PIE"], n_chart_analyses=0, n_question_analyses=0, has_slide_analysis=True,
        free_area=FREE_AREA,
    )
    chart = next(e for e in layout["elements"] if e["role"] == "chart_0")
    slide_an = next(e for e in layout["elements"] if e["role"] == "slide_analysis")
    assert slide_an["y"] > chart["y"]
    # chart shrunk
    assert chart["cy"] < FREE_AREA["cy"]


def test_chart_analysis_adjacent_to_chart():
    layout = compute_layout(
        n_charts=1, chart_types=["PIE"], n_chart_analyses=1, n_question_analyses=0, has_slide_analysis=False,
        free_area=FREE_AREA,
    )
    chart_an = next(e for e in layout["elements"] if e["role"] == "chart_analysis_0")
    assert chart_an["anchor_chart"] == 0


def test_more_than_9_charts_raises():
    import pytest
    with pytest.raises(ValueError, match="9"):
        compute_layout(n_charts=10, chart_types=["PIE"] * 10, n_chart_analyses=0, n_question_analyses=0, has_slide_analysis=False, free_area=FREE_AREA)
```

- [ ] **Step 2: Run failing**

Run: `cd backend && .venv/bin/pytest tests/test_layout_engine.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement layout_engine**

Create `backend/aurum_encuestas/layout_engine.py`:

```python
"""Heurística determinística A para colocar charts + análisis en el área libre de una slide."""

PADDING = 200000  # EMU (~0.2 inch)
SLIDE_ANALYSIS_HEIGHT_RATIO = 0.15
CHART_ANALYSIS_HEIGHT_RATIO = 0.18

GRID = {
    1: (1, 1), 2: (1, 2), 3: (1, 3),
    4: (2, 2), 5: (2, 3), 6: (2, 3),
    7: (3, 3), 8: (3, 3), 9: (3, 3),
}


def compute_layout(
    n_charts: int,
    chart_types: list[str],
    n_chart_analyses: int,
    n_question_analyses: int,
    has_slide_analysis: bool,
    free_area: dict,
) -> dict:
    if n_charts > 9 or n_charts < 0:
        raise ValueError("Máximo 9 charts por slide; recibido %d" % n_charts)

    elements: list[dict] = []
    canvas_x = free_area["x"]
    canvas_y = free_area["y"]
    canvas_w = free_area["cx"]
    canvas_h = free_area["cy"]

    # Reserve footer for slide_analysis
    slide_analysis_h = int(canvas_h * SLIDE_ANALYSIS_HEIGHT_RATIO) if has_slide_analysis else 0
    chart_area_h = canvas_h - slide_analysis_h

    # Reserve space for chart-level analyses (below charts)
    has_chart_an = n_chart_analyses > 0
    chart_an_h = int(chart_area_h * CHART_ANALYSIS_HEIGHT_RATIO) if has_chart_an else 0
    grid_h = chart_area_h - chart_an_h

    if n_charts == 0:
        return {"elements": elements, "fallback_used": True}

    rows, cols = GRID[n_charts]
    cell_w = (canvas_w - PADDING * (cols - 1)) // cols
    cell_h = (grid_h - PADDING * (rows - 1)) // rows

    for i in range(n_charts):
        r = i // cols
        c = i % cols
        x = canvas_x + c * (cell_w + PADDING)
        y = canvas_y + r * (cell_h + PADDING)
        elements.append({
            "role": f"chart_{i}",
            "x": x, "y": y, "cx": cell_w, "cy": cell_h,
            "chart_type": chart_types[i] if i < len(chart_types) else "BAR",
        })

    # Chart analyses placed below each chart (max one per chart for now)
    for i in range(min(n_chart_analyses, n_charts)):
        chart_el = elements[i]
        elements.append({
            "role": f"chart_analysis_{i}",
            "x": chart_el["x"],
            "y": chart_el["y"] + chart_el["cy"] + PADDING // 2,
            "cx": chart_el["cx"],
            "cy": chart_an_h - PADDING,
            "anchor_chart": i,
        })

    # Question analyses placed at bottom of chart area
    for i in range(n_question_analyses):
        elements.append({
            "role": f"question_analysis_{i}",
            "x": canvas_x,
            "y": canvas_y + chart_area_h - chart_an_h + PADDING,
            "cx": canvas_w,
            "cy": chart_an_h - PADDING,
        })

    # Slide analysis at footer
    if has_slide_analysis:
        elements.append({
            "role": "slide_analysis",
            "x": canvas_x,
            "y": canvas_y + chart_area_h + PADDING // 2,
            "cx": canvas_w,
            "cy": slide_analysis_h - PADDING,
        })

    return {"elements": elements, "fallback_used": True}
```

- [ ] **Step 4: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_layout_engine.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/layout_engine.py backend/tests/test_layout_engine.py
git commit -m "feat(backend): layout_engine heurística A — grid charts + análisis adjacency"
```

---

### Task 3: pptx_generator — build pptx from project state

**Files:**
- Create: `backend/aurum_encuestas/pptx_generator.py`
- Create: `backend/tests/test_pptx_generator.py`

- [ ] **Step 1: Failing tests**

Create `backend/tests/test_pptx_generator.py`:

```python
from aurum_encuestas.pptx_generator import build_pptx
from aurum_encuestas.models import (
    ProjectState, ProjectInputs, Slide, Chart, Analysis, ParsedDB, Question, Breakdown,
)
from pptx import Presentation


def _state(slides, valid_xlsx_path, valid_template_path):
    return ProjectState(
        version=1, project_name="t",
        inputs=ProjectInputs(db_path=str(valid_xlsx_path), template_path=str(valid_template_path)),
        parsed_db=ParsedDB(
            questions=[Question(id="q1", code="P1", text="$p1.recordacion", options=["Sí", "No"], confidence=1.0)],
            breakdowns=[
                Breakdown(id="general", label="General", categories=["Total"]),
                Breakdown(id="sexo", label="Sexo", categories=["Hombre", "Mujer"]),
            ],
            sample_size=500,
            data_blocks={"counts_cols": [3, 17], "pct_row_cols": [21, 35], "pct_col_cols": [41, 55]},
        ),
        slides=slides,
    )


def test_build_pptx_with_separator_and_shell(tmp_path, valid_xlsx_path, valid_template_path):
    slides = [
        Slide(id="s1", type="separator", title="Sección A"),
        Slide(id="s2", type="shell", title="Sección A", charts=[], analyses=[]),
    ]
    state = _state(slides, valid_xlsx_path, valid_template_path)
    out = tmp_path / "out.pptx"
    build_pptx(state, str(out))
    assert out.exists()

    prs = Presentation(str(out))
    assert len(prs.slides) == 2


def test_build_pptx_substitutes_titulo(tmp_path, valid_xlsx_path, valid_template_path):
    slides = [
        Slide(id="s1", type="separator", title="Sección XYZ"),
    ]
    state = _state(slides, valid_xlsx_path, valid_template_path)
    out = tmp_path / "out.pptx"
    build_pptx(state, str(out))

    prs = Presentation(str(out))
    texts = []
    for sh in prs.slides[0].shapes:
        if sh.has_text_frame:
            texts.append(sh.text_frame.text)
    assert any("Sección XYZ" in t for t in texts)
    assert not any("@Titulo" in t for t in texts)


def test_build_pptx_with_chart(tmp_path, valid_xlsx_path, valid_template_path):
    chart = Chart(id="c1", question_id="q1", breakdown_id="general", chart_type="PIE", multi_series=False)
    slides = [
        Slide(id="s1", type="separator", title="Sec"),
        Slide(id="s2", type="shell", title="Sec", charts=[chart]),
    ]
    state = _state(slides, valid_xlsx_path, valid_template_path)
    out = tmp_path / "out.pptx"
    build_pptx(state, str(out))

    prs = Presentation(str(out))
    chart_shapes = [sh for sh in prs.slides[1].shapes if getattr(sh, "has_chart", False)]
    assert len(chart_shapes) == 1


def test_build_pptx_with_analysis_text(tmp_path, valid_xlsx_path, valid_template_path):
    analysis = Analysis(id="a1", scope="slide", target_id=None, text="Análisis XYZ", ai_generated=True, edited=False)
    slides = [
        Slide(id="s1", type="separator", title="Sec"),
        Slide(id="s2", type="shell", title="Sec", analyses=[analysis]),
    ]
    state = _state(slides, valid_xlsx_path, valid_template_path)
    out = tmp_path / "out.pptx"
    build_pptx(state, str(out))

    prs = Presentation(str(out))
    texts = [sh.text_frame.text for sh in prs.slides[1].shapes if sh.has_text_frame]
    assert any("Análisis XYZ" in t for t in texts)
```

- [ ] **Step 2: Run failing**

Run: `cd backend && .venv/bin/pytest tests/test_pptx_generator.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement pptx_generator**

Create `backend/aurum_encuestas/pptx_generator.py`:

```python
import re
from copy import deepcopy

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Emu

from .data_extractor import extract_chart_data
from .layout_engine import compute_layout
from .models import Analysis, Chart, ProjectState, Slide


CHART_TYPE_MAP = {
    "PIE": XL_CHART_TYPE.PIE,
    "DONUT": XL_CHART_TYPE.DOUGHNUT,
    "BAR": XL_CHART_TYPE.BAR_CLUSTERED,
    "COLUMN": XL_CHART_TYPE.COLUMN_CLUSTERED,
    "BAR_STACKED": XL_CHART_TYPE.BAR_STACKED,
    "COLUMN_STACKED": XL_CHART_TYPE.COLUMN_STACKED,
    "LINE": XL_CHART_TYPE.LINE,
    "AREA": XL_CHART_TYPE.AREA,
    "RADAR": XL_CHART_TYPE.RADAR,
}

PLACEHOLDER_RE = re.compile(r"@(\w+)")


def build_pptx(state: ProjectState, out_path: str) -> None:
    """Build final pptx. Opens template, removes its 2 slides, then for each slide in state
    clones the appropriate source slide (shell or separator), substitutes placeholders, inserts shapes."""
    template_path = state.inputs.template_path
    prs = Presentation(template_path)

    # Cache source XMLs
    shell_src_xml = etree.tostring(prs.slides[0]._element)
    separator_src_xml = etree.tostring(prs.slides[1]._element)
    shell_rels = list(prs.slides[0].part.rels.values())

    # Remove template's 2 slides
    xml_slides = prs.slides._sldIdLst
    slides_list = list(xml_slides)
    for sld in slides_list:
        xml_slides.remove(sld)

    # Compute free_area from original shell slide (before remove)
    from .pptx_template import _compute_free_area
    free_area = _compute_free_area(
        Presentation(template_path).slides[0],
        prs.slide_width, prs.slide_height,
    )

    sep_counter = 0
    for idx, slide_def in enumerate(state.slides):
        if slide_def.type == "separator":
            sep_counter += 1
            _append_separator(prs, separator_src_xml, slide_def.title, sep_counter)
        else:
            _append_shell(prs, shell_src_xml, slide_def, state, free_area)

    prs.save(out_path)


def _append_separator(prs, src_xml: bytes, title: str | None, counter: int) -> None:
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)
    # Clear default placeholders
    for sp in list(slide.shapes):
        sp_el = sp._element
        sp_el.getparent().remove(sp_el)
    # Append shapes from src
    src_tree = etree.fromstring(src_xml)
    src_spTree = src_tree.find(".//{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}spTree") or \
                  src_tree.find(".//{http://schemas.openxmlformats.org/presentationml/2006/main}spTree")
    if src_spTree is None:
        # Try generic
        for child in src_tree.iter():
            if child.tag.endswith("}spTree"):
                src_spTree = child
                break
    if src_spTree is not None:
        for child in list(src_spTree):
            if child.tag.endswith("}sp") or child.tag.endswith("}pic") or child.tag.endswith("}cxnSp"):
                slide.shapes._spTree.append(deepcopy(child))

    _substitute_placeholders(slide, {"@Titulo": f"{counter}. {title or ''}", "@Notas": ""})


def _append_shell(prs, src_xml: bytes, slide_def: Slide, state: ProjectState, free_area: dict) -> None:
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)
    for sp in list(slide.shapes):
        sp_el = sp._element
        sp_el.getparent().remove(sp_el)

    src_tree = etree.fromstring(src_xml)
    src_spTree = None
    for child in src_tree.iter():
        if child.tag.endswith("}spTree"):
            src_spTree = child
            break
    if src_spTree is not None:
        for child in list(src_spTree):
            if child.tag.endswith("}sp") or child.tag.endswith("}pic") or child.tag.endswith("}cxnSp"):
                slide.shapes._spTree.append(deepcopy(child))

    notes_text = slide_def.auto_notes or f"Respuesta única. Número de observaciones: {state.parsed_db.sample_size if state.parsed_db else 500}."
    _substitute_placeholders(slide, {"@Titulo": slide_def.title or "", "@Notas": notes_text})

    # Compute layout for this slide
    n_chart_an = sum(1 for a in slide_def.analyses if a.scope == "chart")
    n_q_an = sum(1 for a in slide_def.analyses if a.scope == "question")
    has_slide_an = any(a.scope == "slide" for a in slide_def.analyses)

    layout = compute_layout(
        n_charts=len(slide_def.charts),
        chart_types=[c.chart_type for c in slide_def.charts],
        n_chart_analyses=n_chart_an,
        n_question_analyses=n_q_an,
        has_slide_analysis=has_slide_an,
        free_area=free_area,
    )

    # Insert charts and analysis textboxes per layout elements
    for el in layout["elements"]:
        role = el["role"]
        if role.startswith("chart_") and not role.startswith("chart_analysis"):
            i = int(role.split("_")[1])
            chart_def = slide_def.charts[i]
            _add_chart(slide, chart_def, state, el)
        elif role.startswith("chart_analysis_"):
            i = int(role.split("_")[2])
            chart_analyses = [a for a in slide_def.analyses if a.scope == "chart"]
            if i < len(chart_analyses):
                _add_textbox(slide, chart_analyses[i].text, el)
        elif role.startswith("question_analysis_"):
            i = int(role.split("_")[2])
            q_analyses = [a for a in slide_def.analyses if a.scope == "question"]
            if i < len(q_analyses):
                _add_textbox(slide, q_analyses[i].text, el)
        elif role == "slide_analysis":
            slide_an = next((a for a in slide_def.analyses if a.scope == "slide"), None)
            if slide_an:
                _add_textbox(slide, slide_an.text, el)


def _add_chart(slide, chart_def: Chart, state: ProjectState, el: dict) -> None:
    data = extract_chart_data(state.inputs.db_path, _find_question(state, chart_def.question_id),
                              chart_def.breakdown_id, state.parsed_db.data_blocks if state.parsed_db else {})
    cd = CategoryChartData()
    # Categories = options, Series = breakdown categories (or single "Total" if general)
    options = _find_question(state, chart_def.question_id).options
    cd.categories = options

    if not chart_def.multi_series:
        # Sum across breakdown cats → single series "Total"
        series = []
        for opt in options:
            total = sum((data[cat].get(opt, {}).get("count", 0) or 0) for cat in data)
            series.append(total)
        cd.add_series("Total", series)
    else:
        for cat in data:
            values = [data[cat].get(opt, {}).get("count", 0) or 0 for opt in options]
            cd.add_series(cat, values)

    chart_type_xl = CHART_TYPE_MAP.get(chart_def.chart_type, XL_CHART_TYPE.BAR_CLUSTERED)
    slide.shapes.add_chart(chart_type_xl, Emu(el["x"]), Emu(el["y"]), Emu(el["cx"]), Emu(el["cy"]), cd)


def _add_textbox(slide, text: str, el: dict) -> None:
    tb = slide.shapes.add_textbox(Emu(el["x"]), Emu(el["y"]), Emu(el["cx"]), Emu(el["cy"]))
    tf = tb.text_frame
    tf.text = text
    tf.word_wrap = True


def _substitute_placeholders(slide, mapping: dict[str, str]) -> None:
    for sh in slide.shapes:
        if not sh.has_text_frame:
            continue
        for para in sh.text_frame.paragraphs:
            full_text = "".join(run.text or "" for run in para.runs)
            for key, val in mapping.items():
                if key in full_text:
                    new_text = full_text.replace(key, val)
                    # rewrite the paragraph as a single run
                    for run in list(para.runs):
                        run.text = ""
                    if para.runs:
                        para.runs[0].text = new_text
                    else:
                        para.add_run().text = new_text


def _find_question(state: ProjectState, qid: str):
    return next(q for q in state.parsed_db.questions if q.id == qid)
```

- [ ] **Step 4: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_pptx_generator.py -v`
Expected: 4 PASS. If lxml/spTree handling fails on local pptx structure, debug and adjust.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/pptx_generator.py backend/tests/test_pptx_generator.py
git commit -m "feat(backend): pptx_generator builds final pptx with chart insertion + placeholder substitution"
```

---

### Task 4: render_service — libreoffice wrapper

**Files:**
- Create: `backend/aurum_encuestas/render_service.py`
- Create: `backend/tests/test_render_service.py`

- [ ] **Step 1: Failing tests**

Create `backend/tests/test_render_service.py`:

```python
import shutil
from pathlib import Path

import pytest

from aurum_encuestas.render_service import render_slide_to_png


HAS_LIBREOFFICE = shutil.which("soffice") or shutil.which("libreoffice")


@pytest.mark.skipif(not HAS_LIBREOFFICE, reason="libreoffice not installed")
def test_render_first_slide_returns_png_bytes(valid_template_path):
    png = render_slide_to_png(str(valid_template_path), slide_index=0)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 1000


def test_render_returns_placeholder_if_libreoffice_missing(valid_template_path, monkeypatch):
    monkeypatch.setattr("aurum_encuestas.render_service._find_soffice", lambda: None)
    png = render_slide_to_png(str(valid_template_path), slide_index=0)
    # Returns embedded placeholder bytes (1x1 transparent png) or known marker — we accept either
    assert len(png) > 0
```

- [ ] **Step 2: Run failing**

Run: `cd backend && .venv/bin/pytest tests/test_render_service.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement render_service**

Create `backend/aurum_encuestas/render_service.py`:

```python
import base64
import shutil
import subprocess
import tempfile
from pathlib import Path

from .errors import RenderError


# 1x1 transparent PNG fallback (base64)
_PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _find_soffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    for p in ("/Applications/LibreOffice.app/Contents/MacOS/soffice", "/usr/bin/libreoffice"):
        if Path(p).exists():
            return p
    return None


def render_slide_to_png(pptx_path: str, slide_index: int = 0) -> bytes:
    """Render specified slide to PNG. Returns bytes. Falls back to placeholder if libreoffice unavailable."""
    soffice = _find_soffice()
    if soffice is None:
        return _PLACEHOLDER_PNG

    with tempfile.TemporaryDirectory() as outdir:
        try:
            subprocess.run(
                [
                    soffice, "--headless", "--convert-to", "png",
                    "--outdir", outdir, pptx_path,
                ],
                capture_output=True, timeout=30, check=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            raise RenderError(f"libreoffice falló: {e}") from e

        # libreoffice exports first slide only by default → for multi-slide we'd need pdf intermediate
        # MVP: return whatever it produced.
        outputs = list(Path(outdir).glob("*.png"))
        if not outputs:
            raise RenderError("libreoffice no produjo PNG")
        return outputs[0].read_bytes()
```

- [ ] **Step 4: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_render_service.py -v`
Expected: 2 PASS (1 skipped if libreoffice missing).

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/render_service.py backend/tests/test_render_service.py
git commit -m "feat(backend): render_service — libreoffice wrapper with placeholder fallback"
```

---

### Task 5: Render service — render specific slide via PDF intermediate (multi-slide support)

**Files:**
- Modify: `backend/aurum_encuestas/render_service.py`
- Modify: `backend/tests/test_render_service.py`

- [ ] **Step 1: Failing test for multi-slide selection**

Append to `backend/tests/test_render_service.py`:

```python
@pytest.mark.skipif(not HAS_LIBREOFFICE, reason="libreoffice not installed")
def test_render_specific_slide(valid_template_path):
    png0 = render_slide_to_png(str(valid_template_path), slide_index=0)
    png1 = render_slide_to_png(str(valid_template_path), slide_index=1)
    assert png0 != png1
```

- [ ] **Step 2: Implement PDF intermediate strategy**

Replace `render_slide_to_png` in `render_service.py`:

```python
import os

def render_slide_to_png(pptx_path: str, slide_index: int = 0) -> bytes:
    """Render specified slide to PNG. Uses pdf intermediate to support multi-slide selection.

    Pipeline: pptx → pdf (libreoffice) → png at slide_index page (pdftoppm if available, else pillow).
    """
    soffice = _find_soffice()
    if soffice is None:
        return _PLACEHOLDER_PNG

    with tempfile.TemporaryDirectory() as outdir:
        # Step 1: pptx → pdf
        try:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", outdir, pptx_path],
                capture_output=True, timeout=45, check=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            raise RenderError(f"libreoffice pptx→pdf falló: {e}") from e

        pdfs = list(Path(outdir).glob("*.pdf"))
        if not pdfs:
            raise RenderError("libreoffice no produjo PDF")
        pdf_path = pdfs[0]

        # Step 2: pdf page N → png
        pdftoppm = shutil.which("pdftoppm")
        if pdftoppm:
            try:
                subprocess.run(
                    [
                        pdftoppm, "-png", "-r", "120",
                        "-f", str(slide_index + 1), "-l", str(slide_index + 1),
                        str(pdf_path), str(Path(outdir) / "page"),
                    ],
                    capture_output=True, timeout=15, check=True,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                raise RenderError(f"pdftoppm falló: {e}") from e
            for p in Path(outdir).glob("page-*.png"):
                return p.read_bytes()
            raise RenderError("pdftoppm no produjo PNG")
        else:
            # Fallback: try pypdfium2 or pdf2image; otherwise convert first slide only via direct png
            try:
                from pdf2image import convert_from_path
                imgs = convert_from_path(str(pdf_path), dpi=120, first_page=slide_index + 1, last_page=slide_index + 1)
                if imgs:
                    import io
                    buf = io.BytesIO()
                    imgs[0].save(buf, "PNG")
                    return buf.getvalue()
            except ImportError:
                pass
            raise RenderError("Sin pdftoppm ni pdf2image disponibles para renderizar slide específica")
```

Add to `backend/pyproject.toml` dependencies:

```toml
  "pdf2image>=1.17",
  "Pillow>=10.0",
```

Re-install: `cd backend && .venv/bin/pip install -e ".[dev]"`

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_render_service.py -v`
Expected: PASS (skipped if no libreoffice, else all pass).

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/render_service.py backend/tests/test_render_service.py backend/pyproject.toml
git commit -m "feat(backend): render_service — multi-slide PDF intermediate (pdftoppm/pdf2image)"
```

---

### Task 6: API — preview-slide + export-pptx endpoints

**Files:**
- Modify: `backend/aurum_encuestas/api.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_api.py`:

```python
import base64
import json
from pathlib import Path
import shutil
import pytest


HAS_SOFFICE = shutil.which("soffice") or shutil.which("libreoffice") or Path("/Applications/LibreOffice.app/Contents/MacOS/soffice").exists()


def _project_payload(xlsx_path: str, tpl_path: str) -> dict:
    return {
        "version": 1,
        "project_name": "Test",
        "inputs": {"db_path": xlsx_path, "template_path": tpl_path, "font_override": None},
        "parsed_db": {
            "questions": [{"id": "q1", "code": "P1", "text": "$p1.recordacion", "options": ["Sí", "No"], "confidence": 1.0}],
            "breakdowns": [
                {"id": "general", "label": "General", "categories": ["Total"]},
                {"id": "sexo", "label": "Sexo", "categories": ["Hombre", "Mujer"]},
            ],
            "sample_size": 500,
            "data_blocks": {"counts_cols": [3, 17], "pct_row_cols": [21, 35], "pct_col_cols": [41, 55]},
        },
        "slides": [
            {"id": "s1", "type": "separator", "title": "Sección", "charts": [], "analyses": [], "auto_notes": None},
            {"id": "s2", "type": "shell", "title": "Sección",
             "charts": [{"id": "c1", "question_id": "q1", "breakdown_id": "general", "chart_type": "PIE", "multi_series": False}],
             "analyses": [], "auto_notes": None},
        ],
    }


@pytest.mark.skipif(not HAS_SOFFICE, reason="libreoffice not installed")
def test_preview_slide_returns_base64_png(valid_xlsx_path, valid_template_path):
    payload = {"state": _project_payload(str(valid_xlsx_path), str(valid_template_path)), "slide_index": 0}
    r = client.post("/api/preview-slide", json=payload)
    assert r.status_code == 200
    png_b64 = r.json()["png_base64"]
    png = base64.b64decode(png_b64)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_export_pptx_writes_file(tmp_path, valid_xlsx_path, valid_template_path):
    out = tmp_path / "out.pptx"
    payload = {"state": _project_payload(str(valid_xlsx_path), str(valid_template_path)), "path": str(out)}
    r = client.post("/api/export-pptx", json=payload)
    assert r.status_code == 200
    assert out.exists()
    assert out.stat().st_size > 1000
```

- [ ] **Step 2: Implement endpoints**

Append to `backend/aurum_encuestas/api.py`:

```python
import base64
import tempfile

from .pptx_generator import build_pptx
from .render_service import render_slide_to_png


class PreviewSlideRequest(BaseModel):
    state: dict
    slide_index: int


@app.post("/api/preview-slide")
async def preview_slide_endpoint(req: PreviewSlideRequest):
    state = ProjectState.model_validate(req.state)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tmp:
        tmp_path = tmp.name
    try:
        build_pptx(state, tmp_path)
        png = render_slide_to_png(tmp_path, slide_index=req.slide_index)
        return {"png_base64": base64.b64encode(png).decode("ascii")}
    finally:
        Path(tmp_path).unlink(missing_ok=True)


class ExportPptxRequest(BaseModel):
    state: dict
    path: str


@app.post("/api/export-pptx")
async def export_pptx_endpoint(req: ExportPptxRequest):
    state = ProjectState.model_validate(req.state)
    build_pptx(state, req.path)
    return {"exported": True, "path": req.path, "size": Path(req.path).stat().st_size}
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_api.py -v`
Expected: PASS (preview may skip if libreoffice absent).

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/api.py backend/tests/test_api.py
git commit -m "feat(backend): /api/preview-slide + /api/export-pptx endpoints"
```

---

### Task 7: Frontend store — addChart/removeChart/updateChart + reset

**Files:**
- Modify: `frontend/src/store/project.ts`
- Modify: `frontend/tests/store.test.ts`

- [ ] **Step 1: Failing tests**

Append to `frontend/tests/store.test.ts`:

```ts
describe("store chart operations", () => {
  beforeEach(() => {
    useProjectStore.setState({ state: null })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    useProjectStore.getState().addSeparator("Sec")
    useProjectStore.getState().addShell()
  })

  it("addChart appends one chart", () => {
    useProjectStore.getState().addCharts("s_id_ignored", "q1", ["general"], "PIE", false)
    // last slide is the shell
    const shell = useProjectStore.getState().state!.slides[1]
    expect(shell.charts.length).toBe(1)
    expect(shell.charts[0].chart_type).toBe("PIE")
  })

  it("addCharts multi-select breakdowns creates N charts", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addCharts(shellId, "q1", ["general", "sexo", "edad"], "BAR", false)
    const shell = useProjectStore.getState().state!.slides[1]
    expect(shell.charts.length).toBe(3)
    expect(shell.charts.every(c => c.chart_type === "BAR")).toBe(true)
  })

  it("updateChartType changes one chart", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addCharts(shellId, "q1", ["general", "sexo"], "PIE", false)
    const chart0 = useProjectStore.getState().state!.slides[1].charts[0]
    useProjectStore.getState().updateChartType(shellId, chart0.id, "BAR")
    const updated = useProjectStore.getState().state!.slides[1].charts[0]
    expect(updated.chart_type).toBe("BAR")
  })

  it("resetSlide clears charts and analyses", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addCharts(shellId, "q1", ["general"], "PIE", false)
    useProjectStore.getState().resetSlide(shellId)
    expect(useProjectStore.getState().state!.slides[1].charts).toEqual([])
  })

  it("resetAll empties slides", () => {
    useProjectStore.getState().resetAll()
    expect(useProjectStore.getState().state!.slides).toEqual([])
  })
})
```

- [ ] **Step 2: Implement actions in store**

Append to `Store` interface in `frontend/src/store/project.ts`:

```ts
  addCharts(slideId: string, questionId: string, breakdownIds: string[], chartType: import("../types").ChartType, multiSeries: boolean): void
  removeChart(slideId: string, chartId: string): void
  updateChartType(slideId: string, chartId: string, chartType: import("../types").ChartType): void
  resetSlide(slideId: string): void
  resetAll(): void
```

Add implementations inside `temporal((set, get) => ({ ... }))`:

```ts
      addCharts(slideId, questionId, breakdownIds, chartType, multiSeries) {
        const s = get().state
        if (!s) return
        const slides = s.slides.map((sl) => {
          if (sl.id !== slideId) return sl
          const newCharts = breakdownIds.map((bid) => ({
            id: uid("ch"), question_id: questionId, breakdown_id: bid, chart_type: chartType, multi_series: multiSeries,
          }))
          return { ...sl, charts: [...sl.charts, ...newCharts] }
        })
        set({ state: { ...s, slides } })
      },

      removeChart(slideId, chartId) {
        const s = get().state
        if (!s) return
        const slides = s.slides.map((sl) =>
          sl.id !== slideId ? sl : { ...sl, charts: sl.charts.filter((c) => c.id !== chartId) },
        )
        set({ state: { ...s, slides } })
      },

      updateChartType(slideId, chartId, chartType) {
        const s = get().state
        if (!s) return
        const slides = s.slides.map((sl) =>
          sl.id !== slideId ? sl : {
            ...sl,
            charts: sl.charts.map((c) => (c.id === chartId ? { ...c, chart_type: chartType } : c)),
          },
        )
        set({ state: { ...s, slides } })
      },

      resetSlide(slideId) {
        const s = get().state
        if (!s) return
        const slides = s.slides.map((sl) =>
          sl.id !== slideId ? sl : { ...sl, charts: [], analyses: [] },
        )
        set({ state: { ...s, slides } })
      },

      resetAll() {
        const s = get().state
        if (!s) return
        set({ state: { ...s, slides: [] } })
      },
```

- [ ] **Step 3: Run tests**

Run: `cd frontend && npm test`
Expected: PASS (all store tests including new ones).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/store/project.ts frontend/tests/store.test.ts
git commit -m "feat(frontend): store actions — addCharts (multi-breakdown), removeChart, updateChartType, reset"
```

---

### Task 8: API client — previewSlide + exportPptx

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add functions**

Append to `frontend/src/api/client.ts`:

```ts
export async function previewSlide(state: ProjectState, slideIndex: number): Promise<{ png_base64: string }> {
  return request("/preview-slide", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state, slide_index: slideIndex }),
  })
}

export async function exportPptx(state: ProjectState, path: string): Promise<{ exported: boolean; path: string; size: number }> {
  return request("/export-pptx", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state, path }),
  })
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(frontend): api client — previewSlide + exportPptx"
```

---

### Task 9: SlideRail with drag-drop reorder + add buttons

**Files:**
- Create: `frontend/src/pages/Editor/SlideRail.tsx`
- Create: `frontend/src/pages/Editor/modals/AddSeparatorModal.tsx`
- Create: `frontend/tests/SlideRail.test.tsx`

- [ ] **Step 1: Failing tests**

Create `frontend/tests/SlideRail.test.tsx`:

```tsx
import { describe, expect, it, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import SlideRail from "../src/pages/Editor/SlideRail"
import { useProjectStore } from "../src/store/project"

describe("SlideRail", () => {
  beforeEach(() => {
    useProjectStore.setState({ state: null })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
  })

  it("disables + Slide when no separator exists", () => {
    render(<SlideRail selectedId={null} onSelect={() => {}} />)
    const btn = screen.getByRole("button", { name: /\+ Slide/i })
    expect(btn).toBeDisabled()
  })

  it("enables + Slide once separator added", async () => {
    useProjectStore.getState().addSeparator("Sec")
    render(<SlideRail selectedId={null} onSelect={() => {}} />)
    const btn = screen.getByRole("button", { name: /\+ Slide/i })
    expect(btn).not.toBeDisabled()
  })

  it("clicking + Separador opens modal", async () => {
    render(<SlideRail selectedId={null} onSelect={() => {}} />)
    await userEvent.click(screen.getByRole("button", { name: /\+ Separador/i }))
    expect(screen.getByLabelText(/Título sección/i)).toBeInTheDocument()
  })

  it("creating separator adds it to the rail", async () => {
    render(<SlideRail selectedId={null} onSelect={() => {}} />)
    await userEvent.click(screen.getByRole("button", { name: /\+ Separador/i }))
    await userEvent.type(screen.getByLabelText(/Título sección/i), "Nueva")
    await userEvent.click(screen.getByRole("button", { name: /^Crear$/i }))
    expect(useProjectStore.getState().state!.slides.length).toBe(1)
  })

  it("rail thumbnails distinguish separator vs shell by class", async () => {
    useProjectStore.getState().addSeparator("S")
    useProjectStore.getState().addShell()
    render(<SlideRail selectedId={null} onSelect={() => {}} />)
    const thumbs = screen.getAllByTestId(/thumb-/)
    expect(thumbs.length).toBe(2)
    expect(thumbs[0]).toHaveClass("border-accent")  // separator class marker
  })
})
```

- [ ] **Step 2: Implement AddSeparatorModal**

Create `frontend/src/pages/Editor/modals/AddSeparatorModal.tsx`:

```tsx
import { useState } from "react"
import Modal from "../../../components/Modal"

interface Props {
  open: boolean
  onClose(): void
  onCreate(title: string): void
}

export default function AddSeparatorModal({ open, onClose, onCreate }: Props) {
  const [title, setTitle] = useState("")
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return
    onCreate(title.trim())
    setTitle("")
    onClose()
  }
  return (
    <Modal open={open} onClose={onClose} title="Nuevo separador" footer={
      <>
        <button onClick={onClose} className="px-3 py-1.5 text-sm rounded bg-neutral-700">Cancelar</button>
        <button onClick={handleSubmit} className="px-3 py-1.5 text-sm rounded bg-accent text-neutral-900 font-semibold">Crear</button>
      </>
    }>
      <form onSubmit={handleSubmit}>
        <label htmlFor="sep-title" className="block text-xs text-neutral-400 mb-1">Título sección</label>
        <input
          id="sep-title"
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
        />
      </form>
    </Modal>
  )
}
```

- [ ] **Step 3: Implement SlideRail with dnd-kit**

Create `frontend/src/pages/Editor/SlideRail.tsx`:

```tsx
import { useState } from "react"
import { DndContext, closestCenter, DragEndEvent, PointerSensor, useSensor, useSensors } from "@dnd-kit/core"
import { SortableContext, useSortable, verticalListSortingStrategy, arrayMove } from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { Plus } from "lucide-react"
import { useProjectStore } from "../../store/project"
import AddSeparatorModal from "./modals/AddSeparatorModal"

interface Props {
  selectedId: string | null
  onSelect(id: string): void
}

export default function SlideRail({ selectedId, onSelect }: Props) {
  const slides = useProjectStore((s) => s.state?.slides ?? [])
  const addSeparator = useProjectStore((s) => s.addSeparator)
  const addShell = useProjectStore((s) => s.addShell)
  const reorderSlide = useProjectStore((s) => s.reorderSlide)
  const [sepOpen, setSepOpen] = useState(false)

  const hasSeparator = slides.some((s) => s.type === "separator")
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))

  function handleDragEnd(ev: DragEndEvent) {
    const { active, over } = ev
    if (over && active.id !== over.id) {
      const fromIdx = slides.findIndex((s) => s.id === active.id)
      const toIdx = slides.findIndex((s) => s.id === over.id)
      reorderSlide(fromIdx, toIdx)
    }
  }

  return (
    <aside className="bg-neutral-900 border-r border-neutral-700 p-2 flex flex-col gap-1 overflow-y-auto">
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={slides.map((s) => s.id)} strategy={verticalListSortingStrategy}>
          {slides.map((slide, idx) => (
            <SortableThumb
              key={slide.id}
              slide={slide}
              index={idx}
              selected={selectedId === slide.id}
              onClick={() => onSelect(slide.id)}
            />
          ))}
        </SortableContext>
      </DndContext>

      <div className="mt-auto flex flex-col gap-1 pt-2">
        <button
          onClick={() => setSepOpen(true)}
          className="text-xs bg-neutral-800 hover:bg-neutral-700 border border-dashed border-neutral-600 py-1.5 rounded flex items-center justify-center gap-1"
        >
          <Plus size={12} /> Separador
        </button>
        <button
          disabled={!hasSeparator}
          onClick={() => addShell()}
          className="text-xs bg-neutral-800 hover:bg-neutral-700 border border-dashed border-neutral-600 py-1.5 rounded flex items-center justify-center gap-1 disabled:opacity-40 disabled:cursor-not-allowed"
          title={hasSeparator ? "" : "Agregá un separador primero"}
        >
          <Plus size={12} /> Slide
        </button>
      </div>

      <AddSeparatorModal open={sepOpen} onClose={() => setSepOpen(false)} onCreate={(t) => addSeparator(t)} />
    </aside>
  )
}

function SortableThumb({ slide, index, selected, onClick }: { slide: any; index: number; selected: boolean; onClick(): void }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: slide.id })
  const style = { transform: CSS.Transform.toString(transform), transition }
  const isSep = slide.type === "separator"
  return (
    <div
      ref={setNodeRef}
      data-testid={`thumb-${slide.id}`}
      style={style}
      {...attributes}
      {...listeners}
      onClick={onClick}
      className={`relative aspect-[16/9] bg-white rounded cursor-pointer border-2 ${selected ? "border-amber-400" : isSep ? "border-accent" : "border-transparent"} ${isSep ? "bg-neutral-200" : ""}`}
    >
      <span className="absolute -top-2 -left-2 bg-neutral-800 text-accent text-[10px] px-1.5 rounded">{index + 1}</span>
      <span className="absolute inset-0 flex items-center justify-center text-[8px] text-neutral-500 px-1 text-center">
        {isSep ? `▸ ${slide.title || ""}` : slide.title || "sin título"}
      </span>
    </div>
  )
}
```

- [ ] **Step 4: Run, verify pass**

Run: `cd frontend && npm test -- SlideRail`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Editor/SlideRail.tsx frontend/src/pages/Editor/modals/AddSeparatorModal.tsx frontend/tests/SlideRail.test.tsx
git commit -m "feat(frontend): SlideRail with dnd-kit reorder + add separator/shell + modal"
```

---

### Task 10: AddChartModal

**Files:**
- Create: `frontend/src/pages/Editor/modals/AddChartModal.tsx`
- Create: `frontend/tests/AddChartModal.test.tsx`

- [ ] **Step 1: Failing tests**

Create `frontend/tests/AddChartModal.test.tsx`:

```tsx
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import AddChartModal from "../src/pages/Editor/modals/AddChartModal"
import type { ParsedDB } from "../src/types"

const DB: ParsedDB = {
  questions: [
    { id: "q1", code: "P1", text: "¿X?", options: ["a", "b"], confidence: 1.0 },
    { id: "q2", code: "P2", text: "¿Y?", options: ["c"], confidence: 1.0 },
  ],
  breakdowns: [
    { id: "general", label: "General", categories: ["Total"] },
    { id: "sexo", label: "Sexo", categories: ["H", "M"] },
  ],
  sample_size: 500,
  data_blocks: { counts_cols: [], pct_row_cols: [], pct_col_cols: [] },
}

describe("AddChartModal", () => {
  it("renders question + breakdown selectors", () => {
    render(<AddChartModal open onClose={() => {}} onApply={() => {}} db={DB} />)
    expect(screen.getByLabelText(/Pregunta/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/General/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Sexo/i)).toBeInTheDocument()
  })

  it("Apply calls onApply with selected", async () => {
    let result: any = null
    render(<AddChartModal open onClose={() => {}} onApply={(r) => { result = r }} db={DB} />)
    await userEvent.click(screen.getByLabelText(/General/i))
    await userEvent.click(screen.getByRole("button", { name: /Aplicar/i }))
    expect(result.questionId).toBe("q1")
    expect(result.breakdownIds).toContain("general")
  })
})
```

- [ ] **Step 2: Implement modal**

Create `frontend/src/pages/Editor/modals/AddChartModal.tsx`:

```tsx
import { useState, useEffect } from "react"
import Modal from "../../../components/Modal"
import type { ChartType, ParsedDB } from "../../../types"

const CHART_TYPES: ChartType[] = ["PIE", "DONUT", "BAR", "COLUMN", "BAR_STACKED", "COLUMN_STACKED", "LINE", "AREA", "RADAR"]

interface ApplyResult {
  questionId: string
  breakdownIds: string[]
  chartType: ChartType
  multiSeries: boolean
}

interface Props {
  open: boolean
  onClose(): void
  onApply(r: ApplyResult): void
  db: ParsedDB | null
}

export default function AddChartModal({ open, onClose, onApply, db }: Props) {
  const [questionId, setQuestionId] = useState<string>("")
  const [breakdownIds, setBreakdownIds] = useState<Set<string>>(new Set())
  const [chartType, setChartType] = useState<ChartType>("PIE")
  const [multiSeries, setMultiSeries] = useState(false)

  useEffect(() => {
    if (open && db && db.questions.length > 0) {
      setQuestionId(db.questions[0].id)
      setBreakdownIds(new Set())
    }
  }, [open, db])

  if (!db) return null

  const toggleBreakdown = (bid: string) => {
    const next = new Set(breakdownIds)
    if (next.has(bid)) next.delete(bid); else next.add(bid)
    setBreakdownIds(next)
  }

  const handleApply = () => {
    if (!questionId || breakdownIds.size === 0) return
    onApply({ questionId, breakdownIds: Array.from(breakdownIds), chartType, multiSeries })
    onClose()
  }

  return (
    <Modal open={open} onClose={onClose} title="Agregar chart" footer={
      <>
        <button onClick={onClose} className="px-3 py-1.5 text-sm rounded bg-neutral-700">Cancelar</button>
        <button
          disabled={!questionId || breakdownIds.size === 0}
          onClick={handleApply}
          className="px-3 py-1.5 text-sm rounded bg-accent text-neutral-900 font-semibold disabled:opacity-40"
        >Aplicar</button>
      </>
    }>
      <label htmlFor="q-select" className="block text-xs text-neutral-400 mb-1">Pregunta</label>
      <select
        id="q-select"
        value={questionId}
        onChange={(e) => setQuestionId(e.target.value)}
        className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
      >
        {db.questions.map((q) => (
          <option key={q.id} value={q.id}>{q.code}: {q.text}</option>
        ))}
      </select>

      <div className="text-xs text-neutral-400 mb-1">Breakdowns (multi-select)</div>
      <div className="grid grid-cols-2 gap-1 mb-3">
        {db.breakdowns.map((b) => (
          <label key={b.id} className="flex items-center gap-2 text-sm bg-neutral-900 px-2 py-1.5 rounded cursor-pointer">
            <input
              type="checkbox"
              checked={breakdownIds.has(b.id)}
              onChange={() => toggleBreakdown(b.id)}
              aria-label={b.label}
            />
            {b.label}
          </label>
        ))}
      </div>

      <label htmlFor="ct-select" className="block text-xs text-neutral-400 mb-1">Tipo de chart</label>
      <select
        id="ct-select"
        value={chartType}
        onChange={(e) => setChartType(e.target.value as ChartType)}
        className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
      >
        {CHART_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
      </select>

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={multiSeries} onChange={(e) => setMultiSeries(e.target.checked)} />
        Multi-serie (desglose por sub-categoría)
      </label>
    </Modal>
  )
}
```

- [ ] **Step 3: Run, verify pass**

Run: `cd frontend && npm test -- AddChartModal`
Expected: 2 PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Editor/modals/AddChartModal.tsx frontend/tests/AddChartModal.test.tsx
git commit -m "feat(frontend): AddChartModal with multi-select breakdowns + chart type"
```

---

### Task 11: ConfigPanel — chart list with type override

**Files:**
- Create: `frontend/src/pages/Editor/ConfigPanel.tsx`
- Create: `frontend/tests/ConfigPanel.test.tsx`

- [ ] **Step 1: Failing tests**

Create `frontend/tests/ConfigPanel.test.tsx`:

```tsx
import { describe, expect, it, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import ConfigPanel from "../src/pages/Editor/ConfigPanel"
import { useProjectStore } from "../src/store/project"
import type { ParsedDB } from "../src/types"

const DB: ParsedDB = {
  questions: [{ id: "q1", code: "P1", text: "?", options: ["a"], confidence: 1.0 }],
  breakdowns: [{ id: "general", label: "General", categories: ["Total"] }],
  sample_size: 500,
  data_blocks: { counts_cols: [], pct_row_cols: [], pct_col_cols: [] },
}

describe("ConfigPanel", () => {
  beforeEach(() => {
    useProjectStore.setState({ state: null, parsedDb: DB })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    useProjectStore.getState().addSeparator("Sec")
    useProjectStore.getState().addShell()
  })

  it("shows title (read-only) for shell from separator", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    render(<ConfigPanel slideId={shellId} />)
    expect(screen.getByDisplayValue("Sec")).toBeDisabled()
  })

  it("allows separator title edit", () => {
    const sepId = useProjectStore.getState().state!.slides[0].id
    render(<ConfigPanel slideId={sepId} />)
    expect(screen.getByDisplayValue("Sec")).not.toBeDisabled()
  })

  it("clicking + Chart opens modal", async () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    render(<ConfigPanel slideId={shellId} />)
    await userEvent.click(screen.getByRole("button", { name: /\+ Chart/i }))
    expect(screen.getByText(/Agregar chart/i)).toBeInTheDocument()
  })

  it("chart list shows added charts with type override select", async () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addCharts(shellId, "q1", ["general"], "PIE", false)
    render(<ConfigPanel slideId={shellId} />)
    const selects = screen.getAllByRole("combobox")
    expect(selects.some((sel) => (sel as HTMLSelectElement).value === "PIE")).toBe(true)
  })
})
```

- [ ] **Step 2: Implement ConfigPanel**

Create `frontend/src/pages/Editor/ConfigPanel.tsx`:

```tsx
import { useState } from "react"
import { Plus, Trash2 } from "lucide-react"
import { useProjectStore } from "../../store/project"
import AddChartModal from "./modals/AddChartModal"
import type { ChartType } from "../../types"

const CHART_TYPES: ChartType[] = ["PIE", "DONUT", "BAR", "COLUMN", "BAR_STACKED", "COLUMN_STACKED", "LINE", "AREA", "RADAR"]

interface Props {
  slideId: string | null
}

export default function ConfigPanel({ slideId }: Props) {
  const state = useProjectStore((s) => s.state)
  const parsedDb = useProjectStore((s) => s.parsedDb)
  const addCharts = useProjectStore((s) => s.addCharts)
  const removeChart = useProjectStore((s) => s.removeChart)
  const updateChartType = useProjectStore((s) => s.updateChartType)
  const updateSeparatorTitle = useProjectStore((s) => s.updateSeparatorTitle)
  const [chartModalOpen, setChartModalOpen] = useState(false)

  const slide = state?.slides.find((s) => s.id === slideId)
  if (!slide) return <aside className="bg-neutral-900 border-l border-neutral-700 p-3 text-sm text-neutral-500">Seleccioná una slide</aside>

  const isSep = slide.type === "separator"

  return (
    <aside className="bg-neutral-900 border-l border-neutral-700 p-3 text-sm overflow-y-auto">
      <h3 className="text-xs uppercase text-neutral-500 mb-2">{isSep ? "Separador" : "Shell"}</h3>
      <label className="block text-xs text-neutral-400 mb-1">Título</label>
      <input
        value={slide.title || ""}
        disabled={!isSep}
        onChange={(e) => isSep && updateSeparatorTitle(slide.id, e.target.value)}
        className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-sm mb-4 disabled:opacity-60"
      />

      {!isSep && (
        <>
          <h4 className="text-xs uppercase text-neutral-500 mb-2">Charts ({slide.charts.length})</h4>
          {slide.charts.map((c) => {
            const q = parsedDb?.questions.find((q) => q.id === c.question_id)
            const b = parsedDb?.breakdowns.find((b) => b.id === c.breakdown_id)
            return (
              <div key={c.id} className="bg-neutral-800 border border-neutral-700 rounded p-2 mb-2 flex items-center gap-2">
                <span className="bg-blue-700 text-white text-xs px-1.5 rounded">{q?.code || c.question_id}</span>
                <span className="text-xs flex-1 truncate">{b?.label || c.breakdown_id}</span>
                <select
                  value={c.chart_type}
                  onChange={(e) => updateChartType(slide.id, c.id, e.target.value as ChartType)}
                  className="text-xs bg-neutral-900 border border-neutral-700 rounded px-1 py-0.5"
                >
                  {CHART_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                <button onClick={() => removeChart(slide.id, c.id)} className="text-neutral-500 hover:text-red-400">
                  <Trash2 size={12} />
                </button>
              </div>
            )
          })}
          <button
            onClick={() => setChartModalOpen(true)}
            className="w-full text-xs bg-transparent border border-dashed border-neutral-600 rounded py-1.5 flex items-center justify-center gap-1 text-neutral-400 hover:text-neutral-200"
          >
            <Plus size={12} /> Chart
          </button>

          <AddChartModal
            open={chartModalOpen}
            onClose={() => setChartModalOpen(false)}
            onApply={(r) => addCharts(slide.id, r.questionId, r.breakdownIds, r.chartType, r.multiSeries)}
            db={parsedDb}
          />
        </>
      )}
    </aside>
  )
}
```

- [ ] **Step 3: Run, verify pass**

Run: `cd frontend && npm test -- ConfigPanel`
Expected: 4 PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Editor/ConfigPanel.tsx frontend/tests/ConfigPanel.test.tsx
git commit -m "feat(frontend): ConfigPanel with chart list + type override + add chart modal"
```

---

### Task 12: Preview component with debounced render

**Files:**
- Create: `frontend/src/pages/Editor/Preview.tsx`
- Create: `frontend/src/hooks/useDebounce.ts`

- [ ] **Step 1: Implement useDebounce**

Create `frontend/src/hooks/useDebounce.ts`:

```ts
import { useEffect, useState } from "react"

export function useDebounce<T>(value: T, delay: number = 500): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return debounced
}
```

- [ ] **Step 2: Implement Preview**

Create `frontend/src/pages/Editor/Preview.tsx`:

```tsx
import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"
import { useProjectStore } from "../../store/project"
import { useDebounce } from "../../hooks/useDebounce"
import * as api from "../../api/client"

interface Props {
  slideId: string | null
}

export default function Preview({ slideId }: Props) {
  const state = useProjectStore((s) => s.state)
  const [pngUrl, setPngUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const slideIdx = state?.slides.findIndex((s) => s.id === slideId) ?? -1
  const debouncedState = useDebounce(state, 500)

  useEffect(() => {
    if (!debouncedState || slideIdx < 0) return
    let cancelled = false
    setLoading(true); setError(null)
    api.previewSlide(debouncedState, slideIdx)
      .then((r) => {
        if (cancelled) return
        const blob = new Blob([Uint8Array.from(atob(r.png_base64), (c) => c.charCodeAt(0))], { type: "image/png" })
        setPngUrl(URL.createObjectURL(blob))
      })
      .catch((e: { message?: string }) => !cancelled && setError(e.message || "Error renderizando"))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [debouncedState, slideIdx])

  return (
    <section className="bg-neutral-800 flex items-center justify-center relative overflow-hidden">
      {loading && <div className="absolute top-3 right-3 text-neutral-400"><Loader2 size={16} className="animate-spin" /></div>}
      {error && <div className="text-red-400 text-sm">[Render error: {error}] <button onClick={() => setError(null)} className="underline">retry</button></div>}
      {!error && pngUrl && (
        <img src={pngUrl} alt={`Slide ${slideIdx + 1}`} className="max-w-full max-h-full shadow-xl" />
      )}
      {!pngUrl && !loading && !error && (
        <div className="text-neutral-500 text-sm">Seleccioná una slide para previsualizar</div>
      )}
    </section>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Editor/Preview.tsx frontend/src/hooks/useDebounce.ts
git commit -m "feat(frontend): Preview component with debounced PNG render"
```

---

### Task 13: EditorFooter (undo/redo/reset)

**Files:**
- Create: `frontend/src/pages/Editor/EditorFooter.tsx`
- Create: `frontend/src/hooks/useKeyboardShortcuts.ts`
- Create: `frontend/tests/EditorFooter.test.tsx`

- [ ] **Step 1: Failing test**

Create `frontend/tests/EditorFooter.test.tsx`:

```tsx
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import EditorFooter from "../src/pages/Editor/EditorFooter"
import { useProjectStore } from "../src/store/project"

describe("EditorFooter", () => {
  it("renders undo/redo/reset buttons", () => {
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    render(<EditorFooter />)
    expect(screen.getByRole("button", { name: /undo/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /redo/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /reset todo/i })).toBeInTheDocument()
  })

  it("Reset todo clears slides", async () => {
    useProjectStore.setState({ state: null })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    useProjectStore.getState().addSeparator("X")
    render(<EditorFooter />)
    await userEvent.click(screen.getByRole("button", { name: /reset todo/i }))
    expect(useProjectStore.getState().state!.slides).toEqual([])
  })
})
```

- [ ] **Step 2: Implement keyboard shortcuts hook**

Create `frontend/src/hooks/useKeyboardShortcuts.ts`:

```ts
import { useEffect } from "react"

interface ShortcutMap {
  [key: string]: () => void
}

export function useKeyboardShortcuts(map: ShortcutMap) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const key = [
        e.metaKey || e.ctrlKey ? "Cmd+" : "",
        e.shiftKey ? "Shift+" : "",
        e.altKey ? "Alt+" : "",
        e.key.toLowerCase(),
      ].join("")
      const action = map[key]
      if (action) {
        e.preventDefault()
        action()
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [map])
}
```

- [ ] **Step 3: Implement EditorFooter**

Create `frontend/src/pages/Editor/EditorFooter.tsx`:

```tsx
import { Undo2, Redo2, RotateCcw } from "lucide-react"
import { useProjectStore } from "../../store/project"
import { useKeyboardShortcuts } from "../../hooks/useKeyboardShortcuts"

export default function EditorFooter() {
  const undo = useProjectStore.temporal.getState().undo
  const redo = useProjectStore.temporal.getState().redo
  const resetAll = useProjectStore((s) => s.resetAll)
  const updatedAt = useProjectStore((s) => s.state?.updated_at)

  useKeyboardShortcuts({
    "Cmd+z": undo,
    "Cmd+Shift+z": redo,
  })

  return (
    <footer className="h-10 bg-neutral-800 border-t border-neutral-700 flex items-center px-4 gap-2 text-xs">
      <button onClick={() => undo()} aria-label="undo" className="flex items-center gap-1 bg-neutral-700 hover:bg-neutral-600 px-2 py-1 rounded">
        <Undo2 size={12} /> Undo
      </button>
      <button onClick={() => redo()} aria-label="redo" className="flex items-center gap-1 bg-neutral-700 hover:bg-neutral-600 px-2 py-1 rounded">
        <Redo2 size={12} /> Redo
      </button>
      <button
        onClick={() => {
          if (window.confirm("Borrar todas las slides? No se puede deshacer fácilmente.")) resetAll()
        }}
        aria-label="reset todo"
        className="flex items-center gap-1 bg-red-900/40 hover:bg-red-900/60 border border-red-900 text-red-300 px-2 py-1 rounded"
      >
        <RotateCcw size={12} /> Reset todo
      </button>
      <span className="ml-auto text-neutral-500">{updatedAt && `Actualizado: ${new Date(updatedAt).toLocaleTimeString()}`}</span>
    </footer>
  )
}
```

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm test -- EditorFooter`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Editor/EditorFooter.tsx frontend/src/hooks/useKeyboardShortcuts.ts frontend/tests/EditorFooter.test.tsx
git commit -m "feat(frontend): EditorFooter with undo/redo/reset + Cmd+Z shortcuts"
```

---

### Task 14: Export modal

**Files:**
- Create: `frontend/src/pages/Editor/modals/ExportModal.tsx`

- [ ] **Step 1: Implement**

Create `frontend/src/pages/Editor/modals/ExportModal.tsx`:

```tsx
import { useState } from "react"
import Modal from "../../../components/Modal"
import * as api from "../../../api/client"
import { useProjectStore } from "../../../store/project"

interface Props {
  open: boolean
  onClose(): void
}

export default function ExportModal({ open, onClose }: Props) {
  const state = useProjectStore((s) => s.state)
  const [name, setName] = useState(`AurumEncuestas_${new Date().toISOString().replace(/[:.]/g, "").slice(0, 13)}.pptx`)
  const [folder, setFolder] = useState(`${(typeof globalThis !== "undefined" && (globalThis as any).os) ? "" : ""}/Users/${typeof globalThis !== "undefined" ? "" : ""}/Downloads`.replace("//", "/"))
  const [autoOpen, setAutoOpen] = useState(true)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  if (!open || !state) return null

  // default folder fallback if blank
  const effectiveFolder = folder || `~/Downloads`

  const handleExport = async () => {
    setBusy(true); setError(null); setResult(null)
    try {
      const fullPath = `${effectiveFolder.replace(/\/$/, "")}/${name}`
      const r = await api.exportPptx(state, fullPath)
      setResult(r.path)
      if (autoOpen) {
        window.open(`file://${r.path}`)
      }
    } catch (e) {
      setError((e as { message?: string }).message || "Error desconocido")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Exportar PPTX" footer={
      <>
        <button onClick={onClose} className="px-3 py-1.5 text-sm rounded bg-neutral-700">Cancelar</button>
        <button onClick={handleExport} disabled={busy} className="px-3 py-1.5 text-sm rounded bg-accent text-neutral-900 font-semibold disabled:opacity-40">
          {busy ? "Exportando..." : "Exportar"}
        </button>
      </>
    }>
      <label className="block text-xs text-neutral-400 mb-1">Nombre archivo</label>
      <input value={name} onChange={(e) => setName(e.target.value)} className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm" />
      <label className="block text-xs text-neutral-400 mb-1">Carpeta</label>
      <input value={folder} onChange={(e) => setFolder(e.target.value)} placeholder="~/Downloads" className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm" />
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={autoOpen} onChange={(e) => setAutoOpen(e.target.checked)} />
        Abrir al terminar
      </label>
      {result && <div className="mt-3 text-xs text-green-400">✓ Exportado a {result}</div>}
      {error && <div className="mt-3 text-xs text-red-400">{error}</div>}
    </Modal>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Editor/modals/ExportModal.tsx
git commit -m "feat(frontend): ExportModal with name/folder/auto-open"
```

---

### Task 15: Wire everything in EditorPage + Topbar export button

**Files:**
- Modify: `frontend/src/pages/Editor/EditorPage.tsx`
- Modify: `frontend/src/components/Topbar.tsx`

- [ ] **Step 1: Update Topbar with Export button**

Edit `frontend/src/components/Topbar.tsx` — add Export button + ExportModal state:

```tsx
import { useState } from "react"
import { Link, NavLink } from "react-router-dom"
import { useProjectStore } from "../store/project"
import { Pill } from "./Pills"
import ExportModal from "../pages/Editor/modals/ExportModal"

export default function Topbar() {
  const state = useProjectStore((s) => s.state)
  const dbName = state ? state.inputs.db_path.split("/").pop() : null
  const tplName = state ? state.inputs.template_path.split("/").pop() : null
  const font = state?.inputs.font_override
  const [exportOpen, setExportOpen] = useState(false)

  const tabClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-1 rounded text-sm ${isActive ? "bg-neutral-700 text-white" : "text-neutral-300 hover:bg-neutral-800"}`

  return (
    <header className="h-12 bg-neutral-800 border-b border-neutral-700 flex items-center px-4 gap-4">
      <Link to="/" className="font-semibold text-accent">AurumEncuestas</Link>
      <nav className="flex gap-1">
        <NavLink to="/editor" className={tabClass}>Editor</NavLink>
        <NavLink to="/training" className={tabClass}>Entrenamiento</NavLink>
      </nav>
      <div className="flex-1" />
      <div className="flex items-center gap-2">
        {dbName && <Pill label="DB" value={dbName} ok />}
        {tplName && <Pill label="Template" value={tplName} ok />}
        {font && <Pill label="Font" value={font} />}
      </div>
      <button
        onClick={() => setExportOpen(true)}
        disabled={!state}
        className="ml-2 px-3 py-1 text-sm rounded bg-accent text-neutral-900 font-semibold disabled:opacity-40"
      >Exportar PPTX</button>
      <ExportModal open={exportOpen} onClose={() => setExportOpen(false)} />
    </header>
  )
}
```

- [ ] **Step 2: Wire EditorPage**

Overwrite `frontend/src/pages/Editor/EditorPage.tsx`:

```tsx
import { useState } from "react"
import { useSearchParams } from "react-router-dom"
import { useProjectStore } from "../../store/project"
import XlsxVerifyWizard from "../Wizard/XlsxVerifyWizard"
import SlideRail from "./SlideRail"
import Preview from "./Preview"
import ConfigPanel from "./ConfigPanel"
import EditorFooter from "./EditorFooter"

export default function EditorPage() {
  const [params, setParams] = useSearchParams()
  const showWizard = params.get("wizard") === "1"
  const slides = useProjectStore((s) => s.state?.slides ?? [])
  const [selectedId, setSelectedId] = useState<string | null>(slides[0]?.id ?? null)

  // when slides list changes, pick first if none selected
  if (!selectedId && slides.length > 0) {
    setSelectedId(slides[0].id)
  }

  if (showWizard) {
    return <XlsxVerifyWizard onConfirm={() => setParams({})} />
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 grid grid-cols-[130px_1fr_320px] overflow-hidden">
        <SlideRail selectedId={selectedId} onSelect={setSelectedId} />
        <Preview slideId={selectedId} />
        <ConfigPanel slideId={selectedId} />
      </div>
      <EditorFooter />
    </div>
  )
}
```

- [ ] **Step 3: Build + smoke**

Run: `cd frontend && npm run build`
Expected: succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Editor/EditorPage.tsx frontend/src/components/Topbar.tsx
git commit -m "feat(frontend): wire SlideRail + Preview + ConfigPanel + Footer + Export in EditorPage"
```

---

### Task 16: M3 wrap-up — full E2E manual smoke + tag

**Files:** none

- [ ] **Step 1: Full backend tests**

Run: `cd backend && .venv/bin/pytest -v`
Expected: PASS (35+ tests).

- [ ] **Step 2: Full frontend tests**

Run: `cd frontend && npm test`
Expected: PASS (15+ tests).

- [ ] **Step 3: Manual E2E smoke**

Terminal A: `make dev-backend`
Terminal B: `make dev-frontend`

In browser:
1. Open http://localhost:5173
2. Upload BD Aurora xlsx + template.pptx
3. Confirm wizard
4. Add Separador "Recordación"
5. Add Slide (shell)
6. Click Slide in rail
7. Click + Chart → pick P1 + General + Sexo + Pie + Apply
8. Wait 1-3s, preview PNG appears with 2 charts
9. Test undo (Cmd+Z): chart count goes back
10. Test reorder: drag separator below shell, observe renumbering
11. Click Topbar "Exportar PPTX" → name + folder + Export
12. Verify file exists in folder + opens in PowerPoint with editable charts

Expected: full flow works. If preview slow (>5s), accept it; if errors, fix.

- [ ] **Step 4: Tag**

```bash
git tag m3-slide-builder
git log --oneline | head -25
```

---

## M3 Done When

- User can build a deck end-to-end: separadores + shells + charts + reorder + undo + export
- Preview shows real PNG render via libreoffice within 3 seconds
- Exported pptx opens in PowerPoint with editable charts (right-click → "Edit Data")
- All ~50 tests pass
- Git tag `m3-slide-builder`
