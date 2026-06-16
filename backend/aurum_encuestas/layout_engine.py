"""Heurística determinística A para colocar charts + análisis en el área libre de una slide."""

PADDING = 200000  # EMU (~0.2 inch)
SLIDE_ANALYSIS_HEIGHT_RATIO = 0.15
CHART_ANALYSIS_HEIGHT_RATIO = 0.18

GRID = {
    1: (1, 1), 2: (1, 2), 3: (1, 3),
    4: (2, 2), 5: (2, 3), 6: (2, 3),
    7: (3, 3), 8: (3, 3), 9: (3, 3),
}


def compute_layout(
    n_charts: int,
    chart_types: list[str],
    n_chart_analyses: int,
    n_question_analyses: int,
    has_slide_analysis: bool,
    free_area: dict,
) -> dict:
    if n_charts > 9 or n_charts < 0:
        raise ValueError("Máximo 9 charts por slide; recibido %d" % n_charts)

    elements: list[dict] = []
    canvas_x = free_area["x"]
    canvas_y = free_area["y"]
    canvas_w = free_area["cx"]
    canvas_h = free_area["cy"]

    # Reserve footer for slide_analysis
    slide_analysis_h = int(canvas_h * SLIDE_ANALYSIS_HEIGHT_RATIO) if has_slide_analysis else 0
    chart_area_h = canvas_h - slide_analysis_h

    # Reserve space for chart-level analyses (below charts)
    has_chart_an = n_chart_analyses > 0
    chart_an_h = int(chart_area_h * CHART_ANALYSIS_HEIGHT_RATIO) if has_chart_an else 0
    grid_h = chart_area_h - chart_an_h

    if n_charts > 0:
        rows, cols = GRID[n_charts]
        cell_w = (canvas_w - PADDING * (cols - 1)) // cols
        cell_h = (grid_h - PADDING * (rows - 1)) // rows

        for i in range(n_charts):
            r = i // cols
            c = i % cols
            x = canvas_x + c * (cell_w + PADDING)
            y = canvas_y + r * (cell_h + PADDING)
            elements.append({
                "role": f"chart_{i}",
                "x": x, "y": y, "cx": cell_w, "cy": cell_h,
                "chart_type": chart_types[i] if i < len(chart_types) else "BAR",
            })

        # Chart analyses placed below each chart (max one per chart for now)
        for i in range(min(n_chart_analyses, n_charts)):
            chart_el = elements[i]
            elements.append({
                "role": f"chart_analysis_{i}",
                "x": chart_el["x"],
                "y": chart_el["y"] + chart_el["cy"] + PADDING // 2,
                "cx": chart_el["cx"],
                "cy": chart_an_h - PADDING,
                "anchor_chart": i,
            })

    # Question analyses placed at bottom of chart area
    for i in range(n_question_analyses):
        elements.append({
            "role": f"question_analysis_{i}",
            "x": canvas_x,
            "y": canvas_y + chart_area_h - chart_an_h + PADDING,
            "cx": canvas_w,
            "cy": chart_an_h - PADDING,
        })

    # Slide analysis at footer
    if has_slide_analysis:
        elements.append({
            "role": "slide_analysis",
            "x": canvas_x,
            "y": canvas_y + chart_area_h + PADDING // 2,
            "cx": canvas_w,
            "cy": slide_analysis_h - PADDING,
        })

    return {"elements": elements, "fallback_used": True}
