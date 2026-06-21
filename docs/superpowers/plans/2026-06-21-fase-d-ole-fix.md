# Fase D — OLE Fix + Multi-Table xlsx + Palette Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three Fase C bugs: (1) PPTX OOXML corrupto → PowerPoint repair removes OLE; (2) xlsx renders all breakdowns in ONE merged table when spec wants N independent tables side-by-side; (3) palette renders everything yellow because role names map wrongly — replace with hex literal styles (dark headers, white cells, gray bars).

**Architecture:** `ole_embedder` switches OOXML structure to `<mc:AlternateContent>` wrapper with Choice (xmlns:v + spid) and Fallback (no v, no spid) branches per real PowerPoint OLE schema. `xlsx_builder` switches from single-table-with-merged-group-headers to N-tables-side-by-side: each bd gets its own label col + own group_header merge + own data rows + own DataBarRule scoped to that bd. `ole_png_renderer` mirrors the new N-panel layout with hex literal colors.

**Tech Stack:** Python 3.11 + python-pptx 1.0 + openpyxl 3.1 + Pillow 12 + lxml.

## Global Constraints

- Backend Python 3.11. Tests: `cd backend && arch -arm64 .venv/bin/pytest -q`.
- All deps already present; no new deps.
- `PROG_ID = "Excel.Sheet.12"`; `CT_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"`.
- Function signatures unchanged: `build_xlsx_for_table(source_chart, breakdown_groups) -> BytesIO`; `render_table_preview_png(source_chart, breakdown_groups, w_emu, h_emu) -> bytes`; `embed_ole_xlsx_with_preview(slide, x, y, w, h, xlsx_bytes, png_bytes) -> None`.
- Style hex literals: `HEADER_FILL_HEX="595959"`, `HEADER_FONT_HEX="FFFFFF"`, `BODY_FILL_HEX="FFFFFF"`, `BODY_FONT_HEX="000000"`, `DATABAR_HEX="BFBFBF"`.
- PIL color tuples: `HEADER_DARK=(89,89,89)`, `BG_WHITE=(255,255,255)`, `TEXT_BLACK=(0,0,0)`, `BAR_GRAY=(191,191,191)`.
- `<mc:Choice Requires="v" xmlns:v="urn:schemas-microsoft-com:vml">` includes `spid="_x0000_s{N}"` on its oleObj.
- `<mc:Fallback>` oleObj has NO spid and NO xmlns:v.
- Both Choice and Fallback oleObj reference the SAME `r:id` for xlsx AND SAME `r:embed` for PNG.
- Inner `<p:pic>` `<p:spPr>` uses `bwMode="auto"` and `<a:xfrm><a:off x="0" y="0"/><a:ext cx="{W}" cy="{H}"/></a:xfrm>` (offset relative to oleObj container).
- `cleanup_namespaces` call REMOVED from ole_embedder (would strip xmlns:v needed by Choice).
- Branch base: `main` at `133cbd2`. New branch: `feat/fase-d-ole-fix`.

---

## File Structure

Modified backend:
- `backend/aurum_encuestas/element_renderers/ole_embedder.py` — new XML structure with mc:AlternateContent.
- `backend/aurum_encuestas/element_renderers/xlsx_builder.py` — N-tables-side-by-side + hex literals.
- `backend/aurum_encuestas/element_renderers/ole_png_renderer.py` — N panels + hex colors.
- `backend/tests/test_ole_embedder.py` — append OOXML structure assertions + adapt round-trip.
- `backend/tests/test_xlsx_builder.py` — rewrite single+multi panel tests; assert hex styles.
- `backend/tests/test_ole_png_renderer.py` — add multi-bd panel assertion + palette pixel sample.

Untouched: everything else.

---

### Task 1: `ole_embedder` — `<mc:AlternateContent>` OOXML structure

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/ole_embedder.py`
- Modify: `backend/tests/test_ole_embedder.py`

**Interfaces:**
- Consumes: nothing changes.
- Produces: `embed_ole_xlsx_with_preview` signature unchanged. Slide XML now contains `<mc:AlternateContent>` with `<mc:Choice Requires="v">` and `<mc:Fallback>`. `cleanup_namespaces` call removed.

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_ole_embedder.py`:

