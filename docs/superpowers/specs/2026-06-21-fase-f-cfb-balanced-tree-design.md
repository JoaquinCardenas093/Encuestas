# Fase F — CFB Balanced Tree + Excel Format Polish + show_legend Toggle Design Spec

**Date:** 2026-06-21
**Status:** Approved (brainstorming) → ready for writing-plans
**Branch base:** `main` at `b475c3e` (post Fase E merge)

## Goal

Fix bugs reported after Fase E ship:

1. **PowerPoint still flags "Reparar" on open**: Mac PowerPoint applies a strict MS-CFB §2.6.4 validator that rejects right-leaning sibling chains + allocation-order entry layout. Fix: implement a balanced red-black tree over sorted entries inside `cfb_writer`.

2. **Slide still shows "Distribución general/segmentada" + extra empty/yellow tables**: AI-generated `~/.aurum/training/style_guide.json` carries the old split pattern. User wipes it; renderer falls back to `BUILTIN_STYLE_GUIDE` which must contain a single-element TABLE_WITH_MINIBARS pattern for breakdown slides.

3. **Excel xlsx format too pale / text misaligned**: bars too dark, value text overlaps bar. Switch DataBarRule color to a more visible pale-gray, right-align value text inside cells.

4. **show_legend toggle ignored by xlsx + PNG**: `Chart.show_legend` field exists since Fase B but `xlsx_builder` and `ole_png_renderer` always render the label col regardless. Read the field; omit label col when False.

## Non-Goals

- Charts (PIE / BAR / their _GROUPED variants): untouched.
- Frontend: zero changes.
- Re-running corpus training: user-driven.

## Locked decisions

1. **Bug A**: balanced red-black tree per MS-CFB §2.6.4, entries sorted by `(name_length, UPPER(name) UTF-16)`.
2. **Bug B**: BUILTIN_STYLE_GUIDE gains a `table_only_full_width` pattern; user wipes their style_guide.json to use BUILTIN. Manual fix doc updated.
3. **Bug C+E**: DataBarRule color `D9D9D9`. Data cells right-aligned. PIL bar color `(217,217,217)` matching.
4. **Bug D**: `xlsx_builder` and `ole_png_renderer` read `source_chart.show_legend`. When False: skip label col entirely.

## Architecture

```
cfb_writer.build_excel_ole_cfb
   ├─ Streams allocation (unchanged)
   ├─ _sort_entries(entries) → sorted by (name_len_chars, UPPER(name_utf16))
   ├─ _build_balanced_tree(sorted_entries) → assigns left_sib/right_sib/color
   │      and returns the root entry index (used by Root.child)
   └─ Header + FAT + dir (with balanced entries) + mini-FAT + streams

xlsx_builder.build_xlsx_for_table(source_chart, breakdown_groups)
   ├─ show_legend = getattr(source_chart, "show_legend", False)
   ├─ if show_legend: render label col + data cols
   ├─ else: only data cols, starts at col 1
   ├─ DataBarRule color = "D9D9D9"
   └─ Data cells: Alignment(horizontal="right", indent=1)

ole_png_renderer.render_table_preview_png(source_chart, breakdown_groups, w_emu, h_emu)
   ├─ show_legend = getattr(source_chart, "show_legend", False)
   ├─ if show_legend: per-panel label col + data cols
   ├─ else: only data cols
   └─ BAR_GRAY = (217, 217, 217)

ole_table_renderer.render: no signature change, just propagates source_chart
   to builder + renderer (already does via getattr inside helpers).

BUILTIN_STYLE_GUIDE: add `table_only_full_width` pattern:
   trigger: question_type=binary AND n_breakdowns>=1
   priority: 10 (high — beats binary_general_with_demographics)
   implementation.elements: single kind=chart, chart_type=TABLE_WITH_MINIBARS,
                            position {x_rel=0.04, y_rel=0.18, w_rel=0.92, h_rel=0.70}
```

## Component contracts

### `cfb_writer.build_excel_ole_cfb(xlsx_bytes: bytes) -> bytes`

Signature unchanged. Internally:
1. Build the 5 dir entries (Root + Package + 3 mini streams).
2. Sort the 4 non-Root entries by `(utf16_name_byte_length, UPPER(name).encode("utf-16-le"))`.
3. Build a balanced binary tree (approximation of red-black): pick middle of sorted list as root, recurse on left/right halves. Color middle BLACK (1), others RED (0).
4. Update Root entry's `child` field to point at the tree root index.
5. Update each entry's `left_sib`/`right_sib` to the tree children indices (or `NOSTREAM` if leaf).

Other CFB structure unchanged.

### `xlsx_builder.build_xlsx_for_table(source_chart, breakdown_groups) -> BytesIO`

