"""Image element renderer — copies referenced template image shape to slide."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .render_context import RenderContext

log = logging.getLogger(__name__)


def render(slide, element: dict, ctx: RenderContext) -> None:
    """Render an image element by referencing a named template shape.

    Images in the Aurum pattern system live in the template PPTX. The renderer
    looks up the shape by source_ref ID in ctx.slide_config.template_shapes
    (a dict populated by pattern_renderer from the template slide). If the shape
    is not found, the renderer silently skips — missing logos should not crash
    generation.
    """
    source_ref = element.get("source_ref", "")
    template_shapes = getattr(ctx.slide_config, "template_shapes", {}) or {}

    template_shape = template_shapes.get(source_ref)
    if template_shape is None:
        log.debug("image_renderer: template shape %r not found — skipping", source_ref)
        return

    from .chart_renderer import _resolve_position
    x, y, cx, cy = _resolve_position(element.get("position", {}), ctx)

    try:
        _copy_picture_shape(slide, template_shape, x, y, cx, cy)
    except Exception as exc:
        log.warning("image_renderer: could not copy shape %r: %s", source_ref, exc)


def _copy_picture_shape(slide, template_shape, x: int, y: int, cx: int, cy: int) -> None:
    """Deep-copy a picture shape from template to target slide at new position."""
    import copy

    sp_tree = slide.shapes._spTree
    elem_copy = copy.deepcopy(template_shape._element)

    # Update position and size in the copied XML element
    xfrm_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    xfrm = elem_copy.find(f".//{{{xfrm_ns}}}xfrm")
    if xfrm is not None:
        off = xfrm.find(f"{{{xfrm_ns}}}off")
        ext = xfrm.find(f"{{{xfrm_ns}}}ext")
        if off is not None:
            off.set("x", str(x))
            off.set("y", str(y))
        if ext is not None:
            ext.set("cx", str(cx))
            ext.set("cy", str(cy))

    sp_tree.append(elem_copy)
