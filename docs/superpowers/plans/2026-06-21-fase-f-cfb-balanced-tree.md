# Fase F Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the four remaining bugs after Fase E: PowerPoint still requests repair (CFB dir needs balanced red-black tree); slide still shows extra "Distribución general/segmentada" shapes from a stale AI-generated style_guide (provide a clean BUILTIN pattern + user-wipe doc); xlsx databar too pale + value text misaligned; xlsx + PNG ignore `Chart.show_legend` toggle.

**Architecture:** Touch only the 5 modules that own these bugs. `cfb_writer.py` learns to sort dir entries per MS-CFB §2.6.4 + build a balanced binary tree (left/right siblings + colors). `xlsx_builder.py` + `ole_png_renderer.py` read `source_chart.show_legend` and skip the label col when False, plus update bar color to `D9D9D9` / `(217,217,217)` and right-align value text in xlsx. `style_guide.py` BUILTIN gains a high-priority `table_only_full_width` pattern with one element (the OLE table). `docs/MANUAL-STYLE-GUIDE-FIX.md` adds a "quick reset" section telling the user to `rm ~/.aurum/training/style_guide.json`.

**Tech Stack:** Python 3.11 + openpyxl + Pillow + lxml (already in stack).

## Global Constraints

- Backend Python 3.11. Tests: `cd backend && arch -arm64 .venv/bin/pytest -q`.
- `cfb_writer.build_excel_ole_cfb(xlsx_bytes: bytes) -> bytes` signature unchanged.
- `xlsx_builder.build_xlsx_for_table(source_chart, breakdown_groups: list[str]) -> BytesIO` signature unchanged.
- `ole_png_renderer.render_table_preview_png(source_chart, breakdown_groups: list[str], w_emu: int, h_emu: int) -> bytes` signature unchanged.
- `show_legend` read via `bool(getattr(source_chart, "show_legend", False))` — default False.
- DataBarRule color literal: `"D9D9D9"`. PIL bar color tuple: `(217, 217, 217)`.
- BUILTIN_STYLE_GUIDE new pattern `table_only_full_width` priority = 10.
- Branch base: `main` at `b475c3e` (post Fase E merge). New branch: `feat/fase-f-cfb-balanced`.

---

## File Structure

Modified backend:
- `backend/aurum_encuestas/element_renderers/cfb_writer.py` — sorted dir entries + balanced tree.
- `backend/aurum_encuestas/element_renderers/xlsx_builder.py` — show_legend + databar color + right-align.
- `backend/aurum_encuestas/element_renderers/ole_png_renderer.py` — show_legend + bar color.
- `backend/aurum_encuestas/style_guide.py` — BUILTIN add table_only_full_width.

Modified tests:
- `backend/tests/test_cfb_writer.py` — append 2 balanced-tree assertions.
- `backend/tests/test_xlsx_builder.py` — append 4 assertions; adapt existing fixtures to pass `show_legend=True`.
- `backend/tests/test_ole_png_renderer.py` — append 1 assertion; adapt existing fixtures to pass `show_legend=True`.
- `backend/tests/test_style_guide.py` — append 1 assertion.

Modified docs:
- `docs/MANUAL-STYLE-GUIDE-FIX.md` — add Quick reset section.

Untouched: everything else.

---

### Task 1: `cfb_writer` balanced red-black tree

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/cfb_writer.py`
- Modify: `backend/tests/test_cfb_writer.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `_sort_dir_entries_indices(entries: list[dict]) -> list[int]` private helper — returns indices of non-Root entries sorted by `(utf16_byte_length, UPPER(name).encode("utf-16-le"))`.
  - `_assign_balanced_tree(entries: list[dict], sorted_indices: list[int]) -> int` — assigns each entry's `left_sib`, `right_sib`, `color` for a balanced binary tree; returns the index of the root.
  - Existing `_dir_entry(...)` gains optional `left_sib`, `right_sib`, `color` kwargs (already present but values now come from the tree builder).

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_cfb_writer.py`:

```python
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
```

- [ ] **Step 2: Run failing tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_cfb_writer.py::test_dir_entries_sorted_by_msfb_rule tests/test_cfb_writer.py::test_dir_tree_balanced_depth_bounded -v
```

