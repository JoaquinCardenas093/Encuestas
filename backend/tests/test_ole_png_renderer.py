# backend/tests/test_ole_png_renderer.py — adapted for show_legend toggle
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image


def _make_source(n_options=2, bds_spec=None, show_legend=False):
    q = SimpleNamespace(options=[f"opt{i}" for i in range(n_options)])
    all_bds = {}
    for bd_id, label, cats in (bds_spec or []):
        all_bds[bd_id] = {"label": label, "categories": {cat: opts for cat, opts in cats}}
    return SimpleNamespace(
        question=q,
        all_breakdowns_data=all_bds,
        breakdown_ids=[bd_id for bd_id, _, _ in (bds_spec or [])],
        show_legend=show_legend,
    )


def test_returns_png_magic_bytes():
    from aurum_encuestas.element_renderers.ole_png_renderer import render_table_preview_png

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
        ]),
    ], show_legend=True)
    png = render_table_preview_png(src, ["edad"], 4_000_000, 2_000_000)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_size_matches_emu_bbox():
    from aurum_encuestas.element_renderers.ole_png_renderer import render_table_preview_png

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
        ]),
    ], show_legend=True)
    # 4_000_000 EMU / 9525 ≈ 419 px; 2_000_000 / 9525 ≈ 210 px
    png = render_table_preview_png(src, ["edad"], 4_000_000, 2_000_000)
    img = Image.open(BytesIO(png))
    assert img.size == (4_000_000 // 9525, 2_000_000 // 9525)


def test_empty_breakdown_returns_valid_white_image():
    from aurum_encuestas.element_renderers.ole_png_renderer import render_table_preview_png

    src = _make_source(n_options=0, bds_spec=[], show_legend=True)
    png = render_table_preview_png(src, [], 4_000_000, 2_000_000)
    img = Image.open(BytesIO(png))
    # White majority pixel
    assert img.getpixel((0, 0)) == (255, 255, 255)


def test_uses_default_font_when_calibri_missing():
    from aurum_encuestas.element_renderers.ole_png_renderer import render_table_preview_png
    from PIL import ImageFont

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
        ]),
    ], show_legend=True)
    with patch.object(ImageFont, "truetype", side_effect=IOError("font missing")):
        png = render_table_preview_png(src, ["edad"], 4_000_000, 2_000_000)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_bar_width_proportional_to_pct():
    """Bar fills cell left→right proportional to pct. High pct → wider bar than low pct."""
    from io import BytesIO
    from PIL import Image
    from types import SimpleNamespace
    from aurum_encuestas.element_renderers.ole_png_renderer import render_table_preview_png

    q = SimpleNamespace(options=["opt0", "opt1"])
    src = SimpleNamespace(
        question=q,
        all_breakdowns_data={
            "edad": {"label": "Edad", "categories": {
                "18-39": {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}},
            }},
        },
        breakdown_ids=["edad"],
        show_legend=False,
    )
    png = render_table_preview_png(src, ["edad"], 6_000_000, 3_000_000)
    img = Image.open(BytesIO(png))
    w, h = img.size

    # Layout: cur_x=5, no label col, single cell spans whole width.
    # Header band: y in [0, 28]. Cat row: [28, 52]. Count: [52, 74].
    # opt0 row at y in [74, 74+row_opt]. opt1 row after.
    # Scan opt0 row (high pct 0.9): bar should cover most of cell.
    # Scan opt1 row (low pct 0.1): bar should cover only ~10% from left.

    opt0_y = 90  # safely inside opt0 row
    opt1_y = 140  # safely inside opt1 row (row_opt capped ≤44, so opt1 starts ≥118)

    def bar_extent(y):
        """Walk pixels at row y from cell_left=5; return last x where pixel is BAR_GRAY."""
        last_gray = 5
        for x in range(5, w):
            p = img.getpixel((x, y))
            # BAR_GRAY=(217,217,217) — wide tolerance vs anti-alias
            if 200 <= p[0] <= 230 and abs(p[0] - p[1]) <= 5 and abs(p[1] - p[2]) <= 5:
                last_gray = x
        return last_gray - 5

    opt0_bar = bar_extent(opt0_y)
    opt1_bar = bar_extent(opt1_y)
    # opt0 bar must be substantially wider than opt1 (proportional to 0.9 vs 0.1)
    assert opt0_bar > opt1_bar * 3, \
        f"expected opt0_bar (pct=0.9) >> opt1_bar (pct=0.1); got opt0={opt0_bar} opt1={opt1_bar}"


