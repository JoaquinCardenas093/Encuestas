"""M6 Color Resolver.

Symbolic color role → hex cascade:
  1. chart.colors[element_idx]                   (per-chart explicit)
  2. project_palette[role]                       (project-level)
  3. style_guide.global.suggested_palette[idx]   (AI-suggested)
  4. _BUILTIN_DEFAULTS[idx % len]                (fallback greys)

All returned hex values are normalized to #RRGGBB uppercase.

Auto-derive: auto_derive(primary_hex, n) produces n colors from primary using
lumMod-like lightness variation (implemented in pure RGB/HLS — no external deps).
"""
from __future__ import annotations

import colorsys
import logging
import re
from typing import Any

log = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# Built-in default palette (neutral greys + accent)
# ────────────────────────────────────────────────────────────────────────────

_BUILTIN_DEFAULTS: list[str] = [
    "#7F7F7F",  # primary grey
    "#BFBFBF",  # secondary light grey
    "#FFC000",  # accent yellow
    "#404040",  # dark grey
    "#D9D9D9",  # very light grey
    "#A6A6A6",  # mid grey
    "#595959",  # dark mid grey
    "#D6D6D6",  # near-white grey
]

# ────────────────────────────────────────────────────────────────────────────
# hex normalization
# ────────────────────────────────────────────────────────────────────────────

_HEX_RE = re.compile(r"^#?([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")


def normalize_hex(color: str) -> str:
    """Normalize a hex color string to #RRGGBB uppercase.

    Accepts: #RGB, RGB, #RRGGBB, RRGGBB (case-insensitive).
    Returns _BUILTIN_DEFAULTS[0] (#7F7F7F) for invalid inputs.
    """
    if not isinstance(color, str):
        return _BUILTIN_DEFAULTS[0]

    color = color.strip()
    m = _HEX_RE.match(color)
    if not m:
        return _BUILTIN_DEFAULTS[0]

    h = m.group(1)
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2  # expand #RGB → RRGGBB
    return f"#{h.upper()}"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = normalize_hex(hex_color).lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


# ────────────────────────────────────────────────────────────────────────────
# resolve — main cascade
# ────────────────────────────────────────────────────────────────────────────

def resolve(
    role: str,
    chart_colors: list[str],
    project_palette: dict | None,
    style_guide,
    element_idx: int = 0,
) -> str:
    """Resolve a symbolic color role to a normalized hex string.

    Cascade (first non-empty wins):
    1. chart_colors[element_idx]
    2. project_palette[role]
    3. style_guide.global_.suggested_palette[element_idx % len]
    4. _BUILTIN_DEFAULTS[element_idx % len]
    """
    # 1. chart.colors[element_idx]
    if chart_colors and element_idx < len(chart_colors):
        return normalize_hex(chart_colors[element_idx])

    # 2. project_palette[role]
    if project_palette and role in project_palette:
        return normalize_hex(project_palette[role])

    # 3. style_guide.global_.suggested_palette
    try:
        palette = style_guide.global_.suggested_palette
        if palette:
            return normalize_hex(palette[element_idx % len(palette)])
    except (AttributeError, TypeError, IndexError) as exc:
        log.debug("resolve: error accessing style_guide palette: %s", exc)

    # 4. built-in defaults
    return _BUILTIN_DEFAULTS[element_idx % len(_BUILTIN_DEFAULTS)]


# ────────────────────────────────────────────────────────────────────────────
# auto_derive — N colors from primary via HLS lightness variations
# ────────────────────────────────────────────────────────────────────────────

def auto_derive(primary_hex: str, n: int) -> list[str]:
    """Derive n colors from a single primary hex using HLS lightness modulation.

    Strategy:
    - color[0] = primary (unchanged)
    - colors[1..n-1] = primary with lightness shifted by evenly spaced lumMod steps
      spanning from slightly darker to lighter (avoids invisible white/black extremes)

    Lightness modulations: for k in [1..n-1], lightness adjusted by
      Δl = (k / (n - 1 or 1)) * max_range, centered around primary lightness.
    Range clamped to [0.15, 0.90] to avoid invisible extremes.

    All colors returned as #RRGGBB uppercase.
    """
    if n <= 0:
        return []

    primary_norm = normalize_hex(primary_hex)
    if primary_norm == _BUILTIN_DEFAULTS[0] and not _HEX_RE.match(primary_hex.strip() if isinstance(primary_hex, str) else ""):
        # primary was invalid — use builtin cycle
        return [_BUILTIN_DEFAULTS[i % len(_BUILTIN_DEFAULTS)] for i in range(n)]

    if n == 1:
        return [primary_norm]

    r, g, b = _hex_to_rgb(primary_norm)
    hue, lum, sat = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)

    results: list[str] = [primary_norm]

    # Generate n-1 variants spaced across a lightness range
    # Range: go from lighter to darker (or fill gap if primary is at extreme)
    l_min = 0.15
    l_max = 0.90
    # Create n-1 target lightness values that differ from primary lum
    # Spread evenly in [l_min, l_max], excluding the primary lightness slot
    candidates = []
    step = (l_max - l_min) / max(n, 2)
    for i in range(1, n + 1):
        candidate_l = l_min + i * step
        if abs(candidate_l - lum) > 0.03:  # avoid near-duplicates
            candidates.append(min(l_max, max(l_min, candidate_l)))
    # If we ended up with fewer candidates than needed, generate more
    if len(candidates) < n - 1:
        extra_step = (l_max - l_min) / (n + 1)
        for i in range(n):
            cl = l_min + (i + 0.5) * extra_step
            if cl not in candidates:
                candidates.append(cl)

    # Take n-1 candidates, prefer those furthest from primary first
    candidates_sorted = sorted(candidates[:n - 1 + 5], key=lambda cl: -abs(cl - lum))
    selected = candidates_sorted[:n - 1]
    # Sort selected lightness values for monotonic appearance (lightest to darkest or vice versa)
    selected.sort(reverse=True)

    for candidate_l in selected[:n - 1]:
        r2, g2, b2 = colorsys.hls_to_rgb(hue, candidate_l, sat)
        ri, gi, bi = round(r2 * 255), round(g2 * 255), round(b2 * 255)
        ri = max(0, min(255, ri))
        gi = max(0, min(255, gi))
        bi = max(0, min(255, bi))
        results.append(_rgb_to_hex(ri, gi, bi))

    # Ensure exactly n colors
    while len(results) < n:
        results.append(_BUILTIN_DEFAULTS[len(results) % len(_BUILTIN_DEFAULTS)])

    return results[:n]


