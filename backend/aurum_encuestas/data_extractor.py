from openpyxl import load_workbook

from .models import Question


def extract_chart_data(xlsx_path: str, question: Question, breakdown_id: str, data_blocks: dict) -> dict:
    """Returns {breakdown_category: {option: {count, pct}}} for the given question + breakdown."""
    wb = load_workbook(xlsx_path, data_only=True)
    ws = wb.worksheets[0]

    # Find the rows of this question's options
    q_rows = _find_question_rows(ws, question)

    counts_start = data_blocks["counts_cols"][0]
    pct_start = data_blocks["pct_row_cols"][0]

    breakdown_cols = _resolve_breakdown_cols(ws, breakdown_id, counts_start)
    pct_breakdown_cols = _resolve_breakdown_cols(ws, breakdown_id, pct_start)

    result: dict[str, dict[str, dict]] = {}
    for cat, col in breakdown_cols.items():
        result[cat] = {}
        pct_col = pct_breakdown_cols.get(cat)
        for opt, row in q_rows.items():
            count = ws.cell(row, col).value or 0
            pct = ws.cell(row, pct_col).value if pct_col else None
            try:
                count_v = int(count)
            except (TypeError, ValueError):
                count_v = 0
            try:
                pct_v = float(pct) if pct is not None else None
            except (TypeError, ValueError):
                pct_v = None
            result[cat][opt] = {"count": count_v, "pct": pct_v}
    return result


def _find_question_rows(ws, question: Question) -> dict[str, int]:
    """Find rows for this question's options by matching col A marker + col B options."""
    rows: dict[str, int] = {}
    in_question = False
    options_left = list(question.options)

    for r in range(3, ws.max_row + 1):
        a = ws.cell(r, 1).value
        b = ws.cell(r, 2).value
        if a and str(a).strip() == question.text:
            in_question = True
            if b and str(b).strip() in options_left:
                rows[str(b).strip()] = r
                options_left.remove(str(b).strip())
        elif in_question and not a and b and str(b).strip() in options_left:
            rows[str(b).strip()] = r
            options_left.remove(str(b).strip())
        elif in_question and a is not None and str(a).strip():
            break  # next question started
    return rows


def _resolve_breakdown_cols(ws, breakdown_id: str, block_start_col: int) -> dict[str, int]:
    """Map category label → column index for the given breakdown within the column block."""
    row2 = {c.column: (c.value or "") for c in ws[2]}

    if breakdown_id == "general":
        # General column is the first column of the block
        return {"Total": block_start_col}

    # Find which range of cols belong to this breakdown
    row1 = {c.column: (c.value or "") for c in ws[1]}
    target_label_map = {"edad": "Rango de edad", "sexo": "Sexo", "nse": "NSE", "punto": "Punto"}
    target_label = target_label_map.get(breakdown_id)
    if not target_label:
        return {}

    # Find header for this breakdown WITHIN the block (col >= block_start_col)
    sorted_cols = sorted([c for c in row1.keys() if c >= block_start_col])
    group_starts = []
    for c in sorted_cols:
        v = str(row1[c]).strip()
        if v:
            group_starts.append((c, v))

    found = None
    for i, (c, label) in enumerate(group_starts):
        if label == target_label:
            end_col = group_starts[i + 1][0] if i + 1 < len(group_starts) else c + 7
            found = (c, end_col)
            break

    if not found:
        return {}

    start, end = found
    out = {}
    for c in range(start, end):
        cat = str(row2.get(c) or "").strip()
        if cat:
            out[cat] = c
    return out
