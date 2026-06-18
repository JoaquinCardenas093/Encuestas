"""M6 Table Element Renderer — stub.

Renders ElementTable (segmented_breakdowns, comparison_grid, simple_data)
onto a python-pptx slide using native table shapes.
Full implementation in M6.5.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pptx.slide import Slide as PptxSlide


def render_table(element: Any, slide: "PptxSlide", data: dict, free_area: dict, resolved_colors: dict) -> None:
    """Stub: render table element. No-op until M6.5."""
    pass
