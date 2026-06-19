"""Build embedded xlsx for OLE TABLE_WITH_MINIBARS render."""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def build_xlsx_for_table(source_chart, breakdown_groups: list[str]) -> BytesIO:
    """Return in-memory xlsx mirroring the TABLE_WITH_MINIBARS layout.

    Layout: row 1 margin; row 2 group_header (merged across each bd's cats);
    row 3 cat sub-headers; row 4 counts; rows 5+ option rows with pct values
    + DataBarRule conditional formatting.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Datos"

    question = getattr(source_chart, "question", None)
    options = list(getattr(question, "options", []) or [])
    all_bds = getattr(source_chart, "all_breakdowns_data", {}) or {}

    bds = [(bd_id, all_bds.get(bd_id, {})) for bd_id in breakdown_groups if bd_id in all_bds]

    HEADER_ROW = 2
    CAT_ROW = 3
    COUNTS_ROW = 4
    FIRST_OPT_ROW = 5
    LABEL_COL = 2          # col B
    FIRST_DATA_COL = 3     # col C

    # Style primitives
    gray_fill = PatternFill("solid", fgColor="7F7F7F")
    dark_fill = PatternFill("solid", fgColor="404040")
    yellow_font_bold_11 = Font(color="EEC245", bold=True, name="Calibri", size=11)
    yellow_font_bold_10 = Font(color="EEC245", bold=True, name="Calibri", size=10)
    white_font_10 = Font(color="FFFFFF", name="Calibri", size=10)
    white_font_bold_11 = Font(color="FFFFFF", bold=True, name="Calibri", size=11)
    center = Alignment(horizontal="center", vertical="center")
    right = Alignment(horizontal="right", vertical="center")
    left = Alignment(horizontal="left", vertical="center")

    # Col B labels (always rendered)
    counts_cell = ws.cell(row=COUNTS_ROW, column=LABEL_COL, value="Observaciones")
    counts_cell.fill = gray_fill
    counts_cell.font = yellow_font_bold_11
    counts_cell.alignment = right

    for i, opt in enumerate(options):
        c = ws.cell(row=FIRST_OPT_ROW + i, column=LABEL_COL, value=opt)
        c.fill = gray_fill
        c.font = white_font_bold_11
        c.alignment = right

    # Per breakdown panel
    cur_col = FIRST_DATA_COL
    for bd_id, bd in bds:
        cats = bd.get("categories", {}) or {}
        n_cats = len(cats)
        if n_cats == 0:
            continue

        start = cur_col
        end = cur_col + n_cats - 1

        # Merged group header
        ws.merge_cells(
            start_row=HEADER_ROW, start_column=start,
            end_row=HEADER_ROW, end_column=end,
        )
        gh = ws.cell(row=HEADER_ROW, column=start, value=bd.get("label") or bd_id)
        gh.fill = dark_fill
        gh.font = yellow_font_bold_11
        gh.alignment = center

        for i, (cat_label, opt_cells) in enumerate(cats.items()):
            col = start + i

            ch = ws.cell(row=CAT_ROW, column=col, value=cat_label)
            ch.fill = gray_fill
            ch.font = yellow_font_bold_10
            ch.alignment = center

            total = sum(int((opt_cells.get(o) or {}).get("count") or 0) for o in options)
            cc = ws.cell(row=COUNTS_ROW, column=col, value=total)
            cc.fill = gray_fill
            cc.font = yellow_font_bold_11
            cc.alignment = center

            for j, opt in enumerate(options):
                row = FIRST_OPT_ROW + j
                pct = float((opt_cells.get(opt) or {}).get("pct") or 0)
                oc = ws.cell(row=row, column=col, value=pct)
                oc.number_format = "0.0%"
                oc.fill = gray_fill
                oc.font = white_font_10
                oc.alignment = left

            col_letter = get_column_letter(col)
            range_str = f"{col_letter}{FIRST_OPT_ROW}:{col_letter}{FIRST_OPT_ROW + len(options) - 1}"
            rule = DataBarRule(
                start_type="num", start_value=0,
                end_type="num", end_value=1,
                color="404040",
                showValue=True,
            )
            ws.conditional_formatting.add(range_str, rule)

        cur_col = end + 2   # leave one spacer column

    # Column + row dimensions
    ws.column_dimensions["A"].width = 2
    ws.column_dimensions[get_column_letter(LABEL_COL)].width = 18
    for c in range(FIRST_DATA_COL, max(cur_col, FIRST_DATA_COL + 1)):
        ws.column_dimensions[get_column_letter(c)].width = 14

    ws.row_dimensions[HEADER_ROW].height = 24
    ws.row_dimensions[CAT_ROW].height = 22
    ws.row_dimensions[COUNTS_ROW].height = 18
    for j in range(len(options)):
        ws.row_dimensions[FIRST_OPT_ROW + j].height = 28

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