Signature unchanged. Internal change:
- Read `show_legend = bool(getattr(source_chart, "show_legend", False))`.
- When True: render col A (label_col) with "Observaciones" + option labels per breakdown (as today).
- When False: skip col A entirely; first data col is `data_start = cur_col`, merge spans only data cols.
- DataBarRule color literal changes from `"BFBFBF"` to `"D9D9D9"`.
- Body data cells use `Alignment(horizontal="right", indent=1)` instead of left-align (so the value text sits to the right of the bar inside each cell).

### `ole_png_renderer.render_table_preview_png(source_chart, breakdown_groups, w_emu, h_emu) -> bytes`

Signature unchanged. Internal change:
- Read `show_legend = bool(getattr(source_chart, "show_legend", False))`.
- When False: each panel = just data cols; no per-panel label col.
- `BAR_GRAY` constant changes from `(191, 191, 191)` to `(217, 217, 217)`.

### `style_guide.py` BUILTIN

Add a new pattern entry to `BUILTIN_STYLE_GUIDE`:

```python
{
    "id": "table_only_full_width",
    "priority": 10,
    "trigger": {
        "$and": [
            {"field": "question_type", "$eq": "binary"},
            {"field": "n_breakdowns", "$gte": 1}
        ]
    },
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

Higher priority than the existing `binary_general_with_demographics` (priority 0) so this wins for breakdown-table slides.

### `docs/MANUAL-STYLE-GUIDE-FIX.md`

Add a section "Quick reset (recommended)":

```
## Quick reset (recommended)

Delete your active style_guide.json entirely:

  rm ~/.aurum/training/style_guide.json

The renderer falls back to the BUILTIN style guide, which includes a
clean `table_only_full_width` pattern for TABLE_WITH_MINIBARS + breakdown
slides. No manual JSON editing required.

You can re-run training (`/api/training/analyze`) later if you want
AI-generated patterns again.
```

## Testing strategy

### Backend tests

`backend/tests/test_cfb_writer.py` (append):
- `test_dir_entries_sorted_by_msfb_rule` — extract dir entries via olefile, assert siblings come in `(length, UPPER(name))` order.
- `test_dir_tree_balanced` — extract tree via olefile, assert tree depth ≤ ceil(log2(N+1)) + 1.
- Existing 6 tests still pass.

`backend/tests/test_xlsx_builder.py` (append):
- `test_xlsx_show_legend_true_includes_label_col` — col A has labels.
- `test_xlsx_show_legend_false_no_label_col` — col A is empty/unused.
- `test_databar_color_is_d9d9d9` — assert color hex.
- `test_data_cell_alignment_right` — assert `cell.alignment.horizontal == "right"`.

`backend/tests/test_ole_png_renderer.py` (append):
- `test_png_show_legend_false_skips_panel_label` — sample pixels at label col position; expect background.

`backend/tests/test_style_guide.py` (append):
- `test_builtin_has_table_only_full_width_pattern` — assert pattern present with priority 10 + correct trigger.

Existing tests adapt:
- Existing `xlsx_builder` tests that assumed label col always present: pass `show_legend=True` via SimpleNamespace fixture.
- Existing `ole_png_renderer` tests: same.

## File map

Modified:
- `backend/aurum_encuestas/element_renderers/cfb_writer.py`
- `backend/aurum_encuestas/element_renderers/xlsx_builder.py`
- `backend/aurum_encuestas/element_renderers/ole_png_renderer.py`
- `backend/aurum_encuestas/style_guide.py`
- `backend/tests/test_cfb_writer.py`
- `backend/tests/test_xlsx_builder.py`
- `backend/tests/test_ole_png_renderer.py`
- `backend/tests/test_style_guide.py`
- `docs/MANUAL-STYLE-GUIDE-FIX.md`

Untouched:
- Frontend.
- `ole_embedder.py`, `ole_table_renderer.py` (propagation already via getattr).
- `pattern_renderer.py`, `chart_renderer.py`, `table_renderer.py`.
- `models.py`, `pattern_classifier.py`.

## Open risks

1. **Balanced tree spec edge cases**: MS-CFB §2.6.4 requires actual red-black properties; my approximation (balanced binary tree, color middle BLACK) may still trip strict validators. Mitigation: verify with `oletools` if installed; round-trip via olefile asserts core invariants.

2. **`show_legend=False` breaks existing test fixtures**: existing xlsx tests assume label col exists. Need to either default fixture `show_legend=True` or split fixtures.

3. **BUILTIN pattern priority**: `priority=10` must beat all other binary+breakdown patterns. If another pattern has priority >10, this won't match. Verify by inspecting BUILTIN_STYLE_GUIDE other priorities.

4. **DataBarRule color too pale on Windows**: `#D9D9D9` may be invisible on white. Test on real Excel Mac + Windows during smoke validation.

5. **Manual style_guide wipe is user-driven**: doc updated but user must actually `rm`. No automation.