Expected: FAIL — current writer uses allocation order + right-leaning chain.

- [ ] **Step 3: Add helpers `_sort_dir_entries_indices` and `_assign_balanced_tree` in `cfb_writer.py`**

Add the following helpers before `build_excel_ole_cfb`:

```python
def _sort_dir_entries_indices(entries_with_names: list[tuple[int, str]]) -> list[int]:
    """Return entry indices sorted per MS-CFB §2.6.4:
       primary key = UTF-16 byte length of name (including NUL terminator),
       secondary key = UPPER(name) encoded UTF-16-LE.
    
    `entries_with_names`: list of (entry_index, name_string).
    """
    def sort_key(item):
        idx, name = item
        utf16_byte_len = (len(name) + 1) * 2  # include NUL
        upper_utf16 = name.upper().encode("utf-16-le")
        return (utf16_byte_len, upper_utf16)
    
    return [idx for idx, _ in sorted(entries_with_names, key=sort_key)]


def _assign_balanced_tree(
    n_entries: int,
    sorted_indices: list[int],
) -> tuple[int, dict[int, tuple[int, int, int]]]:
    """Build a balanced binary tree over `sorted_indices`.
    
    Returns:
      - root_index: index of the root entry in the directory.
      - sib_color_map: {entry_idx: (left_sib, right_sib, color)} where color is 1=BLACK, 0=RED.
                       left/right sib are entry indices or 0xFFFFFFFF (NOSTREAM).
    
    Strategy: pick middle of sorted list as root (BLACK), recurse on left and right halves.
    """
    NOSTREAM = 0xFFFFFFFF
    sib_color: dict[int, tuple[int, int, int]] = {}
    
    def build(lo: int, hi: int, depth: int) -> int:
        """Return the index of the subtree root, or NOSTREAM if empty."""
        if lo > hi:
            return NOSTREAM
        mid = (lo + hi) // 2
        idx = sorted_indices[mid]
        left = build(lo, mid - 1, depth + 1)
        right = build(mid + 1, hi, depth + 1)
        # Color: alternate by depth. Root BLACK. Children RED on odd depth, BLACK on even.
        color = 1 if depth % 2 == 0 else 0
        sib_color[idx] = (left, right, color)
        return idx
    
    if not sorted_indices:
        return NOSTREAM, sib_color
    
    root = build(0, len(sorted_indices) - 1, 0)
    return root, sib_color
```

- [ ] **Step 4: Rewrite the directory entries section of `build_excel_ole_cfb`**

In `build_excel_ole_cfb`, after the entries list is built but BEFORE serializing, integrate the sort + tree. Locate the existing block that builds `entries` (the list of `_dir_entry(...)` outputs) and replace the post-build serialization logic with:

```python
# Sort non-Root entries (indices 1..N) per MS-CFB §2.6.4
non_root_with_names = [
    (1, "Package"),
    (2, "\x01Ole"),
    (3, "\x01CompObj"),
    (4, "\x03ObjInfo"),
]
sorted_indices = _sort_dir_entries_indices(non_root_with_names)
tree_root, sib_color = _assign_balanced_tree(len(non_root_with_names), sorted_indices)
```

Then, when building each `_dir_entry`, look up its (left_sib, right_sib, color) from `sib_color` instead of using the right-leaning chain. The Root entry's `child` field becomes `tree_root` (the index of the balanced-tree root) instead of a fixed value.

You'll need to refactor the dir-entry list building to be: build skeleton list first → compute sorted_indices + tree → patch each entry's siblings + color → serialize.

A clean refactor:

