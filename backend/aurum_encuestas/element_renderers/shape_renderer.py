"""M6 Shape Element Renderer — stub.

Renders ElementShape (line, rectangle) onto a python-pptx slide.
Full implementation in M6.5.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pptx.slide import Slide as PptxSlide


def render_shape(element: Any, slide: "PptxSlide", free_area: dict, resolved_colors: dict) -> None:
    """Stub: render shape element. No-op until M6.5."""
    pass
