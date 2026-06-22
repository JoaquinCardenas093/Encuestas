# Fase H — Package Relationship Form Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Drop CFB entirely. Replace `oleObject{N}.bin` with raw `Microsoft_Excel_Worksheet{N}.xlsx` part + RT.PACKAGE rel. Match real Office Excel embed shape verified by investigation.

**Architecture:** ~20 LOC swap in `ole_embedder.py` + delete `cfb_writer.py` + rewrite affected tests.

**Tech Stack:** Python 3.11, python-pptx, lxml.

## Global Constraints

- Python 3.11. `cd backend && arch -arm64 .venv/bin/pytest -q`.
- `embed_ole_xlsx_with_preview` signature unchanged.
- Partname template: `/ppt/embeddings/Microsoft_Excel_Worksheet{N}.xlsx`.
- Content type literal: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.
- Rel type: `RT.PACKAGE` from `pptx.opc.constants.RELATIONSHIP_TYPE`.
- Blob content: raw `xlsx_bytes` (no length prefix, no CFB wrap).
- Slide XML structure unchanged.
- Delete `cfb_writer.py` + `test_cfb_writer.py` entirely.

---

### Task 1: Rewrite `ole_embedder.py` + tests

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/ole_embedder.py`
- Modify: `backend/tests/test_ole_embedder.py`
- Delete: `backend/aurum_encuestas/element_renderers/cfb_writer.py`
- Delete: `backend/tests/test_cfb_writer.py`

**Interfaces:**
- Consumes: `pptx.opc.constants.RELATIONSHIP_TYPE.PACKAGE`, `pptx.opc.constants.CONTENT_TYPE.PNG`.
- Produces: `embed_ole_xlsx_with_preview` adds raw xlsx part + RT.PACKAGE rel + PNG part + RT.IMAGE rel + graphicFrame XML with `<p:oleObj progId="Excel.Sheet.12">` mc:AlternateContent.

- [ ] **Step 1: Write failing tests**

Replace `backend/tests/test_ole_embedder.py` with this new set (keep helpers + adapted tests):

```python
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
    assert any(
        p.startswith("/ppt/embeddings/Microsoft_Excel_Worksheet") and p.endswith(".xlsx")
        for p in partnames
    )


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


def test_slide_rels_contain_package_and_image_types():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(
        slide, x=0, y=0, w=4_572_000, h=2_286_000,
        xlsx_bytes=_xlsx_bytes(), png_bytes=_png_bytes(),
    )
    types = {rel.reltype for rel in slide.part.rels.values()}
    assert any(t.endswith("/package") for t in types), types
    assert any(t.endswith("/image") for t in types), types


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
    xlsx_parts = [
        str(p.partname) for p in package.iter_parts()
        if str(p.partname).startswith("/ppt/embeddings/Microsoft_Excel_Worksheet")
    ]
    png_parts = [str(p.partname) for p in package.iter_parts() if str(p.partname).endswith(".png")]
    assert len(set(xlsx_parts)) == 2
    assert len(set(png_parts)) == 2


def test_round_trip_save_and_reopen_succeeds():
    """Save+reopen round trip — regression guard for partname/blob shape."""
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(
        slide, x=0, y=0, w=4_572_000, h=2_286_000,
        xlsx_bytes=_xlsx_bytes(), png_bytes=_png_bytes(),
    )
    buf = BytesIO()
    prs.save(buf)
    buf.seek(0)
    prs2 = Presentation(buf)
    xlsx_parts = [
        p for p in prs2.part.package.iter_parts()
        if str(p.partname).startswith("/ppt/embeddings/Microsoft_Excel_Worksheet")
    ]
    assert len(xlsx_parts) == 1
    assert xlsx_parts[0].blob[:4] == b"PK\x03\x04", "embedded blob must be raw xlsx PK zip"


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
    assert 'xmlns:v="urn:schemas-microsoft-com:vml"' in xml
    assert 'spid="_x0000_s' in xml