```python
# Build dir entries with NOSTREAM sibs and color BLACK as defaults;
# patch siblings + color after the tree is computed.
NOSTREAM = 0xFFFFFFFF

# Allocate "skeleton" entries (just name + type + clsid + start + size)
entry_specs = [
    # (name, entry_type, clsid, start_sect, stream_size)
    ("Root Entry", 5, EXCEL_CLSID, MINISTREAM_SECTOR,
     sum((s + MINI_SECTOR_SIZE - 1) // MINI_SECTOR_SIZE for _, _, _, s in mini_alloc) * MINI_SECTOR_SIZE),
    ("Package", 2, b"\x00"*16, PKG_FIRST_IDX, package_size),
]
for mname, _, start_mini, msize in mini_alloc:
    entry_specs.append((mname, 2, b"\x00"*16, start_mini, msize))

# Sort + build tree
non_root_with_names = [(i, spec[0]) for i, spec in enumerate(entry_specs) if i > 0]
sorted_indices = _sort_dir_entries_indices(non_root_with_names)
tree_root, sib_color = _assign_balanced_tree(len(non_root_with_names), sorted_indices)

# Now build entries with proper siblings/color
entries = []
for idx, (name, etype, clsid, start, size) in enumerate(entry_specs):
    if idx == 0:
        # Root: child points at tree root
        left, right, color, child = NOSTREAM, NOSTREAM, 1, tree_root
    else:
        left, right, color = sib_color.get(idx, (NOSTREAM, NOSTREAM, 1))
        child = NOSTREAM
    entries.append(_dir_entry(
        name=name, entry_type=etype,
        name_len=2*(len(name)+1),
        color=color,
        left_sib=left, right_sib=right, child=child,
        clsid=clsid,
        start_sect=start, stream_size=size,
    ))
```

- [ ] **Step 5: Run tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_cfb_writer.py -v
```

Expected: all 8 tests pass (6 existing + 2 new).

- [ ] **Step 6: Full suite**

```bash
cd backend && arch -arm64 .venv/bin/pytest -q 2>&1 | tail -3
```

Expected: 346 baseline + 2 new = 348 pass.

- [ ] **Step 7: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/cfb_writer.py backend/tests/test_cfb_writer.py
git commit -m "fix(cfb_writer): balanced red-black dir tree + sorted siblings

PowerPoint Mac strict CFB validator was rejecting our right-leaning
sibling chain + allocation-order entries. Per MS-CFB §2.6.4 sort
siblings by (UTF-16 byte length, UPPER(name) UTF-16) and build a
balanced binary tree with alternating depth-based colors. Root entry
child now points to the tree root index.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `xlsx_builder` show_legend + databar color + right-align

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/xlsx_builder.py`
- Modify: `backend/tests/test_xlsx_builder.py`

**Interfaces:**
- Consumes: `source_chart.show_legend` (bool, default False).
- Produces: when `show_legend=True`, layout unchanged from Fase E (label col + data cols). When False, no label col — data starts at the leftmost col per bd. DataBar color = `D9D9D9`. Data cell `Alignment(horizontal="right", indent=1)`.

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_xlsx_builder.py`:

```python
def test_xlsx_show_legend_true_includes_label_col():
    """show_legend=True → label col with 'Observaciones' + option labels."""
    from aurum_encuestas.element_renderers.xlsx_builder import build_xlsx_for_table

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
        ]),
    ])
    src.show_legend = True
    buf = build_xlsx_for_table(src, ["edad"])
    wb = load_workbook(buf)
    ws = wb.active
    assert ws["A4"].value == "Observaciones"
    assert ws["A5"].value == "opt0"


def test_xlsx_show_legend_false_skips_label_col():
    """show_legend=False → no label col; data starts at col A."""
    from aurum_encuestas.element_renderers.xlsx_builder import build_xlsx_for_table

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
            ("40-59", {"opt0": {"pct": 0.8, "count": 80}, "opt1": {"pct": 0.2, "count": 20}}),
        ]),
    ])
    src.show_legend = False
    buf = build_xlsx_for_table(src, ["edad"])
    wb = load_workbook(buf)
    ws = wb.active
    # Label col A is empty
    assert ws["A4"].value is None
    assert ws["A5"].value is None
    # Cat headers at A3 + B3 (no label col), data at A5 + B5
    assert ws["A3"].value == "18-39"
    assert ws["B3"].value == "40-59"
    assert abs(ws["A5"].value - 0.9) < 1e-9


