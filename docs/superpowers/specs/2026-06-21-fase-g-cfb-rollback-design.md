# Fase G — CFB CompObj Header Fix + Tree Revert Design Spec

**Date:** 2026-06-21
**Status:** Approved (post-Fase F investigation) → ready for SDD execution
**Branch base:** `main` at `1c8ec10` (post Fase F merge)

## Goal

Fix two bugs surfaced after Fase F merged. Investigation report at
`.git/sdd/post-fase-f-investigation.md` (medium-high confidence findings).

1. **Bug 1 (Mac "Reparar")**: `_build_compobj_stream` writes first 12 bytes
   wrong. Pre-existing since Fase E. Real Office writes
   `01 00 FE FF | 00000A03 | FFFFFFFF`; we write
   `FE FF 00 00 | 00000A03 | FF 00 00 00`. Three fields wrong.
2. **Bug 3 (OLE double-click broken — regression)**: F1's balanced tree
   produces RED node placement that violates RB black-height invariants.
   Mac Excel.app's stricter CFB parser rejects activation. Fase E
   right-leaning all-BLACK chain was empirically tolerated.

## Non-Goals

- True red-black tree construction (Option B from report — keep for future
  if revert insufficient).
- Re-implementing OOXML mc:AlternateContent (untouched, byte-identical E↔F).
- Frontend changes.
- Style guide / classifier / pattern changes (Bug 2 resolved by user wiping
  `~/.aurum/training/style_guide.json` + BUILTIN priority -10 from Fase F).

## Locked decisions

1. **Bug 1**: Pure constant fix in `_build_compobj_stream` lines 47-72.
   Match real Office bytes verbatim.
2. **Bug 3**: Revert `_assign_balanced_tree` → Fase E right-leaning all-BLACK
   chain. KEEP `_sort_dir_entries_indices` (sort harmless and per-spec).
   Root entry's `child` → physical slot 1 (smallest in sort order).

## Architecture

```
cfb_writer._build_compobj_stream:
   parts[0] = b"\x01\x00\xFE\xFF"       # Version + Reserved + ByteOrder
   parts[1] = pack("<I", 0x00000A03)    # Version DWORD
   parts[2] = pack("<I", 0xFFFFFFFF)    # Reserved2
   parts[3..] unchanged                 # CLSID + AnsiUserType + ...

cfb_writer dir entry construction:
   sorted_specs = sort_by_msfb_rule(specs)   # KEEP F1 sort
   entries[0] Root: child = 1
   for phys_slot in 1..N:
       entries[phys_slot] = name=sorted_specs[phys_slot-1].name,
                            color = 1 (BLACK),
                            left_sib = NOSTREAM,
                            right_sib = phys_slot + 1 if not last else NOSTREAM
   # Remove _assign_balanced_tree call entirely.
```

## Component contracts

### `cfb_writer._build_compobj_stream() -> bytes`

First 28 bytes match real Office Equation.3 sample header layout:
- `01 00 FE FF` (4B): Version + Reserved + ByteOrder LE marker
- `03 0A 00 00` (4B): Version DWORD
- `FF FF FF FF` (4B): Reserved2
- 16B: Excel.Sheet.12 CLSID `{00020820-0000-0000-C000-000000000046}`

Tail (AnsiUserType, AnsiClipboardFormat, UnicodeMarker, etc.) unchanged.

### `cfb_writer.build_excel_ole_cfb(xlsx_bytes) -> bytes`

Signature unchanged. Dir tree shape: right-leaning chain in MS-CFB sort
order, all BLACK. Root.child = 1.

## Testing strategy

`backend/tests/test_cfb_writer.py`:

- **NEW** `test_compobj_header_matches_real_office`:
  ```python
  cfb = build_excel_ole_cfb(_make_xlsx_bytes())
  ole = olefile.OleFileIO(BytesIO(cfb))
  co = ole.openstream("\x01CompObj").read()
  assert co[:4] == b"\x01\x00\xFE\xFF"
  assert co[8:12] == b"\xFF\xFF\xFF\xFF"
  ```
- **NEW** `test_dir_tree_is_right_leaning_all_black_chain` (revised — replaces
  Fase F balanced-tree assertion):
  ```python
  cfb = build_excel_ole_cfb(_make_xlsx_bytes())
  ole = olefile.OleFileIO(BytesIO(cfb))
  # Walk siblings from Root.child via right_sib chain
  cur = ole.direntries[0].sid_child
  while cur != 0xFFFFFFFF:
      e = ole.direntries[cur]
      assert e.color == 1  # BLACK
      assert e.sid_left == 0xFFFFFFFF
      cur = e.sid_right
  ```
- **REMOVE** Fase F's `test_dir_tree_balanced_depth_bounded` (asserted
  depth ≤ ceil(log2(N+1))+1 — incompatible with chain shape).
- **KEEP** Fase F's `test_dir_entries_sorted_by_msfb_rule` (sort behavior
  preserved).

## File map

Modified:
- `backend/aurum_encuestas/element_renderers/cfb_writer.py`
- `backend/tests/test_cfb_writer.py`

Untouched:
- ALL F2/F3/F4 work (xlsx_builder, ole_png_renderer, style_guide, classifier).
- ole_embedder, ole_table_renderer (already byte-identical E↔F).

## Open risks

1. **Mac smoke test required**: All test evidence is structural; only Mac
   PowerPoint Mac OLE activation flow proves the fix. Mitigation: user
   regenerates + tests double-click after merge.
2. **Reverting balanced tree leaves us spec-noncompliant**: MS-CFB §2.6.4
   technically requires RB tree. Empirical evidence is the all-BLACK chain
   is tolerated. If Mac PowerPoint changes its parser, this could regress.
   Mitigation: comment explaining the deviation; Option B (real RB) is
   reserved for future if needed.
3. **Investigation report confidence is medium for Bug 3**: cannot rule
   out Excel.app `Workbook` stream expectation. Mitigation: user smoke
   test after merge confirms or invalidates.
