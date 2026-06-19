# Chart Catalog Overhaul Fase C Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the python-pptx native table render for `TABLE_WITH_MINIBARS` with an OLE-embedded editable xlsx object. The slide shows a static PNG preview (matching Fase B layout pixel-for-pixel); double-clicking activates Excel.

**Architecture:** Four new private modules under `backend/aurum_encuestas/element_renderers/`: `xlsx_builder` (openpyxl → in-memory xlsx), `ole_png_renderer` (PIL → preview PNG), `ole_embedder` (lxml XML → OLE shape + parts + rels), `ole_table_renderer` (orchestrator). `pattern_renderer._synthesize_table_element` changes `kind` from `"table"` to `"ole_table"`; a new `_KIND_RENDERERS["ole_table"]` entry routes there. `table_renderer.py` stays untouched as legacy (dispatch never hits it).

**Tech Stack:** Python 3.11 + python-pptx 1.0 + openpyxl 3.1 + Pillow 12 + lxml.

## Global Constraints

- Backend Python target `3.11`. Tests: `cd backend && arch -arm64 .venv/bin/pytest -q`.
- All required deps already present in `backend/pyproject.toml`: `openpyxl>=3.1`, `python-pptx>=0.6.23`, `Pillow>=10.0`, `lxml` (transitive). NO new dep additions required.
- `PROG_ID = "Excel.Sheet.12"` for the OLE object.
- Content types: xlsx = `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`; PNG via python-pptx's `CONTENT_TYPE.PNG`.
- Relationship types: `RT.OLE_OBJECT` (`http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject`) and `RT.IMAGE` (`http://schemas.openxmlformats.org/officeDocument/2006/relationships/image`).
- Embedded part naming convention: `/ppt/embeddings/oleObjectN.xlsx` and `/ppt/media/imageN.png` (N auto-incremented to avoid collisions).
- Style colors (verbatim from Fase B): `primary=#7F7F7F`, `secondary=#404040`, `background=#EEC245` (used as text), `#FFFFFF` for option-row text.
- PNG canvas DPI: 96 → 9525 EMU per pixel.
- Branch base: `main` at `ffc02b8`. New branch: `feat/chart-catalog-phase-c`.

---

## File Structure

**New backend modules** (one responsibility each):

| File | Responsibility |
|---|---|
| `backend/aurum_encuestas/element_renderers/xlsx_builder.py` | `build_xlsx_for_table(source_chart, breakdown_groups) → BytesIO` |
| `backend/aurum_encuestas/element_renderers/ole_png_renderer.py` | `render_table_preview_png(source_chart, breakdown_groups, w_emu, h_emu) → bytes` |
| `backend/aurum_encuestas/element_renderers/ole_embedder.py` | `embed_ole_xlsx_with_preview(slide, x, y, w, h, xlsx_bytes, png_bytes) → None` |
| `backend/aurum_encuestas/element_renderers/ole_table_renderer.py` | `render(slide, element, ctx)` orchestrator |

**Modified:**

| File | Change |
|---|---|
| `backend/aurum_encuestas/pattern_renderer.py` | `_KIND_RENDERERS["ole_table"]` entry; `_synthesize_table_element` returns `kind="ole_table"` |
| `backend/tests/test_pattern_renderer.py` | Adapt existing `test_chart_with_table_type_routes_to_table_renderer` to assert oleObj shape; new tests for ole_table dispatch |
| `backend/tests/test_render_e2e.py` | Adapt `test_e2e_table_with_minibars_renders_single_panel_table` to assert OLE shape (not `has_table`) |

**New test files** (one per new module):
- `backend/tests/test_xlsx_builder.py`
- `backend/tests/test_ole_png_renderer.py`
- `backend/tests/test_ole_embedder.py`
- `backend/tests/test_ole_table_renderer.py`

**Untouched:**
- `backend/aurum_encuestas/element_renderers/table_renderer.py` (legacy after Fase C; tests still run direct calls).
- Frontend: zero changes.

---

### Task 1: `xlsx_builder` — openpyxl Workbook from EnrichedChart

**Files:**
- Create: `backend/aurum_encuestas/element_renderers/xlsx_builder.py`
- Test: `backend/tests/test_xlsx_builder.py`

**Interfaces:**
- Consumes: `EnrichedChart`-shaped object (duck-typed via `getattr`: `.question.options`, `.all_breakdowns_data`).
- Produces: `build_xlsx_for_table(source_chart, breakdown_groups: list[str]) -> BytesIO` — returns a seekable in-memory xlsx (position 0). Empty `breakdown_groups` → workbook with only labels in col B, no data panels.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_xlsx_builder.py — new file
from io import BytesIO
from types import SimpleNamespace

from openpyxl import load_workbook
from openpyxl.formatting.rule import DataBarRule


def _make_source(n_options=2, bds_spec=None):
    """bds_spec: list of (bd_id, label, [(cat_label, {opt: {"pct": float, "count": int}})])"""
    q = SimpleNamespace(options=[f"opt{i}" for i in range(n_options)])
    all_bds = {}
    for bd_id, label, cats in (bds_spec or []):
        all_bds[bd_id] = {
            "label": label,
            "categories": {cat: opts for cat, opts in cats},
        }
    return SimpleNamespace(
        question=q,
        all_breakdowns_data=all_bds,
        breakdown_ids=[bd_id for bd_id, _, _ in (bds_spec or [])],
    )


