# Fase G — CFB CompObj Header Fix + Tree Revert Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Bug 1 (CompObj header bytes pre-existing wrong) + Bug 3 (Fase F balanced tree breaks Mac OLE activation) per investigation report `.git/sdd/post-fase-f-investigation.md`.

**Architecture:** Pure constant fix in CompObj header + revert tree construction to Fase E right-leaning all-BLACK chain while keeping Fase F sort.

**Tech Stack:** Python 3.11, struct, olefile (test dep).

## Global Constraints

- Python 3.11. Run tests via `cd backend && arch -arm64 .venv/bin/pytest -q`.
- `_build_compobj_stream` first 12 bytes = `01 00 FE FF` + `03 0A 00 00` + `FF FF FF FF`. Tail unchanged.
- Dir tree: right-leaning chain in MS-CFB sort order, all BLACK, Root.child = phys_slot 1.
- KEEP `_sort_dir_entries_indices` from Fase F.
- REMOVE `_assign_balanced_tree` (or stop calling it).
- `build_excel_ole_cfb` signature unchanged.
- Add 2 reproducer tests verbatim from investigation report Section "Reproducible test".
- Remove `test_dir_tree_balanced_depth_bounded` (incompatible with chain shape).
- KEEP `test_dir_entries_sorted_by_msfb_rule`.

---

### Task 1: Fix CompObj header bytes

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/cfb_writer.py:47-72`
- Test: `backend/tests/test_cfb_writer.py`

**Interfaces:**
- Consumes: nothing (pure constant fix)
- Produces: `_build_compobj_stream()` returns bytes starting with `01 00 FE FF | 03 0A 00 00 | FF FF FF FF | <16B Excel CLSID>` then unchanged tail.

- [ ] **Step 1: Write failing test**

Add to `backend/tests/test_cfb_writer.py`:
```python
def test_compobj_header_matches_real_office():
    """Office-generated CompObj starts with 01 00 FE FF [version DWORD]
    FF FF FF FF [CLSID]. Verifies first 12 bytes match real Office layout."""
    cfb = build_excel_ole_cfb(_make_xlsx_bytes())
    ole = olefile.OleFileIO(BytesIO(cfb))
    co = ole.openstream("\x01CompObj").read()
    assert co[:4] == b"\x01\x00\xFE\xFF", f"CompObj[0:4]={co[:4].hex()}"
    assert co[8:12] == b"\xFF\xFF\xFF\xFF", f"CompObj[8:12]={co[8:12].hex()}"
    ole.close()
```

- [ ] **Step 2: Run test → expect FAIL**

`cd backend && arch -arm64 .venv/bin/pytest tests/test_cfb_writer.py::test_compobj_header_matches_real_office -v`
Expected: FAIL — current bytes `feff0000` and `ff000000`.

- [ ] **Step 3: Fix `_build_compobj_stream` lines 47-72**

Read current implementation. Replace first 3 `parts.append(struct.pack(...))` for the header with:
```python
parts.append(b"\x01\x00\xFE\xFF")                # 4B Version+Reserved+ByteOrder
parts.append(struct.pack("<I", 0x00000A03))      # 4B Version DWORD (unchanged)
parts.append(struct.pack("<I", 0xFFFFFFFF))      # 4B Reserved2 (was 0x000000FF)
```

CLSID + AnsiUserType + AnsiClipboardFormat + UnicodeMarker etc. tail unchanged.

- [ ] **Step 4: Run new test → PASS**

`cd backend && arch -arm64 .venv/bin/pytest tests/test_cfb_writer.py::test_compobj_header_matches_real_office -v`

- [ ] **Step 5: Run full cfb_writer suite → all PASS**

`cd backend && arch -arm64 .venv/bin/pytest tests/test_cfb_writer.py -q`

- [ ] **Step 6: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/cfb_writer.py backend/tests/test_cfb_writer.py
git commit -m "fix(cfb_writer): correct CompObj header bytes to match real Office output"
```

---