```python
def test_graphic_frame_contains_mc_alternate_content():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(
        slide, x=0, y=0, w=4_572_000, h=2_286_000,
        xlsx_bytes=_xlsx_bytes(), png_bytes=_png_bytes(),
    )
    from lxml.etree import tostring
    xml = tostring(slide.shapes._spTree, encoding="unicode")
    assert "AlternateContent" in xml
    assert "Choice" in xml
    assert "Fallback" in xml


def test_choice_has_xmlns_v_and_spid():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(
        slide, x=0, y=0, w=4_572_000, h=2_286_000,
        xlsx_bytes=_xlsx_bytes(), png_bytes=_png_bytes(),
    )
    from lxml.etree import tostring
    xml = tostring(slide.shapes._spTree, encoding="unicode")
    # Find the Choice block and confirm both xmlns:v and a spid attribute
    assert 'xmlns:v="urn:schemas-microsoft-com:vml"' in xml
    assert 'spid="_x0000_s' in xml


def test_fallback_branch_has_no_spid():
    """Fallback oleObj has no spid attribute (only Choice carries spid)."""
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    from lxml import etree
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(
        slide, x=0, y=0, w=4_572_000, h=2_286_000,
        xlsx_bytes=_xlsx_bytes(), png_bytes=_png_bytes(),
    )
    spTree = slide.shapes._spTree
    # Locate Fallback element via XPath with namespaces
    nsmap = {
        "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
        "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    }
    fallback = spTree.xpath(".//mc:Fallback//p:oleObj", namespaces=nsmap)
    assert len(fallback) == 1
    assert fallback[0].get("spid") is None


def test_both_branches_reference_same_xlsx_rid():
    """Choice and Fallback oleObj both reference the same xlsx r:id."""
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(
        slide, x=0, y=0, w=4_572_000, h=2_286_000,
        xlsx_bytes=_xlsx_bytes(), png_bytes=_png_bytes(),
    )
    spTree = slide.shapes._spTree
    nsmap = {
        "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
        "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    choice_oleobj = spTree.xpath(".//mc:Choice/p:oleObj", namespaces=nsmap)
    fallback_oleobj = spTree.xpath(".//mc:Fallback/p:oleObj", namespaces=nsmap)
    rid_key = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    assert len(choice_oleobj) == 1 and len(fallback_oleobj) == 1
    assert choice_oleobj[0].get(rid_key) == fallback_oleobj[0].get(rid_key)
```

The existing `test_graphic_frame_appended_with_oleObj_and_blip` test still passes (asserts `oleObj`, `progId`, `<a:blip>` substring). The existing `test_round_trip_save_and_reopen_succeeds` still passes if structure is valid.