def test_builds_single_panel_layout():
    from aurum_encuestas.element_renderers.xlsx_builder import build_xlsx_for_table

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.92, "count": 230}, "opt1": {"pct": 0.08, "count": 20}}),
            ("40-59", {"opt0": {"pct": 0.91, "count": 228}, "opt1": {"pct": 0.09, "count": 22}}),
        ]),
    ])
    buf = build_xlsx_for_table(src, ["edad"])
    wb = load_workbook(buf)
    ws = wb.active
    # Group header merged across cols C–D in row 2
    assert any(str(mr) == "C2:D2" for mr in ws.merged_cells.ranges)
    # Group header value
    assert ws["C2"].value == "Edad"
    # Cat headers in row 3
    assert ws["C3"].value == "18-39"
    assert ws["D3"].value == "40-59"
    # Counts row 4 — sum of option counts per cat (230+20=250)
    assert ws["C4"].value == 250
    assert ws["D4"].value == 250
    # Option rows 5+
    assert abs(ws["C5"].value - 0.92) < 1e-9
    assert abs(ws["D5"].value - 0.91) < 1e-9
    assert abs(ws["C6"].value - 0.08) < 1e-9
    # Label col B
    assert ws["B4"].value == "Observaciones"
    assert ws["B5"].value == "opt0"
    assert ws["B6"].value == "opt1"


def test_data_bar_rule_color_dark():
    from aurum_encuestas.element_renderers.xlsx_builder import build_xlsx_for_table

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
        ]),
    ])
    buf = build_xlsx_for_table(src, ["edad"])
    wb = load_workbook(buf)
    ws = wb.active
    # At least one DataBarRule applied to the cat column C5:C6 range
    rules_for_range = ws.conditional_formatting._cf_rules
    found_databar_color = None
    for cf_range, rules in rules_for_range.items():
        for rule in rules:
            db = getattr(rule, "dataBar", None)
            if db is not None and db.color is not None:
                found_databar_color = db.color.value
                break
    # openpyxl stores ARGB; "FF404040" or "404040" both acceptable
    assert found_databar_color is not None
    assert "404040" in found_databar_color.upper()


def test_builds_multi_panel_layout_with_spacers():
    from aurum_encuestas.element_renderers.xlsx_builder import build_xlsx_for_table

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
            ("40-59", {"opt0": {"pct": 0.8, "count": 80}, "opt1": {"pct": 0.2, "count": 20}}),
        ]),
        ("sexo", "Sexo", [
            ("F", {"opt0": {"pct": 0.7, "count": 70}, "opt1": {"pct": 0.3, "count": 30}}),
            ("M", {"opt0": {"pct": 0.85, "count": 85}, "opt1": {"pct": 0.15, "count": 15}}),
        ]),
    ])
    buf = build_xlsx_for_table(src, ["edad", "sexo"])
    wb = load_workbook(buf)
    ws = wb.active
    # Edad spans C2:D2; spacer at col E; Sexo spans F2:G2
    assert any(str(mr) == "C2:D2" for mr in ws.merged_cells.ranges)
    assert any(str(mr) == "F2:G2" for mr in ws.merged_cells.ranges)
    assert ws["C2"].value == "Edad"
    assert ws["F2"].value == "Sexo"
    # Spacer col E has no merged header
    assert ws["E2"].value is None


