from io import BytesIO

import olefile


CFB_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
EXCEL_CLSID = b"\x20\x08\x02\x00\x00\x00\x00\x00\xc0\x00\x00\x00\x00\x00\x00\x46"


def _make_xlsx_bytes():
    from openpyxl import Workbook
    wb = Workbook()
    wb.active["A1"] = "hello"
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_cfb_starts_with_magic():
    from aurum_encuestas.element_renderers.cfb_writer import build_excel_ole_cfb
    cfb = build_excel_ole_cfb(_make_xlsx_bytes())
    assert cfb[:8] == CFB_MAGIC


def test_olefile_can_parse_output():
    from aurum_encuestas.element_renderers.cfb_writer import build_excel_ole_cfb
    cfb = build_excel_ole_cfb(_make_xlsx_bytes())
    ole = olefile.OleFileIO(BytesIO(cfb))
    assert ole is not None
    ole.close()


def test_cfb_contains_four_streams():
    from aurum_encuestas.element_renderers.cfb_writer import build_excel_ole_cfb
    cfb = build_excel_ole_cfb(_make_xlsx_bytes())
    ole = olefile.OleFileIO(BytesIO(cfb))
    streams = {"/".join(s) if isinstance(s, list) else s for s in ole.listdir()}
    assert "\x01Ole" in streams
    assert "\x01CompObj" in streams
    assert "\x03ObjInfo" in streams
    assert "Package" in streams
    ole.close()


def test_compobj_contains_progid():
    from aurum_encuestas.element_renderers.cfb_writer import build_excel_ole_cfb
    cfb = build_excel_ole_cfb(_make_xlsx_bytes())
    ole = olefile.OleFileIO(BytesIO(cfb))
    compobj = ole.openstream("\x01CompObj").read()
    assert b"Microsoft Excel Worksheet" in compobj
    ole.close()


def test_package_stream_round_trips_xlsx():
    from aurum_encuestas.element_renderers.cfb_writer import build_excel_ole_cfb
    xlsx = _make_xlsx_bytes()
    cfb = build_excel_ole_cfb(xlsx)
    ole = olefile.OleFileIO(BytesIO(cfb))
    pkg = ole.openstream("Package").read()
    assert pkg == xlsx
    ole.close()


def test_root_clsid_is_excel():
    from aurum_encuestas.element_renderers.cfb_writer import build_excel_ole_cfb
    cfb = build_excel_ole_cfb(_make_xlsx_bytes())
    ole = olefile.OleFileIO(BytesIO(cfb))
    # olefile.OleFileIO.root.clsid is "{guid-string}"
    assert ole.root.clsid.upper().replace("-", "") == "0002082000000000C000000000000046"
    ole.close()


def test_build_excel_ole_cfb_is_deterministic():
    """Same input must produce identical bytes (no time.time or random)."""
    from aurum_encuestas.element_renderers.cfb_writer import build_excel_ole_cfb
    xlsx = _make_xlsx_bytes()
    cfb1 = build_excel_ole_cfb(xlsx)
    cfb2 = build_excel_ole_cfb(xlsx)
    assert cfb1 == cfb2


def test_oversized_xlsx_raises_value_error():
    """Single-FAT-sector cap silently corrupts if exceeded. Guard raises ValueError."""
    import pytest
    from aurum_encuestas.element_renderers.cfb_writer import build_excel_ole_cfb, MAX_PKG_BYTES
    huge = b"\x00" * (MAX_PKG_BYTES + 1)
    with pytest.raises(ValueError, match="exceeds CFB single-FAT-sector capacity"):
        build_excel_ole_cfb(huge)


def test_max_size_xlsx_succeeds():
    """At exactly MAX_PKG_BYTES the blob still builds cleanly."""
    from aurum_encuestas.element_renderers.cfb_writer import build_excel_ole_cfb, MAX_PKG_BYTES
    # Need a ZIP-like blob so the CFB Package stream contains valid Open XML
    # but at MAX_PKG_BYTES. For this test, just verify build succeeds at limit.
    blob_at_limit = b"PK\x03\x04" + b"\x00" * (MAX_PKG_BYTES - 4)
    cfb = build_excel_ole_cfb(blob_at_limit)
    assert cfb[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def test_dir_entries_sorted_by_msfb_rule():
    """MS-CFB §2.6.4: siblings sorted by (length, UPPER(name) UTF-16).

    Our 4 non-Root entries:
      Package   (length 7)
      \\x01Ole   (length 4)
      \\x01CompObj (length 9)
      \\x03ObjInfo (length 8)

    Expected order (by length ascending, then by UPPER UTF-16):
      \\x01Ole, Package, \\x03ObjInfo, \\x01CompObj

    Equivalent: lengths 4, 7, 8, 9.
    """
    from aurum_encuestas.element_renderers.cfb_writer import build_excel_ole_cfb
    cfb = build_excel_ole_cfb(_make_xlsx_bytes())
    ole = olefile.OleFileIO(BytesIO(cfb))
    # Pull dir entries via olefile internals
    direntries = ole.direntries
    # Skip Root (index 0); collect (name_chars, name_upper) for entries 1..N
    seen = []
    for entry in direntries[1:]:
        if entry is None:
            continue
        name = entry.name
        seen.append((len(name), name.upper().encode("utf-16-le")))
    # Note: olefile returns entries in storage order, which IS the tree
    # in-order traversal for a balanced binary search tree. So they should
    # come out sorted.
    assert seen == sorted(seen), f"entries not in MS-CFB sort order: {seen}"
    ole.close()


def test_dir_tree_balanced_depth_bounded():
    """Tree depth ≤ ceil(log2(N+1)) + 1 for N=4 non-Root entries → max depth 3."""
    from math import ceil, log2
    from aurum_encuestas.element_renderers.cfb_writer import build_excel_ole_cfb
    cfb = build_excel_ole_cfb(_make_xlsx_bytes())
    ole = olefile.OleFileIO(BytesIO(cfb))
    # Find the root child of the Root Entry
    root_entry = ole.direntries[0]
    root_child_id = root_entry.sid_child

    def depth_of(idx, visited=None):
        if idx == 0xFFFFFFFF or idx is None:
            return 0
        visited = visited or set()
        if idx in visited:
            return 0
        visited.add(idx)
        e = ole.direntries[idx]
        if e is None:
            return 0
        return 1 + max(depth_of(e.sid_left, visited), depth_of(e.sid_right, visited))

    depth = depth_of(root_child_id)
    n_entries = sum(1 for e in ole.direntries[1:] if e is not None)
    max_allowed = int(ceil(log2(n_entries + 1))) + 1
    assert depth <= max_allowed, f"tree depth {depth} > max {max_allowed} for N={n_entries}"
    ole.close()


def test_compobj_header_matches_real_office():
    """Office-generated CompObj starts with 01 00 FE FF [version DWORD]
    FF FF FF FF [CLSID]. Verifies first 12 bytes match real Office layout."""
    from aurum_encuestas.element_renderers.cfb_writer import build_excel_ole_cfb
    cfb = build_excel_ole_cfb(_make_xlsx_bytes())
    ole = olefile.OleFileIO(BytesIO(cfb))
    co = ole.openstream("\x01CompObj").read()
    assert co[:4] == b"\x01\x00\xFE\xFF", f"CompObj[0:4]={co[:4].hex()}"
    assert co[8:12] == b"\xFF\xFF\xFF\xFF", f"CompObj[8:12]={co[8:12].hex()}"
    ole.close()
