"""Orchestrator for kind=ole_table — builds xlsx, PNG, and OLE shape."""
from __future__ import annotations

import logging

from .ole_embedder import embed_ole_xlsx_with_preview
from .ole_png_renderer import render_table_preview_png
from .xlsx_builder import build_xlsx_for_table

log = logging.getLogger(__name__)


def render(slide, element: dict, ctx) -> None:
    """Dispatch entrypoint for kind=ole_table elements.

    Builds an in-memory xlsx mirroring the table layout, renders a PIL preview
    PNG at the same bbox, and embeds both as an OLE graphicFrame on the slide.
    """
    from .chart_renderer import _resolve_position
    try:
        x, y, cx, cy = _resolve_position(element.get("position", {}), ctx)
    except Exception as exc:
        log.error("ole_table_renderer: position resolve failed: %s", exc)
        return

    data_source = element.get("data_source", {}) or {}
    chart_ref_index = data_source.get("chart_ref_index", 0)
    breakdown_groups = list(data_source.get("breakdown_groups", []) or [])

    charts_list = getattr(ctx.slide_config, "charts", []) or []
    if not (0 <= chart_ref_index < len(charts_list)):
        log.warning("ole_table_renderer: chart_ref_index %d out of range — skipping", chart_ref_index)
        return

    source_chart = charts_list[chart_ref_index]

    try:
        xlsx_buf = build_xlsx_for_table(source_chart, breakdown_groups)
        xlsx_bytes = xlsx_buf.getvalue()
    except Exception as exc:
        log.error("ole_table_renderer: xlsx build failed: %s", exc)
        return

    try:
        png_bytes = render_table_preview_png(source_chart, breakdown_groups, cx, cy)
    except Exception as exc:
        log.error("ole_table_renderer: PNG render failed: %s", exc)
        return

    try:
        embed_ole_xlsx_with_preview(slide, x, y, cx, cy, xlsx_bytes, png_bytes)
    except Exception as exc:
        log.error("ole_table_renderer: OLE embed failed: %s", exc)
        return
