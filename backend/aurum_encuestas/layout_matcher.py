from .layout_engine import compute_layout
from .models import LayoutBank
from .training_extractor import signature_for_slide


def match_layout(
    bank: LayoutBank,
    n_charts: int,
    chart_types: list[str],
    n_chart_an: int,
    n_q_an: int,
    has_slide_an: bool,
    free_area: dict,
) -> dict:
    """Try exact signature match in bank; fallback to heuristic A.

    Returns: {"source": "bank"|"heuristic", "layout_id": ..., "elements": [...]}.
    """
    sig = signature_for_slide(n_charts, chart_types, n_chart_an, n_q_an, has_slide_an)
    for lay in bank.layouts:
        if lay.signature == sig:
            return {
                "source": "bank",
                "layout_id": lay.id,
                "elements": [e.model_dump() for e in lay.elements],
            }

    fallback = compute_layout(
        n_charts=n_charts,
        chart_types=chart_types,
        n_chart_analyses=n_chart_an,
        n_question_analyses=n_q_an,
        has_slide_analysis=has_slide_an,
        free_area=free_area,
    )
    return {
        "source": "heuristic",
        "layout_id": None,
        "elements": fallback["elements"],
    }
