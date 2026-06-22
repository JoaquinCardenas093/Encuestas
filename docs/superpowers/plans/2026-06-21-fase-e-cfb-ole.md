# Fase E — CFB OLE Wrap + Pattern Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two bugs post Fase D: (1) Excel opens blank "Reparado" when user double-clicks OLE — the embedded `.xlsx` Open XML zip is not a valid OLE blob. Wrap it in a CFB container with Excel-specific streams. (2) Slide still shows split "Distribución general"/"Distribución segmentada" + empty left table from a stale AI-generated style_guide pattern. Edit the active `style_guide.json` manually + fix the prompt example so future regenerations are clean.

**Architecture:** New module `cfb_writer.py` builds a CFB binary with the 4 Excel OLE streams (`\x01Ole`, `\x01CompObj`, `\x03ObjInfo`, `Package`). `ole_embedder` calls `build_excel_ole_cfb(xlsx_bytes)` before adding the OLE part, switches partname template from `.xlsx` to `.bin`, and uses content type `application/vnd.openxmlformats-officedocument.oleObject`. Pattern cleanup is documentation + prompt edit + manual style_guide.json edit.

**Tech Stack:** Python 3.11 stdlib only at runtime (`struct`, `io`); `olefile>=0.46` as dev dependency for round-trip tests.

## Global Constraints

- Backend Python 3.11. Tests: `cd backend && arch -arm64 .venv/bin/pytest -q`.
- CFB sector size = 512 bytes; mini sector size = 64; mini stream cutoff = 4096.
- CFB version: major=3, minor=0x3E.
- Root storage CLSID = `{00020820-0000-0000-C000-000000000046}` (Excel 12 Worksheet); encoded as 16-byte little-endian GUID `20 08 02 00 00 00 00 00 C0 00 00 00 00 00 00 46`.
- `\x01CompObj` stream contains the well-known Excel "Microsoft Excel Worksheet" descriptor.
- `Package` stream contains the raw xlsx ZIP blob (no prefix).
- `\x01Ole` stream is 20 bytes: version (4) + flags (4) + linked-update (4) + reserved (8) — all zeros except version `02 00 01 00`.
- `\x03ObjInfo` stream is 6 bytes: `40 00 09 00 00 00`.
- Partname template changes from `/ppt/embeddings/oleObject{}.xlsx` to `/ppt/embeddings/oleObject{}.bin`.
- Content type for OLE part: `application/vnd.openxmlformats-officedocument.oleObject` (NOT the xlsx CT).
- Branch base: `main` at `9fb0fca`. New branch: `feat/fase-e-cfb-ole`.

---

## File Structure

New backend:
- `backend/aurum_encuestas/element_renderers/cfb_writer.py` — minimal CFB writer.
- `backend/tests/test_cfb_writer.py` — CFB structure + olefile round-trip tests.

Modified backend:
- `backend/aurum_encuestas/element_renderers/ole_embedder.py` — call CFB writer, swap partname + content type.
- `backend/aurum_encuestas/llm_client.py` — pattern example replaced with single-element TABLE_WITH_MINIBARS.
- `backend/pyproject.toml` — add `olefile>=0.46` to dev extras.
- `backend/tests/test_ole_embedder.py` — adapt partname/CT assertions.

Documentation:
- `docs/MANUAL-STYLE-GUIDE-FIX.md` — instructions for the user to edit `~/.aurum/training/style_guide.json` manually.

Untouched:
- Frontend.
- `xlsx_builder.py`, `ole_png_renderer.py`, `ole_table_renderer.py`.
- `pattern_renderer.py`, all other renderers.

---

### Task 1: `cfb_writer` minimal CFB writer for Excel OLE

**Files:**
- Create: `backend/aurum_encuestas/element_renderers/cfb_writer.py`
- Create: `backend/tests/test_cfb_writer.py`
- Modify: `backend/pyproject.toml` (add olefile to dev extras)

**Interfaces:**
- Consumes: raw xlsx bytes.
- Produces: `build_excel_ole_cfb(xlsx_bytes: bytes) -> bytes` returning a CFB binary blob with 4 Excel OLE streams.

- [ ] **Step 1: Add olefile dev dep**

