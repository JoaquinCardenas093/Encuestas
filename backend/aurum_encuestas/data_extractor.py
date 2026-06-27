from openpyxl import load_workbook

from .models import Breakdown, Question


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


def extract_all_breakdowns_data(
    xlsx_path: str,
    question: Question,
    breakdowns: list[Breakdown],
    data_blocks: dict,
) -> dict:
    """Returns nested structure with every breakdown group for the question.

    Shape:
        {
            group_id: {
                "label": str,                                   # display name
                "categories": {
                    category_label: {
                        option_text: {"count": int, "pct": float|None}
                    }
                }
            }
        }

    Used by segmented-table renderer to build group-merged headers without
    needing N separate chart_ref_index queries.
    """
    wb = load_workbook(xlsx_path, data_only=True)
    ws = wb.worksheets[0]
    q_rows = _find_question_rows(ws, question)

    counts_start = data_blocks["counts_cols"][0]
    pct_start = data_blocks["pct_row_cols"][0]

    result: dict[str, dict] = {}
    for bd in breakdowns:
        cnt_cols = _resolve_breakdown_cols(ws, bd.id, counts_start)
        pct_cols = _resolve_breakdown_cols(ws, bd.id, pct_start)
        # Keep only the categories declared by the parsed breakdown — guards
        # against _resolve_breakdown_cols over-reaching into the next block
        # (e.g. "Punto" picking up the "General" column of block 2).
        allowed = set(bd.categories)
        cats: dict[str, dict] = {}
        for cat in bd.categories:  # preserve declared order
            col = cnt_cols.get(cat)
            if col is None:
                continue
            pct_col = pct_cols.get(cat)
            cell_map: dict[str, dict] = {}
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
                cell_map[opt] = {"count": count_v, "pct": pct_v}
            cats[cat] = cell_map
        # Reference `allowed` so future code can also filter stray cats; silence linter.
        _ = allowed
        result[bd.id] = {"label": bd.label, "categories": cats}
    return result


def _find_question_rows(ws, question: Question) -> dict[str, int]:
    """Find rows for this question's options.

    Primary: anchor on the col-A marker (== question.text or a variable-code
    prefix like '$p3.llamado' for the sheet's '$p3.llamado.acción'), then collect
    col-B options under it. Fallback (multi-response questions whose col-A marker
    doesn't match question.text at all): scan col B for the option texts directly.
    """
    q_text = (question.text or "").strip()
    rows: dict[str, int] = {}
    in_question = False
    options_left = list(question.options)

    def _is_marker(a_s: str) -> bool:
        # Exact, or one is a dotted-prefix of the other ($p3.llamado vs $p3.llamado.acción).
        return bool(a_s) and (
            a_s == q_text
            or a_s.startswith(q_text + ".")
            or q_text.startswith(a_s + ".")
        )

    for r in range(3, ws.max_row + 1):
        a = ws.cell(r, 1).value
        b = ws.cell(r, 2).value
        a_s = str(a).strip() if a is not None else ""
        b_s = str(b).strip() if b is not None else ""
        if _is_marker(a_s):
            in_question = True
            if b_s in options_left:
                rows[b_s] = r
                options_left.remove(b_s)
        elif in_question and not a_s and b_s in options_left:
            rows[b_s] = r
            options_left.remove(b_s)
        elif in_question and a_s:
            break  # next question started
    if rows:
        return rows

    # Fallback: match purely by option text in col B (first occurrence). Option
    # strings are long, unique sentences so cross-question collisions are unlikely.
    opts = {str(o).strip() for o in question.options}
    for r in range(3, ws.max_row + 1):
        b = ws.cell(r, 2).value
        b_s = str(b).strip() if b is not None else ""
        if b_s in opts and b_s not in rows:
            rows[b_s] = r
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