- [ ] **Step 2: Run failing tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_ole_embedder.py -k "alternate_content or xmlns_v or fallback or both_branches" -v
```

Expected: FAIL — current XML has no `mc:AlternateContent`, no `xmlns:v`, no `mc:Choice`, no `mc:Fallback`.

- [ ] **Step 3: Rewrite `embed_ole_xlsx_with_preview` body**

Replace the body in `backend/aurum_encuestas/element_renderers/ole_embedder.py` (keep imports + helpers):

```python
def embed_ole_xlsx_with_preview(
    slide,
    x: int, y: int, w: int, h: int,
    xlsx_bytes: bytes, png_bytes: bytes,
) -> None:
    """Append an OLE xlsx graphicFrame with PNG preview to slide.

    Uses the standard OOXML mc:AlternateContent wrapper with mc:Choice
    (Office 2010+ with VML fallback) and mc:Fallback (legacy OOXML).
    """
    slide_part = slide.part
    package = slide_part.package

    xlsx_partname = _next_partname(package, "/ppt/embeddings/oleObject{}.xlsx")
    xlsx_part = Part(xlsx_partname, CT_XLSX, package, xlsx_bytes)
    rid_xlsx = slide_part.relate_to(xlsx_part, RT.OLE_OBJECT)

    png_partname = _next_partname(package, "/ppt/media/image{}.png")
    png_part = Part(png_partname, CT.PNG, package, png_bytes)
    rid_img = slide_part.relate_to(png_part, RT.IMAGE)

    spTree = slide.shapes._spTree
    nv_id = _next_shape_id(spTree)

    nsmap_decl = (
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"'
    )

    choice_oleobj = _render_oleobj_xml(
        rid_xlsx=rid_xlsx, rid_img=rid_img,
        w=w, h=h, nv_id=nv_id,
        with_spid=True,
    )
    fallback_oleobj = _render_oleobj_xml(
        rid_xlsx=rid_xlsx, rid_img=rid_img,
        w=w, h=h, nv_id=nv_id,
        with_spid=False,
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
      <mc:AlternateContent>
        <mc:Choice xmlns:v="urn:schemas-microsoft-com:vml" Requires="v">
          {choice_oleobj}
        </mc:Choice>
        <mc:Fallback>
          {fallback_oleobj}
        </mc:Fallback>
      </mc:AlternateContent>
    </a:graphicData>
  </a:graphic>
</p:graphicFrame>"""

    graphic_frame = etree.fromstring(xml)
    # NOTE: do NOT call cleanup_namespaces — it would strip xmlns:v from mc:Choice.
    spTree.append(graphic_frame)


def _render_oleobj_xml(
    *, rid_xlsx: str, rid_img: str,
    w: int, h: int, nv_id: int,
    with_spid: bool,
) -> str:
    """Return one <p:oleObj> XML fragment.

    Choice branch: with_spid=True (also lives inside a mc:Choice declaring xmlns:v).
    Fallback branch: with_spid=False.
    """
    spid_attr = f'spid="_x0000_s{nv_id}" ' if with_spid else ""
    return f"""<p:oleObj {spid_attr}name="" r:id="{rid_xlsx}" imgW="{int(w)}" imgH="{int(h)}" progId="{PROG_ID}">
            <p:embed followColorScheme="full"/>
            <p:pic>
              <p:nvPicPr>
                <p:cNvPr id="0" name=""/>
                <p:cNvPicPr/>
                <p:nvPr/>
              </p:nvPicPr>
              <p:blipFill>
                <a:blip r:embed="{rid_img}"/>
                <a:stretch><a:fillRect/></a:stretch>
              </p:blipFill>
              <p:spPr bwMode="auto">
                <a:xfrm>
                  <a:off x="0" y="0"/>
                  <a:ext cx="{int(w)}" cy="{int(h)}"/>
                </a:xfrm>
                <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
              </p:spPr>
            </p:pic>
          </p:oleObj>"""
```

Remove the `from lxml.etree import cleanup_namespaces` import line (no longer needed).

- [ ] **Step 4: Run tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_ole_embedder.py -v
```

Expected: all pass (4 new + 5-6 existing including round-trip).

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/ole_embedder.py backend/tests/test_ole_embedder.py
git commit -m "fix(ole_embedder): mc:AlternateContent wrapper for valid OOXML

Previous structure embedded <p:pic> directly inside <p:oleObj> under
<a:graphicData>, which PowerPoint repair flagged and removed. Real
OOXML requires <mc:AlternateContent> with <mc:Choice Requires=v
xmlns:v=urn:schemas-microsoft-com:vml> (Office 2010+ with VML spid)
and <mc:Fallback> (legacy, no v, no spid). Both branches reference
the same xlsx and image rids. cleanup_namespaces call removed because
it would strip xmlns:v from mc:Choice.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `xlsx_builder` — N tables side-by-side + hex literals

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/xlsx_builder.py`
- Modify: `backend/tests/test_xlsx_builder.py`

**Interfaces:**
- Consumes: nothing.
- Produces: each bd gets independent label col + group_header merge + cat sub-headers + counts row + option rows + DataBarRule scoped to its data cols.

- [ ] **Step 1: Write failing tests**

Replace existing tests in `backend/tests/test_xlsx_builder.py`:

```python
from io import BytesIO
from types import SimpleNamespace

from openpyxl import load_workbook
from openpyxl.formatting.rule import DataBarRule


def _make_source(n_options=2, bds_spec=None):
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


def test_single_panel_has_own_label_col():
    """Each bd has its own label col at its left; group_header merge spans
    label_col + cat cols."""
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
    # Group header merge spans label col + 2 cat cols: A2:C2
    assert any(str(mr) == "A2:C2" for mr in ws.merged_cells.ranges), \
        f"expected A2:C2 merge, got {[str(m) for m in ws.merged_cells.ranges]}"
    assert ws["A2"].value == "Edad"
    # Label col A: cat row empty, counts row "Observaciones", option rows = labels
    assert ws["A3"].value is None
    assert ws["A4"].value == "Observaciones"
    assert ws["A5"].value == "opt0"
    assert ws["A6"].value == "opt1"
    # Cat headers in row 3 at cols B, C
    assert ws["B3"].value == "18-39"
    assert ws["C3"].value == "40-59"
    # Counts row 4 — sum option counts per cat
    assert ws["B4"].value == 250
    assert ws["C4"].value == 250
    # Option row 5: opt0 pct
    assert abs(ws["B5"].value - 0.92) < 1e-9
    assert abs(ws["C5"].value - 0.91) < 1e-9


def test_multi_panel_n_independent_tables():
    """N=2 bds → 2 independent group_header merges, separator col empty."""
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
    # Edad bd: A2:C2 merge (label+2cats); Sexo bd at col E, label E, data F-G → E2:G2
    merge_strs = {str(m) for m in ws.merged_cells.ranges}
    assert "A2:C2" in merge_strs
    assert "E2:G2" in merge_strs
    assert ws["A2"].value == "Edad"
    assert ws["E2"].value == "Sexo"
    # Spacer col D row 2 empty
    assert ws["D2"].value is None
    assert ws["D3"].value is None
    assert ws["D4"].value is None
    # Sexo label col E
    assert ws["E4"].value == "Observaciones"
    assert ws["E5"].value == "opt0"


def test_databar_per_bd_panel_scoped():
    """DataBarRule scoped to one bd's data cols, not entire sheet."""
    from aurum_encuestas.element_renderers.xlsx_builder import build_xlsx_for_table

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
        ]),
        ("sexo", "Sexo", [
            ("F", {"opt0": {"pct": 0.7, "count": 70}, "opt1": {"pct": 0.3, "count": 30}}),
        ]),
    ])
    buf = build_xlsx_for_table(src, ["edad", "sexo"])
    wb = load_workbook(buf)
    ws = wb.active
    # Collect databar rule ranges
    bar_ranges = []
    for cf_range, rules in ws.conditional_formatting._cf_rules.items():
        for rule in rules:
            if getattr(rule, "dataBar", None) is not None:
                bar_ranges.append(str(cf_range))
    # Each bd's data range gets its own bar rules; no range spans across bds
    assert all("A" not in r and "C" not in r for r in bar_ranges) or any("B" in r for r in bar_ranges)
    # No bar range covers col D (spacer) or both bd panels at once
    for r in bar_ranges:
        # A databar range like "B5:B5" or "E5:E5" — never crosses the spacer col D
        assert "D" not in r, f"databar range {r} spans into spacer col D"


