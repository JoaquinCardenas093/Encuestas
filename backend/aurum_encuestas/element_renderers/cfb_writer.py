"""Minimal CFB (Compound File Binary) writer for Excel OLE.

Spec: [MS-CFB] https://learn.microsoft.com/openspecs/windows_protocols/ms-cfb
Layout (FAT indices, file_sector = fat_index + 1):
  file sector 0          : CFB header (not in FAT)
  fat index 0            : FAT sector
  fat index 1..d         : Directory sectors (d = ceil(n_entries*128/512))
  fat index d+1          : Mini-FAT sector
  fat index d+2          : Mini-stream container (one normal sector → 8 mini-sectors)
  fat index d+3..        : Package stream sectors (xlsx blob)

Streams:
  Root entry             : CLSID = Excel.Sheet.12, start = mini-stream container
  \\x01Ole               : 20-byte version header (mini stream)
  \\x01CompObj           : Excel descriptor (mini stream)
  \\x03ObjInfo           : 6-byte object info (mini stream)
  Package                : raw xlsx blob (normal stream)
"""

import struct

SECTOR_SIZE = 512
MINI_SECTOR_SIZE = 64
MINI_STREAM_CUTOFF = 4096
ENDOFCHAIN = 0xFFFFFFFE
FREESECT = 0xFFFFFFFF
FATSECT = 0xFFFFFFFD
DIFSECT = 0xFFFFFFFC
NOSTREAM = 0xFFFFFFFF

CFB_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
# CLSID {00020820-0000-0000-C000-000000000046} little-endian encoded
EXCEL_CLSID = b"\x20\x08\x02\x00\x00\x00\x00\x00\xc0\x00\x00\x00\x00\x00\x00\x46"

# \x01Ole stream: version 02 00 01 00, no flags, no linked update, reserved zero (20 bytes)
OLE_STREAM = b"\x02\x00\x01\x00" + b"\x00" * 4 + b"\x00" * 4 + b"\x00" * 8

# \x03ObjInfo stream: 6 bytes (40 00 09 00 00 00)
OBJINFO_STREAM = b"\x40\x00\x09\x00\x00\x00"


def _build_compobj_stream() -> bytes:
    """Build \\x01CompObj stream per [MS-OLEDS] §2.3.6 for Excel.Sheet.12."""
    parts = []
    parts.append(struct.pack("<I", 0xFFFE))                     # 4 bytes
    parts.append(struct.pack("<I", 0x0A03))                     # 4 bytes
    parts.append(struct.pack("<I", 0x000000FF))                 # 4 bytes
    parts.append(EXCEL_CLSID)                                   # CLSID 16 bytes
    # AnsiUserType — length-prefixed Pascal string with NUL terminator
    user_type = b"Microsoft Excel Worksheet\x00"
    parts.append(struct.pack("<I", len(user_type)))
    parts.append(user_type)
    # AnsiClipboardFormat tag + CF_DIB
    parts.append(struct.pack("<I", 0xFFFFFFFF))
    parts.append(struct.pack("<I", 0x00000008))
    # Reserved1 — length-prefixed string "" (4 byte length 0)
    parts.append(struct.pack("<I", 0))
    # UnicodeMarker
    parts.append(struct.pack("<I", 0x71B239F4))
    # UnicodeUserType — length-prefixed UTF-16 string (count of UTF-16 code units)
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
    """Return UTF-16-LE encoded name padded to 64 bytes (32 chars max incl NUL)."""
    raw = (name + "\x00").encode("utf-16-le")
    if len(raw) > 64:
        raw = raw[:64]
    return raw + b"\x00" * (64 - len(raw))


