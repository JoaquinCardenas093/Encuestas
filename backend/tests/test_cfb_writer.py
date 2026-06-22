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