def test_empty_breakdown_groups_returns_valid_xlsx():
    from aurum_encuestas.element_renderers.xlsx_builder import build_xlsx_for_table

    src = _make_source(n_options=2, bds_spec=[])
    buf = build_xlsx_for_table(src, [])
    # No crash; openpyxl can read it
    wb = load_workbook(buf)
    ws = wb.active
    # Labels in col B are present even without data panels
    assert ws["B4"].value == "Observaciones"
    assert ws["B5"].value == "opt0"
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_xlsx_builder.py -v
```

Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `xlsx_builder.py`**

Create `backend/aurum_encuestas/element_renderers/xlsx_builder.py` with the body from spec § Section 2:

```python
"""Build embedded xlsx for OLE TABLE_WITH_MINIBARS render."""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def build_xlsx_for_table(source_chart, breakdown_groups: list[str]) -> BytesIO:
    """Return in-memory xlsx mirroring the TABLE_WITH_MINIBARS layout.

    Layout: row 1 margin; row 2 group_header (merged across each bd's cats);
    row 3 cat sub-headers; row 4 counts; rows 5+ option rows with pct values
    + DataBarRule conditional formatting.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Datos"

    question = getattr(source_chart, "question", None)
    options = list(getattr(question, "options", []) or [])
    all_bds = getattr(source_chart, "all_breakdowns_data", {}) or {}

    bds = [(bd_id, all_bds.get(bd_id, {})) for bd_id in breakdown_groups if bd_id in all_bds]

    HEADER_ROW = 2
    CAT_ROW = 3
    COUNTS_ROW = 4
    FIRST_OPT_ROW = 5
    LABEL_COL = 2          # col B
    FIRST_DATA_COL = 3     # col C

    # Style primitives
    gray_fill = PatternFill("solid", fgColor="7F7F7F")
    dark_fill = PatternFill("solid", fgColor="404040")
    yellow_font_bold_11 = Font(color="EEC245", bold=True, name="Calibri", size=11)
    yellow_font_bold_10 = Font(color="EEC245", bold=True, name="Calibri", size=10)
    white_font_10 = Font(color="FFFFFF", name="Calibri", size=10)
    white_font_bold_11 = Font(color="FFFFFF", bold=True, name="Calibri", size=11)
    center = Alignment(horizontal="center", vertical="center")
    right = Alignment(horizontal="right", vertical="center")
    left = Alignment(horizontal="left", vertical="center")

    # Col B labels (always rendered)
    counts_cell = ws.cell(row=COUNTS_ROW, column=LABEL_COL, value="Observaciones")
    counts_cell.fill = gray_fill
    counts_cell.font = yellow_font_bold_11
    counts_cell.alignment = right

    for i, opt in enumerate(options):
        c = ws.cell(row=FIRST_OPT_ROW + i, column=LABEL_COL, value=opt)
        c.fill = gray_fill
        c.font = white_font_bold_11
        c.alignment = right

    # Per breakdown panel
    cur_col = FIRST_DATA_COL
    for bd_id, bd in bds:
        cats = bd.get("categories", {}) or {}
        n_cats = len(cats)
        if n_cats == 0:
            continue

        start = cur_col
        end = cur_col + n_cats - 1

        # Merged group header
        ws.merge_cells(
            start_row=HEADER_ROW, start_column=start,
            end_row=HEADER_ROW, end_column=end,
        )
        gh = ws.cell(row=HEADER_ROW, column=start, value=bd.get("label") or bd_id)
        gh.fill = dark_fill
        gh.font = yellow_font_bold_11
        gh.alignment = center

        for i, (cat_label, opt_cells) in enumerate(cats.items()):
            col = start + i

            ch = ws.cell(row=CAT_ROW, column=col, value=cat_label)
            ch.fill = gray_fill
            ch.font = yellow_font_bold_10
            ch.alignment = center

            total = sum(int((opt_cells.get(o) or {}).get("count") or 0) for o in options)
            cc = ws.cell(row=COUNTS_ROW, column=col, value=total)
            cc.fill = gray_fill
            cc.font = yellow_font_bold_11
            cc.alignment = center

            for j, opt in enumerate(options):
                row = FIRST_OPT_ROW + j
                pct = float((opt_cells.get(opt) or {}).get("pct") or 0)
                oc = ws.cell(row=row, column=col, value=pct)
                oc.number_format = "0.0%"
                oc.fill = gray_fill
                oc.font = white_font_10
                oc.alignment = left

            col_letter = get_column_letter(col)
            range_str = f"{col_letter}{FIRST_OPT_ROW}:{col_letter}{FIRST_OPT_ROW + len(options) - 1}"
            rule = DataBarRule(
                start_type="num", start_value=0,
                end_type="num", end_value=1,
                color="404040",
                showValue=True,
            )
            ws.conditional_formatting.add(range_str, rule)

        cur_col = end + 2   # leave one spacer column

    # Column + row dimensions
    ws.column_dimensions["A"].width = 2
    ws.column_dimensions[get_column_letter(LABEL_COL)].width = 18
    for c in range(FIRST_DATA_COL, max(cur_col, FIRST_DATA_COL + 1)):
        ws.column_dimensions[get_column_letter(c)].width = 14

    ws.row_dimensions[HEADER_ROW].height = 24
    ws.row_dimensions[CAT_ROW].height = 22
    ws.row_dimensions[COUNTS_ROW].height = 18
    for j in range(len(options)):
        ws.row_dimensions[FIRST_OPT_ROW + j].height = 28

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
```

- [ ] **Step 4: Run tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_xlsx_builder.py -v
```

Expected: PASS for all 4 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/xlsx_builder.py backend/tests/test_xlsx_builder.py
git commit -m "feat(xlsx_builder): in-memory xlsx for OLE TABLE_WITH_MINIBARS

openpyxl Workbook with merged group headers per breakdown, cat
sub-headers, counts row (sum of option counts), option rows with
pct values + DataBarRule conditional formatting (color #404040).
Single-bd and multi-bd layouts share the same row plan; spacer
columns separate panels.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `ole_png_renderer` — PIL preview matching xlsx layout

**Files:**
- Create: `backend/aurum_encuestas/element_renderers/ole_png_renderer.py`
- Test: `backend/tests/test_ole_png_renderer.py`

**Interfaces:**
- Consumes: same `EnrichedChart`-shape as Task 1.
- Produces: `render_table_preview_png(source_chart, breakdown_groups: list[str], w_emu: int, h_emu: int) -> bytes` — PNG bytes sized at `(w_emu // 9525, h_emu // 9525)` with min `(400, 200)`. Empty breakdowns → white PNG.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_ole_png_renderer.py — new
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image


def _make_source(n_options=2, bds_spec=None):
    q = SimpleNamespace(options=[f"opt{i}" for i in range(n_options)])
    all_bds = {}
    for bd_id, label, cats in (bds_spec or []):
        all_bds[bd_id] = {"label": label, "categories": {cat: opts for cat, opts in cats}}
    return SimpleNamespace(
        question=q,
        all_breakdowns_data=all_bds,
        breakdown_ids=[bd_id for bd_id, _, _ in (bds_spec or [])],
    )


def test_returns_png_magic_bytes():
    from aurum_encuestas.element_renderers.ole_png_renderer import render_table_preview_png

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
        ]),
    ])
    png = render_table_preview_png(src, ["edad"], 4_000_000, 2_000_000)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_size_matches_emu_bbox():
    from aurum_encuestas.element_renderers.ole_png_renderer import render_table_preview_png

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
        ]),
    ])
    # 4_000_000 EMU / 9525 ≈ 419 px; 2_000_000 / 9525 ≈ 210 px
    png = render_table_preview_png(src, ["edad"], 4_000_000, 2_000_000)
    img = Image.open(BytesIO(png))
    assert img.size == (4_000_000 // 9525, 2_000_000 // 9525)


def test_empty_breakdown_returns_valid_white_image():
    from aurum_encuestas.element_renderers.ole_png_renderer import render_table_preview_png

    src = _make_source(n_options=0, bds_spec=[])
    png = render_table_preview_png(src, [], 4_000_000, 2_000_000)
    img = Image.open(BytesIO(png))
    # White majority pixel
    assert img.getpixel((0, 0)) == (255, 255, 255)


def test_uses_default_font_when_calibri_missing():
    from aurum_encuestas.element_renderers.ole_png_renderer import render_table_preview_png
    from PIL import ImageFont

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
        ]),
    ])
    with patch.object(ImageFont, "truetype", side_effect=IOError("font missing")):
        png = render_table_preview_png(src, ["edad"], 4_000_000, 2_000_000)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_ole_png_renderer.py -v
```

Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `ole_png_renderer.py`**

```python
"""PIL preview matching xlsx_builder layout for OLE TABLE_WITH_MINIBARS."""
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

EMU_PER_PX = 9525  # 914400 EMU/inch ÷ 96 px/inch

# Colors (palette role hexes, verbatim from Fase B)
GRAY = (127, 127, 127)
DARK = (64, 64, 64)
YELLOW = (238, 194, 69)
WHITE = (255, 255, 255)


def render_table_preview_png(
    source_chart,
    breakdown_groups: list[str],
    w_emu: int,
    h_emu: int,
) -> bytes:
    """Render PIL preview mirroring the xlsx layout. Returns PNG bytes."""
    w_px = max(400, w_emu // EMU_PER_PX)
    h_px = max(200, h_emu // EMU_PER_PX)
    img = Image.new("RGB", (w_px, h_px), WHITE)
    draw = ImageDraw.Draw(img)

    question = getattr(source_chart, "question", None)
    options = list(getattr(question, "options", []) or [])
    all_bds = getattr(source_chart, "all_breakdowns_data", {}) or {}
    bds = [(bd_id, all_bds.get(bd_id, {})) for bd_id in breakdown_groups if bd_id in all_bds]

    if not bds or not options:
        return _save_png(img)

    try:
        font_hdr = ImageFont.truetype("Calibri Bold", 16)
        font_cat = ImageFont.truetype("Calibri Bold", 13)
        font_count = ImageFont.truetype("Calibri Bold", 14)
        font_lbl = ImageFont.truetype("Calibri Bold", 13)
        font_opt = ImageFont.truetype("Calibri", 12)
    except (IOError, OSError):
        default = ImageFont.load_default()
        font_hdr = font_cat = font_count = font_lbl = font_opt = default

    label_col_w = 110
    gap_w = 12

    row_hdr = 28
    row_cat = 26
    row_count = 22
    row_opt = 34
    total_h_needed = row_hdr + row_cat + row_count + row_opt * len(options)
    if total_h_needed < h_px:
        extra = (h_px - total_h_needed) // max(len(options), 1)
        row_opt += extra

    sum_cats = sum(len(bd.get("categories", {}) or {}) for _, bd in bds)
    total_data_w = w_px - label_col_w - gap_w * (len(bds) - 1) - 10
    cell_w = max(60, total_data_w // max(sum_cats, 1))

    y_hdr = 0
    y_cat = y_hdr + row_hdr
    y_count = y_cat + row_cat
    y_opt0 = y_count + row_count

    # Label col B
    draw.rectangle([0, y_count, label_col_w, y_count + row_count], fill=GRAY)
    _centered_text(draw, "Observaciones", font_lbl, YELLOW, 0, y_count, label_col_w, row_count, align="right")
    for j, opt in enumerate(options):
        oy = y_opt0 + j * row_opt
        draw.rectangle([0, oy, label_col_w, oy + row_opt], fill=GRAY)
        _centered_text(draw, opt, font_lbl, WHITE, 0, oy, label_col_w, row_opt, align="right")

    cur_x = label_col_w + 5
    for bd_id, bd in bds:
        cats = bd.get("categories", {}) or {}
        n_cats = len(cats)
        if n_cats == 0:
            continue
        panel_w = cell_w * n_cats

        draw.rectangle([cur_x, y_hdr, cur_x + panel_w, y_hdr + row_hdr], fill=DARK)
        _centered_text(draw, bd.get("label") or bd_id, font_hdr, YELLOW, cur_x, y_hdr, panel_w, row_hdr)

        for i, (cat_label, opt_cells) in enumerate(cats.items()):
            cx = cur_x + i * cell_w

            draw.rectangle([cx, y_cat, cx + cell_w, y_cat + row_cat], fill=GRAY)
            _centered_text(draw, cat_label, font_cat, YELLOW, cx, y_cat, cell_w, row_cat)

            total = sum(int((opt_cells.get(o) or {}).get("count") or 0) for o in options)
            draw.rectangle([cx, y_count, cx + cell_w, y_count + row_count], fill=GRAY)
            _centered_text(draw, str(total) if total else "", font_count, YELLOW,
                           cx, y_count, cell_w, row_count)

            for j, opt in enumerate(options):
                oy = y_opt0 + j * row_opt
                pct = float((opt_cells.get(opt) or {}).get("pct") or 0)
                draw.rectangle([cx, oy, cx + cell_w, oy + row_opt], fill=GRAY)

                bar_h = int(row_opt * 0.6)
                bar_y = oy + (row_opt - bar_h) // 2
                bar_w = int((cell_w - 50) * min(1.0, max(0.0, pct)))
                if bar_w > 0:
                    draw.rectangle([cx + 50, bar_y, cx + 50 + bar_w, bar_y + bar_h], fill=DARK)

                pct_text = f"{pct * 100:.1f}%"
                draw.text((cx + 6, oy + (row_opt - 14) // 2), pct_text, font=font_opt, fill=WHITE)

        cur_x += panel_w + gap_w

    return _save_png(img)


def _centered_text(draw, text, font, color, x, y, w, h, align="center"):
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
    except Exception:
        bbox = (0, 0, len(text) * 7, 12)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    if align == "right":
        tx = x + w - tw - 8
    else:
        tx = x + (w - tw) // 2
    ty = y + (h - th) // 2
    draw.text((tx, ty), text, font=font, fill=color)


def _save_png(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
```

- [ ] **Step 4: Run tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_ole_png_renderer.py -v
```

Expected: PASS for all 4 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/ole_png_renderer.py backend/tests/test_ole_png_renderer.py
git commit -m "feat(ole_png_renderer): PIL preview for OLE TABLE_WITH_MINIBARS

Mirrors xlsx_builder layout to a PIL canvas: merged group headers
(dark fill, yellow text), cat sub-headers + counts (gray fill,
yellow text), option rows (gray fill, white text) with data bars
(dark fill) sized by pct and pct text overlaid. Calibri fonts with
PIL default fallback. Returns PNG bytes sized to the EMU bbox at
96 DPI.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `ole_embedder` — lxml XML manipulation

**Files:**
- Create: `backend/aurum_encuestas/element_renderers/ole_embedder.py`
- Test: `backend/tests/test_ole_embedder.py`

**Interfaces:**
- Consumes: `pptx.slide.Slide` object, EMU coords, xlsx bytes, PNG bytes.
- Produces: `embed_ole_xlsx_with_preview(slide, x: int, y: int, w: int, h: int, xlsx_bytes: bytes, png_bytes: bytes) -> None` — appends a `<p:graphicFrame>` containing `<p:oleObj progId="Excel.Sheet.12">` to slide; registers xlsx and PNG as embedded parts; adds slide relationships.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_ole_embedder.py — new
from io import BytesIO

from pptx import Presentation
from pptx.util import Inches


def _make_slide():
    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)
    return prs, prs.slides.add_slide(prs.slide_layouts[6])


def _png_bytes():
    from PIL import Image
    img = Image.new("RGB", (100, 50), (255, 255, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _xlsx_bytes():
    from openpyxl import Workbook
    wb = Workbook()
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_embedded_xlsx_part_added():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(
        slide, x=914_400, y=914_400, w=4_572_000, h=2_286_000,
        xlsx_bytes=_xlsx_bytes(), png_bytes=_png_bytes(),
    )
    package = slide.part.package
    partnames = [str(p.partname) for p in package.iter_parts()]
    assert any(p.startswith("/ppt/embeddings/oleObject") and p.endswith(".xlsx") for p in partnames)


def test_image_part_added():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(
        slide, x=0, y=0, w=4_572_000, h=2_286_000,
        xlsx_bytes=_xlsx_bytes(), png_bytes=_png_bytes(),
    )
    package = slide.part.package
    partnames = [str(p.partname) for p in package.iter_parts()]
    assert any(p.startswith("/ppt/media/image") and p.endswith(".png") for p in partnames)


def test_slide_rels_contain_ole_object_and_image_types():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(
        slide, x=0, y=0, w=4_572_000, h=2_286_000,
        xlsx_bytes=_xlsx_bytes(), png_bytes=_png_bytes(),
    )
    types = {rel.reltype for rel in slide.part.rels.values()}
    assert any("oleObject" in t for t in types)
    assert any(t.endswith("/image") for t in types)


def test_graphic_frame_appended_with_oleObj_and_blip():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(
        slide, x=0, y=0, w=4_572_000, h=2_286_000,
        xlsx_bytes=_xlsx_bytes(), png_bytes=_png_bytes(),
    )
    spTree = slide.shapes._spTree
    xml = spTree.xml if hasattr(spTree, "xml") else __import__("lxml.etree", fromlist=["tostring"]).tostring(spTree, encoding="unicode")
    assert "graphicFrame" in xml
    assert "oleObj" in xml
    assert 'progId="Excel.Sheet.12"' in xml
    assert "<a:blip" in xml


def test_multiple_embeds_get_distinct_partnames():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(slide, 0, 0, 4_572_000, 2_286_000, _xlsx_bytes(), _png_bytes())
    embed_ole_xlsx_with_preview(slide, 0, 3_000_000, 4_572_000, 2_286_000, _xlsx_bytes(), _png_bytes())
    package = slide.part.package
    xlsx_parts = [str(p.partname) for p in package.iter_parts() if str(p.partname).endswith(".xlsx")]
    png_parts = [str(p.partname) for p in package.iter_parts() if str(p.partname).endswith(".png")]
    assert len(set(xlsx_parts)) == 2
    assert len(set(png_parts)) == 2
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_ole_embedder.py -v
```

Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `ole_embedder.py`**

```python
"""Add OLE-embedded xlsx + PNG preview to a slide via lxml XML manipulation.

