# Fase D — OLE Fix + Multi-Table xlsx + Palette Design Spec

**Date:** 2026-06-21
**Status:** Approved (brainstorming) → ready for writing-plans
**Branch base:** `main` at `133cbd2` (post Fase C merge)

## Goal

Fix three bugs reported after Fase C ship:

1. **OOXML corrupto**: Generated `.pptx` triggers PowerPoint repair prompt; OLE shape removed by repair. Cause: invalid `<p:graphicFrame>` schema with `<p:pic>` nested directly inside `<p:oleObj>` under `<a:graphicData>`. Real OOXML requires `<mc:AlternateContent>` wrapper with `<mc:Choice>` + `<mc:Fallback>` branches.

2. **xlsx multi-bd layout**: Current xlsx renders ALL selected breakdowns in ONE table with merged group headers spanning the whole sheet. Spec requires N INDEPENDENT tables side-by-side, one per breakdown, each with its own label column and counts row.

3. **Palette wrong**: `_SEGMENTED_CELLS_FASE_B` uses role names (`fill: "primary"`, `text_color: "background"`). `color_resolver` maps `"background"` → `palette[2]` = `#EEC245` (yellow). Output renders everything yellow when reference shows: dark gray headers (white text) + white cells (black text) + light gray data bars.

## Non-Goals

- Charts (PIE, PIE_GROUPED, BAR_HORIZONTAL, BAR_HORIZONTAL_GROUPED) — untouched.
- Frontend — zero changes.
- Re-rendering PNG preview after user edits xlsx via OLE — same Fase C caveat.
- `table_renderer.py` legacy — untouched (still unreachable by dispatch).

## Locked decisions

1. **Bug #1 fix approach**: keep OLE (user requirement = OLE must work). Encode the OOXML standard `<mc:AlternateContent>` wrapper with `<mc:Choice Requires="v">` (Office 2010+) AND `<mc:Fallback>` (Office 2007). Both branches contain identical `<p:oleObj>` + `<p:pic>`; only difference is the Choice has `xmlns:v` and `spid` attribute.

2. **Bug #2 fix approach**: each selected breakdown gets its own complete table within the xlsx (and PIL canvas). N tables side-by-side, with a spacer column between tables. Each table has its own label column ("Observaciones"/option labels) at its left.

3. **Bug #3 fix approach**: replace role names in `_SEGMENTED_CELLS_FASE_B` and equivalent xlsx/PIL style constants with hex literals. Header dark gray + white text. Cells white bg + black text. Bars light gray.

## Architecture

```
ole_embedder.py
  └─ _render_oleobj_xml(rid, img_rid, w, h, nv_id, *, with_spid: bool, with_v_xmlns: bool)
       returns oleObj XML fragment for Choice (with_spid=True, with_v_xmlns=True)
                                    or Fallback (with_spid=False, with_v_xmlns=False)
  └─ embed_ole_xlsx_with_preview()
       graphicFrame
         > a:graphic > a:graphicData uri=ole
              > mc:AlternateContent
                   > mc:Choice Requires="v"  xmlns:v=...
                       > [oleObj from _render_oleobj_xml]
                   > mc:Fallback
                       > [oleObj from _render_oleobj_xml]

xlsx_builder.py
  build_xlsx_for_table(source_chart, breakdown_groups)
    cur_col = 1
    for bd_id, bd in breakdowns:
      label_col = cur_col
      data_start = cur_col + 1
      data_end = data_start + n_cats - 1
      # Row 2: merged group_header label..data_end (bd label inside)
      # Row 3: cat sub-headers (data_start..data_end)
      # Row 4: counts row — label col = "Observaciones", data cols = totals
      # Row 5+: option rows — label col = option name, data cols = pct + DataBarRule
      cur_col = data_end + 2   # 1 spacer col after this bd

ole_png_renderer.py
  render_table_preview_png(source_chart, breakdown_groups, w_emu, h_emu)
    For each bd, draw an independent panel:
      - own group_header band (full panel width, dark fill)
      - own cat sub-header row (data cols only)
      - own counts row (label col + data cols)
      - option rows (label col + data cols with internal bars)
    Panels separated by horizontal gap.
```