Edit `backend/pyproject.toml`. Locate `[project.optional-dependencies]` section, find `dev = [...]` list, append `"olefile>=0.46",`:

```toml
[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
  "httpx>=0.27",
  "ruff>=0.4",
  "olefile>=0.46",
]
```

Install:
```bash
cd backend && arch -arm64 .venv/bin/pip install olefile
```

- [ ] **Step 2: Write failing tests**

Create `backend/tests/test_cfb_writer.py`:

```python
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
```

- [ ] **Step 3: Run failing tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_cfb_writer.py -v
```

Expected: FAIL — module doesn't exist.

- [ ] **Step 4: Implement `cfb_writer.py`**

Create `backend/aurum_encuestas/element_renderers/cfb_writer.py`:

```python
"""Minimal CFB (Compound File Binary) writer for Excel OLE.

Spec: [MS-CFB] https://learn.microsoft.com/openspecs/windows_protocols/ms-cfb
Layout:
  Sector 0          : CFB header (512 bytes)
  Sector 1          : FAT sector — tracks sector chain types
  Sector 2          : Directory sector (4 entries × 128 bytes)
  Sector 3+         : Stream data sectors (normal FAT)
  Mini-FAT sector   : Allocates mini-stream sectors for streams < 4096 bytes
  Mini-stream sect. : Contains \\x01Ole + \\x01CompObj + \\x03ObjInfo (all < 4096)
  Normal sectors    : Package stream (xlsx blob, almost always > 4096)

Streams:
  Root entry        : CLSID = Excel.Sheet.12, points to mini-stream sectors
  \\x01Ole          : 20 bytes (version header)
  \\x01CompObj      : Excel descriptor (well-known Excel CompObj bytes)
  \\x03ObjInfo      : 6 bytes (object info flags)
  Package           : raw xlsx blob
"""

import struct
from io import BytesIO

SECTOR_SIZE = 512
MINI_SECTOR_SIZE = 64
MINI_STREAM_CUTOFF = 4096
ENDOFCHAIN = 0xFFFFFFFE
FREESECT = 0xFFFFFFFF
FATSECT = 0xFFFFFFFD
DIFSECT = 0xFFFFFFFC

CFB_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
# CLSID {00020820-0000-0000-C000-000000000046} little-endian encoded
EXCEL_CLSID = b"\x20\x08\x02\x00\x00\x00\x00\x00\xc0\x00\x00\x00\x00\x00\x00\x46"

# \x01Ole stream: version 02 00 01 00, no flags, no linked update, reserved zero (20 bytes)
OLE_STREAM = b"\x02\x00\x01\x00" + b"\x00" * 4 + b"\x00" * 4 + b"\x00" * 8

# \x03ObjInfo stream: 6 bytes (40 00 09 00 00 00)
OBJINFO_STREAM = b"\x40\x00\x09\x00\x00\x00"


