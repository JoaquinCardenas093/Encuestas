"""Chart element renderer — dispatches all 9 chart types via python-pptx."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.util import Emu, Pt

if TYPE_CHECKING:
    from .render_context import RenderContext

log = logging.getLogger(__name__)

# Mapping from spec chart_type string to python-pptx XL_CHART_TYPE
_CHART_TYPE_MAP: dict[str, int] = {
    "PIE":               XL_CHART_TYPE.PIE,
    "DONUT":             XL_CHART_TYPE.DOUGHNUT,
    "BAR_HORIZONTAL":    XL_CHART_TYPE.BAR_CLUSTERED,
    "BAR_CLUSTERED":     XL_CHART_TYPE.BAR_CLUSTERED,
    "BAR_STACKED":       XL_CHART_TYPE.BAR_STACKED,
    "COLUMN_CLUSTERED":  XL_CHART_TYPE.COLUMN_CLUSTERED,
    "COLUMN_STACKED":    XL_CHART_TYPE.COLUMN_STACKED,
    "LINE":              XL_CHART_TYPE.LINE,
    "AREA":              XL_CHART_TYPE.AREA,
}

_LABEL_POSITION_MAP = {
    "inside":       XL_LABEL_POSITION.INSIDE_END,
    "outside_end":  XL_LABEL_POSITION.OUTSIDE_END,
    "center":       XL_LABEL_POSITION.CENTER,
    "best_fit":     XL_LABEL_POSITION.BEST_FIT,
}

_LEGEND_POSITION_MAP = {
    "right":  XL_LEGEND_POSITION.RIGHT,
    "bottom": XL_LEGEND_POSITION.BOTTOM,
    "top":    XL_LEGEND_POSITION.TOP,
    "left":   XL_LEGEND_POSITION.LEFT,
}


def render(slide, element: dict, ctx: RenderContext) -> None:
    """Render a chart element onto slide in-place."""
    chart_type_str = element.get("chart_type", "BAR_HORIZONTAL")
    xl_chart_type = _CHART_TYPE_MAP.get(chart_type_str)
    if xl_chart_type is None:
        log.warning("Unknown chart_type %r — falling back to BAR_CLUSTERED", chart_type_str)
        xl_chart_type = XL_CHART_TYPE.BAR_CLUSTERED

    # Resolve data source
    data_source = element.get("data_source", {})
    chart_ref_index = data_source.get("chart_ref_index", 0)
    value_field = data_source.get("value_field", "pct")

    charts_list = getattr(ctx.slide_config, "charts", []) or []
    if chart_ref_index >= len(charts_list):
        log.warning("chart_ref_index %d out of range (have %d charts) — skipping", chart_ref_index, len(charts_list))
        return

    source_chart = charts_list[chart_ref_index]

    # Build CategoryChartData
    chart_data = _build_chart_data(source_chart, value_field, element.get("sort", "none"))

    # Resolve position
    x, y, cx, cy = _resolve_position(element.get("position", {}), ctx)

    # Add chart shape
    try:
        chart_shape = slide.shapes.add_chart(xl_chart_type, Emu(x), Emu(y), Emu(cx), Emu(cy), chart_data)
    except Exception as exc:
        log.error("Failed to add chart shape: %s", exc)
        return

    chart = chart_shape.chart

    # Apply colors to series
    _apply_series_colors(chart, ctx.chart_colors)

    # Apply labels
    labels_cfg = element.get("labels", {})
    _apply_labels(chart, labels_cfg, ctx)

    # Apply legend
    legend_str = element.get("legend", "none")
    if legend_str == "none":
        chart.has_legend = False
    else:
        chart.has_legend = True
        pos = _LEGEND_POSITION_MAP.get(legend_str, XL_LEGEND_POSITION.RIGHT)
        chart.legend.position = pos
        chart.legend.include_in_layout = False

    # Chart title
    title_text = element.get("title")
    if title_text:
        chart.has_title = True
        chart.chart_title.text_frame.text = title_text
    else:
        chart.has_title = False


def _build_chart_data(source_chart, value_field: str, sort: str) -> CategoryChartData:
    """Extract CategoryChartData from a slide_config chart object."""
    cd = CategoryChartData()

    question = getattr(source_chart, "question", None)
    options = question.options if question else []
    data = getattr(source_chart, "data", {}) or {}

    # Use General breakdown or first available
    breakdown_data = data.get("General") or (next(iter(data.values())) if data else {})

    if not options and breakdown_data:
        options = list(breakdown_data.keys())

    # Sort if requested
    if sort in ("desc_by_value", "asc_by_value") and breakdown_data:
        reverse = sort == "desc_by_value"
        options = sorted(
            options,
            key=lambda o: (breakdown_data.get(o) or {}).get(value_field, 0),
            reverse=reverse,
        )

    cd.categories = options

    values = []
    for opt in options:
        cell = (breakdown_data.get(opt) or {})
        v = cell.get(value_field, 0) or 0
        values.append(float(v))

    cd.add_series("", values)
    return cd


def _apply_series_colors(chart, colors: list[str]) -> None:
    """Apply hex color list to chart series/points."""
    try:
        for series_idx, series in enumerate(chart.series):
            if series_idx < len(colors):
                fill = series.format.fill
                fill.solid()
                fill.fore_color.rgb = RGBColor.from_string(colors[series_idx].lstrip("#"))
            # For pie/donut, color individual points
            try:
                for point_idx, point in enumerate(series.points):
                    color = colors[point_idx % len(colors)] if colors else "#7F7F7F"
                    point.format.fill.solid()
                    point.format.fill.fore_color.rgb = RGBColor.from_string(color.lstrip("#"))
            except Exception:
                pass  # Not all chart types support per-point coloring
    except Exception as exc:
        log.debug("Could not apply series colors: %s", exc)


def _apply_labels(chart, labels_cfg: dict, ctx: RenderContext) -> None:
    """Apply label settings to all plot series."""
    if not labels_cfg:
        return
    try:
        plot = chart.plots[0]
        plot.has_data_labels = any([
            labels_cfg.get("show_category_name"),
            labels_cfg.get("show_value"),
            labels_cfg.get("show_percentage"),
        ])
        if not plot.has_data_labels:
            return

        dls = plot.data_labels
        if labels_cfg.get("show_category_name"):
            dls.show_category_name = True
        if labels_cfg.get("show_percentage"):
            dls.show_percentage = True
        if labels_cfg.get("show_value"):
            dls.show_value = True

        pos_str = labels_cfg.get("position", "outside_end")
        pos = _LABEL_POSITION_MAP.get(pos_str, XL_LABEL_POSITION.OUTSIDE_END)
        try:
            dls.position = pos
        except Exception:
            pass

        font_size = labels_cfg.get("font_size") or ctx.typography.get("label_size", 9)
        try:
            dls.font.size = Pt(font_size)
        except Exception:
            pass
    except Exception as exc:
        log.debug("Could not apply labels: %s", exc)


def _resolve_position(position: dict, ctx: RenderContext) -> tuple[int, int, int, int]:
    """Convert relative position dict to absolute EMU via free_area."""
    fa = ctx.free_area
    fa_x = fa.get("x", 0)
    fa_y = fa.get("y", 0)
    fa_cx = fa.get("cx", 1)
    fa_cy = fa.get("cy", 1)

    if "anchor" in position:
        anchor_id = position["anchor"]
        anchor_rect = ctx.resolved_anchors.get(anchor_id, {})
        base_x = anchor_rect.get("x", fa_x)
        base_y = anchor_rect.get("y", fa_y)
        base_cx = anchor_rect.get("cx", fa_cx)
        base_cy = anchor_rect.get("cy", fa_cy)
        relative = position.get("relative", "right_of")
        offset_rel = position.get("offset_rel", 0.0)
        w_rel = position.get("w_rel", 0.3)
        h_rel = position.get("h_rel", 0.5)
        w = int(w_rel * fa_cx)
        h = int(h_rel * fa_cy)
        offset = int(offset_rel * fa_cx)
        if relative == "right_of":
            x = base_x + base_cx + offset
            y = base_y
        elif relative == "below":
            x = base_x
            y = base_y + base_cy + offset
        elif relative == "above":
            x = base_x
            y = base_y - h - offset
        elif relative == "left_of":
            x = base_x - w - offset
            y = base_y
        else:
            x, y = base_x, base_y
        return x, y, w, h

    x_rel = position.get("x_rel", 0.0)
    y_rel = position.get("y_rel", 0.0)
    w_rel = position.get("w_rel", 0.5)
    h_rel = position.get("h_rel", 0.5)
    x = fa_x + int(x_rel * fa_cx)
    y = fa_y + int(y_rel * fa_cy)
    w = int(w_rel * fa_cx)
    h = int(h_rel * fa_cy)
    return x, y, w, h
