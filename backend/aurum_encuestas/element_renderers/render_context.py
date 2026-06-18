from dataclasses import dataclass, field
from typing import Any


@dataclass
class RenderContext:
    """Carries all resolved data needed by element renderers."""
    free_area: dict                      # {x, y, cx, cy} in EMU
    chart_colors: list[str]              # hex strings, per-series
    resolved_colors: dict[str, str]      # role -> hex (primary, secondary, background, accent, ...)
    typography: dict[str, Any]           # font_family, title_size, label_size, body_size, etc.
    slide_config: Any                    # slide config object (charts, analyses, parsed_db ref)
    style_guide: Any = None              # full StyleGuide for global settings
    resolved_anchors: dict[str, dict] = field(default_factory=dict)  # element_id -> {x,y,cx,cy} EMU
