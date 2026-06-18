"""Table element renderer — dispatches to structure-specific builders."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Pt

if TYPE_CHECKING:
    from .render_context import RenderContext

log = logging.getLogger(__name__)

_ALIGN_MAP = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}


def render(slide, element: dict, ctx: RenderContext) -> None:
    """Dispatch to the correct table structure builder."""
    structure = element.get("structure", "simple_data")
    if structure == "simple_data":
        _render_simple_data(slide, element, ctx)
    elif structure == "segmented_breakdowns":
        _render_segmented_breakdowns(slide, element, ctx)
    elif structure == "comparison_grid":
        _render_comparison_grid(slide, element, ctx)
    else:
        log.warning("table_renderer: unknown structure %r — falling back to simple_data", structure)
        _render_simple_data(slide, element, ctx)


# ---------------------------------------------------------------------------
# simple_data: header row + data rows
# ---------------------------------------------------------------------------

def _render_simple_data(slide, element: dict, ctx: RenderContext) -> None:
    """Basic table with one header row and N data rows."""
    from .chart_renderer import _resolve_position
    x, y, cx, cy = _resolve_position(element.get("position", {}), ctx)

    data_source = element.get("data_source", {})
    chart_ref_index = data_source.get("chart_ref_index", 0)
    charts_list = getattr(ctx.slide_config, "charts", []) or []
    if chart_ref_index >= len(charts_list):
        log.warning("table_renderer: chart_ref_index %d out of range — skipping", chart_ref_index)
        return

    source_chart = charts_list[chart_ref_index]
    question = getattr(source_chart, "question", None)
    options = question.options if question else []
    data = getattr(source_chart, "data", {}) or {}
    breakdowns = list(data.keys())

    if not breakdowns:
        return

    # Build rows: header + one row per option
    n_cols = len(breakdowns) + 1  # label col + one per breakdown
    n_rows = len(options) + 1     # header + data rows

    try:
        table_shape = slide.shapes.add_table(n_rows, n_cols, Emu(x), Emu(y), Emu(cx), Emu(cy))
        tbl = table_shape.table
    except Exception as exc:
        log.error("table_renderer: failed to add table: %s", exc)
        return

    cells_cfg = element.get("cells", {})
    header_style = (cells_cfg.get("group_header") or {}).get("style", {})

    # Header row
    _set_cell(tbl.cell(0, 0), "Opción", ctx, header_style)
    for col_idx, breakdown in enumerate(breakdowns, start=1):
        _set_cell(tbl.cell(0, col_idx), breakdown, ctx, header_style)

    # Data rows
    option_style = (cells_cfg.get("option_row") or {}).get("style", {})
    for row_idx, option in enumerate(options, start=1):
        _set_cell(tbl.cell(row_idx, 0), option, ctx, option_style)
        for col_idx, breakdown in enumerate(breakdowns, start=1):
            cell_data = (data.get(breakdown) or {}).get(option) or {}
            pct = cell_data.get("pct", 0) or 0
            _set_cell(tbl.cell(row_idx, col_idx), f"{pct * 100:.1f}%", ctx, option_style)


def _set_cell(cell, text: str, ctx: RenderContext, style: dict) -> None:
    """Set cell text and basic style."""
    tf = cell.text_frame
    tf.clear()
    p = tf.paragraphs[0]

    align_h = style.get("align_h", "left")
    p.alignment = _ALIGN_MAP.get(align_h, PP_ALIGN.LEFT)

    run = p.add_run()
    run.text = text

    font_size = style.get("font_size", ctx.typography.get("body_size", 9))
    run.font.size = Pt(font_size)

    if style.get("bold"):
        run.font.bold = True

    font_family = ctx.typography.get("font_family", "Arial")
    run.font.name = font_family

    text_color_role = style.get("text_color", "primary")
    hex_text = ctx.resolved_colors.get(text_color_role, "#000000")
    try:
        run.font.color.rgb = RGBColor.from_string(hex_text.lstrip("#"))
    except Exception:
        pass

    fill_role = style.get("fill")
    if fill_role:
        fill_hex = ctx.resolved_colors.get(fill_role)
        if fill_hex:
            try:
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor.from_string(fill_hex.lstrip("#"))
            except Exception:
                pass


# ---------------------------------------------------------------------------
# segmented_breakdowns — group_header + category_header + counts_row + option rows
# ---------------------------------------------------------------------------

def _render_segmented_breakdowns(slide, element: dict, ctx: RenderContext) -> None:
    """Build segmented breakdown table per spec section 6.

    Row layout per breakdown group:
      - group_header row (spans all categories in breakdown)
      - category_header row (one cell per category)
      - counts_row (Observaciones + N per category)
      - option_row × N_options (one row per question option)

    Columns:
      col 0            = label column (question option text / row label)
      col 1..N_cats    = one column per breakdown category
    """
    from .chart_renderer import _resolve_position
    x, y, cx, cy = _resolve_position(element.get("position", {}), ctx)

    data_source = element.get("data_source", {})
    chart_ref_index = data_source.get("chart_ref_index", 0)
    breakdown_groups_filter = data_source.get("breakdown_groups", "all_except_general")

    charts_list = getattr(ctx.slide_config, "charts", []) or []
    if chart_ref_index >= len(charts_list):
        log.warning("table_renderer segmented: chart_ref_index out of range — skipping")
        return

    source_chart = charts_list[chart_ref_index]
    question = getattr(source_chart, "question", None)
    options = question.options if question else []
    data = getattr(source_chart, "data", {}) or {}

    # Collect breakdown groups excluding General if requested
    if breakdown_groups_filter == "all_except_general":
        breakdown_keys = [k for k in data.keys() if k.lower() != "general"]
    elif breakdown_groups_filter == "all":
        breakdown_keys = list(data.keys())
    elif isinstance(breakdown_groups_filter, list):
        breakdown_keys = breakdown_groups_filter
    else:
        breakdown_keys = list(data.keys())

    if not breakdown_keys:
        log.debug("table_renderer segmented: no breakdown groups — skipping")
        return

    cells_cfg = element.get("cells", {})
    group_hdr_cfg = cells_cfg.get("group_header", {})
    cat_hdr_cfg = cells_cfg.get("category_header", {})
    counts_cfg = cells_cfg.get("counts_row", {})
    option_cfg = cells_cfg.get("option_row", {})

    # Determine columns: label col + one col per breakdown category
    n_data_cols = len(breakdown_keys)
    n_cols = 1 + n_data_cols

    # Rows per breakdown group: group_header(1) + category_header(1) + counts_row(1) + options
    N_HEADER_ROWS = 3  # group_header, category_header, counts_row
    n_rows = N_HEADER_ROWS + len(options)

    try:
        table_shape = slide.shapes.add_table(n_rows, n_cols, Emu(x), Emu(y), Emu(cx), Emu(cy))
        tbl = table_shape.table
    except Exception as exc:
        log.error("table_renderer segmented: failed to add table: %s", exc)
        return

    g_style = group_hdr_cfg.get("style", {})
    c_style = cat_hdr_cfg.get("style", {})
    cnt_style = counts_cfg.get("style", {})
    opt_style = option_cfg.get("style", {})

    # Row 0: group_header — label cell + one cell per breakdown (merge if merge_per_breakdown)
    _set_cell(tbl.cell(0, 0), "", ctx, g_style)
    for col_idx, bd_key in enumerate(breakdown_keys, start=1):
        _set_cell(tbl.cell(0, col_idx), bd_key, ctx, g_style)

    # Row 1: category_header — "Categoría" label + each breakdown category label
    _set_cell(tbl.cell(1, 0), "", ctx, c_style)
    for col_idx, bd_key in enumerate(breakdown_keys, start=1):
        _set_cell(tbl.cell(1, col_idx), bd_key, ctx, c_style)

    # Row 2: counts_row — "Observaciones" label + N per category
    counts_label = counts_cfg.get("label_first_col", "Observaciones")
    _set_cell(tbl.cell(2, 0), counts_label, ctx, cnt_style)
    for col_idx, bd_key in enumerate(breakdown_keys, start=1):
        bd_data = data.get(bd_key) or {}
        total_count = sum((bd_data.get(opt) or {}).get("count", 0) for opt in options)
        _set_cell(tbl.cell(2, col_idx), str(int(total_count)), ctx, cnt_style)

    # Rows 3+: option_rows
    value_format = option_cfg.get("value_format", "percentage")
    value_decimals = option_cfg.get("value_decimals", 1)
    minibar_cfg = option_cfg.get("minibar", {})

    for opt_idx, option in enumerate(options):
        row_idx = N_HEADER_ROWS + opt_idx
        _set_cell(tbl.cell(row_idx, 0), option, ctx, opt_style)
        for col_idx, bd_key in enumerate(breakdown_keys, start=1):
            bd_data = data.get(bd_key) or {}
            cell_data = bd_data.get(option) or {}
            pct = cell_data.get("pct", 0) or 0
            count = cell_data.get("count", 0) or 0
            if value_format == "percentage":
                val_str = f"{pct * 100:.{value_decimals}f}%"
            elif value_format == "count":
                val_str = str(int(count))
            else:  # both
                val_str = f"{pct * 100:.{value_decimals}f}% ({int(count)})"
            _set_cell(tbl.cell(row_idx, col_idx), val_str, ctx, opt_style)

    # Apply cell dimensions from layout config
    layout_cfg = element.get("layout", {})
    _apply_table_layout(tbl, layout_cfg, cx, cy, len(options))

    # Minibar overlays — rendered after table is positioned
    if minibar_cfg.get("enabled", False):
        _render_minibar_overlays(
            slide, tbl, options, breakdown_keys, data,
            minibar_cfg, opt_style, ctx,
            table_x=x, table_y=y, table_cx=cx, table_cy=cy,
            n_header_rows=N_HEADER_ROWS,
        )


def _apply_table_layout(tbl, layout_cfg: dict, total_cx: int, total_cy: int, n_options: int) -> None:
    """Set column widths and row heights from layout config."""
    try:
        col_widths = layout_cfg.get("col_widths", "auto")
        if col_widths == "equal" or col_widths == "auto":
            per_col = total_cx // max(len(tbl.columns), 1)
            for col in tbl.columns:
                col.width = per_col
        elif isinstance(col_widths, list):
            for i, w_rel in enumerate(col_widths):
                if i < len(tbl.columns):
                    tbl.columns[i].width = int(w_rel * total_cx)
    except Exception as exc:
        log.debug("Could not set column widths: %s", exc)


def _render_minibar_overlays(
    slide, tbl, options: list, breakdown_keys: list, data: dict,
    minibar_cfg: dict, opt_style: dict, ctx: RenderContext,
    table_x: int, table_y: int, table_cx: int, table_cy: int,
    n_header_rows: int,
) -> None:
    """Add MSO rectangle overlays on option row cells to represent minibar values."""
    color_role = minibar_cfg.get("color_role", "primary")
    bar_hex = ctx.resolved_colors.get(color_role, "#7F7F7F")
    height_rel = minibar_cfg.get("height_rel_to_cell", 0.4)
    show_pct_text = minibar_cfg.get("show_percent_text", False)
    pct_text_pos = minibar_cfg.get("percent_text_position", "left_of_bar")

    try:
        # Compute cumulative column X offsets
        col_x_offsets = [0]
        for col in tbl.columns:
            col_x_offsets.append(col_x_offsets[-1] + col.width)

        # Compute cumulative row Y offsets
        row_y_offsets = [0]
        for row in tbl.rows:
            row_y_offsets.append(row_y_offsets[-1] + row.height)

        for opt_idx in range(len(options)):
            row_idx = n_header_rows + opt_idx
            if row_idx >= len(row_y_offsets) - 1:
                continue
            cell_y_abs = table_y + row_y_offsets[row_idx]
            cell_h = tbl.rows[row_idx].height
            bar_h = int(cell_h * height_rel)
            bar_y = cell_y_abs + (cell_h - bar_h) // 2

            option = options[opt_idx]
            for col_idx, bd_key in enumerate(breakdown_keys, start=1):
                if col_idx >= len(col_x_offsets):
                    continue
                cell_x_abs = table_x + col_x_offsets[col_idx]
                cell_w = tbl.columns[col_idx].width

                bd_data = data.get(bd_key) or {}
                pct = (bd_data.get(option) or {}).get("pct", 0) or 0
                bar_w = int(cell_w * float(pct))
                if bar_w <= 0:
                    continue

                # Add minibar rectangle
                try:
                    bar_shape = slide.shapes.add_shape(
                        1,  # MSO_SHAPE_TYPE.RECTANGLE
                        Emu(cell_x_abs), Emu(bar_y), Emu(bar_w), Emu(bar_h),
                    )
                    bar_shape.fill.solid()
                    bar_shape.fill.fore_color.rgb = RGBColor.from_string(bar_hex.lstrip("#"))
                    bar_shape.line.fill.background()
                except Exception as exc:
                    log.debug("minibar overlay: could not add rect: %s", exc)
                    continue

                # Percent text overlay
                if show_pct_text:
                    pct_str = f"{pct * 100:.1f}%"
                    if pct_text_pos == "left_of_bar":
                        txt_x = cell_x_abs
                        txt_w = bar_w
                    elif pct_text_pos == "right_of_bar":
                        txt_x = cell_x_abs + bar_w
                        txt_w = cell_w - bar_w
                    else:  # inside_bar
                        txt_x = cell_x_abs
                        txt_w = bar_w
                    try:
                        txt_shape = slide.shapes.add_textbox(
                            Emu(txt_x), Emu(bar_y), Emu(max(txt_w, 1)), Emu(bar_h),
                        )
                        tf = txt_shape.text_frame
                        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
                        run = tf.paragraphs[0].add_run()
                        run.text = pct_str
                        run.font.size = Pt(ctx.typography.get("label_size", 8))
                        run.font.name = ctx.typography.get("font_family", "Arial")
                    except Exception as exc:
                        log.debug("minibar text overlay failed: %s", exc)
    except Exception as exc:
        log.warning("minibar overlays: error: %s", exc)


# ---------------------------------------------------------------------------
# comparison_grid — side-by-side breakdown comparison
# ---------------------------------------------------------------------------

def _render_comparison_grid(slide, element: dict, ctx: RenderContext) -> None:
    """Side-by-side comparison of breakdown data for the same question.

    Layout:
      Row 0: header — blank + one col per breakdown
      Row 1+: one row per question option, values side-by-side
    """
    from .chart_renderer import _resolve_position
    x, y, cx, cy = _resolve_position(element.get("position", {}), ctx)

    data_source = element.get("data_source", {})
    chart_ref_index = data_source.get("chart_ref_index", 0)
    charts_list = getattr(ctx.slide_config, "charts", []) or []
    if chart_ref_index >= len(charts_list):
        log.warning("comparison_grid: chart_ref_index out of range — skipping")
        return

    source_chart = charts_list[chart_ref_index]
    question = getattr(source_chart, "question", None)
    options = question.options if question else []
    data = getattr(source_chart, "data", {}) or {}
    breakdown_keys = list(data.keys())

    if not breakdown_keys or not options:
        return

    n_cols = 1 + len(breakdown_keys)
    n_rows = 1 + len(options)

    try:
        table_shape = slide.shapes.add_table(n_rows, n_cols, Emu(x), Emu(y), Emu(cx), Emu(cy))
        tbl = table_shape.table
    except Exception as exc:
        log.error("comparison_grid: failed to add table: %s", exc)
        return

    cells_cfg = element.get("cells", {})
    header_style = (cells_cfg.get("group_header") or {}).get("style", {})
    option_style = (cells_cfg.get("option_row") or {}).get("style", {})
    option_cfg = cells_cfg.get("option_row", {})
    value_format = option_cfg.get("value_format", "percentage")
    value_decimals = option_cfg.get("value_decimals", 1)

    # Header row
    _set_cell(tbl.cell(0, 0), "Opción", ctx, header_style)
    for col_idx, bd_key in enumerate(breakdown_keys, start=1):
        _set_cell(tbl.cell(0, col_idx), bd_key, ctx, header_style)

    # Data rows
    for row_idx, option in enumerate(options, start=1):
        _set_cell(tbl.cell(row_idx, 0), option, ctx, option_style)
        for col_idx, bd_key in enumerate(breakdown_keys, start=1):
            bd_data = data.get(bd_key) or {}
            cell_data = bd_data.get(option) or {}
            pct = cell_data.get("pct", 0) or 0
            count = cell_data.get("count", 0) or 0
            if value_format == "percentage":
                val_str = f"{pct * 100:.{value_decimals}f}%"
            elif value_format == "count":
                val_str = str(int(count))
            else:
                val_str = f"{pct * 100:.{value_decimals}f}% ({int(count)})"
            _set_cell(tbl.cell(row_idx, col_idx), val_str, ctx, option_style)