def _dir_entry(
    name: str, entry_type: int, name_len_bytes: int,
    color: int = 1,
    left_sib: int = NOSTREAM, right_sib: int = NOSTREAM, child: int = NOSTREAM,
    clsid: bytes = b"\x00" * 16,
    start_sect: int = 0, stream_size: int = 0,
) -> bytes:
    """Build a 128-byte directory entry."""
    name_padded = _utf16_padded_name(name)
    entry = (
        name_padded                                       # 64 bytes
        + struct.pack("<H", name_len_bytes)               # 2 bytes (length in bytes incl NUL)
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
    assert len(entry) == 128, f"dir entry is {len(entry)} not 128"
    return entry


def build_excel_ole_cfb(xlsx_bytes: bytes) -> bytes:
    """Build a CFB blob wrapping the xlsx as Excel.Sheet.12 OLE.

    Sector layout (FAT indices; file_sector_n = fat_index + 1):
      fat[0]                      = FAT
      fat[1..n_dir]               = directory sectors
      fat[n_dir+1]                = mini-FAT
      fat[n_dir+2]                = mini-stream container
      fat[n_dir+3..]              = Package stream
    """
    # ---- 1. Mini streams (\x01Ole, \x01CompObj, \x03ObjInfo) ----
    mini_streams = [
        ("\x01Ole", OLE_STREAM),
        ("\x01CompObj", COMPOBJ_STREAM),
        ("\x03ObjInfo", OBJINFO_STREAM),
    ]
    mini_alloc: list[tuple[str, bytes, int, int]] = []  # (name, data, start_mini, size)
    next_mini = 0
    for name, data in mini_streams:
        size = len(data)
        n_mini = (size + MINI_SECTOR_SIZE - 1) // MINI_SECTOR_SIZE
        mini_alloc.append((name, data, next_mini, size))
        next_mini += n_mini

    # Mini-stream container: concatenate, each stream padded to MINI_SECTOR_SIZE
    mini_container = b""
    for _, data, _, _ in mini_alloc:
        mini_container += _pad_to_sector(data, MINI_SECTOR_SIZE)
    mini_stream_size = len(mini_container)
    # Pad container to full normal sector
    mini_container = _pad_to_sector(mini_container, SECTOR_SIZE)
    assert len(mini_container) == SECTOR_SIZE, "mini-container expected to fit in 1 sector"

    # ---- 2. Mini-FAT entries ----
    minifat = []
    for _, _, start_mini, size in mini_alloc:
        n = (size + MINI_SECTOR_SIZE - 1) // MINI_SECTOR_SIZE
        for k in range(n):
            if k == n - 1:
                minifat.append(ENDOFCHAIN)
            else:
                minifat.append(start_mini + k + 1)
    while len(minifat) < SECTOR_SIZE // 4:
        minifat.append(FREESECT)
    minifat_bytes = b"".join(struct.pack("<I", v) for v in minifat)

    # ---- 3. Directory entries (5 entries: Root + Package + 3 mini streams) ----
    # We need to know n_dir_sectors before computing FAT indices.
    n_entries = 1 + 1 + len(mini_alloc)  # Root + Package + 3 mini = 5
    dir_bytes_unpadded_len = n_entries * 128
    n_dir_sectors = (dir_bytes_unpadded_len + SECTOR_SIZE - 1) // SECTOR_SIZE
    # Round up dir to whole sectors (rest filled with empty dir entries below)

    # ---- 4. Compute FAT indices ----
    FAT_IDX = 0
    DIR_FIRST_IDX = 1
    MINIFAT_IDX = DIR_FIRST_IDX + n_dir_sectors
    MINISTREAM_IDX = MINIFAT_IDX + 1
    PKG_FIRST_IDX = MINISTREAM_IDX + 1

    # ---- 5. Package stream as normal sectors ----
    package_size = len(xlsx_bytes)
    n_pkg_sectors = (package_size + SECTOR_SIZE - 1) // SECTOR_SIZE
    package_padded = _pad_to_sector(xlsx_bytes, SECTOR_SIZE)

    # ---- 6. Build FAT ----
    fat = [FREESECT] * (SECTOR_SIZE // 4)
    fat[FAT_IDX] = FATSECT
    # Directory chain
    for i in range(n_dir_sectors):
        if i == n_dir_sectors - 1:
            fat[DIR_FIRST_IDX + i] = ENDOFCHAIN
        else:
            fat[DIR_FIRST_IDX + i] = DIR_FIRST_IDX + i + 1
    fat[MINIFAT_IDX] = ENDOFCHAIN
    fat[MINISTREAM_IDX] = ENDOFCHAIN
    # Package chain
    for i in range(n_pkg_sectors):
        if i == n_pkg_sectors - 1:
            fat[PKG_FIRST_IDX + i] = ENDOFCHAIN
        else:
            fat[PKG_FIRST_IDX + i] = PKG_FIRST_IDX + i + 1
    fat_bytes = b"".join(struct.pack("<I", v) for v in fat)

    # ---- 7. Directory entries ----
    # Entry layout:
    #   0: Root Entry (type 5) — clsid = Excel, start = MINISTREAM_IDX, size = mini_stream_size
    #   1: Package          — start = PKG_FIRST_IDX, size = package_size
    #   2: \x01Ole          — mini stream
    #   3: \x01CompObj      — mini stream
    #   4: \x03ObjInfo      — mini stream
    # Tree: Root's child = 1 (Package). Sibling tree built as right-leaning chain:
    #   Package.right_sib = 2; \x01Ole.right_sib = 3; \x01CompObj.right_sib = 4; \x03ObjInfo none.
    def name_len_bytes(s: str) -> int:
        return 2 * (len(s) + 1)

    entries = []
    entries.append(_dir_entry(
        name="Root Entry",
        entry_type=5,
        name_len_bytes=name_len_bytes("Root Entry"),
        color=1,
        child=1,
        clsid=EXCEL_CLSID,
        start_sect=MINISTREAM_IDX,
        stream_size=mini_stream_size,
    ))
    entries.append(_dir_entry(
        name="Package",
        entry_type=2,
        name_len_bytes=name_len_bytes("Package"),
        color=1,
        right_sib=2,
        start_sect=PKG_FIRST_IDX,
        stream_size=package_size,
    ))
    for idx, (mname, _, start_mini, msize) in enumerate(mini_alloc, start=2):
        right = idx + 1 if idx < (1 + 1 + len(mini_alloc) - 1) else NOSTREAM
        entries.append(_dir_entry(
            name=mname,
            entry_type=2,
            name_len_bytes=name_len_bytes(mname),
            color=1,
            right_sib=right,
            start_sect=start_mini,
            stream_size=msize,
        ))
    dir_bytes = b"".join(entries)
    # Pad with empty (zeroed) dir entries to fill the directory sectors
    target_dir_len = n_dir_sectors * SECTOR_SIZE
    if len(dir_bytes) < target_dir_len:
        # Empty entries: all-zero 128-byte block with entry_type=0 (already zero) is fine.
        # But left/right/child should be NOSTREAM (0xFFFFFFFF), not 0, to be safe.
        n_empty = (target_dir_len - len(dir_bytes)) // 128
        empty_entry = (
            b"\x00" * 64                             # name
            + struct.pack("<H", 0)                   # name_len
            + struct.pack("<B", 0)                   # entry_type = empty
            + struct.pack("<B", 0)                   # color
            + struct.pack("<I", NOSTREAM)            # left
            + struct.pack("<I", NOSTREAM)            # right
            + struct.pack("<I", NOSTREAM)            # child
            + b"\x00" * 16                           # clsid
            + struct.pack("<I", 0)                   # state
            + struct.pack("<Q", 0)                   # ctime
            + struct.pack("<Q", 0)                   # mtime
            + struct.pack("<I", 0)                   # start sect
            + struct.pack("<Q", 0)                   # size
        )
        assert len(empty_entry) == 128
        dir_bytes += empty_entry * n_empty
    assert len(dir_bytes) == target_dir_len, f"dir is {len(dir_bytes)} not {target_dir_len}"

    # ---- 8. CFB Header (512 bytes) ----
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
        + struct.pack("<I", DIR_FIRST_IDX)            # first dir sector (FAT index)
        + struct.pack("<I", 0)                        # transaction signature
        + struct.pack("<I", MINI_STREAM_CUTOFF)       # mini stream cutoff
        + struct.pack("<I", MINIFAT_IDX)              # first mini-FAT sector (FAT index)
        + struct.pack("<I", 1)                        # num mini-FAT sectors
        + struct.pack("<I", ENDOFCHAIN)               # first DIFAT sector
        + struct.pack("<I", 0)                        # num DIFAT sectors
    )
    # DIFAT array (109 entries × 4 bytes = 436 bytes); DIFAT[0] = FAT_IDX
    difat = [FAT_IDX] + [FREESECT] * 108
    difat_bytes = b"".join(struct.pack("<I", v) for v in difat)
    header += difat_bytes
    header = _pad_to_sector(header, SECTOR_SIZE)
    assert len(header) == SECTOR_SIZE, f"header is {len(header)} not 512"

    # ---- 9. Assemble file ----
    # file sector 0 = header
    # file sector 1 = FAT (FAT index 0)
    # file sectors 2..2+n_dir-1 = directory (FAT indices 1..n_dir)
    # next = mini-FAT
    # next = mini-stream container
    # next = Package padded
    out = bytearray()
    out += header
    out += fat_bytes
    out += dir_bytes
    out += minifat_bytes
    out += mini_container
    out += package_padded
    return bytes(out)