def test_palette_dark_header_white_body():
    """Sample pixels: header band is dark gray; body row is white."""
    from io import BytesIO
    from PIL import Image
    from types import SimpleNamespace
    from aurum_encuestas.element_renderers.ole_png_renderer import render_table_preview_png

    q = SimpleNamespace(options=["opt0", "opt1"])
    src = SimpleNamespace(
        question=q,
        all_breakdowns_data={
            "edad": {"label": "Edad", "categories": {
                "18-39": {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}},
            }},
        },
        breakdown_ids=["edad"],
        show_legend=True,
    )
    png = render_table_preview_png(src, ["edad"], 6_000_000, 3_000_000)
    img = Image.open(BytesIO(png))
    # Sample top-center (header band — should be dark gray ~89)
    w, h = img.size
    hx, hy = w // 2, 5
    hp = img.getpixel((hx, hy))
    assert hp[0] < 130 and hp[1] < 130 and hp[2] < 130, \
        f"expected dark header pixel at ({hx},{hy}), got {hp}"
    # Body row pixel must be white. Layout: hdr 28 + cat 24 + count 22 = 74.
    # Option rows after that, row_opt capped at 44.
    # Sample opt1 row (pct=0.1 — bar only covers 10% from left edge of cell).
    # opt1 row at y in [74+row_opt, 74+2*row_opt]; center pixel sits in white zone past bar.
    body_y = min(h - 5, 140)
    bp = img.getpixel((hx, body_y))
    assert bp[0] > 240 and bp[1] > 240 and bp[2] > 240, \
        f"expected white body pixel at ({hx},{body_y}), got {bp}"


def test_multi_bd_renders_n_panels_with_gap():
    """2 bds → distinguishable horizontal panels with white gap between them."""
    from io import BytesIO
    from PIL import Image
    from types import SimpleNamespace
    from aurum_encuestas.element_renderers.ole_png_renderer import render_table_preview_png

    q = SimpleNamespace(options=["opt0", "opt1"])
    src = SimpleNamespace(
        question=q,
        all_breakdowns_data={
            "edad": {"label": "Edad", "categories": {
                "18-39": {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}},
            }},
            "sexo": {"label": "Sexo", "categories": {
                "F": {"opt0": {"pct": 0.5, "count": 50}, "opt1": {"pct": 0.5, "count": 50}},
            }},
        },
        breakdown_ids=["edad", "sexo"],
        show_legend=True,
    )
    png = render_table_preview_png(src, ["edad", "sexo"], 8_000_000, 3_000_000)
    img = Image.open(BytesIO(png))
    w, h = img.size
    # Scan a horizontal line through the header band; expect:
    # dark, white-gap, dark
    y = 5
    pixels = [img.getpixel((x, y)) for x in range(0, w, max(w // 80, 1))]
    # Compress to run-length: collect transitions dark↔white
    runs = []
    prev_state = None
    for p in pixels:
        state = "D" if p[0] < 130 else ("W" if p[0] > 240 else None)
        if state and state != prev_state:
            runs.append(state)
            prev_state = state
    # Must see at least D, W, D — two distinct dark clusters with white gap between
    dark_runs = sum(1 for r in runs if r == "D")
    assert dark_runs >= 2, f"expected >=2 dark panels separated by white gap; runs={runs}"


def test_show_legend_false_skips_label_column():
    """When show_legend=False, label columns should not be rendered.
    Render TWO versions (True & False) and sample pixels in the count row:
    - With show_legend=True: label col text "Observaciones" drawn → black pixels
    - With show_legend=False: label column skipped → white pixels
    This ensures the guard doesn't regress silently."""
    from aurum_encuestas.element_renderers.ole_png_renderer import render_table_preview_png

    bds_spec = [
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
        ]),
    ]

    # Render with show_legend=True
    src_true = _make_source(n_options=2, bds_spec=bds_spec, show_legend=True)
    png_true = render_table_preview_png(src_true, ["edad"], 4_000_000, 2_000_000)
    img_true = Image.open(BytesIO(png_true))

    # Render with show_legend=False
    src_false = _make_source(n_options=2, bds_spec=bds_spec, show_legend=False)
    png_false = render_table_preview_png(src_false, ["edad"], 4_000_000, 2_000_000)
    img_false = Image.open(BytesIO(png_false))

    # Both should be valid PNGs
    assert png_true[:8] == b"\x89PNG\r\n\x1a\n"
    assert png_false[:8] == b"\x89PNG\r\n\x1a\n"

    # Sample label-col text pixels in the count row where "Observaciones" is drawn.
    # Layout: y_hdr=0, y_cat=28, y_count=52, y_count+row_count=74 (so y ~59-65 is text area)
    # With show_legend=True: label text "Observaciones" rendered at (x ~15-40, y ~59-65) in black
    # With show_legend=False: label column is 0-width, so this region is white
    sample_x, sample_y = 20, 61

    pixel_true = img_true.getpixel((sample_x, sample_y))
    pixel_false = img_false.getpixel((sample_x, sample_y))

    # When show_legend=True: text drawn in label column → should be black
    assert pixel_true[0] < 100 and pixel_true[1] < 100 and pixel_true[2] < 100, \
        f"expected black text in label column at ({sample_x},{sample_y}) with show_legend=True, got {pixel_true}"

    # When show_legend=False: label column skipped → pixel should be pure white
    assert pixel_false[0] > 240 and pixel_false[1] > 240 and pixel_false[2] > 240, \
        f"expected white at ({sample_x},{sample_y}) with show_legend=False, got {pixel_false}"
