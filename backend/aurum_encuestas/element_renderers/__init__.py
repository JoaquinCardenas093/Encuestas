"""M6 Element Renderers package.

Each submodule handles one element kind from the style guide schema:
  chart_renderer   — PIE, BAR_HORIZONTAL, etc.  (M6.5)
  table_renderer   — segmented_breakdowns, etc.  (M6.5)
  text_renderer    — analysis text boxes         (M6.5)
  shape_renderer   — lines, rectangles           (M6.5)
  image_renderer   — template image refs         (M6.5)

All render functions are stubs until M6.5.
"""

from .chart_renderer import render_chart
from .table_renderer import render_table
from .text_renderer import render_text
from .shape_renderer import render_shape
from .image_renderer import render_image

__all__ = ["render_chart", "render_table", "render_text", "render_shape", "render_image"]