def test_databar_color_is_d9d9d9():
    from aurum_encuestas.element_renderers.xlsx_builder import build_xlsx_for_table

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
        ]),
    ])
    src.show_legend = True
    buf = build_xlsx_for_table(src, ["edad"])
    wb = load_workbook(buf)
    ws = wb.active
    for cf_range, rules in ws.conditional_formatting._cf_rules.items():
        for rule in rules:
            db = getattr(rule, "dataBar", None)
            if db is not None and db.color is not None:
                assert "D9D9D9" in (db.color.value or "").upper()
                return
    raise AssertionError("no DataBarRule found")


def test_data_cell_alignment_right():
    from aurum_encuestas.element_renderers.xlsx_builder import build_xlsx_for_table

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
        ]),
    ])
    src.show_legend = True
    buf = build_xlsx_for_table(src, ["edad"])
    wb = load_workbook(buf)
    ws = wb.active
    # Data cell at B5 (first option row, first cat col when show_legend=True)
    cell = ws["B5"]
    assert cell.alignment.horizontal == "right"
```

Existing tests need `src.show_legend = True` added at fixture setup so the old assertions about "Observaciones" still pass. Find each `_make_source(...)` call in the existing tests and append `src.show_legend = True` before the `build_xlsx_for_table` call.

- [ ] **Step 2: Run failing tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_xlsx_builder.py -v 2>&1 | tail -20
```

Expected: 4 new tests FAIL; existing tests now FAIL too because `show_legend` default is False and current code always renders label col, so the old assertions about `ws["A4"] == "Observaciones"` actually still pass with default fixture — but the new `show_legend=False` test fails because the code doesn't yet skip the label col.

- [ ] **Step 3: Add show_legend branching to `build_xlsx_for_table`**

In `xlsx_builder.py`, at the top of `build_xlsx_for_table` after extracting `options` and `all_bds`, add:

```python
show_legend = bool(getattr(source_chart, "show_legend", False))
```

Then guard every block that touches the label col with `if show_legend:`. Specifically:
1. Inside the per-bd loop, change `label_col = cur_col` + `data_start = cur_col + 1` to:
   ```python
   if show_legend:
       label_col = cur_col
       data_start = cur_col + 1
   else:
       data_start = cur_col
       label_col = None  # no label col
   data_end = data_start + n_cats - 1
   ```
2. The merge for group_header: when show_legend → `merge_cells(...label_col..data_end)`; else → `merge_cells(...data_start..data_end)`.
3. The "Observaciones" cell write: only if `show_legend`.
4. The option-row label col writes: only if `show_legend`.
5. The label col width setting (`column_dimensions[get_column_letter(label_col)].width = LABEL_COL_W`): only if `show_legend`.
6. The cur_col advance after each bd: `cur_col = data_end + 2` (spacer col still 2 wide regardless).

Change DataBarRule color literal:
```python
DATABAR_HEX = "D9D9D9"
```

Change data cell alignment in the option-row write block:
```python
oc.alignment = Alignment(horizontal="right", indent=1, vertical="center")
```

- [ ] **Step 4: Run tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_xlsx_builder.py -v
```

Expected: all pass (new 4 + adapted existing).

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/xlsx_builder.py backend/tests/test_xlsx_builder.py
git commit -m "fix(xlsx_builder): show_legend toggle + pale databar + right-align cells

Reads source_chart.show_legend (default False). When True, renders the
label col with 'Observaciones' + option names; when False, omits the
label col entirely so each panel is just data cols with merged headers.
DataBarRule color switched from BFBFBF to D9D9D9 (paler, matching the
reference Excel format). Data cells horizontal-aligned right with
indent=1 so the value text sits to the right of the bar rather than
overlapping it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `ole_png_renderer` show_legend + bar color

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/ole_png_renderer.py`
- Modify: `backend/tests/test_ole_png_renderer.py`

