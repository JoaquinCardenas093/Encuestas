"""Shape element renderer — line and rectangle."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pptx.dml.color import RGBColor
from pptx.util import Emu, Pt

if TYPE_CHECKING:
    from .render_context import RenderContext

log = logging.getLogger(__name__)


def render(slide, element: dict, ctx: RenderContext) -> None:
    """Render a shape element (line or rectangle) onto slide."""
    from .chart_renderer import _resolve_position
    x, y, cx, cy = _resolve_position(element.get("position", {}), ctx)
    style = element.get("style") or {}
    shape_type = element.get("shape_type", "rectangle")

    color_role = style.get("color", "primary")
    hex_color = ctx.resolved_colors.get(color_role, "#7F7F7F")

    if shape_type == "line":
        _render_line(slide, x, y, cx, cy, hex_color, style.get("width_pt", 1.0))
    else:
        _render_rectangle(slide, x, y, cx, cy, hex_color, style, ctx)


def _render_line(slide, x: int, y: int, cx: int, cy: int, hex_color: str, width_pt: float) -> None:
    try:
        # Use a thin rectangle to simulate a line (1pt height if cy==0)
        height = cy if cy > 0 else int(Pt(1))
        rect = slide.shapes.add_shape(1, Emu(x), Emu(y), Emu(cx), Emu(height))
        rect.fill.solid()
        rect.fill.fore_color.rgb = RGBColor.from_string(hex_color.lstrip("#"))
        rect.line.fill.background()
    except Exception as exc:
        log.warning("shape_renderer: could not render line: %s", exc)


def _render_rectangle(slide, x: int, y: int, cx: int, cy: int, hex_color: str, style: dict, ctx: RenderContext) -> None:
    try:
        rect = slide.shapes.add_shape(1, Emu(x), Emu(y), Emu(cx), Emu(cy))
        fill_role = style.get("fill")
        if fill_role:
            fill_hex = ctx.resolved_colors.get(fill_role, hex_color)
            rect.fill.solid()
            rect.fill.fore_color.rgb = RGBColor.from_string(fill_hex.lstrip("#"))
        else:
            rect.fill.background()
        rect.line.fill.background()
    except Exception as exc:
        log.warning("shape_renderer: could not render rectangle: %s", exc)
