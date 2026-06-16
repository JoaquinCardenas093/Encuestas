from aurum_encuestas.layout_engine import compute_layout

FREE_AREA = {"x": 600000, "y": 1200000, "cx": 11000000, "cy": 5000000}


def test_single_chart_full_area():
    layout = compute_layout(
        n_charts=1, chart_types=["PIE"], n_chart_analyses=0, n_question_analyses=0, has_slide_analysis=False,
        free_area=FREE_AREA,
    )
    assert layout["elements"][0]["role"] == "chart_0"
    assert layout["elements"][0]["cx"] >= 9000000  # near full width


def test_two_charts_side_by_side():
    layout = compute_layout(
        n_charts=2, chart_types=["PIE", "BAR"], n_chart_analyses=0, n_question_analyses=0, has_slide_analysis=False,
        free_area=FREE_AREA,
    )
    chart_els = [e for e in layout["elements"] if e["role"].startswith("chart_")]
    assert len(chart_els) == 2
    # both at same Y
    assert chart_els[0]["y"] == chart_els[1]["y"]
    # different X
    assert chart_els[0]["x"] < chart_els[1]["x"]


def test_four_charts_2x2_grid():
    layout = compute_layout(
        n_charts=4, chart_types=["PIE"] * 4, n_chart_analyses=0, n_question_analyses=0, has_slide_analysis=False,
        free_area=FREE_AREA,
    )
    charts = [e for e in layout["elements"] if e["role"].startswith("chart_")]
    assert len(charts) == 4
    # 2 rows, 2 cols
    ys = sorted(set(c["y"] for c in charts))
    xs = sorted(set(c["x"] for c in charts))
    assert len(ys) == 2
    assert len(xs) == 2


def test_with_slide_analysis_reserves_footer():
    layout = compute_layout(
        n_charts=1, chart_types=["PIE"], n_chart_analyses=0, n_question_analyses=0, has_slide_analysis=True,
        free_area=FREE_AREA,
    )
    chart = next(e for e in layout["elements"] if e["role"] == "chart_0")
    slide_an = next(e for e in layout["elements"] if e["role"] == "slide_analysis")
    assert slide_an["y"] > chart["y"]
    # chart shrunk
    assert chart["cy"] < FREE_AREA["cy"]


def test_chart_analysis_adjacent_to_chart():
    layout = compute_layout(
        n_charts=1, chart_types=["PIE"], n_chart_analyses=1, n_question_analyses=0, has_slide_analysis=False,
        free_area=FREE_AREA,
    )
    chart_an = next(e for e in layout["elements"] if e["role"] == "chart_analysis_0")
    assert chart_an["anchor_chart"] == 0


def test_more_than_9_charts_raises():
    import pytest
    with pytest.raises(ValueError, match="9"):
        compute_layout(n_charts=10, chart_types=["PIE"] * 10, n_chart_analyses=0, n_question_analyses=0, has_slide_analysis=False, free_area=FREE_AREA)
