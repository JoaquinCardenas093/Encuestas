"""M6 Image Element Renderer — stub.

Renders ElementImage (template shape reference) onto a python-pptx slide.
Full implementation in M6.5.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pptx.slide import Slide as PptxSlide


def render_image(element: Any, slide: "PptxSlide", template_shapes: list, free_area: dict) -> None:
    """Stub: render image element. No-op until M6.5."""
    pass