**Interfaces:**
- Consumes: `source_chart.show_legend`.
- Produces: panel layout omits label col when `show_legend=False`. Bar color = `(217, 217, 217)`.

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_ole_png_renderer.py`:

```python
def test_png_show_legend_false_no_panel_label_pixels():
    """show_legend=False → leftmost columns of canvas are NOT a gray label band;
    they're white (no label col rendered)."""
    from io import BytesIO
    from PIL import Image
    from types import SimpleNamespace
    from aurum_encuestas.element_renderers.ole_png_renderer import render_table_preview_png

    q = SimpleNamespace(options=["opt0", "opt1"])
    src = SimpleNamespace(
        question=q,
        all_breakdowns_data={
            "edad": {"label": "Edad", "categories": {
                "18-39": {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}},
            }},
        },
        breakdown_ids=["edad"],
        show_legend=False,
    )
    png = render_table_preview_png(src, ["edad"], 6_000_000, 3_000_000)
    img = Image.open(BytesIO(png))
    # Sample where the label col would be (around x=20-40) at the body row (y=80)
    # With show_legend=False: this should be white (no label col) OR dark (cat header / counts).
    # With show_legend=True: this would be white body of the label col (right of edge).
    # The discriminator: at x=5, y=80, with show_legend=False there is NO panel here
    # because the only panel starts at margin 5 with cat header (dark) at top.
    # The body row at y=80 should be white background since no panel covers it.
    px = img.getpixel((3, 80))
    # Background outside any panel = pure WHITE
    assert px[0] > 240 and px[1] > 240 and px[2] > 240
```

Existing PNG tests need `src.show_legend = True` so they keep producing the old label-col layout.

- [ ] **Step 2: Run failing tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_ole_png_renderer.py -v 2>&1 | tail -10
```

Expected: new test fails; existing tests that don't set show_legend break.

- [ ] **Step 3: Update `render_table_preview_png`**

In `ole_png_renderer.py`:
1. Change `BAR_GRAY = (191, 191, 191)` → `BAR_GRAY = (217, 217, 217)`.
2. At the top of `render_table_preview_png` after extracting bds:
   ```python
   show_legend = bool(getattr(source_chart, "show_legend", False))
   ```
3. Compute `effective_label_w` based on toggle:
   ```python
   effective_label_w = label_col_w if show_legend else 0
   ```
   Replace every use of `label_col_w` in layout math with `effective_label_w`.
4. Inside the per-panel drawing loop, gate the label col drawing on `if show_legend`. The "Observaciones" + option labels are only drawn when True.

- [ ] **Step 4: Adapt existing tests**

Find every test that calls `render_table_preview_png` and add `src.show_legend = True` to the SimpleNamespace fixture before the call.

- [ ] **Step 5: Run tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_ole_png_renderer.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/ole_png_renderer.py backend/tests/test_ole_png_renderer.py
git commit -m "fix(ole_png_renderer): show_legend toggle + paler bar color

Read source_chart.show_legend (default False). When False, panels
omit the internal label col (data cols only). When True, per-panel
label col with Observaciones + option names. BAR_GRAY switched from
(191,191,191) to (217,217,217) matching xlsx DataBar D9D9D9.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: BUILTIN_STYLE_GUIDE add `table_only_full_width` + doc update

**Files:**
- Modify: `backend/aurum_encuestas/style_guide.py`
- Modify: `backend/tests/test_style_guide.py`
- Modify: `docs/MANUAL-STYLE-GUIDE-FIX.md`

**Interfaces:**
- Consumes: nothing new.
- Produces: BUILTIN gains a `table_only_full_width` pattern; doc has Quick reset section.

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_style_guide.py`:

```python
def test_builtin_has_table_only_full_width_pattern():
    from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE
    matched = [p for p in BUILTIN_STYLE_GUIDE.patterns if p.id == "table_only_full_width"]
    assert len(matched) == 1, f"expected exactly one table_only_full_width pattern; got {len(matched)}"
    p = matched[0]
    assert p.priority == 10
    elements = list(p.implementation.elements)
    assert len(elements) == 1
    el = elements[0]
    # el may be a pydantic model — access via attribute or .model_dump()
    el_dict = el.model_dump() if hasattr(el, "model_dump") else el
    assert el_dict["kind"] == "chart"
    assert el_dict["chart_type"] == "TABLE_WITH_MINIBARS"
    assert el_dict["position"]["x_rel"] == 0.04
    assert el_dict["position"]["w_rel"] == 0.92