python-pptx 1.0 does not expose a public API to add an oleObject shape with
a custom preview image. We build the part + relationships + graphicFrame XML
directly.
"""
from lxml import etree
from pptx.opc.constants import CONTENT_TYPE as CT
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.opc.package import Part
from pptx.opc.packuri import PackURI
from pptx.oxml.ns import qn

CT_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PROG_ID = "Excel.Sheet.12"


def embed_ole_xlsx_with_preview(
    slide,
    x: int, y: int, w: int, h: int,
    xlsx_bytes: bytes, png_bytes: bytes,
) -> None:
    """Append an OLE xlsx graphicFrame with a PNG preview to slide."""
    slide_part = slide.part
    package = slide_part.package

    xlsx_partname = _next_partname(package, "/ppt/embeddings/oleObject{}.xlsx")
    xlsx_part = Part(xlsx_partname, CT_XLSX, xlsx_bytes, package)
    rId_xlsx = slide_part.relate_to(xlsx_part, RT.OLE_OBJECT)

    png_partname = _next_partname(package, "/ppt/media/image{}.png")
    png_part = Part(png_partname, CT.PNG, png_bytes, package)
    rId_img = slide_part.relate_to(png_part, RT.IMAGE)

    spTree = slide.shapes._spTree
    nv_id = _next_shape_id(spTree)

    nsmap_decl = (
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
    )

    xml = f"""<p:graphicFrame {nsmap_decl}>
  <p:nvGraphicFramePr>
    <p:cNvPr id="{nv_id}" name="OLEObject {nv_id}"/>
    <p:cNvGraphicFramePr>
      <a:graphicFrameLocks noChangeAspect="1"/>
    </p:cNvGraphicFramePr>
    <p:nvPr/>
  </p:nvGraphicFramePr>
  <p:xfrm>
    <a:off x="{int(x)}" y="{int(y)}"/>
    <a:ext cx="{int(w)}" cy="{int(h)}"/>
  </p:xfrm>
  <a:graphic>
    <a:graphicData uri="http://schemas.openxmlformats.org/presentationml/2006/ole">
      <p:oleObj spid="_x0000_s{nv_id}" name="" r:id="{rId_xlsx}" imgW="{int(w)}" imgH="{int(h)}" progId="{PROG_ID}">
        <p:embed followColorScheme="full"/>
        <p:pic>
          <p:nvPicPr>
            <p:cNvPr id="0" name=""/>
            <p:cNvPicPr/>
            <p:nvPr/>
          </p:nvPicPr>
          <p:blipFill>
            <a:blip r:embed="{rId_img}"/>
            <a:stretch><a:fillRect/></a:stretch>
          </p:blipFill>
          <p:spPr>
            <a:xfrm>
              <a:off x="{int(x)}" y="{int(y)}"/>
              <a:ext cx="{int(w)}" cy="{int(h)}"/>
            </a:xfrm>
            <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          </p:spPr>
        </p:pic>
      </p:oleObj>
    </a:graphicData>
  </a:graphic>
