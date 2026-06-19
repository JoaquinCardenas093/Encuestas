# Chart Catalog Overhaul — Fase C Design Spec

**Date:** 2026-06-19
**Status:** Approved (brainstorming) → ready for writing-plans
**Branch base:** `main` at `ffc02b8` (post Fase B merge)
**Phase:** C of 3 — final phase. OLE-embedded editable xlsx replaces the python-pptx native table for `TABLE_WITH_MINIBARS`.

## Goal

Replace the `TABLE_WITH_MINIBARS` python-pptx native table render (Fase B) with an OLE-embedded xlsx object. The slide shows a static PNG preview that matches the Fase B layout pixel-for-pixel; double-clicking the preview activates Excel and lets the user edit the underlying spreadsheet data. Charts (PIE, PIE_GROUPED, BAR_HORIZONTAL, BAR_HORIZONTAL_GROUPED) are NOT touched — they already use `CategoryChartData` which PowerPoint exposes via "Edit Data" natively.

## Non-Goals

- Bidirectional sync between the embedded xlsx and the underlying source data file. User edits the xlsx via OLE; the parent project's xlsx (the survey source) is NOT updated. Regenerating the pptx from the project recreates the embedded xlsx.
- Touching charts (`PIE`, `PIE_GROUPED`, `BAR_HORIZONTAL`, `BAR_HORIZONTAL_GROUPED`) — they keep their existing `CategoryChartData` path.
- Re-rendering the PNG preview after the user edits the xlsx via OLE. The preview is stale until the pptx is regenerated. (Acceptable: matches Office's normal stale-thumbnail behavior.)

## Locked decisions (from grilling)

1. **Visual model**: OLE Excel replaces the table. The slide shape IS the OLE object with a custom PNG preview. Double-click activates Excel.
2. **Scope**: only `TABLE_WITH_MINIBARS` (both single-bd and multi-bd). PIE / BAR / their _GROUPED variants stay on `CategoryChartData`.
3. **Minibars in xlsx**: Excel native `DataBarRule` conditional formatting. Color = secondary dark (`#404040`).
4. **OLE fallback**: static PNG preview embedded so LibreOffice / PowerPoint web / Linux viewers still see the table layout even without OLE support.

## Architecture overview

```
pattern_renderer.render_pattern
  └─ dispatch peek (Fase A T5):
        source_chart.chart_type == "TABLE_WITH_MINIBARS"
          AND real breakdown_ids present
        → _synthesize_table_element returns kind="ole_table"   ← changed in Fase C
                                              (was "table" in Fase B)
        → _KIND_RENDERERS["ole_table"] = ole_table_renderer    ← new entry
  └─ ole_table_renderer.render(slide, element, ctx)
        1. xlsx_builder.build_xlsx_for_table(source_chart, breakdown_groups)
              → openpyxl Workbook → BytesIO
        2. ole_png_renderer.render_table_preview_png(source_chart, breakdown_groups, w_emu, h_emu)
              → PIL canvas → PNG bytes
        3. ole_embedder.embed_ole_xlsx_with_preview(slide, x, y, w, h, xlsx_bytes, png_bytes)
              → adds xlsx Part + PNG Part + slide rels + graphicFrame XML
```

`table_renderer.py` is **untouched** but the dispatch never invokes it post-Fase C. It remains as legacy code; future cleanup may remove the `segmented_breakdowns` path.

## Component contracts

### `xlsx_builder.build_xlsx_for_table(source_chart, breakdown_groups: list[str]) -> BytesIO`

Returns an in-memory xlsx whose layout mirrors img 17 (single bd) / img 18 (multi bd):
- Row 1: empty top margin.
- Row 2: group_header row — merged across N cats per breakdown; fill=`#404040`, font yellow `#EEC245`, bold, size 11pt.
- Row 3: cat sub-header row — fill=`#7F7F7F`, font yellow, bold, size 10pt.
- Row 4: counts row — fill=`#7F7F7F`, font yellow, bold, size 11pt; cell value = sum of option counts per cat.
- Row 5+: option rows — fill=`#7F7F7F`, font white `#FFFFFF`, size 10pt; cell value = pct (number_format `0.0%`); DataBarRule applied to each cat column over the option-row range, color `#404040`.
- Col A: 2-char-width margin (no content).
- Col B: legend column — "Observaciones" in counts row, options in option rows; fill=`#7F7F7F`, label-aligned right; counts cell font yellow, option cells font white.
- Col C+: data cells (cat columns per breakdown). Spacer column inserted between breakdown panels.
- Column widths: A=2, B=18, data cols=14.

### `ole_png_renderer.render_table_preview_png(source_chart, breakdown_groups: list[str], w_emu: int, h_emu: int) -> bytes`

PIL renderer that draws the same logical layout to a PNG canvas sized at `(w_emu // 9525, h_emu // 9525)` pixels (96 DPI). Renders fills, text (Calibri if available, else default), and data bars as filled rectangles scaled by pct. Returns PNG bytes. Empty breakdown_groups → white canvas (no crash).

### `ole_embedder.embed_ole_xlsx_with_preview(slide, x, y, w, h, xlsx_bytes, png_bytes) -> None`

Adds three artifacts to the pptx:
1. `/ppt/embeddings/oleObjectN.xlsx` Part (content_type = `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`).
2. `/ppt/media/imageN.png` Part (PNG).
3. Slide relationships: `oleObject` rel to xlsx, `image` rel to png.
4. Slide XML appended a `<p:graphicFrame>` containing `<p:oleObj progId="Excel.Sheet.12">` with embedded `<p:pic>` referencing the PNG via `<a:blip r:embed="<imgRid>"/>`.

The graphicFrame's `<p:xfrm>` and the inner `<p:pic>` `<a:xfrm>` both reflect the (x, y, w, h) EMU bbox.

### `ole_table_renderer.render(slide, element, ctx) -> None`

Resolves position, fetches `source_chart` from `ctx.slide_config.charts[chart_ref_index]`, then calls the three helpers in sequence. No fallback logic — if any sub-step fails, log error and skip.

### `pattern_renderer` changes

- `_KIND_RENDERERS["ole_table"] = "aurum_encuestas.element_renderers.ole_table_renderer"` added.
- `_synthesize_table_element` returns `{"kind": "ole_table", ...}` (was `"table"`); drops `structure` and `style_overrides` keys (no longer used).
- The peek block in `render_pattern` is unchanged — it already detects `chart_type == "TABLE_WITH_MINIBARS"` AND real breakdown_ids.

## Dependencies

New dep: `Pillow >= 10.0`. Verify the existing `backend/requirements.txt` then append.

Existing deps used: `openpyxl` (already pulled in by `xlsx_parser.py`), `python-pptx` (already core), `lxml` (already a python-pptx transitive dep).

## Testing strategy

### Backend

`backend/tests/test_xlsx_builder.py`:
- `test_builds_single_panel_layout` — 1 bd × 2 cats × 2 options. Assert merged group_header cells, cat header row, counts row, option rows, DataBarRule applied to option-row range.
- `test_builds_multi_panel_layout` — 3 bds (Edad/Sexo/NSE). Assert spacer columns between panels; merged group_headers per bd.
- `test_data_bar_rule_color_dark` — assert `DataBarRule.color == "404040"`.
- `test_label_col_has_observaciones_and_options` — assert col B row 4 == "Observaciones"; rows 5+ contain each option string.
- `test_empty_breakdown_groups_returns_empty_xlsx` — no rows, no crash.

`backend/tests/test_ole_png_renderer.py`:
- `test_returns_png_bytes` — bytes start with `b"\x89PNG"`.
- `test_size_matches_emu_bbox` — `Image.open(BytesIO(png)).size == (w_emu // 9525, h_emu // 9525)`.
- `test_empty_breakdown_renders_white_image` — no crash, returns valid PNG.
- `test_uses_default_font_when_calibri_missing` — monkeypatch ImageFont.truetype to raise IOError; renderer still produces bytes.

`backend/tests/test_ole_embedder.py`:
- `test_embedded_xlsx_part_added` — after embed, package iter_parts has `/ppt/embeddings/oleObject1.xlsx` with CT_XLSX content_type.
- `test_image_part_added` — `/ppt/media/imageN.png` present.
- `test_relationships_added_to_slide_part` — slide.part.rels contains OLE_OBJECT + IMAGE rels.
- `test_graphic_frame_shape_appended` — slide.shapes has new graphicFrame; XML contains `<p:oleObj progId="Excel.Sheet.12">` and `<a:blip r:embed=...>`.
- `test_multiple_embeds_get_distinct_partnames` — calling twice produces oleObject1.xlsx + oleObject2.xlsx.

`backend/tests/test_ole_table_renderer.py`:
- `test_render_full_pipeline_creates_xlsx_image_and_shape` — integration: builds a SimpleNamespace source_chart, calls `render`, asserts xlsx part + PNG part + graphicFrame all present.

`backend/tests/test_pattern_renderer.py` append:
- `test_synthesize_table_element_kind_is_ole_table` — after Fase C, `_synthesize_table_element` returns `kind == "ole_table"` (was `"table"`).
- `test_kind_ole_table_routes_to_ole_table_renderer` — dispatch through `_KIND_RENDERERS["ole_table"]` resolves to the module.
- Existing test `test_chart_with_table_type_routes_to_table_renderer` adapts: now asserts shape has the graphicFrame (not python-pptx table).

### Pre-existing tests to adapt

- `test_table_renderer.py` — entire file becomes inert for the dispatch path (its tests still pass because they call `_render_segmented_breakdowns` directly). Keep file unchanged.
- `test_render_e2e.py::test_e2e_table_with_minibars_renders_single_panel_table` — after Fase C, the assertion `sh.has_table` becomes false (there's no python-pptx table). Replace with `assert any(sh.shape_type == 13 ... or "oleObj" in sh._element.xml for sh in s.shapes)` or similar. Plan handles the adaptation.

## File map

New backend modules:
- `backend/aurum_encuestas/element_renderers/xlsx_builder.py`
- `backend/aurum_encuestas/element_renderers/ole_png_renderer.py`
- `backend/aurum_encuestas/element_renderers/ole_embedder.py`
- `backend/aurum_encuestas/element_renderers/ole_table_renderer.py`

Modified:
- `backend/aurum_encuestas/pattern_renderer.py` — `_KIND_RENDERERS` adds `"ole_table"`; `_synthesize_table_element` returns `kind="ole_table"`.
- `backend/requirements.txt` — add `Pillow>=10.0`.
- `backend/tests/test_pattern_renderer.py` — adapt and append.
- `backend/tests/test_render_e2e.py` — adapt assertion for graphicFrame instead of has_table.

New test files:
- `backend/tests/test_xlsx_builder.py`
- `backend/tests/test_ole_png_renderer.py`
- `backend/tests/test_ole_embedder.py`
- `backend/tests/test_ole_table_renderer.py`

Untouched:
- `backend/aurum_encuestas/element_renderers/table_renderer.py` (legacy after Fase C; no live dispatch hits it).
- Frontend: zero changes. UI stays identical.

## Open risks

1. **Pillow font availability.** Calibri is rarely installed on Linux CI. PIL falls back to bitmap default which renders visually different. Mitigation: bundle a `Calibri.ttf` (license-permitted alternative `LiberationSans-Regular.ttf`) in `backend/aurum_encuestas/assets/` and load via explicit path. Plan must include the font drop.
2. **OLE shape XML rendering across PowerPoint platforms.** Mac, Windows, web each handle OLE differently. The XML structure used here is the standard Office Open XML form and should work cross-Office. LibreOffice may ignore the OLE entirely — viewer sees only the PNG (acceptable per decision Q4).
3. **PNG preview stale after user edits via OLE.** The auto-generated PowerPoint thumbnail does update when Excel closes; our embedded custom preview does not. Acceptable: documented Office behavior. If problematic later, drop the custom preview and let PowerPoint render its own thumbnail.
4. **File size growth.** ~15-30 KB per xlsx + 50-200 KB per PNG → roughly 70-slide × 30-table deck = +5-7 MB. Acceptable.
5. **`_next_partname` not concurrency-safe.** Single-threaded `pptx_generator`; not a real risk today.
6. **DataBarRule rendering width**. PowerPoint's OLE auto-thumbnail may not show data bars at the full width Excel uses natively; users see the PIL-rendered PNG instead, which matches design fidelity.
7. **`embed_ole_object` API in python-pptx**. We use direct lxml XML manipulation rather than python-pptx's `slide.shapes.add_ole_object` (which only supports icon previews). Plan locks lxml-direct approach.
8. **Test fixture complexity for OLE shapes**. python-pptx does not natively introspect oleObj shapes. Tests assert by parsing the slide XML for `<p:oleObj>` and `<a:blip r:embed>` elements.
