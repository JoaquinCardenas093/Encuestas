"""PIL preview matching xlsx_builder layout for OLE TABLE_WITH_MINIBARS."""
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

EMU_PER_PX = 9525  # 914400 EMU/inch ÷ 96 px/inch

# Colors (palette role hexes, verbatim from Fase B)
GRAY = (127, 127, 127)
DARK = (64, 64, 64)
YELLOW = (238, 194, 69)
WHITE = (255, 255, 255)


def render_table_preview_png(
    source_chart,
    breakdown_groups: list[str],
    w_emu: int,
    h_emu: int,
) -> bytes:
    """Render PIL preview mirroring the xlsx layout. Returns PNG bytes."""
    w_px = max(400, w_emu // EMU_PER_PX)
    h_px = max(200, h_emu // EMU_PER_PX)
    img = Image.new("RGB", (w_px, h_px), WHITE)
    draw = ImageDraw.Draw(img)

    question = getattr(source_chart, "question", None)
    options = list(getattr(question, "options", []) or [])
    all_bds = getattr(source_chart, "all_breakdowns_data", {}) or {}
    bds = [(bd_id, all_bds.get(bd_id, {})) for bd_id in breakdown_groups if bd_id in all_bds]

    if not bds or not options:
        return _save_png(img)

    try:
        font_hdr = ImageFont.truetype("Calibri Bold", 16)
        font_cat = ImageFont.truetype("Calibri Bold", 13)
        font_count = ImageFont.truetype("Calibri Bold", 14)
        font_lbl = ImageFont.truetype("Calibri Bold", 13)
        font_opt = ImageFont.truetype("Calibri", 12)
    except (IOError, OSError):
        import PIL.ImageFont as _pil_font
        try:
            default = _pil_font.load_default_imagefont()
        except Exception:
            default = ImageFont.load_default()
        font_hdr = font_cat = font_count = font_lbl = font_opt = default

    label_col_w = 110
    gap_w = 12

    row_hdr = 28
    row_cat = 26
    row_count = 22
    row_opt = 34
    total_h_needed = row_hdr + row_cat + row_count + row_opt * len(options)
    if total_h_needed < h_px:
        extra = (h_px - total_h_needed) // max(len(options), 1)
        row_opt += extra

    sum_cats = sum(len(bd.get("categories", {}) or {}) for _, bd in bds)
    total_data_w = w_px - label_col_w - gap_w * (len(bds) - 1) - 10
    cell_w = max(60, total_data_w // max(sum_cats, 1))

    y_hdr = 0
    y_cat = y_hdr + row_hdr
    y_count = y_cat + row_cat
    y_opt0 = y_count + row_count

    # Label col B
    draw.rectangle([0, y_count, label_col_w, y_count + row_count], fill=GRAY)
    _centered_text(draw, "Observaciones", font_lbl, YELLOW, 0, y_count, label_col_w, row_count, align="right")
    for j, opt in enumerate(options):
        oy = y_opt0 + j * row_opt
        draw.rectangle([0, oy, label_col_w, oy + row_opt], fill=GRAY)
        _centered_text(draw, opt, font_lbl, WHITE, 0, oy, label_col_w, row_opt, align="right")

    cur_x = label_col_w + 5
    for bd_id, bd in bds:
        cats = bd.get("categories", {}) or {}
        n_cats = len(cats)
        if n_cats == 0:
            continue
        panel_w = cell_w * n_cats

        draw.rectangle([cur_x, y_hdr, cur_x + panel_w, y_hdr + row_hdr], fill=DARK)
        _centered_text(draw, bd.get("label") or bd_id, font_hdr, YELLOW, cur_x, y_hdr, panel_w, row_hdr)

        for i, (cat_label, opt_cells) in enumerate(cats.items()):
            cx = cur_x + i * cell_w

            draw.rectangle([cx, y_cat, cx + cell_w, y_cat + row_cat], fill=GRAY)
            _centered_text(draw, cat_label, font_cat, YELLOW, cx, y_cat, cell_w, row_cat)

            total = sum(int((opt_cells.get(o) or {}).get("count") or 0) for o in options)
            draw.rectangle([cx, y_count, cx + cell_w, y_count + row_count], fill=GRAY)
            _centered_text(draw, str(total) if total else "", font_count, YELLOW,
                           cx, y_count, cell_w, row_count)

            for j, opt in enumerate(options):
                oy = y_opt0 + j * row_opt
                pct = float((opt_cells.get(opt) or {}).get("pct") or 0)
                draw.rectangle([cx, oy, cx + cell_w, oy + row_opt], fill=GRAY)

                bar_h = int(row_opt * 0.6)
                bar_y = oy + (row_opt - bar_h) // 2
                bar_w = int((cell_w - 50) * min(1.0, max(0.0, pct)))
                if bar_w > 0:
                    draw.rectangle([cx + 50, bar_y, cx + 50 + bar_w, bar_y + bar_h], fill=DARK)

                pct_text = f"{pct * 100:.1f}%"
                draw.text((cx + 6, oy + (row_opt - 14) // 2), pct_text, font=font_opt, fill=WHITE)

        cur_x += panel_w + gap_w

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
