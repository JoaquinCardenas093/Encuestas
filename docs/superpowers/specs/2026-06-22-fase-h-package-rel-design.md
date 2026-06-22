# Fase H — Package Relationship Form (drop CFB) Design Spec

**Date:** 2026-06-22
**Status:** Approved (post deep CFB investigation) → ready for SDD execution
**Branch base:** `main` at `2ad64fe` (post Fase G merge)

## Goal

Replace the entire CFB-wrapped OLE path with the modern Package
relationship form that real Microsoft Office (2007+) uses for Excel
embeddings. Deep investigation (`.git/sdd/deep-cfb-investigation.md`)
established that real Office Excel embeds are **raw `.xlsx` (PK zip),
NOT CFB**, related via `RT.PACKAGE` with content type
`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.

Mac PowerPoint flags "Reparar" because no modern Office writes CFB-wrapped
Excel.Sheet.12 OLE — even byte-perfect CFB is "legacy/suspect" to the
validator. Surgical CFB fixes (Option B) would still fight this perception.

## Non-Goals

- CFB byte-level fixes (Option B from investigation report — reject).
- Frontend changes.
- Style guide / classifier / pattern changes.
- `.xlsx` content (xlsx_builder unchanged).
- PNG preview (`ole_png_renderer` unchanged).
- Slide graphicFrame XML attribute set (progId, mc:AlternateContent
  structure stay identical — only the rel target/content-type swap).

## Locked decisions

1. **Drop CFB entirely.** Delete `cfb_writer.py` + `test_cfb_writer.py`.
2. **Partname template:** `/ppt/embeddings/Microsoft_Excel_Worksheet{N}.xlsx`
   (matches real Office naming convention).
3. **Content type:** `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
   (literal string; not in `pptx.opc.constants.CT` enum).
4. **Relationship type:** `RT.PACKAGE` (resolves to
   `http://schemas.openxmlformats.org/officeDocument/2006/relationships/package`).
5. **Blob content:** raw `xlsx_bytes` as-is (no length prefix, no wrapper).
6. **Slide XML:** `<p:oleObj progId="Excel.Sheet.12">` UNCHANGED. r:id now
   resolves to the xlsx Package rel instead of the .bin OLE rel. mc:Choice
   + mc:Fallback structure preserved.
7. **olefile dev dep** retained for potential future CFB inspection but no
   production code path uses it.

## Architecture

```
ole_embedder.embed_ole_xlsx_with_preview(slide, x, y, w, h, xlsx_bytes, png_bytes)
   ├─ xlsx_part = Part(/ppt/embeddings/Microsoft_Excel_Worksheet{N}.xlsx,
   │                   "application/vnd...spreadsheetml.sheet",
   │                   package, xlsx_bytes)
   ├─ rid_xlsx = slide_part.relate_to(xlsx_part, RT.PACKAGE)
   ├─ png_part (unchanged)
   ├─ rid_img (unchanged)
   └─ graphicFrame XML (unchanged structure)

cfb_writer.py                         → DELETED
backend/tests/test_cfb_writer.py      → DELETED
```

## Component contracts

### `ole_embedder.embed_ole_xlsx_with_preview(...)` — modified

Signature unchanged. Internal change:

```python
# Was:
#   from .cfb_writer import build_excel_ole_cfb
#   CT_OLE_OBJECT = "application/vnd.openxmlformats-officedocument.oleObject"
#   cfb_blob = build_excel_ole_cfb(xlsx_bytes)
#   bin_partname = _next_partname(package, "/ppt/embeddings/oleObject{}.bin")
#   bin_part = Part(bin_partname, CT_OLE_OBJECT, package, cfb_blob)
#   rid_xlsx = slide_part.relate_to(bin_part, RT.OLE_OBJECT)

# Now:
CT_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
xlsx_partname = _next_partname(package, "/ppt/embeddings/Microsoft_Excel_Worksheet{}.xlsx")
xlsx_part = Part(xlsx_partname, CT_XLSX, package, xlsx_bytes)
rid_xlsx = slide_part.relate_to(xlsx_part, RT.PACKAGE)
```

`cfb_writer` import dropped. PNG embed + graphicFrame XML unchanged.

## Testing strategy

### Replace `test_ole_embedder.py` tests

**Delete:**
- `test_embedded_ole_bin_part_added` (asserted .bin partname)
- `test_embedded_part_is_bin_not_xlsx` (now inverted)
- `test_embedded_part_content_type_is_oleObject` (now xlsx CT)
- `test_embedded_blob_is_cfb` (now PK zip)
- `test_round_trip_save_and_reopen_succeeds` assertion `blob[:8] == CFB_MAGIC` → change to `blob[:4] == b"PK\x03\x04"`

**Add:**
- `test_embedded_xlsx_part_added` — assert any part `/ppt/embeddings/Microsoft_Excel_Worksheet*.xlsx` exists.
- `test_embedded_part_content_type_is_xlsx` — assert content_type == `"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"`.
- `test_embedded_blob_is_pk_zip` — assert `blob[:4] == b"PK\x03\x04"` (xlsx zip magic).
- `test_slide_rel_uses_package_type` — assert rel reltype contains `/package` (NOT `/oleObject`).

**Keep:**
- `test_image_part_added`
- `test_graphic_frame_appended_with_oleObj_and_blip`
- `test_multiple_embeds_get_distinct_partnames` (adapt to xlsx partname pattern)
- `test_graphic_frame_contains_mc_alternate_content`
- `test_choice_has_xmlns_v_and_spid`
- `test_fallback_branch_has_no_spid`
- `test_both_branches_reference_same_xlsx_rid`
- `test_round_trip_save_and_reopen_succeeds` (assertion updated to PK magic)

### Adapt `test_slide_rels_contain_ole_object_and_image_types`

Was: asserted at least one rel type contains "oleObject".
Now: at least one rel type contains "/package" + one ends with "/image".

### Delete entirely

`backend/tests/test_cfb_writer.py` — 12 tests removed.

## File map

Modified:
- `backend/aurum_encuestas/element_renderers/ole_embedder.py`
- `backend/tests/test_ole_embedder.py`

Deleted:
- `backend/aurum_encuestas/element_renderers/cfb_writer.py`
- `backend/tests/test_cfb_writer.py`

Untouched:
- All other element_renderers (`xlsx_builder`, `ole_png_renderer`, `ole_table_renderer`).
- Frontend.
- Style guide / classifier.
- `pyproject.toml` (olefile dev dep stays).

## Smoke test (post-merge)

1. Wipe `~/.aurum/training/style_guide.json` (already done).
2. Regenerate `.pptx`.
3. Open in Mac PowerPoint:
   - **NO** Reparar prompt.
   - Single full-width OLE table.
   - Double-click activates Excel with data visible (xlsx loads as native).

## Open risks

1. **`RT.PACKAGE` reltype constant value differs from what Mac validates**.
   Investigation confirmed the URI matches Office's output. Very low risk.
2. **python-pptx `Part` constructor handling of unknown content types**.
   Verified that python-pptx accepts arbitrary CT strings via `Part(..., content_type, ...)`. Low risk.
3. **Existing user .pptx files generated with CFB OLE** become unopenable
   in Excel (because the rel target was the .bin path that no longer
   exists in fresh re-generates). Mitigation: this is a user re-run; old
   files are stale anyway.
4. **`_meta.breakdowns` exclude 'general'** is already in classifier path
   from Fase F — not touched here. Confirmed via `git log`.
