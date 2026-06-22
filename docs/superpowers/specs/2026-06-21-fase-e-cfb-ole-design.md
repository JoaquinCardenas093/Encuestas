# Fase E — CFB OLE Wrap + Pattern Cleanup Design Spec

**Date:** 2026-06-21
**Status:** Approved (brainstorming) → ready for writing-plans
**Branch base:** `main` at `9fb0fca` (post Fase D merge)

## Goal

Fix two bugs reported after Fase D ship:

1. **Excel opens blank "Reparado"**: PowerPoint extracts the embedded `oleObject{N}.xlsx` but Excel rejects the raw `.xlsx` Open XML zip when invoked via OLE and produces an empty repaired sheet. Real PowerPoint OLE wraps the xlsx inside a CFB (Compound File Binary) container with `\x01CompObj` (progId=Excel.Sheet.12) + `\x01Ole` + `\x03ObjInfo` + `Package` streams. Implement a minimal CFB writer and switch `ole_embedder` to embed the CFB-wrapped blob as `oleObject{N}.bin` with content type `application/vnd.openxmlformats-officedocument.oleObject`.

2. **"Distribución general / segmentada" split + empty left table**: the active AI-generated style_guide pattern contains 4 elements: a text shape "Distribución general", a left PIE chart, a text shape "Distribución segmentada", and the OLE table on the right. The split came from a copy-paste pattern example in `llm_client.py` system prompt. Manually edit the active `~/.aurum/training/style_guide.json` to remove the split (keep only the table, reposition full-width). Edit the prompt example so future regenerated style_guides emit a single-element pattern.

## Non-Goals

- Charts (PIE, PIE_GROUPED, BAR_HORIZONTAL, BAR_HORIZONTAL_GROUPED): untouched.
- Frontend: zero changes.
- Re-training the corpus via `analyze_training_corpus`: user does manual edit per decision.
- Versioning the active `style_guide.json` in git: it lives under `~/.aurum/` and is user-local.

## Locked decisions

1. **CFB writer minimal hardcoded** (~300-400 LOC new module). No external dep at runtime. `olefile` added as dev-only test dependency for round-trip verification.
2. **Excel.Sheet.12** progId + CLSID `{00020820-0000-0000-C000-000000000046}` hardcoded in CompObj stream.
3. **`Package` stream**: raw xlsx ZIP blob, no prefix. Excel auto-detects Open XML by magic.
4. **Partname swap**: `oleObject{N}.xlsx` → `oleObject{N}.bin`. Content type `application/vnd.openxmlformats-officedocument.oleObject` (NOT the xlsx content type).
5. **Manual style_guide edit** for current install + prompt fix for future regenerations.

## Architecture

```
ole_embedder.embed_ole_xlsx_with_preview()
  └─ cfb_writer.build_excel_ole_cfb(xlsx_bytes) → bytes  ← NEW
       returns CFB blob with Excel OLE streams:
         \x01Ole       (20 bytes OLE version header)
         \x01CompObj   (CompObj header: progId Excel.Sheet.12 + CLSID)
         \x03ObjInfo   (6 bytes object info)
         Package       (raw xlsx blob)
  └─ Add CFB blob as Part /ppt/embeddings/oleObject{N}.bin
       content_type = "application/vnd.openxmlformats-officedocument.oleObject"
  └─ Slide rel to OLE_OBJECT (unchanged)
  └─ graphicFrame XML (unchanged from Fase D mc:AlternateContent)
```

### Style guide cleanup

Manual edit of `~/.aurum/training/style_guide.json`:
- Locate pattern with elements containing the strings "Distribución general" + "Distribución segmentada".
- Remove the 3 non-table elements (2 text + 1 chart).
- Reposition the remaining `kind=table` (or `kind=chart` with `chart_type=TABLE_WITH_MINIBARS`) element to `x_rel=0.04, y_rel=0.18, w_rel=0.92, h_rel=0.70`.
- Save back.

Prompt edit at `backend/aurum_encuestas/llm_client.py` (around the `EJEMPLO COMPLETO DE 1 PATTERN BIEN ARMADO` block):
- Replace the 4-element split example with a single-element `kind=chart, chart_type=TABLE_WITH_MINIBARS` pattern occupying full slide width.

## Component contracts

### `cfb_writer.build_excel_ole_cfb(xlsx_bytes: bytes) -> bytes`

Produces a CFB binary that satisfies these invariants:
- Starts with `D0 CF 11 E0 A1 B1 1A E1` magic.
- 512-byte sector size (sector shift = 9, mini sector shift = 6).
- Major version 3, minor version 0x3E.
- Root storage CLSID = `{00020820-0000-0000-C000-000000000046}` (Excel 12 worksheet).
- Has 4 streams: `\x01Ole`, `\x01CompObj`, `\x03ObjInfo`, `Package`.
- `\x01Ole` is exactly 20 bytes: version (4) + flags (4) + linked-update-options (4) + reserved (8).
- `\x01CompObj` per [MS-OLEDS] §2.3.6: 28-byte header + length-prefixed `AnsiUserType` ("Microsoft Excel Worksheet") + length-prefixed `AnsiClipboardFormatHeader` (-1, 0) + length-prefixed `Reserved1` ("") + UnicodeMarker (0x71B239F4) + length-prefixed `UnicodeUserType` + length-prefixed `UnicodeClipboardFormat`.

  For simplicity hardcode the well-known Excel CompObj bytes from a known-good sample.