def test_fallback_branch_has_no_spid():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    from lxml import etree
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(
        slide, x=0, y=0, w=4_572_000, h=2_286_000,
        xlsx_bytes=_xlsx_bytes(), png_bytes=_png_bytes(),
    )
    root = etree.fromstring(etree.tostring(slide.shapes._spTree))
    nsmap = {
        "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
        "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    }
    fallback = root.xpath(".//mc:Fallback//p:oleObj", namespaces=nsmap)
    assert len(fallback) == 1
    assert fallback[0].get("spid") is None


def test_both_branches_reference_same_xlsx_rid():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    from lxml import etree
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(
        slide, x=0, y=0, w=4_572_000, h=2_286_000,
        xlsx_bytes=_xlsx_bytes(), png_bytes=_png_bytes(),
    )
    root = etree.fromstring(etree.tostring(slide.shapes._spTree))
    nsmap = {
        "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
        "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    choice_oleobj = root.xpath(".//mc:Choice/p:oleObj", namespaces=nsmap)
    fallback_oleobj = root.xpath(".//mc:Fallback/p:oleObj", namespaces=nsmap)
    rid_key = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    assert len(choice_oleobj) == 1 and len(fallback_oleobj) == 1
    assert choice_oleobj[0].get(rid_key) == fallback_oleobj[0].get(rid_key)


def test_embedded_part_content_type_is_xlsx():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(
        slide, x=0, y=0, w=4_572_000, h=2_286_000,
        xlsx_bytes=_xlsx_bytes(), png_bytes=_png_bytes(),
    )
    package = slide.part.package
    for p in package.iter_parts():
        name = str(p.partname)
        if name.startswith("/ppt/embeddings/Microsoft_Excel_Worksheet") and name.endswith(".xlsx"):
            assert p.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            return
    raise AssertionError("no xlsx embedding part found")


def test_embedded_blob_is_pk_zip():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(
        slide, x=0, y=0, w=4_572_000, h=2_286_000,
        xlsx_bytes=_xlsx_bytes(), png_bytes=_png_bytes(),
    )
    package = slide.part.package
    for p in package.iter_parts():
        name = str(p.partname)
        if name.startswith("/ppt/embeddings/Microsoft_Excel_Worksheet") and name.endswith(".xlsx"):
            assert p.blob[:4] == b"PK\x03\x04"
            return
    raise AssertionError("no xlsx embedding part found")
```

- [ ] **Step 2: Run new tests → FAIL**

`cd backend && arch -arm64 .venv/bin/pytest tests/test_ole_embedder.py -q`
Expected: all FAIL — current `ole_embedder` still produces .bin/CFB.

- [ ] **Step 3: Rewrite `ole_embedder.py`**

Replace lines 14-17 + 33-36 with:
```python
# Drop the cfb_writer import:
# from .cfb_writer import build_excel_ole_cfb   # DELETED

CT_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PROG_ID = "Excel.Sheet.12"
```

And replace the embed body (current lines 33-36):
```python
xlsx_partname = _next_partname(package, "/ppt/embeddings/Microsoft_Excel_Worksheet{}.xlsx")
xlsx_part = Part(xlsx_partname, CT_XLSX, package, xlsx_bytes)
rid_xlsx = slide_part.relate_to(xlsx_part, RT.PACKAGE)
```

Drop `CT_OLE_OBJECT` constant. Drop `cfb_blob = build_excel_ole_cfb(...)` line. Drop the `bin_partname` + `bin_part` lines. Keep everything else (PNG part, graphicFrame XML).

- [ ] **Step 4: Run tests → PASS**

`cd backend && arch -arm64 .venv/bin/pytest tests/test_ole_embedder.py -q`
Expected: 12/12 pass.

- [ ] **Step 5: Delete `cfb_writer.py` + `test_cfb_writer.py`**

```bash
rm backend/aurum_encuestas/element_renderers/cfb_writer.py
rm backend/tests/test_cfb_writer.py
```

- [ ] **Step 6: Run full backend suite → PASS**

`cd backend && arch -arm64 .venv/bin/pytest -q`
Expected: 356 - 12 (cfb tests) + 0 (xlsx test count unchanged) = ~344 pass + 3 skip.

- [ ] **Step 7: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/ole_embedder.py \
        backend/tests/test_ole_embedder.py
git rm backend/aurum_encuestas/element_renderers/cfb_writer.py \
       backend/tests/test_cfb_writer.py
git commit -m "feat(ole_embedder): use Package relationship form (raw xlsx); drop CFB"
```
