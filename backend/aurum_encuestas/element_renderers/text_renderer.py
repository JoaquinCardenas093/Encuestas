"""M6 Text Element Renderer — stub.

Renders ElementText (analysis/static/computed content) onto a python-pptx slide
as a text box with styled runs.
Full implementation in M6.5.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pptx.slide import Slide as PptxSlide


def render_text(element: Any, slide: "PptxSlide", context: dict, free_area: dict, resolved_colors: dict) -> None:
    """Stub: render text element. No-op until M6.5."""
    pass
