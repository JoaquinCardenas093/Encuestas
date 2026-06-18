"""M6 Pattern Renderer — orchestrates element rendering for a matched pattern.

Resolves positions (rel→abs via free_area), resolves data sources, resolves
color roles, and dispatches to element_renderers[kind].
Full implementation in M6.6. This stub is a no-op.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pptx.slide import Slide as PptxSlide
    from .style_guide import Pattern


def render_pattern(
    pattern: "Pattern",
    slide: "PptxSlide",
    slide_config: dict,
    parsed_db: dict,
    free_area: dict,
    chart_colors: list[str],
    project_palette: dict | None,
    style_guide: Any,
) -> None:
    """Stub: render all elements of a matched pattern onto a python-pptx slide.

    No-op until M6.6. The caller (pptx_generator) falls back to legacy chart
    insertion when this returns without adding shapes.
    """
    pass