## Component contracts

### `ole_embedder.embed_ole_xlsx_with_preview(slide, x, y, w, h, xlsx_bytes, png_bytes) -> None`

Signature unchanged. Internal XML structure replaced with `<mc:AlternateContent>` wrapper:

- `<p:graphicFrame>` declares `xmlns:p`, `xmlns:a`, `xmlns:r`.
- Inside `<a:graphicData uri="...ole">`: `<mc:AlternateContent xmlns:mc="...">`.
- `<mc:Choice Requires="v" xmlns:v="urn:schemas-microsoft-com:vml">` containing `<p:oleObj spid="_x0000_s{N}" name="" r:id="{ole_rid}" imgW="{W}" imgH="{H}" progId="Excel.Sheet.12"><p:embed followColorScheme="full"/><p:pic>...</p:pic></p:oleObj>`.
- `<mc:Fallback>` containing identical `<p:oleObj>` but WITHOUT the `spid` attribute and WITHOUT `xmlns:v` (the Fallback is plain OOXML, no VML).
- Inside both oleObj `<p:pic>`: `<p:nvPicPr>` + `<p:blipFill>` with `<a:blip r:embed="{img_rid}"/>` + `<a:stretch><a:fillRect/></a:stretch>` + `<p:spPr bwMode="auto"><a:xfrm><a:off x="0" y="0"/><a:ext cx="{W}" cy="{H}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>`.
- `cleanup_namespaces` call removed because lxml's strict cleanup may also strip `xmlns:v` from Choice (where it IS needed). Verify via test.

### `xlsx_builder.build_xlsx_for_table(source_chart, breakdown_groups) -> BytesIO`

Signature unchanged. Layout replaced:

- Each bd has its own independent table.
- Iteration writes per-bd: label col, cat sub-header row, counts row, option rows.
- Per-bd group header merge spans `(label_col, data_end)` — includes the label col.
- `cur_col = data_end + 2` after each bd (1 spacer col).
- DataBarRule applied per option row over THAT bd's cat range only (NOT spanning sheet).
- Hex style literals: `HEADER_FILL_HEX="595959"`, `HEADER_FONT_HEX="FFFFFF"`, `BODY_FILL_HEX="FFFFFF"`, `BODY_FONT_HEX="000000"`, `DATABAR_HEX="BFBFBF"`.

### `ole_png_renderer.render_table_preview_png(source_chart, breakdown_groups, w_emu, h_emu) -> bytes`

Signature unchanged. Layout replaced:

- Compute `panel_widths` per bd = label_col_w + n_cats * cell_w.
- Total content_w = sum(panel_widths) + gap_w * (n_bds - 1).
- If total_w > canvas_w → shrink cell_w proportionally.
- Per panel: draw group header (panel full width), cat headers (data cols only), counts row (label col + data cols), option rows (label col + data cols with internal bars).
- Hex colors: HEADER_DARK=`(89,89,89)`, BG_WHITE=`(255,255,255)`, TEXT_BLACK=`(0,0,0)`, BAR_GRAY=`(191,191,191)`.

## Testing strategy

### Backend tests

`backend/tests/test_ole_embedder.py` (append):
- `test_graphic_frame_contains_mc_alternate_content`
- `test_choice_branch_has_xmlns_v_and_spid`
- `test_fallback_branch_has_no_spid_no_xmlns_v`
- `test_both_branches_reference_same_xlsx_and_png_rids`
- `test_round_trip_save_and_reopen_succeeds_after_alternate_content` (existing + extend)

