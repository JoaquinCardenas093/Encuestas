from datetime import UTC, datetime
from pathlib import Path

from pptx import Presentation

from .models import LayoutBank, LayoutElement, LearnedLayout


def signature_for_slide(n_charts: int, chart_types: list[str], n_chart_an: int, n_q_an: int, has_slide_an: bool) -> str:
    types = ",".join(sorted(chart_types))
    return f"{n_charts}|{types}|{n_chart_an}|{n_q_an}|{1 if has_slide_an else 0}"


def extract_layouts_from_pptx(pptx_path: str) -> list[LearnedLayout]:
    prs = Presentation(pptx_path)
    layouts: list[LearnedLayout] = []

    for slide_idx, slide in enumerate(prs.slides):
        charts = [sh for sh in slide.shapes if getattr(sh, "has_chart", False)]
        text_boxes = [sh for sh in slide.shapes if sh.has_text_frame and not getattr(sh, "has_chart", False)]
        if not charts:
            continue

        chart_types = []
        chart_els: list[LayoutElement] = []
        for i, ch in enumerate(charts):
            ct = _xl_to_app(ch.chart.chart_type) if hasattr(ch.chart, "chart_type") else "BAR"
            chart_types.append(ct)
            chart_els.append(LayoutElement(
                role=f"chart_{i}",
                x=ch.left or 0, y=ch.top or 0, cx=ch.width or 0, cy=ch.height or 0,
                chart_type=ct,
            ))

        # Classify text boxes by proximity to charts → chart_analysis, else slide_analysis
        text_els: list[LayoutElement] = []
        for tb in text_boxes:
            text = tb.text_frame.text or ""
            if "@" in text and "Titulo" in text or "Notas" in text:
                continue
            text_els.append(LayoutElement(
                role="slide_analysis" if _is_bottom(tb, prs.slide_height) else "chart_analysis_0",
                x=tb.left or 0, y=tb.top or 0, cx=tb.width or 0, cy=tb.height or 0,
            ))

        n_chart_an = sum(1 for e in text_els if e.role.startswith("chart_analysis"))
        n_slide_an = sum(1 for e in text_els if e.role == "slide_analysis")
        signature = signature_for_slide(len(charts), chart_types, n_chart_an, 0, n_slide_an > 0)

        free_area = {
            "x": min(e.x for e in chart_els),
            "y": min(e.y for e in chart_els),
            "cx": prs.slide_width,
            "cy": prs.slide_height,
        }

        layouts.append(LearnedLayout(
            id=f"lay_{slide_idx:03d}",
            signature=signature,
            source=f"{Path(pptx_path).name}#slide{slide_idx + 1}",
            free_area=free_area,
            elements=chart_els + text_els,
        ))

    return layouts


def _is_bottom(shape, slide_height: int) -> bool:
    top = shape.top or 0
    return top > slide_height * 0.7


_REVERSE_CHART_MAP = {
    5: "PIE",
    -4120: "DONUT",
    57: "BAR",
    51: "COLUMN",
    58: "BAR_STACKED",
    52: "COLUMN_STACKED",
    4: "LINE",
    1: "AREA",
    -4151: "RADAR",
}


def _xl_to_app(xl_type) -> str:
    try:
        v = int(xl_type)
    except (TypeError, ValueError):
        return "BAR"
    return _REVERSE_CHART_MAP.get(v, "BAR")


def build_bank_from_pptxs(pptx_paths: list[str]) -> LayoutBank:
    all_layouts: list[LearnedLayout] = []
    for p in pptx_paths:
        try:
            all_layouts.extend(extract_layouts_from_pptx(p))
        except Exception:
            continue
    return LayoutBank(
        extracted_at=datetime.now(UTC).isoformat(),
        source_pptxs=[Path(p).name for p in pptx_paths],
        layouts=all_layouts,
    )
