"""PIL preview matching xlsx_builder layout for OLE TABLE_WITH_MINIBARS."""
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

EMU_PER_PX = 9525

# Palette (matches xlsx_builder hex literals)
HEADER_DARK = (153, 153, 153)  # #999999 — matches xlsx HEADER_FILL_HEX
BG_WHITE = (255, 255, 255)
TEXT_BLACK = (0, 0, 0)
TEXT_WHITE = (255, 255, 255)
BAR_GRAY = (217, 217, 217)
BORDER_GRAY = (0, 0, 0)  # black (matches xlsx BORDER_HEX)

# Font candidates: try Calibri (Windows / installed), Arial Bold (macOS Supplemental),
# Helvetica (macOS System), in order. Fall back to PIL default bitmap.
_FONT_BOLD_CANDIDATES = (
    "Calibri Bold.ttf",
    "Calibrib.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "Arial Bold",
    "Helvetica",
)
_FONT_REG_CANDIDATES = (
    "Calibri.ttf",
    "Calibri",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "Arial",
    "Helvetica",
)


def _load_font(candidates, size, default):
    """Try each candidate path/name; return first that loads or default."""
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except (IOError, OSError):
            continue
    return default


def render_table_preview_png(
    source_chart,
    breakdown_groups: list[str],
    w_emu: int,
    h_emu: int,
) -> bytes:
    """PIL canvas: N panels side-by-side, each = optional label col + dark headers
    + white body + gray bars. Label col toggled by source_chart.show_legend.
    Returns PNG bytes."""
    w_px = max(400, w_emu // EMU_PER_PX)
    h_px = max(200, h_emu // EMU_PER_PX)
    img = Image.new("RGB", (w_px, h_px), BG_WHITE)
    draw = ImageDraw.Draw(img)

    question = getattr(source_chart, "question", None)
    options = list(getattr(question, "options", []) or [])
    all_bds = getattr(source_chart, "all_breakdowns_data", {}) or {}
    bds = [(bd_id, all_bds.get(bd_id, {})) for bd_id in breakdown_groups if bd_id in all_bds]

    if not bds or not options:
        return _save_png(img)

    if hasattr(ImageFont, "load_default_imagefont"):
        default_font = ImageFont.load_default_imagefont()
    else:
        default_font = ImageFont.load_default()
    font_hdr = _load_font(_FONT_BOLD_CANDIDATES, 14, default_font)
    font_cat = _load_font(_FONT_BOLD_CANDIDATES, 12, default_font)
    font_count = _load_font(_FONT_BOLD_CANDIDATES, 13, default_font)
    font_lbl = _load_font(_FONT_BOLD_CANDIDATES, 12, default_font)
    font_opt = _load_font(_FONT_REG_CANDIDATES, 11, default_font)

    # Read show_legend flag (default False)
    show_legend = bool(getattr(source_chart, "show_legend", False))

    # Layout: per-panel label col + N cat cols, with horizontal gap between panels
    gap_px = 15
    n_bds = len(bds)
    total_cats = sum(len(bd.get("categories", {}) or {}) for _, bd in bds)
    content_w = w_px - 10

    # Try preferred label_col_w; shrink if necessary so cell_w >= 45
    preferred_label_w = 95
    min_label_w = 40
    label_col_w = preferred_label_w
    while label_col_w >= min_label_w:
        available_for_cats = content_w - label_col_w * n_bds - gap_px * (n_bds - 1)
        if available_for_cats >= total_cats * 45:
            break
        label_col_w -= 5
    label_col_w = max(min_label_w, label_col_w)

    # Use effective_label_w: 0 when show_legend=False, otherwise label_col_w
    effective_label_w = label_col_w if show_legend else 0
    available_for_cats = content_w - effective_label_w * n_bds - gap_px * (n_bds - 1)
    cell_w = max(45, available_for_cats // max(total_cats, 1))

    row_hdr = 28
    row_cat = 24
    row_count = 22
    row_opt = 32
    # Cap row_opt stretch to keep cells compact (matches Excel DataBar render).
    # Without cap, tall canvases stretch each row to fill, making bars look square.
    max_row_opt = 44
    total_rows_h = row_hdr + row_cat + row_count + row_opt * len(options)
    if total_rows_h < h_px:
        extra = min((h_px - total_rows_h) // max(len(options), 1), max_row_opt - row_opt)
        if extra > 0:
            row_opt += extra

    y_hdr = 0
    y_cat = y_hdr + row_hdr
    y_count = y_cat + row_cat
    y_opt0 = y_count + row_count

    cur_x = 5
    for bd_index, (bd_id, bd) in enumerate(bds):
        cats = bd.get("categories", {}) or {}
        n_cats = len(cats)
        if n_cats == 0:
            continue
        # Only the FIRST bd renders the label col when show_legend=True.
        # Subsequent bds share the first's leyenda visually (no own col).
        bd_eff_label_w = effective_label_w if (show_legend and bd_index == 0) else 0
        panel_w = bd_eff_label_w + cell_w * n_cats

        # Group header band — DATA cols only (excludes label col per design target)
        hdr_x = cur_x + bd_eff_label_w
        hdr_w = cell_w * n_cats
        draw.rectangle([hdr_x, y_hdr, hdr_x + hdr_w, y_hdr + row_hdr], fill=HEADER_DARK)
        _centered_text(draw, bd.get("label") or bd_id, font_hdr, TEXT_WHITE,
                       hdr_x, y_hdr, hdr_w, row_hdr)

        # Cat sub-headers — data cols only (label col empty in cat row)
        for i, (cat_label, _) in enumerate(cats.items()):
            cx = cur_x + bd_eff_label_w + i * cell_w
            draw.rectangle([cx, y_cat, cx + cell_w, y_cat + row_cat], fill=HEADER_DARK)
            _centered_text(draw, cat_label, font_cat, TEXT_WHITE, cx, y_cat, cell_w, row_cat)

        # Counts row: label col = "Observaciones" (only first bd), data cols = totals
        if bd_eff_label_w > 0:
            lx = cur_x
            draw.rectangle([lx, y_count, lx + bd_eff_label_w, y_count + row_count], fill=BG_WHITE)
            _centered_text(draw, "Observaciones", font_lbl, TEXT_BLACK,
                           lx, y_count, bd_eff_label_w, row_count, align="right")
        for i, (_, opt_cells) in enumerate(cats.items()):
            cx = cur_x + bd_eff_label_w + i * cell_w
            total = sum(int((opt_cells.get(o) or {}).get("count") or 0) for o in options)
            draw.rectangle([cx, y_count, cx + cell_w, y_count + row_count], fill=BG_WHITE)
            _centered_text(draw, str(total) if total else "", font_count, TEXT_BLACK,
                           cx, y_count, cell_w, row_count)

        # Option rows
        for j, opt in enumerate(options):
            oy = y_opt0 + j * row_opt

            # Label col (only first bd)
            if bd_eff_label_w > 0:
                lx = cur_x
                draw.rectangle([lx, oy, lx + bd_eff_label_w, oy + row_opt], fill=BG_WHITE)
                _centered_text(draw, opt, font_lbl, TEXT_BLACK,
                               lx, oy, bd_eff_label_w, row_opt, align="right")

            for i, (_, opt_cells) in enumerate(cats.items()):
                cx = cur_x + bd_eff_label_w + i * cell_w
                pct = float((opt_cells.get(opt) or {}).get("pct") or 0)
                draw.rectangle([cx, oy, cx + cell_w, oy + row_opt], fill=BG_WHITE)

                # Solid bar (no gradient — matches xlsx DataBarRule gradient=False).
                bar_h = min(row_opt - 6, 22)
                bar_y = oy + (row_opt - bar_h) // 2
                bar_w = int(cell_w * min(1.0, max(0.0, pct)))
                if bar_w > 0:
                    draw.rectangle([cx, bar_y, cx + bar_w, bar_y + bar_h], fill=BAR_GRAY)

                # Cell bottom border (1px) for table grid look.
                draw.line([(cx, oy + row_opt - 1), (cx + cell_w, oy + row_opt - 1)],
                          fill=BORDER_GRAY, width=1)

                # Text left-aligned with indent, overlays bar from left.
                pct_text = f"{pct * 100:.1f}%"
                tx = cx + 6
                draw.text((tx, oy + (row_opt - 14) // 2), pct_text, font=font_opt, fill=TEXT_BLACK)

        cur_x += panel_w + gap_px

    return _save_png(img)


def _centered_text(draw, text, font, color, x, y, w, h, align="center"):
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
    except Exception:
        bbox = (0, 0, len(text) * 7, 12)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    if align == "right":
        tx = x + w - tw - 8
    else:
        tx = x + (w - tw) // 2
    ty = y + (h - th) // 2
    draw.text((tx, ty), text, font=font, fill=color)


def _save_png(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
