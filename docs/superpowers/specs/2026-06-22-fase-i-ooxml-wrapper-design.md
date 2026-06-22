# Fase I — OOXML Wrapper Match Real Office Excel Embed Design Spec

**Date:** 2026-06-22
**Status:** Approved (post OOXML wrapper investigation) → ready for SDD
**Branch base:** `main` at `32d4a38` (post Fase H merge)

## Goal

Bug 1 (Mac "Reparar") persists after Fase H even though xlsx embeds and Excel double-click works correctly. Investigation
(`.git/sdd/ooxml-wrapper-investigation.md`) byte-diffed our slide XML vs
real Office Excel-embed (`PPT Aurora ejemplo.pptx` slide26, 54 embeds total
verified). Found 4 FATAL OOXML defects in our `oleObj`/`mc:AlternateContent` wrapper.

## Non-Goals

- Frontend changes.
- Style guide / classifier / pattern changes.
- xlsx_builder, ole_png_renderer, ole_table_renderer code.
- EMF preview (PNG stays — investigation marks EMF as "Likely" not Fatal).
- creationId / modId GUIDs (cosmetic, never triggers Reparar).
- Spurious `Default Extension="bin"` in `[Content_Types].xml` cleanup
  (separate concern — non-fatal dead weight).

## Locked decisions

Per investigation Smoking Gun ranking (4 FATAL):

1. Remove `<p:pic>` from `<mc:Choice>`. Choice gets ONLY `<p:embed/>` inside oleObj.
2. `<p:embed/>` self-closing with NO attributes. Drop `followColorScheme="full"`.
3. `<p:oleObj name="Worksheet"/>` on BOTH Choice and Fallback (matches all 54 Aurora embeds).
4. Drop `spid="_x0000_s{N}"` from Choice oleObj entirely.

Plus structural:
5. Move `xmlns:mc` from `<p:graphicFrame>` onto `<mc:AlternateContent>`. Drop `mc:Ignorable="v"`.
6. Fallback `<p:pic>` `<a:off>` uses absolute slide-space coords `(x, y)` not `(0, 0)`.
7. Fallback `<p:pic>` `<p:cNvPr id>` matches outer `<p:cNvPr id>` (`nv_id`).
8. Add `<a:picLocks noChangeAspect="1" noChangeArrowheads="1"/>` inside `<p:cNvPicPr>`.
9. Add `<a:srcRect/>` sibling before `<a:stretch>` in Fallback `<p:blipFill>`.
10. Rename `<p:cNvPr name>` `"OLEObject N"` → `"Object N"` (Office convention).

## Architecture

```
embed_ole_xlsx_with_preview(slide, x, y, w, h, xlsx_bytes, png_bytes)
   ├─ xlsx_part (Fase H, unchanged)
   ├─ png_part (Fase H, unchanged)
   ├─ choice_oleobj (NEW: minimal — name="Worksheet" + r:id + imgW + imgH + progId + <p:embed/>)
   ├─ fallback_oleobj (refactored: name="Worksheet" + <p:embed/> + <p:pic with absolute xfrm>)
   └─ graphicFrame XML wrap (no xmlns:mc, no mc:Ignorable on graphicFrame)
```

## Component contracts

### `ole_embedder.embed_ole_xlsx_with_preview(...)` — modified

Signature unchanged.

**Choice branch generation:**

```python
choice_oleobj = (
    f'<p:oleObj name="Worksheet" r:id="{rid_xlsx}" '
    f'imgW="{int(w)}" imgH="{int(h)}" progId="Excel.Sheet.12">'
    f'<p:embed/>'
    f'</p:oleObj>'
)
```

**Fallback branch generation via new `_render_fallback_oleobj_xml`:**

