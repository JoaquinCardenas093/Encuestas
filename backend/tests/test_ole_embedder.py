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


def test_round_trip_save_and_reopen_succeeds():
    """Regression: Part(blob, package) arg order was inverted, corrupting the
    serialized pptx blob. This test exercises full save+reopen to catch any
    repeat of that defect."""
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(
        slide, x=0, y=0, w=4_572_000, h=2_286_000,
        xlsx_bytes=_xlsx_bytes(), png_bytes=_png_bytes(),
    )
    buf = BytesIO()
    prs.save(buf)
    buf.seek(0)
    # Reopen the saved pptx — fails if Part blob was a Package object
    prs2 = Presentation(buf)
    # Embedded xlsx part should be readable
    xlsx_parts = [p for p in prs2.part.package.iter_parts() if str(p.partname).endswith(".xlsx") and "embeddings" in str(p.partname)]
    assert len(xlsx_parts) == 1
    # Its blob is the original xlsx bytes (xlsx file magic = b"PK\x03\x04")
    assert xlsx_parts[0].blob[:4] == b"PK\x03\x04"
