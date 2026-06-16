from aurum_encuestas.layout_matcher import match_layout
from aurum_encuestas.models import LayoutBank, LayoutElement, LearnedLayout

FREE_AREA = {"x": 600000, "y": 1200000, "cx": 11000000, "cy": 5000000}


def _layout(sig: str) -> LearnedLayout:
    return LearnedLayout(
        id=f"lay_{sig}", signature=sig, source="x.pptx#slide1",
        free_area=FREE_AREA,
        elements=[LayoutElement(role="chart_0", x=0, y=0, cx=1000, cy=1000, chart_type="PIE")],
    )


def test_match_finds_exact_signature():
    bank = LayoutBank(layouts=[_layout("2|BAR,PIE|0|0|0"), _layout("1|PIE|0|0|0")])
    res = match_layout(bank=bank, n_charts=2, chart_types=["PIE", "BAR"], n_chart_an=0, n_q_an=0, has_slide_an=False, free_area=FREE_AREA)
    assert res["source"] == "bank"
    assert res["layout_id"] == "lay_2|BAR,PIE|0|0|0"


def test_match_falls_back_to_heuristic_when_no_signature():
    bank = LayoutBank(layouts=[_layout("1|PIE|0|0|0")])
    res = match_layout(bank=bank, n_charts=4, chart_types=["PIE"] * 4, n_chart_an=0, n_q_an=0, has_slide_an=False, free_area=FREE_AREA)
    assert res["source"] == "heuristic"
    chart_els = [e for e in res["elements"] if e["role"].startswith("chart_")]
    assert len(chart_els) == 4


def test_match_with_empty_bank_uses_heuristic():
    bank = LayoutBank(layouts=[])
    res = match_layout(bank=bank, n_charts=1, chart_types=["PIE"], n_chart_an=0, n_q_an=0, has_slide_an=False, free_area=FREE_AREA)
    assert res["source"] == "heuristic"