def _build_compobj_stream() -> bytes:
    """Build \\x01CompObj stream per [MS-OLEDS] §2.3.6 for Excel.Sheet.12."""
    # Header: Reserved1 + Version + Reserved2 (28 bytes)
    # Reserved1 = 0xFFFE  (4 bytes BOM-ish), Version = 0x0A03 in some samples
    # Followed by length-prefixed AnsiUserType, ClipboardFormat, Reserved string,
    # UnicodeMarker, UnicodeUserType, UnicodeClipboardFormat.
    #
    # Hardcoded well-known Excel 12 CompObj bytes:
    parts = []
    # Header (28 bytes):
    # ByteOrder=0xFFFE, Version=0x0A03, Reserved1=0x000000FF, Reserved2=0x0000FFFF,
    # plus 16 bytes of Reserved
    parts.append(struct.pack("<I", 0xFFFE))                     # 4 bytes
    parts.append(struct.pack("<I", 0x0A03))                     # 4 bytes
    parts.append(struct.pack("<I", 0x000000FF))                 # 4 bytes
    # CLSID Excel.Sheet.12 (16 bytes)
    parts.append(EXCEL_CLSID)
    # AnsiUserType — length-prefixed Pascal string with NUL terminator
    user_type = b"Microsoft Excel Worksheet\x00"
    parts.append(struct.pack("<I", len(user_type)))
    parts.append(user_type)
    # AnsiClipboardFormat — 4-byte tag; -1 = standard clipboard format
    parts.append(struct.pack("<I", 0xFFFFFFFF))
    # AnsiClipboardFormatId — 4-byte (use CF_DIB = 0x00000008 for Excel)
    parts.append(struct.pack("<I", 0x00000008))
    # Reserved1 — length-prefixed string "" (4 byte length 0)
    parts.append(struct.pack("<I", 0))
    # UnicodeMarker — magic value 0x71B239F4
    parts.append(struct.pack("<I", 0x71B239F4))
    # UnicodeUserType — length-prefixed UTF-16 string
    unicode_user = "Microsoft Excel Worksheet\x00".encode("utf-16-le")
    parts.append(struct.pack("<I", len(unicode_user) // 2))
    parts.append(unicode_user)
    # UnicodeClipboardFormat — tag -1 + CF_DIB
    parts.append(struct.pack("<I", 0xFFFFFFFF))
    parts.append(struct.pack("<I", 0x00000008))
    return b"".join(parts)


COMPOBJ_STREAM = _build_compobj_stream()


def _pad_to_sector(data: bytes, sector_size: int = SECTOR_SIZE) -> bytes:
    """Pad data with zero bytes to a multiple of sector_size."""
    remainder = len(data) % sector_size
    if remainder == 0:
        return data
    return data + b"\x00" * (sector_size - remainder)


def _utf16_padded_name(name: str) -> bytes:
    """Return UTF-16-LE encoded name padded to 64 bytes (32 chars max)."""
    raw = (name + "\x00").encode("utf-16-le")
    if len(raw) > 64:
        raw = raw[:64]
    return raw + b"\x00" * (64 - len(raw))


def _dir_entry(
    name: str, entry_type: int, name_len: int,
    color: int = 0,
    left_sib: int = 0xFFFFFFFF, right_sib: int = 0xFFFFFFFF, child: int = 0xFFFFFFFF,
    clsid: bytes = b"\x00" * 16,
    start_sect: int = ENDOFCHAIN, stream_size: int = 0,
) -> bytes:
    """Build a 128-byte directory entry."""
    name_padded = _utf16_padded_name(name)
    return (
        name_padded                                       # 64 bytes
        + struct.pack("<H", name_len)                     # 2 bytes (length in bytes incl NUL)
        + struct.pack("<B", entry_type)                   # 1 byte (0=empty, 1=storage, 2=stream, 5=root)
        + struct.pack("<B", color)                        # 1 byte (0=red, 1=black)
        + struct.pack("<I", left_sib)                     # 4 bytes
        + struct.pack("<I", right_sib)                    # 4 bytes
        + struct.pack("<I", child)                        # 4 bytes
        + clsid                                           # 16 bytes
        + struct.pack("<I", 0)                            # state bits
        + struct.pack("<Q", 0)                            # creation time
        + struct.pack("<Q", 0)                            # modified time
        + struct.pack("<I", start_sect)                   # starting sector
        + struct.pack("<Q", stream_size)                  # stream size (8 bytes)
    )


def build_excel_ole_cfb(xlsx_bytes: bytes) -> bytes:
    """Build a CFB blob wrapping the xlsx as Excel.Sheet.12 OLE.

    Layout:
      sector 0      : header
      sector 1      : FAT (one sector — supports up to 128 sectors)
      sector 2      : directory (4 entries × 128 bytes = 512 bytes)
      sector 3      : mini-FAT (one sector)
      sector 4      : mini-stream container (one normal sector → 8 mini-sectors of 64 bytes)
      sector 5+     : Package stream sectors
    """
    # 1. Mini streams: \x01Ole (20 bytes) + \x01CompObj (~80 bytes) + \x03ObjInfo (6 bytes)
    #    All go into the mini-stream container.
    mini_streams = [
        ("\x01Ole", OLE_STREAM),
        ("\x01CompObj", COMPOBJ_STREAM),
        ("\x03ObjInfo", OBJINFO_STREAM),
    ]
    # Allocate mini-sectors for each, assign start_mini_sect + size.
    mini_alloc: list[tuple[str, bytes, int, int]] = []  # (name, data, start_mini_sect, size)
    next_mini = 0
    for name, data in mini_streams:
        size = len(data)
        n_mini = (size + MINI_SECTOR_SIZE - 1) // MINI_SECTOR_SIZE
        mini_alloc.append((name, data, next_mini, size))
        next_mini += n_mini

    # Build mini-stream container (concatenate, pad to MINI_SECTOR_SIZE multiples)
    mini_container = b""
    for _, data, _, _ in mini_alloc:
        chunk = _pad_to_sector(data, MINI_SECTOR_SIZE)
        mini_container += chunk
    # Pad mini container to full sector
    mini_container = _pad_to_sector(mini_container, SECTOR_SIZE)
    mini_container_n_sectors = len(mini_container) // SECTOR_SIZE
    assert mini_container_n_sectors == 1, "expected mini-container fits in 1 sector for our streams"

    # 2. Mini-FAT: one entry per mini-sector
    n_mini_used = next_mini
    minifat = []
    for stream_idx, (_, _, start_mini, size) in enumerate(mini_alloc):
        n = (size + MINI_SECTOR_SIZE - 1) // MINI_SECTOR_SIZE
        for k in range(n):
            if k == n - 1:
                minifat.append(ENDOFCHAIN)
            else:
                minifat.append(start_mini + k + 1)
    while len(minifat) < SECTOR_SIZE // 4:
        minifat.append(FREESECT)
    minifat_bytes = b"".join(struct.pack("<I", v) for v in minifat)

    # 3. Package stream as normal sectors
    package_size = len(xlsx_bytes)
    n_pkg_sectors = (package_size + SECTOR_SIZE - 1) // SECTOR_SIZE
    package_padded = _pad_to_sector(xlsx_bytes, SECTOR_SIZE)
    # Package will live in sectors starting at index 5 (after header/FAT/dir/miniFAT/miniContainer).
    PACKAGE_FIRST_SECTOR = 5
    package_chain = list(range(PACKAGE_FIRST_SECTOR, PACKAGE_FIRST_SECTOR + n_pkg_sectors))

    # 4. Sector index assignments
    #   sector 0 = header (not in FAT)
    #   sector 1 = FAT
    #   sector 2 = directory
    #   sector 3 = mini-FAT
    #   sector 4 = mini-stream container
    #   sectors 5..5+n_pkg_sectors-1 = Package stream
    FAT_SECTOR = 0          # index in FAT (sector 1 in file = FAT itself)
    DIR_SECTOR = 1
    MINIFAT_SECTOR = 2
    MINISTREAM_SECTOR = 3
    PKG_FIRST_IDX = 4

    # Build FAT: for each sector index (offset by 1 because sector 0 is header)
    # Each FAT entry tells what comes next for that sector.
    fat = [FREESECT] * (SECTOR_SIZE // 4)
    fat[FAT_SECTOR] = FATSECT                                  # sector 1 (FAT) is a FAT sector
    fat[DIR_SECTOR] = ENDOFCHAIN                               # sector 2 (dir) — last in dir chain
    fat[MINIFAT_SECTOR] = ENDOFCHAIN                           # sector 3 (mini-FAT)
    fat[MINISTREAM_SECTOR] = ENDOFCHAIN                        # sector 4 (mini-stream)
    # Package chain
    for i in range(n_pkg_sectors):
        if i == n_pkg_sectors - 1:
            fat[PKG_FIRST_IDX + i] = ENDOFCHAIN
        else:
            fat[PKG_FIRST_IDX + i] = PKG_FIRST_IDX + i + 1
    fat_bytes = b"".join(struct.pack("<I", v) for v in fat)

    # 5. Directory entries
    #   Entry 0: Root
    #   Entry 1: Package (stream, normal sectors)
    #   Entry 2: \x01Ole (mini stream)
    #   Entry 3: \x01CompObj (mini stream)
    #   Entry 4: \x03ObjInfo (mini stream)
    # Root child points to the first child in red-black tree — use Package (entry 1)
    # Pack tree as flat sibling list using right_sib chain (simplification: olefile tolerates this).
    name_len = lambda s: 2 * (len(s) + 1)
    entries = []
    # Root: type=5, points to mini-stream container, size = total mini-stream bytes
    entries.append(_dir_entry(
        name="Root Entry", entry_type=5,
        name_len=name_len("Root Entry"),
        color=1, child=1,
        clsid=EXCEL_CLSID,
        start_sect=MINISTREAM_SECTOR,
        stream_size=sum((s + MINI_SECTOR_SIZE - 1) // MINI_SECTOR_SIZE for _, _, _, s in mini_alloc) * MINI_SECTOR_SIZE,
    ))
    # Package (normal stream)
    entries.append(_dir_entry(
        name="Package", entry_type=2,
        name_len=name_len("Package"),
        color=1, right_sib=2,
        start_sect=PKG_FIRST_IDX, stream_size=package_size,
    ))
    # Mini streams
    for idx, (mname, _, start_mini, msize) in enumerate(mini_alloc, start=2):
        right = idx + 1 if idx < 4 else 0xFFFFFFFF
        entries.append(_dir_entry(
            name=mname, entry_type=2,
            name_len=name_len(mname),
            color=1, right_sib=right,
            start_sect=start_mini, stream_size=msize,
        ))
    # Pad to full sector (4 entries × 128 = 512, exactly one sector)
    dir_bytes = b"".join(entries)
    dir_bytes = _pad_to_sector(dir_bytes, SECTOR_SIZE)

    # 6. CFB Header (512 bytes)
    header = (
        CFB_MAGIC                                     # 8 bytes magic
        + b"\x00" * 16                                # CLSID (zero for header)
        + struct.pack("<H", 0x003E)                   # minor version
        + struct.pack("<H", 0x0003)                   # major version (3 = 512-byte sectors)
        + struct.pack("<H", 0xFFFE)                   # byte order (little endian)
        + struct.pack("<H", 9)                        # sector shift (2^9 = 512)
        + struct.pack("<H", 6)                        # mini sector shift (2^6 = 64)
        + b"\x00" * 6                                 # reserved
        + struct.pack("<I", 0)                        # num dir sectors (0 for v3)
        + struct.pack("<I", 1)                        # num FAT sectors
        + struct.pack("<I", DIR_SECTOR)               # first dir sector (= sector 2 in file → fat index 1)
        + struct.pack("<I", 0)                        # transaction signature
        + struct.pack("<I", MINI_STREAM_CUTOFF)       # mini stream cutoff
        + struct.pack("<I", MINIFAT_SECTOR)           # first mini-FAT sector (= sector 3 → fat index 2)
        + struct.pack("<I", 1)                        # num mini-FAT sectors
        + struct.pack("<I", ENDOFCHAIN)               # first DIFAT sector
        + struct.pack("<I", 0)                        # num DIFAT sectors
    )
    # DIFAT array (109 entries × 4 bytes = 436 bytes)
    difat = [FAT_SECTOR] + [FREESECT] * 108  # FAT lives in sector 1 → DIFAT[0] = 0 (FAT index 0)
    difat_bytes = b"".join(struct.pack("<I", v) for v in difat)
    header += difat_bytes
    # Header is now 8 + 16 + 24 + 16 + 436 = 500 → pad to 512
    header = _pad_to_sector(header, SECTOR_SIZE)
    assert len(header) == SECTOR_SIZE, f"header is {len(header)} not 512"

    # 7. Assemble file:
    out = bytearray()
    out += header                                  # sector 0
    out += fat_bytes                               # sector 1 (FAT)
    out += dir_bytes                               # sector 2 (directory)
    out += minifat_bytes                           # sector 3 (mini-FAT)
    out += mini_container                          # sector 4 (mini-stream container)
    out += package_padded                          # sectors 5+ (Package stream)
    return bytes(out)
```

> NOTE: This implementation contains binary-format details that may need adjustment based on test failures. The brief intent is correct; iterate on test output to converge.

- [ ] **Step 5: Run tests, iterate until pass**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_cfb_writer.py -v
```

Expected: PASS for all 6 tests. If FAIL, debug binary structure using olefile error messages + hex dump comparisons against a real Excel OLE bin sample (user can provide one by inserting Excel object in PowerPoint manually then extracting).

If a test stays red after reasonable iteration, the implementer should report `BLOCKED` with the exact olefile parse error and stop — the CFB format has many subtle invariants and the writer above may need targeted fixes per failure mode.

- [ ] **Step 6: Run full backend suite**

```bash
cd backend && arch -arm64 .venv/bin/pytest -q 2>&1 | tail -3
```

Expected: 334 baseline + 6 new = 340 pass.

- [ ] **Step 7: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/cfb_writer.py \
        backend/tests/test_cfb_writer.py \
        backend/pyproject.toml
git commit -m "feat(cfb_writer): minimal CFB writer for Excel OLE wrap

Builds a Compound File Binary blob containing the 4 Excel OLE streams
(\\x01Ole, \\x01CompObj, \\x03ObjInfo, Package) wrapping a raw xlsx
blob in the Package stream. Root CLSID is Excel.Sheet.12. Verified via
olefile round-trip: all 4 streams present + Package extracts back to
original xlsx bytes.

Adds olefile>=0.46 as a dev-only test dependency.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `ole_embedder` switch to CFB + `.bin` partname

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/ole_embedder.py`
- Modify: `backend/tests/test_ole_embedder.py`

**Interfaces:**
- Consumes (from Task 1): `build_excel_ole_cfb`.
- Produces: `embed_ole_xlsx_with_preview` signature unchanged; internally wraps xlsx in CFB before adding the OLE part; partname `.bin`; content type `oleObject`.

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_ole_embedder.py`:

```python
def test_embedded_part_is_bin_not_xlsx():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(
        slide, x=0, y=0, w=4_572_000, h=2_286_000,
        xlsx_bytes=_xlsx_bytes(), png_bytes=_png_bytes(),
    )
    package = slide.part.package
    partnames = [str(p.partname) for p in package.iter_parts()]
    assert any(p.startswith("/ppt/embeddings/oleObject") and p.endswith(".bin") for p in partnames)
    assert not any(p.startswith("/ppt/embeddings/oleObject") and p.endswith(".xlsx") for p in partnames)


def test_embedded_part_content_type_is_oleObject():
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(
        slide, x=0, y=0, w=4_572_000, h=2_286_000,
        xlsx_bytes=_xlsx_bytes(), png_bytes=_png_bytes(),
    )
    package = slide.part.package
    for p in package.iter_parts():
        if str(p.partname).startswith("/ppt/embeddings/oleObject") and str(p.partname).endswith(".bin"):
            assert p.content_type == "application/vnd.openxmlformats-officedocument.oleObject"
            return
    raise AssertionError("no .bin oleObject part found")


def test_embedded_blob_is_cfb():
    from io import BytesIO
    import olefile
    from aurum_encuestas.element_renderers.ole_embedder import embed_ole_xlsx_with_preview
    _prs, slide = _make_slide()
    embed_ole_xlsx_with_preview(
        slide, x=0, y=0, w=4_572_000, h=2_286_000,
        xlsx_bytes=_xlsx_bytes(), png_bytes=_png_bytes(),
    )
    package = slide.part.package
    for p in package.iter_parts():
        if str(p.partname).startswith("/ppt/embeddings/oleObject") and str(p.partname).endswith(".bin"):
            blob = p.blob
            assert blob[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
            ole = olefile.OleFileIO(BytesIO(blob))
            streams = {"/".join(s) if isinstance(s, list) else s for s in ole.listdir()}
            assert "Package" in streams
            ole.close()
            return
    raise AssertionError("no .bin oleObject part found")
```

The existing `test_embedded_xlsx_part_added` and `test_round_trip_save_and_reopen_succeeds` need to be adapted (replace `.xlsx` partname assertions with `.bin`, replace `PK\x03\x04` magic with CFB magic).

- [ ] **Step 2: Run failing tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_ole_embedder.py -v 2>&1 | tail -15
```

Expected: FAIL on the new tests; old `.xlsx` tests still pass but soon to be invalid.

- [ ] **Step 3: Update `ole_embedder.py`**

Locate the body of `embed_ole_xlsx_with_preview`. Replace the xlsx Part section:

```python
xlsx_partname = _next_partname(package, "/ppt/embeddings/oleObject{}.xlsx")
xlsx_part = Part(xlsx_partname, CT_XLSX, package, xlsx_bytes)
rid_xlsx = slide_part.relate_to(xlsx_part, RT.OLE_OBJECT)
```

With:

```python
from .cfb_writer import build_excel_ole_cfb

CT_OLE_OBJECT = "application/vnd.openxmlformats-officedocument.oleObject"

cfb_blob = build_excel_ole_cfb(xlsx_bytes)
bin_partname = _next_partname(package, "/ppt/embeddings/oleObject{}.bin")
bin_part = Part(bin_partname, CT_OLE_OBJECT, package, cfb_blob)
rid_xlsx = slide_part.relate_to(bin_part, RT.OLE_OBJECT)
```

The variable name `rid_xlsx` is kept for graphicFrame XML continuity; semantically it's the OLE bin part now. Optionally rename to `rid_ole`.

Place `CT_OLE_OBJECT` as a module-level constant near `CT_XLSX`. Optionally remove `CT_XLSX` constant since it's no longer used.

Also update or remove the `from pptx.opc.constants import CONTENT_TYPE as CT` import if unused now.

- [ ] **Step 4: Adapt the existing tests**

In `test_ole_embedder.py`, find:
- `test_embedded_xlsx_part_added` → rename to `test_embedded_ole_bin_part_added`, assert `.bin` partname.
- `test_round_trip_save_and_reopen_succeeds` → update magic check from `b"PK\x03\x04"` to `b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"`.

- [ ] **Step 5: Run tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_ole_embedder.py -v
```

Expected: all pass.

- [ ] **Step 6: Run full suite**

```bash
cd backend && arch -arm64 .venv/bin/pytest -q 2>&1 | tail -3
```

Expected: 340 → matches 334 baseline + 6 cfb + 3 new ole_embedder − any removed = ~343, 0 fail.

- [ ] **Step 7: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/ole_embedder.py backend/tests/test_ole_embedder.py
git commit -m "fix(ole_embedder): wrap xlsx in CFB + use .bin partname

Real Excel OLE requires the embedded blob to be a Compound File Binary
with progId Excel.Sheet.12 inside a CompObj stream and the xlsx in a
Package stream. Raw xlsx was being rejected by Excel when invoked via
OLE double-click. ole_embedder now calls cfb_writer.build_excel_ole_cfb
before adding the part, uses /ppt/embeddings/oleObjectN.bin partname,
and sets content type to application/vnd.openxmlformats-officedocument.oleObject.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Prompt fix + manual style_guide instructions doc

**Files:**
- Modify: `backend/aurum_encuestas/llm_client.py`
- Create: `docs/MANUAL-STYLE-GUIDE-FIX.md`

**Interfaces:**
- Consumes: nothing new.
- Produces: corrected example pattern in system prompt; documentation file explaining how the user edits the active style_guide.

- [ ] **Step 1: Replace the example block in `llm_client.py`**

Open `backend/aurum_encuestas/llm_client.py`. Locate the block beginning with `EJEMPLO COMPLETO DE 1 PATTERN BIEN ARMADO (binary + demographics, target Aurora):` and ending with the closing `}` of that JSON literal (approximately lines 283-340).

Replace the entire JSON literal example with:

```python
EJEMPLO COMPLETO DE 1 PATTERN BIEN ARMADO (binary + demographics, target Aurora):

{
  "id": "binary_general_with_demographics",
  "priority": 0,
  "trigger": {
    "$and": [
      {"field": "n_charts_in_slide", "$gte": 1},
      {"field": "question_type", "$eq": "binary"},
      {"field": "n_breakdowns", "$gte": 2}
    ]
  },
  "extends": null,
  "best_example": "Aurora.pptx#slide17",
  "why_picked": "Tabla OLE editable que cubre todos los breakdowns. Render via TABLE_WITH_MINIBARS = embedded xlsx + PNG preview.",
  "implementation": {
    "elements": [
      {
        "kind": "chart",
        "id": "main_table",
        "position": {"x_rel": 0.04, "y_rel": 0.18, "w_rel": 0.92, "h_rel": 0.70},
        "chart_type": "TABLE_WITH_MINIBARS",
        "data_source": {"chart_ref_index": 0, "value_field": "pct"}
      }
    ]
  }
}
```

The leading/trailing surrounding text (instructions to the AI) stays intact. Only the JSON literal between the matching pair of `{}` is replaced.

- [ ] **Step 2: Add `docs/MANUAL-STYLE-GUIDE-FIX.md`**

Create the file with this content:

```markdown
# Manual fix: remove "Distribución general/segmentada" split from active style_guide

If your current `~/.aurum/training/style_guide.json` was generated before Fase E
of the chart-catalog overhaul, it likely contains a pattern with four elements:

1. A text shape "Distribución general"
2. A left PIE chart
3. A text shape "Distribución segmentada"
4. A right table (`TABLE_WITH_MINIBARS`)

This split is no longer desired — the OLE table now covers all breakdowns and
should occupy the full slide width.

## Steps

1. Open `~/.aurum/training/style_guide.json` in a text editor.
2. Find the pattern with `"id"` containing `demographics` or with elements
   referencing the strings `"Distribución general"` and `"Distribución segmentada"`.
3. Inside that pattern's `implementation.elements` list, remove the three
   non-table elements (the two text shapes and the PIE chart).
4. Keep the remaining `kind="chart"` element with `chart_type="TABLE_WITH_MINIBARS"`.
   Update its `position` to:
   ```json
   {"x_rel": 0.04, "y_rel": 0.18, "w_rel": 0.92, "h_rel": 0.70}
   ```
5. Save the file.

Next pptx generation will use the cleaned-up pattern.

## Future regeneration

If you re-run training corpus analysis (`/api/training/analyze`), the new
system prompt in `llm_client.py` emits a single-element pattern by default,
so this manual edit will not be needed again.
```

- [ ] **Step 3: Verify llm_client.py still parses (no tests added — this is doc/prompt change)**

```bash
cd backend && arch -arm64 .venv/bin/python -c "from aurum_encuestas.llm_client import SYSTEM_PROMPT_STYLE_GUIDE; print('len', len(SYSTEM_PROMPT_STYLE_GUIDE))"
```

Expected: prints length, no exception.

If the constant has a different name, locate it via:
```bash
grep -n "EJEMPLO COMPLETO" backend/aurum_encuestas/llm_client.py
```

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/llm_client.py docs/MANUAL-STYLE-GUIDE-FIX.md
git commit -m "fix(prompt): single-element TABLE_WITH_MINIBARS example + manual edit doc

Replaces the 4-element split example (left text + PIE + right text + table)
with a single full-width TABLE_WITH_MINIBARS element. The split was being
copied verbatim by AI-generated style_guides, causing the unwanted
'Distribución general/segmentada' shapes to render on every slide.

Adds docs/MANUAL-STYLE-GUIDE-FIX.md with instructions for users to clean
up their already-generated ~/.aurum/training/style_guide.json.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Spec coverage:**
  - Bug #1 CFB OLE wrap → Tasks 1+2 ✅
  - Bug #2 style_guide split → Task 3 prompt fix + doc; manual edit by user ✅
  - Manual smoke flow → spec § Testing ✅
- **Placeholder scan:** No "TBD". All code shown verbatim. One NOTE block in Task 1 Step 4 warns about CFB binary subtlety and asks implementer to iterate on test failures; this is realistic, not a placeholder.
- **Type consistency:** `build_excel_ole_cfb(xlsx_bytes: bytes) -> bytes` stable across Tasks 1, 2. `embed_ole_xlsx_with_preview` signature unchanged. Partname `.bin`, content type `oleObject` consistent in Task 2 tests + impl.
- **Open caveats:**
  - Task 1's CFB writer may need debugging iteration. If `BLOCKED`, the controller can provide a real Excel OLE bin sample (user generates via PowerPoint manual Insert > Object > Microsoft Excel Worksheet) for byte-level comparison.
  - Task 3's manual edit is user action, not automated. Doc covers the recipe.