`backend/tests/test_xlsx_builder.py` (replace existing tests):
- `test_single_panel_layout_has_own_label_col` — assert col B has "Observaciones" + option labels; group_header merge = `B2:D2` (label + 2 cats); no Edad spanning beyond col D.
- `test_multi_panel_layout_n_independent_tables` — N=2 bds → 2 distinct group_header merges (one per bd, NEVER spanning across bds); spacer col between bd_1 and bd_2 is fully empty.
- `test_databar_per_bd_panel_not_across_sheet` — DataBarRule range scoped to one bd's data cols, not entire sheet.
- `test_palette_uses_hex_literals_not_role_names` — header cells fill == "595959", font == "FFFFFF"; body cells fill == "FFFFFF", font == "000000".

`backend/tests/test_ole_png_renderer.py` (append):
- `test_multi_bd_renders_n_panels_with_gap` — 2 bds → distinct horizontal panel regions separated by white gap pixels.
- `test_palette_dark_header_white_body_gray_bars` — sample pixels at header band == HEADER_DARK; body cell pixels == BG_WHITE.

`backend/tests/test_ole_table_renderer.py` (existing): no change needed.

`backend/tests/test_render_e2e.py` (existing e2e): re-run; should still pass after structural fix.

### Manual smoke

After Fase D ships: regenerate the user's reported `.pptx`, open in Mac PowerPoint, verify:
- No repair prompt.
- OLE shape visible with PNG preview matching reference design (dark headers, white cells, gray bars).
- Double-click activates Excel; xlsx shows N independent tables side-by-side.

## File map

Modified:
- `backend/aurum_encuestas/element_renderers/ole_embedder.py`
- `backend/aurum_encuestas/element_renderers/xlsx_builder.py`
- `backend/aurum_encuestas/element_renderers/ole_png_renderer.py`
- `backend/tests/test_ole_embedder.py`
- `backend/tests/test_xlsx_builder.py`
- `backend/tests/test_ole_png_renderer.py`

Untouched:
- Frontend.
- `table_renderer.py`, `pattern_renderer.py`, `chart_renderer.py`.
- `ole_table_renderer.py` (orchestrator).
- `models.py`, `style_guide.py`, `pattern_classifier.py`.

## Open risks

1. **`<mc:AlternateContent>` schema correctness across PowerPoint versions.** Encoded from public OOXML spec + observed real-world `.pptx` files. Round-trip test catches structural validity. Manual smoke catches real-PowerPoint rendering.

2. **`cleanup_namespaces` interaction with `mc:Choice xmlns:v`.** lxml's `cleanup_namespaces` strips xmlns declarations that aren't used by elements in scope. If it strips `xmlns:v` from `mc:Choice` because no descendant uses `v:` prefix, the `Requires="v"` becomes invalid. Mitigation: drop `cleanup_namespaces` call; let lxml emit nested xmlns redeclarations (slightly less clean XML, but valid).

3. **Inner `<p:pic>` `<a:off x="0" y="0"/>`.** Relative to oleObj container or absolute slide coords? Initial impl uses `(0, 0)` (relative). If preview misaligns, switch to absolute matching graphicFrame offset.

4. **PNG canvas multi-panel width overflow.** N panels at fixed `cell_w` may exceed canvas. Plan: shrink `cell_w` proportionally to fit. Test asserts canvas dimensions unchanged.

5. **Fixture-level tests with old assertions.** Existing `test_builds_single_panel_layout` asserts `C2:D2` merge (data cols only). Post Fase D: merge is `B2:D2` (label + data). Tests rewritten in-place.

6. **xlsx_builder helper functions (`_apply_*_style`).** Extracted as module-level constants + per-cell apply, NOT helper functions, to keep simple. Style application inline.

7. **Empty `breakdown_groups`.** Currently returns valid xlsx with only labels in col B. Post Fase D: returns empty workbook (no labels because labels are now per-bd, not shared). Adapt test.

8. **PNG `_centered_text` with new layout.** Panel boundaries change; centering math reuses existing helper. No structural change to helper.
