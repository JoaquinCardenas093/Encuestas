"""Add OLE-embedded xlsx + PNG preview to a slide via lxml XML manipulation.

python-pptx 1.0 does not expose a public API to add an oleObject shape with
a custom preview image. We build the part + relationships + graphicFrame XML
directly.
"""
from lxml import etree
from lxml.etree import cleanup_namespaces
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
    xlsx_part = Part(xlsx_partname, CT_XLSX, package, xlsx_bytes)
    rId_xlsx = slide_part.relate_to(xlsx_part, RT.OLE_OBJECT)

    png_partname = _next_partname(package, "/ppt/media/image{}.png")
    png_part = Part(png_partname, CT.PNG, package, png_bytes)
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
    cleanup_namespaces(graphic_frame, top_nsmap=spTree.nsmap)
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
    return (max(ids) + 1) if ids else 1
