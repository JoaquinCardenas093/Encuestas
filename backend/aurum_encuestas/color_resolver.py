"""M6 Color Resolver — symbolic color role → hex cascade.

Cascade: chart.colors[i] → project.palette[role] → style_guide.suggested_palette[i] → built-in greys.
Auto-derive N colors from primary via lumMod variations.
Full implementation in M6.4. This stub returns sensible built-in defaults.
"""
from __future__ import annotations

from typing import Optional

_BUILTIN_DEFAULTS = ["#7F7F7F", "#BFBFBF", "#FFC000", "#404040", "#D9D9D9", "#A6A6A6", "#595959", "#D6D6D6"]


def resolve(
    role: str,
    chart_colors: list[str],
    project_palette: dict | None,
    style_guide,
    element_idx: int = 0,
) -> str:
    """Stub: resolve symbolic color role to hex.

    Returns a built-in grey until M6.4 implements the full cascade.
    """
    if chart_colors and element_idx < len(chart_colors):
        return chart_colors[element_idx]
    if project_palette and role in project_palette:
        return project_palette[role]
    return _BUILTIN_DEFAULTS[element_idx % len(_BUILTIN_DEFAULTS)]


def auto_derive(primary_hex: str, n: int) -> list[str]:
    """Stub: derive N colors from primary via lumMod variations.

    Returns [primary_hex] repeated n times until M6.4 implements real lumMod.
    """
    return [primary_hex] * n


def update_recent(hex_color: str) -> None:
    """Stub: write hex_color to ~/.aurum/config.json recent_colors list.

    No-op until M6.4.
    """
    pass
