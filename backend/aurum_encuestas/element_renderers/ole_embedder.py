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

    xml = f"""<p:graphicFrame {nsmap_decl} mc:Ignorable="v">
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
