# Fase I — OOXML Wrapper Match Real Office Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Apply 4 FATAL OOXML defects fixes + structural matches per investigation `.git/sdd/ooxml-wrapper-investigation.md`.

**Architecture:** Inline minimal Choice oleObj + new `_render_fallback_oleobj_xml` helper. Drop `_render_oleobj_xml`. Move `xmlns:mc` from graphicFrame onto AlternateContent.

**Tech Stack:** Python 3.11, lxml.

## Global Constraints

- Python 3.11. `cd backend && arch -arm64 .venv/bin/pytest -q`.
- `embed_ole_xlsx_with_preview` signature unchanged.
- Choice oleObj: minimal — `name="Worksheet"` + `r:id` + `imgW` + `imgH` + `progId` + `<p:embed/>` ONLY. NO spid. NO `<p:pic>`.
- Fallback oleObj: `name="Worksheet"` + `<p:embed/>` + `<p:pic>` with absolute slide coords.
- `<p:embed/>` self-closing, NO attributes.
- `<p:cNvPr name>` → `"Object N"`.
- `<p:cNvPr id>` in Fallback `<p:pic>` matches outer `nv_id`.
- Fallback `<p:pic>` `<p:cNvPicPr>` contains `<a:picLocks noChangeAspect="1" noChangeArrowheads="1"/>`.
- Fallback `<p:blipFill>` contains `<a:srcRect/>` before `<a:stretch>`.
- `xmlns:mc` declared on `<mc:AlternateContent>`, NOT on `<p:graphicFrame>`. Drop `mc:Ignorable`.
- Drop `_render_oleobj_xml` (replaced).
- Adapt 1 test + add 8 new + delete 1 per spec test strategy.

---