- `\x03ObjInfo` is 6 bytes per [MS-OLEDS] §2.3.7: `0x0040 0x0009 0x0000` (OBJECT_TYPE_EMBEDDED + flags).
- `Package` stream is the raw xlsx blob unchanged. Excel detects Open XML via ZIP magic.

Round-trip via `olefile.OleFileIO(BytesIO(cfb))` must succeed without warnings; `listdir()` must return all 4 streams; `Package` blob extracted must equal input `xlsx_bytes`.

### `ole_embedder.embed_ole_xlsx_with_preview(...)` — modified

- Build CFB via `build_excel_ole_cfb(xlsx_bytes)`.
- Use partname template `/ppt/embeddings/oleObject{}.bin`.
- Use content type `"application/vnd.openxmlformats-officedocument.oleObject"`.
- Everything else (rels, graphicFrame XML, mc:AlternateContent) unchanged from Fase D.

## Testing strategy

### Backend tests

`backend/tests/test_cfb_writer.py` (NEW):
- `test_cfb_starts_with_magic` — bytes[:8] == CFB_MAGIC.
- `test_olefile_can_parse_output` — `olefile.OleFileIO(BytesIO(cfb))` doesn't raise.
- `test_cfb_contains_four_streams` — listdir returns `\x01Ole`, `\x01CompObj`, `\x03ObjInfo`, `Package`.
- `test_compobj_contains_progid` — `Microsoft Excel Worksheet` ASCII substring present in stream bytes.
- `test_package_stream_round_trips_xlsx` — extracted Package stream == input xlsx bytes.
- `test_root_clsid_is_excel` — root entry CLSID matches Excel 12 GUID.

`backend/tests/test_ole_embedder.py` (adapt):
- Existing `test_embedded_xlsx_part_added` → rename to `test_embedded_ole_bin_part_added`. Assert partname ends with `.bin`, not `.xlsx`.
- Adapt content type assertion to `application/vnd.openxmlformats-officedocument.oleObject`.
- `test_round_trip_save_and_reopen_succeeds` keeps; but assert the bin blob extracted from the saved pptx, when re-parsed by `olefile`, has the 4 streams.

### Dev dep

`backend/pyproject.toml`: add `olefile>=0.46` to `[project.optional-dependencies] dev`.

### Manual smoke

After plan ships:
1. Regenerate `.pptx` via app.
2. Open in PowerPoint Mac. Verify no repair prompt.
3. Double-click OLE shape. Verify Excel opens with actual table data visible (NOT blank).
4. Verify slide still shows only one OLE table full-width (no "Distribución general" + empty left table).

## File map

New backend:
- `backend/aurum_encuestas/element_renderers/cfb_writer.py`
- `backend/tests/test_cfb_writer.py`

Modified backend:
- `backend/aurum_encuestas/element_renderers/ole_embedder.py`
- `backend/aurum_encuestas/llm_client.py`
- `backend/pyproject.toml`
- `backend/tests/test_ole_embedder.py`

Manual edit (not git-tracked):
- `~/.aurum/training/style_guide.json`

Untouched:
- Frontend
- `xlsx_builder.py`, `ole_png_renderer.py`, `ole_table_renderer.py`
- `pattern_renderer.py`, `chart_renderer.py`, `table_renderer.py`

## Open risks

1. **CFB writer correctness**: spec is finicky binary format. Mitigation: hardcode well-known CompObj bytes from a real Excel sample, structure FAT/dir using deterministic 4-stream layout. olefile round-trip catches structural errors.

2. **CompObj stream exact byte layout**: [MS-OLEDS] §2.3.6 specifies header + length-prefixed strings + UnicodeMarker. Subtle off-by-one corrupts the stream. Mitigation: derive expected bytes from a real Excel OLE bin sample using `oletools` or hex dump; encode as static byte literal in the writer.

3. **CFB sector layout**: header (sector 0) + FAT sectors + dir sectors + stream sectors. For 4 small streams + one large Package stream, layout is: sector 0 header → sector 1 FAT → sector 2 dir → sector 3+ streams. With `Package` blob ~5KB, total sectors ≈ 16. Mini-FAT may or may not be needed; if all streams < 4096 then mini-FAT used, else normal FAT.

4. **olefile dev-only dep**: not installed in production runtime. Code under test imports cfb_writer; the test file imports olefile. Production usage path never touches olefile.

5. **Style guide json edit may not match**: user's active style_guide.json could have any naming for the pattern. Edit is a manual user step, not automated. Plan provides instructions only.

6. **Prompt edit affects future style_guides**: any user who re-runs corpus analysis after Fase E will get the single-element pattern. Pre-existing style_guides on disk remain unchanged.