</p:graphicFrame>"""

    graphic_frame = etree.fromstring(xml)
    spTree.append(graphic_frame)


def _next_partname(package, template: str) -> PackURI:
    """Return next-available PackURI matching the template `/ppt/.../partN.ext`."""
    existing = {str(p.partname) for p in package.iter_parts()}
    n = 1
    while True:
        candidate = template.format(n)
        if candidate not in existing:
            return PackURI(candidate)
        n += 1


def _next_shape_id(spTree) -> int:
    ids = [int(el.get("id", "0") or "0") for el in spTree.iter(qn("p:cNvPr"))]
    return (max(ids) if ids else 1) + 1
```

- [ ] **Step 4: Run tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_ole_embedder.py -v
```

Expected: PASS for all 5 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/ole_embedder.py backend/tests/test_ole_embedder.py
git commit -m "feat(ole_embedder): lxml graphicFrame + oleObj + PNG preview

Direct OOXML manipulation since python-pptx 1.0 lacks a public API
for OLE objects with custom preview images. Adds xlsx as
/ppt/embeddings/oleObjectN.xlsx and PNG as /ppt/media/imageN.png,
slide-rels them with RT.OLE_OBJECT + RT.IMAGE, and appends a
<p:graphicFrame> shape with progId=Excel.Sheet.12 and <a:blip>
referencing the PNG. Partname allocation is collision-safe.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `ole_table_renderer` — orchestrator

**Files:**
- Create: `backend/aurum_encuestas/element_renderers/ole_table_renderer.py`
- Test: `backend/tests/test_ole_table_renderer.py`

**Interfaces:**
- Consumes (from Tasks 1-3): `build_xlsx_for_table`, `render_table_preview_png`, `embed_ole_xlsx_with_preview`.
- Produces: `render(slide, element: dict, ctx) -> None` — resolves bbox via `_resolve_position` from `chart_renderer`; fetches `source_chart` from `ctx.slide_config.charts[chart_ref_index]`; calls the three helpers; logs and returns on bad input.

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_ole_table_renderer.py — new
from types import SimpleNamespace

from pptx import Presentation
from pptx.util import Inches


def _make_slide():
    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)
    return prs, prs.slides.add_slide(prs.slide_layouts[6])


def _ctx_with_source(source_chart):
    from aurum_encuestas.element_renderers.render_context import RenderContext
    slide_config = SimpleNamespace(charts=[source_chart], analyses=[], n_charts=1)
    return RenderContext(
        slide_config=slide_config,
        chart_colors=["#7F7F7F", "#404040", "#EEC245", "#C00000", "#FFC000"],
        resolved_colors={"primary": "#7F7F7F", "secondary": "#404040", "background": "#EEC245"},
        free_area={"x": 487680, "y": 1097280, "cx": 11216640, "cy": 5212080},
        typography={"label_size": 9, "body_size": 10, "title_size": 16, "font_family": "Calibri"},
        style_guide=None, resolved_anchors={},
    )


def _make_source():
    q = SimpleNamespace(options=["Sí", "No"])
    return SimpleNamespace(
        question=q,
        breakdown_ids=["edad"],
        all_breakdowns_data={
            "edad": {"label": "Edad", "categories": {
                "18-39": {"Sí": {"pct": 0.92, "count": 230}, "No": {"pct": 0.08, "count": 20}},
                "40-59": {"Sí": {"pct": 0.91, "count": 228}, "No": {"pct": 0.09, "count": 22}},
            }},
        },
    )


def test_render_creates_xlsx_part_image_part_and_graphicFrame():
    from aurum_encuestas.element_renderers.ole_table_renderer import render
    _prs, slide = _make_slide()
    src = _make_source()
    ctx = _ctx_with_source(src)
    element = {
        "kind": "ole_table",
        "id": "t1",
        "position": {"x_rel": 0.1, "y_rel": 0.1, "w_rel": 0.8, "h_rel": 0.6},
        "data_source": {"chart_ref_index": 0, "breakdown_groups": ["edad"]},
    }
    render(slide, element, ctx)
    package = slide.part.package
    partnames = [str(p.partname) for p in package.iter_parts()]
    assert any(p.startswith("/ppt/embeddings/oleObject") and p.endswith(".xlsx") for p in partnames)
    assert any(p.startswith("/ppt/media/image") and p.endswith(".png") for p in partnames)
    spTree = slide.shapes._spTree
    from lxml.etree import tostring
    xml = tostring(spTree, encoding="unicode")
    assert "graphicFrame" in xml
    assert 'progId="Excel.Sheet.12"' in xml


def test_render_skips_when_chart_ref_index_out_of_range(caplog):
    import logging
    from aurum_encuestas.element_renderers.ole_table_renderer import render
    _prs, slide = _make_slide()
    src = _make_source()
    ctx = _ctx_with_source(src)
    element = {
        "kind": "ole_table",
        "id": "t1",
        "position": {"x_rel": 0.1, "y_rel": 0.1, "w_rel": 0.8, "h_rel": 0.6},
        "data_source": {"chart_ref_index": 99, "breakdown_groups": ["edad"]},
    }
    with caplog.at_level(logging.WARNING):
        render(slide, element, ctx)
    # Returned silently — no shapes added
    assert not any("oleObj" in (_str_xml(slide)) for _ in [None])


def _str_xml(slide):
    from lxml.etree import tostring
    return tostring(slide.shapes._spTree, encoding="unicode")
```

- [ ] **Step 2: Run failing test**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_ole_table_renderer.py -v
```

Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `ole_table_renderer.py`**

```python
"""Orchestrator for kind=ole_table — builds xlsx, PNG, and OLE shape."""
from __future__ import annotations

import logging

from .ole_embedder import embed_ole_xlsx_with_preview
from .ole_png_renderer import render_table_preview_png
from .xlsx_builder import build_xlsx_for_table

log = logging.getLogger(__name__)


def render(slide, element: dict, ctx) -> None:
    """Dispatch entrypoint for kind=ole_table elements.

    Builds an in-memory xlsx mirroring the table layout, renders a PIL preview
    PNG at the same bbox, and embeds both as an OLE graphicFrame on the slide.
    """
    from .chart_renderer import _resolve_position
    x, y, cx, cy = _resolve_position(element.get("position", {}), ctx)

    data_source = element.get("data_source", {}) or {}
    chart_ref_index = data_source.get("chart_ref_index", 0)
    breakdown_groups = list(data_source.get("breakdown_groups", []) or [])

    charts_list = getattr(ctx.slide_config, "charts", []) or []
    if not (0 <= chart_ref_index < len(charts_list)):
        log.warning("ole_table_renderer: chart_ref_index %d out of range — skipping", chart_ref_index)
        return

    source_chart = charts_list[chart_ref_index]

    try:
        xlsx_buf = build_xlsx_for_table(source_chart, breakdown_groups)
        xlsx_bytes = xlsx_buf.getvalue()
    except Exception as exc:
        log.error("ole_table_renderer: xlsx build failed: %s", exc)
        return

    try:
        png_bytes = render_table_preview_png(source_chart, breakdown_groups, cx, cy)
    except Exception as exc:
        log.error("ole_table_renderer: PNG render failed: %s", exc)
        return

    try:
        embed_ole_xlsx_with_preview(slide, x, y, cx, cy, xlsx_bytes, png_bytes)
    except Exception as exc:
        log.error("ole_table_renderer: OLE embed failed: %s", exc)
        return
```

- [ ] **Step 4: Run tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_ole_table_renderer.py -v
```

Expected: PASS for both tests.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/ole_table_renderer.py backend/tests/test_ole_table_renderer.py
git commit -m "feat(ole_table_renderer): orchestrator for kind=ole_table

Resolves position, fetches source_chart, then runs xlsx_builder +
ole_png_renderer + ole_embedder in sequence. Each step is guarded;
any failure logs and returns without raising. Replaces the
table_renderer dispatch for TABLE_WITH_MINIBARS (re-routed in
Task 5).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `pattern_renderer` dispatch + e2e adaptation

**Files:**
- Modify: `backend/aurum_encuestas/pattern_renderer.py`
- Modify: `backend/tests/test_pattern_renderer.py`
- Modify: `backend/tests/test_render_e2e.py`

**Interfaces:**
- Consumes (from Task 4): `ole_table_renderer.render`.
- Produces: `_KIND_RENDERERS["ole_table"] = "aurum_encuestas.element_renderers.ole_table_renderer"`. `_synthesize_table_element` returns `{"kind": "ole_table", "id": ..., "position": ..., "data_source": {"chart_ref_index": ..., "breakdown_groups": [...]}}` (drops `structure`).

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_pattern_renderer.py`:

```python
def test_synthesize_table_element_kind_is_ole_table():
    """Fase C: _synthesize_table_element returns kind=ole_table, not table."""
    from aurum_encuestas.pattern_renderer import _synthesize_table_element
    from types import SimpleNamespace

    chart_el = {
        "kind": "chart", "id": "main",
        "position": {"x_rel": 0.1, "y_rel": 0.1, "w_rel": 0.8, "h_rel": 0.8},
        "data_source": {"chart_ref_index": 0, "value_field": "pct"},
    }
    src = SimpleNamespace(breakdown_ids=["edad", "sexo"], chart_type="TABLE_WITH_MINIBARS")
    el = _synthesize_table_element(chart_el, src)
    assert el["kind"] == "ole_table"
    assert "structure" not in el
    assert el["data_source"]["breakdown_groups"] == ["edad", "sexo"]


def test_kind_ole_table_routes_to_ole_table_renderer():
    """_KIND_RENDERERS maps ole_table → ole_table_renderer module path."""
    from aurum_encuestas.pattern_renderer import _KIND_RENDERERS
    assert _KIND_RENDERERS["ole_table"] == "aurum_encuestas.element_renderers.ole_table_renderer"
```

Also adapt the existing `test_chart_with_table_type_routes_to_table_renderer` (or similar) — its current assertion is `any(sh.has_table for sh in slide.shapes)`. Change to assert an oleObj is present:

```python
def test_chart_with_table_type_routes_to_ole_table_renderer():
    """Fase C: TABLE_WITH_MINIBARS chart_type with real breakdown_ids
    routes through ole_table_renderer and produces a graphicFrame with
    oleObj progId=Excel.Sheet.12."""
    from pptx import Presentation
    from types import SimpleNamespace
    from aurum_encuestas.pattern_renderer import render_pattern
    from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE
    from aurum_encuestas.element_renderers.render_context import RenderContext

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    q = SimpleNamespace(options=["Sí", "No"])
    src = SimpleNamespace(
        question=q, breakdown_ids=["edad"], chart_type="TABLE_WITH_MINIBARS", colors=[],
        title=None, show_legend=False, grid_cols=None, cat_titles=None,
        data={},
        all_breakdowns_data={
            "edad": {"label": "Edad", "categories": {
                "18-39": {"Sí": {"pct": 0.9, "count": 90}, "No": {"pct": 0.1, "count": 10}},
                "40-59": {"Sí": {"pct": 0.85, "count": 85}, "No": {"pct": 0.15, "count": 15}},
            }},
        },
    )
    slide_config = SimpleNamespace(charts=[src], analyses=[], n_charts=1)
    ctx = RenderContext(
        slide_config=slide_config,
        chart_colors=["#7F7F7F","#404040","#EEC245","#C00000","#FFC000"],
        resolved_colors={"primary":"#7F7F7F","secondary":"#404040","background":"#EEC245"},
        free_area={"x": 487680, "y": 1097280, "cx": 11216640, "cy": 5212080},
        typography={"label_size":9,"body_size":10,"title_size":16,"font_family":"Calibri"},
        style_guide=BUILTIN_STYLE_GUIDE, resolved_anchors={},
    )
    pattern = next(p for p in BUILTIN_STYLE_GUIDE.patterns if p.id == "binary_general")
    render_pattern(pattern, slide, ctx, BUILTIN_STYLE_GUIDE, list(BUILTIN_STYLE_GUIDE.patterns))
    from lxml.etree import tostring
    xml = tostring(slide.shapes._spTree, encoding="unicode")
    assert 'progId="Excel.Sheet.12"' in xml
    # Fase C: NO python-pptx table is rendered
    assert not any(sh.has_table for sh in slide.shapes)
```

Delete the old `test_chart_with_table_type_routes_to_table_renderer` if it exists with the has_table assertion.

Adapt `backend/tests/test_render_e2e.py::test_e2e_table_with_minibars_renders_single_panel_table`:

Replace its body's assertions with:
```python
    prs = Presentation(str(out))
    found = False
    for s in prs.slides:
        from lxml.etree import tostring
        xml = tostring(s.shapes._spTree, encoding="unicode")
        if 'progId="Excel.Sheet.12"' in xml:
            found = True
            break
    assert found, "expected at least one OLE Excel object on a slide"
    # Fase C: NO python-pptx table
    for s in prs.slides:
        assert not any(sh.has_table for sh in s.shapes)
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_pattern_renderer.py tests/test_render_e2e.py -v
```

Expected: the two new tests + the adapted ones fail (kind still `"table"`, has_table still True).

- [ ] **Step 3: Update `pattern_renderer.py`**

Find `_KIND_RENDERERS` and add an entry:

```python
_KIND_RENDERERS: dict[str, str] = {
    "chart": "aurum_encuestas.element_renderers.chart_renderer",
    "text":  "aurum_encuestas.element_renderers.text_renderer",
    "shape": "aurum_encuestas.element_renderers.shape_renderer",
    "image": "aurum_encuestas.element_renderers.image_renderer",
    "table": "aurum_encuestas.element_renderers.table_renderer",
    "ole_table": "aurum_encuestas.element_renderers.ole_table_renderer",
}
```

Find `_synthesize_table_element` and rewrite:

```python
def _synthesize_table_element(chart_el: dict, source_chart) -> dict:
    """Convert a chart element to an OLE-embedded segmented table element.

    Fase C: the dispatch peek that fires this helper now routes
    TABLE_WITH_MINIBARS to ole_table_renderer instead of the legacy
    table_renderer.
    """
    bds = [
        b for b in (getattr(source_chart, "breakdown_ids", []) or [])
        if b and b.lower() != "general"
    ]
    return {
        "kind": "ole_table",
        "id": chart_el.get("id"),
        "position": chart_el.get("position", {}),
        "data_source": {
            "chart_ref_index": chart_el.get("data_source", {}).get("chart_ref_index", 0),
            "breakdown_groups": bds,
        },
    }
```

- [ ] **Step 4: Run tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_pattern_renderer.py tests/test_render_e2e.py -v
```

Expected: PASS.

- [ ] **Step 5: Run full backend suite**

```bash
cd backend && arch -arm64 .venv/bin/pytest -q 2>&1 | tail -3
```

Expected: 0 fail. Existing `test_table_renderer.py` tests still pass (they invoke `_render_segmented_breakdowns` directly, not via dispatch).

- [ ] **Step 6: Commit**

```bash
git add backend/aurum_encuestas/pattern_renderer.py backend/tests/test_pattern_renderer.py backend/tests/test_render_e2e.py
git commit -m "feat(pattern_renderer): route TABLE_WITH_MINIBARS to ole_table_renderer

_KIND_RENDERERS gains an 'ole_table' entry pointing at the new
orchestrator. _synthesize_table_element returns kind='ole_table'
(was 'table') and drops the 'structure' key. The legacy
table_renderer module is now unused for the dispatch path; its
direct-call tests still pass.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Spec coverage:**
  - Spec § Architecture overview → Tasks 1-5 ✅
  - Spec § Component contracts → Tasks 1 (xlsx_builder), 2 (ole_png_renderer), 3 (ole_embedder), 4 (orchestrator), 5 (dispatch) ✅
  - Spec § Dependencies → already present; pyproject.toml unchanged ✅
  - Spec § Testing strategy → 4 new test files + 2 adapted ✅
  - Spec § Open risks (Pillow font, OLE cross-platform, stale preview, file size, partname collision, DataBar width, OLE API absence in python-pptx, OLE introspection) → addressed via PIL truetype-fallback in T2, lxml manipulation in T3, `_next_partname` in T3, XML-string assertions in T3/T5 ✅
- **Placeholder scan:** No "TBD", "implement later". Tests show actual assertions. The two existing tests being adapted in T5 are named explicitly and the new replacement test code is fully provided.
- **Type consistency:** `build_xlsx_for_table(source_chart, breakdown_groups) -> BytesIO` consistent across T1, T4. `render_table_preview_png(source_chart, breakdown_groups, w_emu, h_emu) -> bytes` consistent across T2, T4. `embed_ole_xlsx_with_preview(slide, x, y, w, h, xlsx_bytes, png_bytes) -> None` consistent across T3, T4. `_synthesize_table_element` signature unchanged from Fase A.
- **Open caveats:**
  - T3 uses `slide_part.relate_to(part, RT.OLE_OBJECT)`. python-pptx 1.0 exposes this. If the version diverges, fall back to `slide_part.rels.get_or_add(...)`.
  - T3 `Part(partname, content_type, blob, package)` constructor signature is stable in python-pptx 1.x. Confirmed during writing.
  - T3 `package.iter_parts()` is the public method. If naming differs in newer versions, use `package._parts` (private).