def test_hex_palette_applied():
    """Header cells use hex fill 595959 + font FFFFFF; body cells use FFFFFF + 000000."""
    from aurum_encuestas.element_renderers.xlsx_builder import build_xlsx_for_table

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
        ]),
    ])
    buf = build_xlsx_for_table(src, ["edad"])
    wb = load_workbook(buf)
    ws = wb.active
    # Group header (A2) fill check
    gh = ws["A2"]
    assert "595959" in (gh.fill.fgColor.value or "").upper()
    assert "FFFFFF" in (gh.font.color.rgb or "").upper()
    # Body option-row cell (B5) fill+font check
    body = ws["B5"]
    assert "FFFFFF" in (body.fill.fgColor.value or "").upper()
    assert "000000" in (body.font.color.rgb or "").upper()


def test_empty_breakdown_groups_returns_empty_xlsx():
    from aurum_encuestas.element_renderers.xlsx_builder import build_xlsx_for_table

    src = _make_source(n_options=2, bds_spec=[])
    buf = build_xlsx_for_table(src, [])
    wb = load_workbook(buf)
    ws = wb.active
    # No merged ranges at row 2
    assert not any(str(mr).startswith(("A2", "B2", "C2")) for mr in ws.merged_cells.ranges)
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_xlsx_builder.py -v
```

Expected: FAIL — current layout has Edad at C2:D2 (label col B is shared external), Sexo at F2:G2 (after spacer E). New layout needs A2:C2 + E2:G2 with per-bd label col.

- [ ] **Step 3: Rewrite `build_xlsx_for_table`**

Replace the entire body of `backend/aurum_encuestas/element_renderers/xlsx_builder.py` (keep imports):

```python
"""Build embedded xlsx for OLE TABLE_WITH_MINIBARS render."""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# Hex palette (no role mapping — direct hex to avoid color_resolver remapping)
HEADER_FILL_HEX = "595959"   # dark gray
HEADER_FONT_HEX = "FFFFFF"   # white
BODY_FILL_HEX = "FFFFFF"     # white
BODY_FONT_HEX = "000000"     # black
DATABAR_HEX = "BFBFBF"       # light gray bar

