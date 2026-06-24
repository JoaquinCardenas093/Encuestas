"""Orchestrator for kind=ole_table — builds xlsx, PNG, and OLE shape."""
from __future__ import annotations

import logging

from .ole_embedder import embed_ole_xlsx_with_preview
from .ole_png_renderer import render_table_preview_png
from .xlsx_builder import build_xlsx_for_table, compute_xlsx_natural_dim_emu

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

    # AI layout override: if slide_config.layout has position for this chart_id,
    # use those EMU coords (skip natural-dim and pattern position).
    ai_overridden = False
    layout = getattr(ctx.slide_config, "layout", None)
    if layout is not None:
        positions = getattr(layout, "positions", None) or {}
        chart_id = getattr(source_chart, "id", None)
        if chart_id and chart_id in positions:
            box = positions[chart_id]
            x = getattr(box, "x_emu", x)
            y = getattr(box, "y_emu", y)
            cx = getattr(box, "cx_emu", cx)
            cy = getattr(box, "cy_emu", cy)
            ai_overridden = True

    # Override pattern position cx/cy with NATURAL xlsx render dim so
    # placeholder PNG + OLE shape match Excel's real render size on double-click.
    # Skip when AI layout already provided explicit dim.
    if not ai_overridden:
        nat_w, nat_h = compute_xlsx_natural_dim_emu(source_chart, breakdown_groups)
        if nat_w > 0 and nat_h > 0:
            cx, cy = nat_w, nat_h

    # Render chart.title above OLE block if set. Reserve top strip for it.
    title_str = (getattr(source_chart, "title", None) or "").strip()
    title_h_emu = 0
    if title_str:
        from pptx.util import Emu, Pt
        from pptx.enum.text import PP_ALIGN
        from pptx.dml.color import RGBColor
        title_h_emu = 360000  # ~0.4" reserve
        tb = slide.shapes.add_textbox(Emu(x), Emu(y), Emu(cx), Emu(title_h_emu))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_top = 0
        tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = title_str
        run.font.size = Pt(16)
        run.font.bold = True
        run.font.name = "Calibri"
        run.font.color.rgb = RGBColor(0, 0, 0)
        # Shrink OLE region to leave room.
        y += title_h_emu
        cy -= title_h_emu

    try:
        xlsx_buf = build_xlsx_for_table(source_chart, breakdown_groups)
        xlsx_bytes = xlsx_buf.getvalue()
    except Exception as exc:
        log.error("ole_table_renderer: xlsx build failed: %s", exc)
        return

    # Prefer libreoffice xlsx → PNG render (pixel-perfect Excel render).
    # Fallback: PIL canvas approximation if soffice unavailable.
    png_bytes: bytes | None = None
    try:
        from ..render_service import render_xlsx_to_png
        png_bytes = render_xlsx_to_png(xlsx_bytes)
    except Exception as exc:
        log.warning("ole_table_renderer: libreoffice xlsx→png failed: %s", exc)
    if not png_bytes:
        try:
            png_bytes = render_table_preview_png(source_chart, breakdown_groups, cx, cy)
        except Exception as exc:
            log.error("ole_table_renderer: PIL PNG render failed: %s", exc)
            return

    # Resize shape bbox to match cropped PNG aspect ratio at target dpi 200.
    # 1 px @ 200 DPI = 9525 * (96/200) ≈ 4572 EMU
    try:
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(png_bytes))
        emu_per_px = int(9525 * 96 / 200)
        cx = img.size[0] * emu_per_px
        cy = img.size[1] * emu_per_px
    except Exception:
        pass

    try:
        embed_ole_xlsx_with_preview(slide, x, y, cx, cy, xlsx_bytes, png_bytes)
    except Exception as exc:
        log.error("ole_table_renderer: OLE embed failed: %s", exc)
        return