### Task 2: Revert balanced tree → Fase E right-leaning all-BLACK chain

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/cfb_writer.py` (tree-construction block + remove/orphan `_assign_balanced_tree`)
- Test: `backend/tests/test_cfb_writer.py` (add chain assertion, remove balanced assertion)

**Interfaces:**
- Consumes: `_sort_dir_entries_indices` (KEEP, Fase F sort behavior preserved)
- Produces: `build_excel_ole_cfb` output with dir tree as right-leaning all-BLACK chain in MS-CFB sort order. Root.child = phys_slot 1. Each entry.color = 1 (BLACK), left_sib = NOSTREAM (0xFFFFFFFF), right_sib = next or NOSTREAM.

- [ ] **Step 1: Write failing test**

Add to `backend/tests/test_cfb_writer.py`:
```python
def test_dir_tree_is_right_leaning_all_black_chain():
    """Mac OLE activation tolerates right-leaning all-BLACK chain (Fase E
    baseline). Fase F's depth-alternating colors broke double-click on Mac."""
    NIL = 0xFFFFFFFF
    cfb = build_excel_ole_cfb(_make_xlsx_bytes())
    ole = olefile.OleFileIO(BytesIO(cfb))
    cur = ole.direntries[0].sid_child
    assert cur != NIL, "Root.child must point to first non-root entry"
    seen = 0
    while cur != NIL:
        e = ole.direntries[cur]
        assert e.color == 1, f"entry {cur} color must be BLACK (1), got {e.color}"
        assert e.sid_left == NIL, f"entry {cur} left_sib must be NIL"
        cur = e.sid_right
        seen += 1
        assert seen <= 10, "chain too long — likely loop"
    assert seen == 4, f"expected 4 entries in chain, got {seen}"
    ole.close()
```

Also REMOVE the existing `test_dir_tree_balanced_depth_bounded` test from the same file (was Fase F-specific — now incompatible).

- [ ] **Step 2: Run new test → FAIL**

`cd backend && arch -arm64 .venv/bin/pytest tests/test_cfb_writer.py::test_dir_tree_is_right_leaning_all_black_chain -v`
Expected: FAIL — Fase F's depth-alternating colors produce RED nodes.

- [ ] **Step 3: Revert tree construction in `build_excel_ole_cfb`**

Read current implementation around lines ~263-330. Replace the block that calls `_assign_balanced_tree(...)` and uses `sib_color.get(...)` with:

```python
# Right-leaning all-BLACK chain in MS-CFB sort order.
# Empirically tolerated by Mac OLE activation (Fase E baseline b475c3e).
# Fase F's depth-alternating RB-approximation broke Mac Excel.app
# double-click; reverted here. See post-fase-f-investigation.md.
sorted_indices = _sort_dir_entries_indices(specs)
sorted_specs = [specs[i] for i in sorted_indices]
n_non_root = len(sorted_specs)

entries: list[bytes] = []
entries.append(_dir_entry(
    name="Root Entry",
    entry_type=5,
    color=1,
    left_sib=NOSTREAM,
    right_sib=NOSTREAM,
    child=1,                                     # first non-root slot
    clsid=EXCEL_CLSID,
    start_sector=mini_container_start,
    size=mini_container_size,
))
for phys_slot, (name, etype, clsid, start, size) in enumerate(sorted_specs, start=1):
    right = phys_slot + 1 if phys_slot < n_non_root else NOSTREAM
    entries.append(_dir_entry(
        name=name,
        entry_type=etype,
        color=1,                                  # BLACK
        left_sib=NOSTREAM,
        right_sib=right,
        child=NOSTREAM,
        clsid=clsid,
        start_sector=start,
        size=size,
    ))
```

Match exact variable names + `_dir_entry` signature from current source — adjust if shape differs.

- [ ] **Step 4: Drop or orphan `_assign_balanced_tree`**

Delete the function body OR leave a `# noqa: deprecated` stub. Cleaner: delete entirely along with any test referencing it.

- [ ] **Step 5: Run new chain test → PASS**

`cd backend && arch -arm64 .venv/bin/pytest tests/test_cfb_writer.py::test_dir_tree_is_right_leaning_all_black_chain -v`

- [ ] **Step 6: Run full cfb_writer suite → PASS**

`cd backend && arch -arm64 .venv/bin/pytest tests/test_cfb_writer.py -q`

Should pass (after removing `test_dir_tree_balanced_depth_bounded`). KEEP `test_dir_entries_sorted_by_msfb_rule`.

- [ ] **Step 7: Run full backend suite → PASS**

`cd backend && arch -arm64 .venv/bin/pytest -q`

Expected: 355 passed (or 354 since balanced test removed and chain test added — net 0 / +0 depending on Fase F count).

- [ ] **Step 8: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/cfb_writer.py backend/tests/test_cfb_writer.py
git commit -m "revert(cfb_writer): right-leaning all-BLACK dir chain (Fase E baseline) — fixes Mac OLE activation regression"
```