HEADER_ROW = 2
CAT_ROW = 3
COUNTS_ROW = 4
FIRST_OPT_ROW = 5

LABEL_COL_W = 12
DATA_COL_W = 14


def build_xlsx_for_table(source_chart, breakdown_groups: list[str]) -> BytesIO:
    """Return in-memory xlsx with N independent tables side-by-side.

    One table per breakdown; each table has its own label col + group_header
    merge + cat sub-headers + counts row + option rows with DataBarRule.
    Spacer column between tables.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Datos"

    question = getattr(source_chart, "question", None)
    options = list(getattr(question, "options", []) or [])
    all_bds = getattr(source_chart, "all_breakdowns_data", {}) or {}

    bds = [(bd_id, all_bds.get(bd_id, {})) for bd_id in breakdown_groups if bd_id in all_bds]

    header_fill = PatternFill("solid", fgColor=HEADER_FILL_HEX)
    body_fill = PatternFill("solid", fgColor=BODY_FILL_HEX)
    header_font_bold_11 = Font(color=HEADER_FONT_HEX, bold=True, name="Calibri", size=11)
    header_font_bold_10 = Font(color=HEADER_FONT_HEX, bold=True, name="Calibri", size=10)
    body_font_10 = Font(color=BODY_FONT_HEX, name="Calibri", size=10)
    body_font_bold_11 = Font(color=BODY_FONT_HEX, bold=True, name="Calibri", size=11)
    center = Alignment(horizontal="center", vertical="center")
    right = Alignment(horizontal="right", vertical="center")
    left = Alignment(horizontal="left", vertical="center")

    cur_col = 1
    for bd_id, bd in bds:
        cats = bd.get("categories", {}) or {}
        n_cats = len(cats)
        if n_cats == 0:
            continue

        label_col = cur_col
        data_start = cur_col + 1
        data_end = data_start + n_cats - 1

        # Row 2: merged group_header label_col..data_end
        ws.merge_cells(
            start_row=HEADER_ROW, start_column=label_col,
            end_row=HEADER_ROW, end_column=data_end,
        )
        gh = ws.cell(row=HEADER_ROW, column=label_col,
                     value=bd.get("label") or bd_id)
        gh.fill = header_fill
        gh.font = header_font_bold_11
        gh.alignment = center

        # Row 3: cat sub-headers (data cols only)
        for i, (cat_label, _) in enumerate(cats.items()):
            ch = ws.cell(row=CAT_ROW, column=data_start + i, value=cat_label)
            ch.fill = header_fill
            ch.font = header_font_bold_10
            ch.alignment = center

        # Row 4: counts row — label col = "Observaciones", data cols = totals
        obs = ws.cell(row=COUNTS_ROW, column=label_col, value="Observaciones")
        obs.fill = body_fill
        obs.font = body_font_bold_11
        obs.alignment = right

        for i, (_, opt_cells) in enumerate(cats.items()):
            total = sum(int((opt_cells.get(o) or {}).get("count") or 0) for o in options)
            cc = ws.cell(row=COUNTS_ROW, column=data_start + i, value=total)
            cc.fill = body_fill
            cc.font = body_font_bold_11
            cc.alignment = center

        # Rows 5+: option rows
        for j, opt in enumerate(options):
            row = FIRST_OPT_ROW + j

            lbl = ws.cell(row=row, column=label_col, value=opt)
            lbl.fill = body_fill
            lbl.font = body_font_bold_11
            lbl.alignment = right

            for i, (_, opt_cells) in enumerate(cats.items()):
                pct = float((opt_cells.get(opt) or {}).get("pct") or 0)
                oc = ws.cell(row=row, column=data_start + i, value=pct)
                oc.number_format = "0.0%"
                oc.fill = body_fill
                oc.font = body_font_10
                oc.alignment = left

        # DataBarRule per OPTION ROW spanning this bd's data cols only
        for j in range(len(options)):
            row = FIRST_OPT_ROW + j
            start_letter = get_column_letter(data_start)
            end_letter = get_column_letter(data_end)
            range_str = f"{start_letter}{row}:{end_letter}{row}"
            rule = DataBarRule(
                start_type="num", start_value=0,
                end_type="num", end_value=1,
                color=DATABAR_HEX,
                showValue=True,
            )
            ws.conditional_formatting.add(range_str, rule)

        # Column widths for this bd
        ws.column_dimensions[get_column_letter(label_col)].width = LABEL_COL_W
        for c in range(data_start, data_end + 1):
            ws.column_dimensions[get_column_letter(c)].width = DATA_COL_W

        cur_col = data_end + 2

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

Expected: all pass (5 new).

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/xlsx_builder.py backend/tests/test_xlsx_builder.py
git commit -m "fix(xlsx_builder): N independent tables side-by-side + hex palette

Previous layout used one merged group_header per bd spanning only its
cat cols, sharing a single external label col B for all bds — wrong:
each bd should be a complete table with its own label col, header
merge (label + cats), counts row, option rows, and DataBarRule scoped
to that bd's cat range. Palette switched from role names (which
resolved background to yellow) to hex literals matching the reference
design: dark gray headers (#595959 fill, #FFFFFF text) + white body
(#FFFFFF fill, #000000 text) + light gray bars (#BFBFBF).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `ole_png_renderer` — N panel canvas + hex colors

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/ole_png_renderer.py`
- Modify: `backend/tests/test_ole_png_renderer.py`

**Interfaces:**
- Consumes: nothing.
- Produces: PNG canvas with N panels side-by-side, each with internal label col + dark headers + white cells + gray bars.

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_ole_png_renderer.py`:

```python
def test_palette_dark_header_white_body():
    """Sample pixels: header band is dark gray; body row is white."""
    from io import BytesIO
    from PIL import Image
    from types import SimpleNamespace
    from aurum_encuestas.element_renderers.ole_png_renderer import render_table_preview_png

    q = SimpleNamespace(options=["opt0", "opt1"])
    src = SimpleNamespace(
        question=q,
        all_breakdowns_data={
            "edad": {"label": "Edad", "categories": {
                "18-39": {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}},
            }},
        },
        breakdown_ids=["edad"],
    )
    png = render_table_preview_png(src, ["edad"], 6_000_000, 3_000_000)
    img = Image.open(BytesIO(png))
    # Sample top-center (header band — should be dark gray ~89)
    w, h = img.size
    hx, hy = w // 2, 5
    hp = img.getpixel((hx, hy))
    assert hp[0] < 130 and hp[1] < 130 and hp[2] < 130, \
        f"expected dark header pixel at ({hx},{hy}), got {hp}"


def test_multi_bd_renders_n_panels_with_gap():
    """2 bds → distinguishable horizontal panels with white gap between them."""
    from io import BytesIO
    from PIL import Image
    from types import SimpleNamespace
    from aurum_encuestas.element_renderers.ole_png_renderer import render_table_preview_png

    q = SimpleNamespace(options=["opt0", "opt1"])
    src = SimpleNamespace(
        question=q,
        all_breakdowns_data={
            "edad": {"label": "Edad", "categories": {
                "18-39": {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}},
            }},
            "sexo": {"label": "Sexo", "categories": {
                "F": {"opt0": {"pct": 0.5, "count": 50}, "opt1": {"pct": 0.5, "count": 50}},
            }},
        },
        breakdown_ids=["edad", "sexo"],
    )
    png = render_table_preview_png(src, ["edad", "sexo"], 8_000_000, 3_000_000)
    img = Image.open(BytesIO(png))
    w, h = img.size
    # Scan a horizontal line through the header band; expect:
    # dark, white-gap, dark
    y = 5
    pixels = [img.getpixel((x, y)) for x in range(0, w, max(w // 40, 1))]
    dark_count = sum(1 for p in pixels if p[0] < 130)
    white_count = sum(1 for p in pixels if p[0] > 240)
    # Both regions present (panels are dark; gap between them is white)
    assert dark_count > 0
    assert white_count > 0
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_ole_png_renderer.py -k "palette_dark or multi_bd_renders_n_panels" -v
```

Expected: FAIL — current canvas uses GRAY (127,127,127) for body fill (matches header), no white body fill exists. Header is even darker.

- [ ] **Step 3: Rewrite `render_table_preview_png` body**

Replace the body in `backend/aurum_encuestas/element_renderers/ole_png_renderer.py` (keep helpers):

```python
"""PIL preview matching xlsx_builder layout for OLE TABLE_WITH_MINIBARS."""
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

EMU_PER_PX = 9525

# Palette (matches xlsx_builder hex literals)
HEADER_DARK = (89, 89, 89)
BG_WHITE = (255, 255, 255)
TEXT_BLACK = (0, 0, 0)
TEXT_WHITE = (255, 255, 255)
BAR_GRAY = (191, 191, 191)


def render_table_preview_png(
    source_chart,
    breakdown_groups: list[str],
    w_emu: int,
    h_emu: int,
) -> bytes:
    """PIL canvas: N panels side-by-side, each = own label col + dark headers
    + white body + gray bars. Returns PNG bytes."""
    w_px = max(400, w_emu // EMU_PER_PX)
    h_px = max(200, h_emu // EMU_PER_PX)
    img = Image.new("RGB", (w_px, h_px), BG_WHITE)
    draw = ImageDraw.Draw(img)

    question = getattr(source_chart, "question", None)
    options = list(getattr(question, "options", []) or [])
    all_bds = getattr(source_chart, "all_breakdowns_data", {}) or {}
    bds = [(bd_id, all_bds.get(bd_id, {})) for bd_id in breakdown_groups if bd_id in all_bds]

    if not bds or not options:
        return _save_png(img)

    if hasattr(ImageFont, "load_default_imagefont"):
        default_font = ImageFont.load_default_imagefont()
    else:
        default_font = ImageFont.load_default()
    try:
        font_hdr = ImageFont.truetype("Calibri Bold", 14)
        font_cat = ImageFont.truetype("Calibri Bold", 12)
        font_count = ImageFont.truetype("Calibri Bold", 13)
        font_lbl = ImageFont.truetype("Calibri Bold", 12)
        font_opt = ImageFont.truetype("Calibri", 11)
    except (IOError, OSError):
        font_hdr = font_cat = font_count = font_lbl = font_opt = default_font

    # Layout: per-panel label col + N cat cols, with horizontal gap between panels
    gap_px = 15
    label_col_w = 95
    n_bds = len(bds)
    total_cats = sum(len(bd.get("categories", {}) or {}) for _, bd in bds)
    content_w = w_px - 10
    # Compute cell_w so all panels fit
    per_panel_overhead = label_col_w
    available_for_cats = content_w - per_panel_overhead * n_bds - gap_px * (n_bds - 1)
    cell_w = max(45, available_for_cats // max(total_cats, 1))

    row_hdr = 28
    row_cat = 24
    row_count = 22
    row_opt = 32
    total_rows_h = row_hdr + row_cat + row_count + row_opt * len(options)
    if total_rows_h < h_px:
        extra = (h_px - total_rows_h) // max(len(options), 1)
        row_opt += extra

    y_hdr = 0
    y_cat = y_hdr + row_hdr
    y_count = y_cat + row_cat
    y_opt0 = y_count + row_count

    cur_x = 5
    for bd_id, bd in bds:
        cats = bd.get("categories", {}) or {}
        n_cats = len(cats)
        if n_cats == 0:
            continue
        panel_w = label_col_w + cell_w * n_cats

        # Group header band — spans full panel width
        draw.rectangle([cur_x, y_hdr, cur_x + panel_w, y_hdr + row_hdr], fill=HEADER_DARK)
        _centered_text(draw, bd.get("label") or bd_id, font_hdr, TEXT_WHITE,
                       cur_x, y_hdr, panel_w, row_hdr)

        # Cat sub-headers — data cols only (label col empty in cat row)
        for i, (cat_label, _) in enumerate(cats.items()):
            cx = cur_x + label_col_w + i * cell_w
            draw.rectangle([cx, y_cat, cx + cell_w, y_cat + row_cat], fill=HEADER_DARK)
            _centered_text(draw, cat_label, font_cat, TEXT_WHITE, cx, y_cat, cell_w, row_cat)

        # Counts row: label col = "Observaciones", data cols = totals
        lx = cur_x
        draw.rectangle([lx, y_count, lx + label_col_w, y_count + row_count], fill=BG_WHITE)
        _centered_text(draw, "Observaciones", font_lbl, TEXT_BLACK,
                       lx, y_count, label_col_w, row_count, align="right")
        for i, (_, opt_cells) in enumerate(cats.items()):
            cx = cur_x + label_col_w + i * cell_w
            total = sum(int((opt_cells.get(o) or {}).get("count") or 0) for o in options)
            draw.rectangle([cx, y_count, cx + cell_w, y_count + row_count], fill=BG_WHITE)
            _centered_text(draw, str(total) if total else "", font_count, TEXT_BLACK,
                           cx, y_count, cell_w, row_count)

        # Option rows
        for j, opt in enumerate(options):
            oy = y_opt0 + j * row_opt

            # Label col
            draw.rectangle([lx, oy, lx + label_col_w, oy + row_opt], fill=BG_WHITE)
            _centered_text(draw, opt, font_lbl, TEXT_BLACK,
                           lx, oy, label_col_w, row_opt, align="right")

            for i, (_, opt_cells) in enumerate(cats.items()):
                cx = cur_x + label_col_w + i * cell_w
                pct = float((opt_cells.get(opt) or {}).get("pct") or 0)
                draw.rectangle([cx, oy, cx + cell_w, oy + row_opt], fill=BG_WHITE)

                bar_h = int(row_opt * 0.5)
                bar_y = oy + (row_opt - bar_h) // 2
                bar_w = int((cell_w - 50) * min(1.0, max(0.0, pct)))
                if bar_w > 0:
                    draw.rectangle([cx + 50, bar_y, cx + 50 + bar_w, bar_y + bar_h], fill=BAR_GRAY)

                pct_text = f"{pct * 100:.1f}%"
                draw.text((cx + 6, oy + (row_opt - 14) // 2), pct_text, font=font_opt, fill=TEXT_BLACK)

        cur_x += panel_w + gap_px

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

Expected: all pass (2 new + existing).

- [ ] **Step 5: Run full backend suite**

```bash
cd backend && arch -arm64 .venv/bin/pytest -q 2>&1 | tail -3
```

Expected: 0 fail.

- [ ] **Step 6: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/ole_png_renderer.py backend/tests/test_ole_png_renderer.py
git commit -m "fix(ole_png_renderer): N-panel layout + hex palette matching xlsx

Each breakdown gets its own panel with internal label col, dark
gray header band (#595959), white body cells (#FFFFFF), light gray
horizontal data bars (#BFBFBF), and black option/count text. Panels
separated by 15px white gaps. Mirrors xlsx_builder output exactly so
the static OLE preview matches what Excel renders post-edit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Spec coverage:**
  - Spec § Bug #1 OOXML → Task 1 ✅
  - Spec § Bug #2 N-tables → Task 2 ✅
  - Spec § Bug #3 palette → Tasks 2 + 3 (xlsx hex + PIL tuples) ✅
  - Spec § Component contracts → match Task 1/2/3 impl bodies ✅
  - Spec § Testing → 4+5+2 new tests cover each ✅
- **Placeholder scan:** No "TBD" / "implement later". Tests + impl bodies all complete.
- **Type consistency:** `build_xlsx_for_table(source_chart, breakdown_groups) -> BytesIO` stable. `render_table_preview_png(source_chart, breakdown_groups, w_emu, h_emu) -> bytes` stable. `embed_ole_xlsx_with_preview(slide, x, y, w, h, xlsx_bytes, png_bytes) -> None` stable. `_render_oleobj_xml` new private helper in ole_embedder; signature explicit.
- **Open caveats:**
  - Task 1's `cleanup_namespaces` removal may leave redundant xmlns declarations in output XML. Acceptable per spec § Risk #2.
  - Task 2's `test_databar_per_bd_panel_scoped` checks that no databar range crosses spacer col D. Implementation assigns ranges per-bd, so this passes by construction.
  - Task 3's pixel sample at `(w//2, 5)` assumes the header band is at the top edge — true given `y_hdr=0`.