```

- [ ] **Step 2: Run failing test**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_style_guide.py::test_builtin_has_table_only_full_width_pattern -v
```

Expected: FAIL — pattern not present.

- [ ] **Step 3: Add pattern to BUILTIN_STYLE_GUIDE**

In `backend/aurum_encuestas/style_guide.py`, find the `BUILTIN_STYLE_GUIDE = StyleGuide.model_validate({...})` call. Inside `"patterns": [...]` list, append:

```python
{
    "id": "table_only_full_width",
    "priority": 10,
    "trigger": {
        "$and": [
            {"field": "question_type", "$eq": "binary"},
            {"field": "n_breakdowns", "$gte": 1},
        ],
    },
    "implementation": {
        "elements": [
            {
                "kind": "chart",
                "id": "main_table",
                "position": {"x_rel": 0.04, "y_rel": 0.18, "w_rel": 0.92, "h_rel": 0.70},
                "chart_type": "TABLE_WITH_MINIBARS",
                "data_source": {"chart_ref_index": 0, "value_field": "pct"},
            },
        ],
    },
},
```

- [ ] **Step 4: Update `docs/MANUAL-STYLE-GUIDE-FIX.md`**

Read the existing file, then prepend a new section at the top (before existing manual instructions):

```markdown
## Quick reset (recommended)

Delete your active style_guide.json entirely:

```bash
rm ~/.aurum/training/style_guide.json
```

The renderer falls back to the BUILTIN style guide, which includes a
clean `table_only_full_width` pattern for TABLE_WITH_MINIBARS + breakdown
slides. No manual JSON editing required.

You can re-run training (`/api/training/analyze`) later if you want
AI-generated patterns again.

---
```

Existing manual-edit instructions stay below as a fallback for users who prefer not to delete.

- [ ] **Step 5: Run tests**

```bash
cd backend && arch -arm64 .venv/bin/pytest tests/test_style_guide.py -v
```

Expected: new test passes + existing tests still pass.

- [ ] **Step 6: Full suite**

```bash
cd backend && arch -arm64 .venv/bin/pytest -q 2>&1 | tail -3
```

Expected: ~352 pass / 3 skip / 0 fail (depends on incremental test counts from prior tasks).

- [ ] **Step 7: Commit**

```bash
git add backend/aurum_encuestas/style_guide.py backend/tests/test_style_guide.py docs/MANUAL-STYLE-GUIDE-FIX.md
git commit -m "feat(style_guide): BUILTIN gains table_only_full_width pattern + doc reset

Pattern priority 10 wins for binary + n_breakdowns>=1 slides, rendering
a single full-width TABLE_WITH_MINIBARS element. Users who delete their
~/.aurum/training/style_guide.json fall back to this clean BUILTIN. Doc
updated with a 'Quick reset' section telling users to rm the file
instead of editing JSON by hand.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Spec coverage:**
  - Bug A balanced tree → Task 1 ✅
  - Bug B BUILTIN + doc → Task 4 ✅
  - Bug C+E databar + alignment → Task 2 ✅
  - Bug D show_legend → Tasks 2 + 3 ✅
- **Placeholder scan:** No "TBD"; all code shown verbatim. Task 1 Step 4 has a "refactor approach" block but the example code is concrete.
- **Type consistency:** All function signatures unchanged. `_sort_dir_entries_indices` and `_assign_balanced_tree` are private helpers, defined and used only in cfb_writer.
- **Open caveats:**
  - Task 1's balanced-tree depth test uses `int(ceil(log2(N+1))) + 1` — for N=4, max_allowed=4. The actual tree depth with balanced binary build over 4 entries is 3 (root + 2 children + 1 grandchild), so the bound is comfortable.
  - Task 2's `show_legend=False` test still calls existing tests — those existing tests need `src.show_legend = True` set per implementer's discretion to keep working.
  - Task 4's `priority=10` assumes no other BUILTIN pattern has higher priority. If a future pattern at priority >10 is added, the table_only pattern stops winning. Today no such pattern exists.
