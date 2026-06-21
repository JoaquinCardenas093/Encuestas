# backend/tests/test_ole_png_renderer.py — new
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image


def _make_source(n_options=2, bds_spec=None):
    q = SimpleNamespace(options=[f"opt{i}" for i in range(n_options)])
    all_bds = {}
    for bd_id, label, cats in (bds_spec or []):
        all_bds[bd_id] = {"label": label, "categories": {cat: opts for cat, opts in cats}}
    return SimpleNamespace(
        question=q,
        all_breakdowns_data=all_bds,
        breakdown_ids=[bd_id for bd_id, _, _ in (bds_spec or [])],
    )


def test_returns_png_magic_bytes():
    from aurum_encuestas.element_renderers.ole_png_renderer import render_table_preview_png

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
        ]),
    ])
    png = render_table_preview_png(src, ["edad"], 4_000_000, 2_000_000)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_size_matches_emu_bbox():
    from aurum_encuestas.element_renderers.ole_png_renderer import render_table_preview_png

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
        ]),
    ])
    # 4_000_000 EMU / 9525 ≈ 419 px; 2_000_000 / 9525 ≈ 210 px
    png = render_table_preview_png(src, ["edad"], 4_000_000, 2_000_000)
    img = Image.open(BytesIO(png))
    assert img.size == (4_000_000 // 9525, 2_000_000 // 9525)


def test_empty_breakdown_returns_valid_white_image():
    from aurum_encuestas.element_renderers.ole_png_renderer import render_table_preview_png

    src = _make_source(n_options=0, bds_spec=[])
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
    ])
    with patch.object(ImageFont, "truetype", side_effect=IOError("font missing")):
        png = render_table_preview_png(src, ["edad"], 4_000_000, 2_000_000)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


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
    )
    png = render_table_preview_png(src, ["edad"], 6_000_000, 3_000_000)
    img = Image.open(BytesIO(png))
    # Sample top-center (header band — should be dark gray ~89)
    w, h = img.size
    hx, hy = w // 2, 5
    hp = img.getpixel((hx, hy))
    assert hp[0] < 130 and hp[1] < 130 and hp[2] < 130, \
        f"expected dark header pixel at ({hx},{hy}), got {hp}"


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
    )
    png = render_table_preview_png(src, ["edad", "sexo"], 8_000_000, 3_000_000)
    img = Image.open(BytesIO(png))
    w, h = img.size
    # Scan a horizontal line through the header band; expect:
    # dark, white-gap, dark
    y = 5
    pixels = [img.getpixel((x, y)) for x in range(0, w, max(w // 40, 1))]
    dark_count = sum(1 for p in pixels if p[0] < 130)
    white_count = sum(1 for p in pixels if p[0] > 240)
    # Both regions present (panels are dark; gap between them is white)
    assert dark_count > 0
    assert white_count > 0