### Task 1: Refactor ole_embedder + tests

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/ole_embedder.py`
- Modify: `backend/tests/test_ole_embedder.py`

**Interfaces:**
- Consumes: existing PNG + xlsx Part flow (Fase H, unchanged).
- Produces: graphicFrame with new wrapper structure matching real Office.

- [ ] **Step 1: Write 8 new failing tests + 1 adapted**

Add to `backend/tests/test_ole_embedder.py`:

```python
def test_choice_oleobj_has_no_pic():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    from lxml import etree
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(slide, 0, 0, 4_572_000, 2_286_000, _xlsx_bytes(), _png_bytes())
    root = etree.fromstring(etree.tostring(slide.shapes._spTree))
    nsmap = {"mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
             "p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
    pics = root.xpath(".//mc:Choice/p:oleObj/p:pic", namespaces=nsmap)
    assert len(pics) == 0, f"mc:Choice/p:oleObj must NOT contain <p:pic>, got {len(pics)}"


def test_choice_oleobj_only_has_embed_child():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    from lxml import etree
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(slide, 0, 0, 4_572_000, 2_286_000, _xlsx_bytes(), _png_bytes())
    root = etree.fromstring(etree.tostring(slide.shapes._spTree))
    nsmap = {"mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
             "p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
    choice_oleobj = root.xpath(".//mc:Choice/p:oleObj", namespaces=nsmap)
    assert len(choice_oleobj) == 1
    children = list(choice_oleobj[0])
    assert len(children) == 1, f"Choice oleObj must have exactly 1 child, got {len(children)}"
    assert etree.QName(children[0].tag).localname == "embed"


def test_oleobj_name_is_Worksheet():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    from lxml import etree
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(slide, 0, 0, 4_572_000, 2_286_000, _xlsx_bytes(), _png_bytes())
    root = etree.fromstring(etree.tostring(slide.shapes._spTree))
    nsmap = {"mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
             "p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
    for ole in root.xpath(".//p:oleObj", namespaces=nsmap):
        assert ole.get("name") == "Worksheet", f"expected name=Worksheet, got {ole.get('name')!r}"


def test_embed_element_has_no_attributes():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    from lxml import etree
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(slide, 0, 0, 4_572_000, 2_286_000, _xlsx_bytes(), _png_bytes())
    root = etree.fromstring(etree.tostring(slide.shapes._spTree))
    nsmap = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
    for embed in root.xpath(".//p:embed", namespaces=nsmap):
        assert len(embed.attrib) == 0, f"<p:embed> must have no attributes, got {dict(embed.attrib)}"


def test_choice_has_xmlns_v_and_no_spid():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    from lxml import etree
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(slide, 0, 0, 4_572_000, 2_286_000, _xlsx_bytes(), _png_bytes())
    xml = etree.tostring(slide.shapes._spTree, encoding="unicode")
    assert 'xmlns:v="urn:schemas-microsoft-com:vml"' in xml
    root = etree.fromstring(etree.tostring(slide.shapes._spTree))
    nsmap = {"mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
             "p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
    choice_oleobj = root.xpath(".//mc:Choice/p:oleObj", namespaces=nsmap)
    assert len(choice_oleobj) == 1
    assert choice_oleobj[0].get("spid") is None, "Choice oleObj must NOT carry spid"


def test_fallback_pic_uses_absolute_slide_coords():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    from lxml import etree
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(slide, x=914_400, y=914_400, w=4_572_000, h=2_286_000,
                                xlsx_bytes=_xlsx_bytes(), png_bytes=_png_bytes())
    root = etree.fromstring(etree.tostring(slide.shapes._spTree))
    nsmap = {"mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
             "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
             "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    off = root.xpath(".//mc:Fallback//p:pic/p:spPr/a:xfrm/a:off", namespaces=nsmap)
    assert len(off) == 1
    assert int(off[0].get("x")) == 914_400
    assert int(off[0].get("y")) == 914_400


def test_fallback_pic_cnvpr_id_matches_outer():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    from lxml import etree
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(slide, 0, 0, 4_572_000, 2_286_000, _xlsx_bytes(), _png_bytes())
    root = etree.fromstring(etree.tostring(slide.shapes._spTree))
    nsmap = {"mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
             "p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
    outer_cnvpr = root.xpath(".//p:graphicFrame/p:nvGraphicFramePr/p:cNvPr", namespaces=nsmap)
    pic_cnvpr = root.xpath(".//mc:Fallback//p:pic/p:nvPicPr/p:cNvPr", namespaces=nsmap)
    assert len(outer_cnvpr) == 1 and len(pic_cnvpr) == 1
    assert outer_cnvpr[0].get("id") == pic_cnvpr[0].get("id")


def test_picLocks_present_in_fallback_pic():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    from lxml import etree
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(slide, 0, 0, 4_572_000, 2_286_000, _xlsx_bytes(), _png_bytes())
    root = etree.fromstring(etree.tostring(slide.shapes._spTree))
    nsmap = {"mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
             "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
             "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    locks = root.xpath(".//mc:Fallback//p:pic/p:nvPicPr/p:cNvPicPr/a:picLocks", namespaces=nsmap)
    assert len(locks) == 1
    assert locks[0].get("noChangeAspect") == "1"
    assert locks[0].get("noChangeArrowheads") == "1"


def test_srcRect_present_in_fallback_blipFill():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    from lxml import etree
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(slide, 0, 0, 4_572_000, 2_286_000, _xlsx_bytes(), _png_bytes())
    root = etree.fromstring(etree.tostring(slide.shapes._spTree))
    nsmap = {"mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
             "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
             "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    srcrects = root.xpath(".//mc:Fallback//p:pic/p:blipFill/a:srcRect", namespaces=nsmap)
    assert len(srcrects) == 1
```

DELETE the old `test_choice_has_xmlns_v_and_spid` (replaced by `test_choice_has_xmlns_v_and_no_spid` above).

- [ ] **Step 2: Run new tests → all FAIL**

`cd backend && arch -arm64 .venv/bin/pytest tests/test_ole_embedder.py -q`
Expected: most new tests FAIL on current Fase H output.

- [ ] **Step 3: Rewrite `ole_embedder.py`**

Read current file. Replace the body of `embed_ole_xlsx_with_preview` from the `nsmap_decl` definition through the `spTree.append(graphic_frame)` line with:

```python
    nsmap_decl = (
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
    )

    choice_oleobj = (
        f'<p:oleObj name="Worksheet" r:id="{rid_xlsx}" '
        f'imgW="{int(w)}" imgH="{int(h)}" progId="{PROG_ID}">'
        f'<p:embed/>'
        f'</p:oleObj>'
    )
    fallback_oleobj = _render_fallback_oleobj_xml(
        rid_xlsx=rid_xlsx, rid_img=rid_img,
        x=x, y=y, w=w, h=h, nv_id=nv_id,
    )

    xml = f"""<p:graphicFrame {nsmap_decl}>
  <p:nvGraphicFramePr>
    <p:cNvPr id="{nv_id}" name="Object {nv_id}"/>
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
      <mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">
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
    spTree.append(graphic_frame)
```

Replace `_render_oleobj_xml` with `_render_fallback_oleobj_xml`:

```python
def _render_fallback_oleobj_xml(
    *, rid_xlsx: str, rid_img: str,
    x: int, y: int, w: int, h: int, nv_id: int,
) -> str:
    """Render Fallback <p:oleObj> with embedded <p:pic> preview.

    Matches structure produced by real Office 2016+ Excel-embed slides.
    """
    return f"""<p:oleObj name="Worksheet" r:id="{rid_xlsx}" imgW="{int(w)}" imgH="{int(h)}" progId="{PROG_ID}">
            <p:embed/>
            <p:pic>
              <p:nvPicPr>
                <p:cNvPr id="{nv_id}" name="Object {nv_id}"/>
                <p:cNvPicPr>
                  <a:picLocks noChangeAspect="1" noChangeArrowheads="1"/>
                </p:cNvPicPr>
                <p:nvPr/>
              </p:nvPicPr>
              <p:blipFill>
                <a:blip r:embed="{rid_img}"/>
                <a:srcRect/>
                <a:stretch><a:fillRect/></a:stretch>
              </p:blipFill>
              <p:spPr bwMode="auto">
                <a:xfrm>
                  <a:off x="{int(x)}" y="{int(y)}"/>
                  <a:ext cx="{int(w)}" cy="{int(h)}"/>
                </a:xfrm>
                <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
              </p:spPr>
            </p:pic>
          </p:oleObj>"""
```

- [ ] **Step 4: Adapt or delete existing tests**

Delete from `backend/tests/test_ole_embedder.py`:
- `test_choice_has_xmlns_v_and_spid` (replaced by new `test_choice_has_xmlns_v_and_no_spid`).

Keep all other existing tests AS-IS; they should still pass:
- `test_fallback_branch_has_no_spid` (still true — spid was never on Fallback)
- `test_both_branches_reference_same_xlsx_rid`
- `test_graphic_frame_appended_with_oleObj_and_blip`
- `test_graphic_frame_contains_mc_alternate_content`
- All part/blob tests

- [ ] **Step 5: Run new tests → all PASS**

`cd backend && arch -arm64 .venv/bin/pytest tests/test_ole_embedder.py -q`

- [ ] **Step 6: Run full backend suite → PASS**

`cd backend && arch -arm64 .venv/bin/pytest -q`
Expected: 343 baseline - 1 deleted + 8 new = 350 passed + 3 skipped (approximate).

- [ ] **Step 7: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/ole_embedder.py backend/tests/test_ole_embedder.py
git commit -m "fix(ole_embedder): match real Office OOXML wrapper (drop p:pic from Choice, p:embed no attrs, name=Worksheet, no spid)"
```