# ────────────────────────────────────────────────────────────────────────────
# Recent colors — persist to ~/.aurum/config.json
# ────────────────────────────────────────────────────────────────────────────

_MAX_RECENTS = 8


def get_recent_colors() -> list[str]:
    """Return recent_colors list from ~/.aurum/config.json. Empty list if not found."""
    try:
        from .config import load_config
        cfg = load_config()
        recents = cfg.ui.get("recent_colors", []) if isinstance(cfg.ui, dict) else []
        return [c for c in recents if isinstance(c, str) and c.startswith("#")]
    except Exception as exc:
        log.debug("get_recent_colors: failed to load config: %s", exc)
        return []


def build_render_context(
    style_guide: Any,
    slide_config: Any,
    chart_colors_override: Any,
    free_area: dict,
) -> Any:
    """Build a fully-resolved RenderContext for a slide.

    Args:
        style_guide: active StyleGuide (provides palette + typography)
        slide_config: object with .charts and .analyses lists
        chart_colors_override: project palette dict (e.g. state.palette) or list of hex
        free_area: dict with {x, y, cx, cy} in EMU

    Returns:
        RenderContext ready for element_renderers
    """
    from .element_renderers.render_context import RenderContext

    # Resolve typography from style_guide
    try:
        typo = style_guide.global_.typography
        typography = {
            "font_family": typo.font_family,
            "title_size": typo.title_size,
            "label_size": typo.label_size,
            "body_size": typo.body_size,
        }
    except Exception:
        typography = {"font_family": "Calibri", "title_size": 16, "label_size": 9, "body_size": 10}

    # Build chart_colors list from override dict or use palette
    if isinstance(chart_colors_override, list):
        chart_colors = chart_colors_override
    elif isinstance(chart_colors_override, dict):
        chart_colors = list(chart_colors_override.values()) if chart_colors_override else []
    else:
        chart_colors = []

    # If no chart_colors provided, fall back to style_guide palette
    if not chart_colors:
        try:
            chart_colors = list(style_guide.global_.suggested_palette or [])
        except Exception:
            chart_colors = list(_BUILTIN_DEFAULTS)

    # Resolve named color roles
    resolved_colors: dict[str, str] = {}
    role_names = ["primary", "secondary", "background", "accent", "dark", "light"]
    project_palette = chart_colors_override if isinstance(chart_colors_override, dict) else None
    for idx, role in enumerate(role_names):
        resolved_colors[role] = resolve(role, chart_colors, project_palette, style_guide, idx)

    return RenderContext(
        free_area=free_area,
        chart_colors=chart_colors,
        resolved_colors=resolved_colors,
        typography=typography,
        slide_config=slide_config,
        style_guide=style_guide,
        resolved_anchors={},
    )


def update_recent(hex_color: str) -> None:
    """Add hex_color to the front of recent_colors in ~/.aurum/config.json.

    - Normalizes hex before storing.
    - Deduplicates (moves to front if already present).
    - Keeps max 8 entries.
    - Silently ignores invalid hex strings.
    """
    if not isinstance(hex_color, str):
        log.debug("update_recent: not a string %r — not stored", hex_color)
        return

    if not _HEX_RE.match(hex_color.strip()):
        log.debug("update_recent: invalid hex %r — not stored", hex_color)
        return

    normalized = normalize_hex(hex_color)

    try:
        from .config import load_config, save_config
        cfg = load_config()
        if not isinstance(cfg.ui, dict):
            cfg.ui = {}
        recents: list[str] = [c for c in cfg.ui.get("recent_colors", []) if isinstance(c, str) and c != normalized]
        recents.insert(0, normalized)
        cfg.ui["recent_colors"] = recents[:_MAX_RECENTS]
        save_config(cfg)
    except Exception as exc:
        log.warning("update_recent: failed to save recent color %r: %s", normalized, exc)