```python
def _render_fallback_oleobj_xml(*, rid_xlsx, rid_img, x, y, w, h, nv_id) -> str:
    return f"""<p:oleObj name="Worksheet" r:id="{rid_xlsx}" imgW="{int(w)}" imgH="{int(h)}" progId="Excel.Sheet.12">
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

**graphicFrame template:**

```python
nsmap_decl = (
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
)
# NOTE: xmlns:mc moved OFF graphicFrame, ON mc:AlternateContent.

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
```

Drop existing `_render_oleobj_xml` (replaced by inline Choice + new `_render_fallback_oleobj_xml`).

## Testing strategy

### Update `test_ole_embedder.py`

**Delete:**
- `test_choice_has_xmlns_v_and_spid` — spid no longer present on Choice; the test would fail. Replace below.

**Replace:**
- `test_fallback_branch_has_no_spid` → keep (asserts fallback has no spid, still true).
- `test_choice_has_xmlns_v_and_spid` → `test_choice_has_xmlns_v_and_no_spid`: assert `xmlns:v` present on `mc:Choice` AND Choice `p:oleObj` has NO `spid` attribute.

**Add:**
- `test_choice_oleobj_has_no_pic` — assert `mc:Choice/p:oleObj` has NO `<p:pic>` child (was duplicated in Fase H).
- `test_choice_oleobj_only_has_embed_child` — assert Choice oleObj has EXACTLY one child `<p:embed/>`.
- `test_oleobj_name_is_Worksheet` — assert Choice + Fallback `p:oleObj` have `name="Worksheet"`.
- `test_embed_element_has_no_attributes` — assert Choice `<p:embed>` AND Fallback `<p:embed>` have NO attributes (no `followColorScheme`).
- `test_fallback_pic_uses_absolute_slide_coords` — assert Fallback `<p:pic>/<p:spPr>/<a:xfrm>/<a:off>` `x` matches outer graphicFrame `x` (not `0`).
- `test_fallback_pic_cnvpr_id_matches_outer` — assert Fallback `<p:pic>/<p:nvPicPr>/<p:cNvPr>` `id` matches outer `<p:nvGraphicFramePr>/<p:cNvPr>` `id`.
- `test_picLocks_present_in_fallback_pic` — assert Fallback `<p:cNvPicPr>` contains `<a:picLocks noChangeAspect="1" noChangeArrowheads="1"/>`.
- `test_srcRect_present_in_fallback_blipFill` — assert Fallback `<p:blipFill>` contains `<a:srcRect/>` before `<a:stretch>`.

**Keep with possible adapt:**
- `test_both_branches_reference_same_xlsx_rid` — Choice oleObj now just has `<p:embed/>` child, but Choice oleObj's `r:id` and Fallback oleObj's `r:id` should still match. Still passes.
- All `test_embedded_*` part-existence tests (unaffected by XML changes).
- `test_graphic_frame_contains_mc_alternate_content` — still passes.
- `test_round_trip_save_and_reopen_succeeds` — still passes.

## File map

Modified:
- `backend/aurum_encuestas/element_renderers/ole_embedder.py`
- `backend/tests/test_ole_embedder.py`

Untouched:
- All other element_renderers.
- Frontend.
- Style guide / classifier.

## Smoke test (post-merge)

1. Regenerate `.pptx`.
2. Open in Mac PowerPoint:
   - **NO Reparar prompt** (THIS bug).
   - Single full-width OLE table (Fase F).
   - Double-click activates Excel with data (Fase H).
3. xlsx data renders correctly inside Excel (already verified post Fase H).

## Open risks

1. **Mac PPT validator quirk not caught by investigation**. Investigation
   covered the structural OOXML defects observed against 54 real embeds.
   Other validator paths (e.g., signature of cNvPr extLst) could still
   trigger. Mitigation: if Reparar persists, surgical iterate against
   investigation Honorable Mentions list.
2. **Smoke test requires user with Mac PowerPoint** — same as all prior phases.
3. **Existing tests that pass today may newly fail because they assumed
   the old structure** (e.g., spid in Choice was asserted as PRESENT in
   Fase D/E test). Adapt per test strategy above.
