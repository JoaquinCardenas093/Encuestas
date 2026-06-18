"""M6 Chart Element Renderer — stub.

Renders ElementChart onto a python-pptx slide.
Full implementation in M6.5.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pptx.slide import Slide as PptxSlide


def render_chart(element: Any, slide: "PptxSlide", data: dict, free_area: dict, resolved_colors: list[str]) -> None:
    """Stub: render chart element. No-op until M6.5."""
    pass
