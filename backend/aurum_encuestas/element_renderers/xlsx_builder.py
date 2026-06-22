"""Build embedded xlsx for OLE TABLE_WITH_MINIBARS render."""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# Hex palette (no role mapping — direct hex to avoid color_resolver remapping)
HEADER_FILL_HEX = "595959"   # dark gray
HEADER_FONT_HEX = "FFFFFF"   # white
BODY_FILL_HEX = "FFFFFF"     # white
BODY_FONT_HEX = "000000"     # black
DATABAR_HEX = "D9D9D9"       # light gray bar (paler)

HEADER_ROW = 2
CAT_ROW = 3
COUNTS_ROW = 4
FIRST_OPT_ROW = 5

LABEL_COL_W = 12
DATA_COL_W = 14


def build_xlsx_for_table(source_chart, breakdown_groups: list[str]) -> BytesIO:
    """Return in-memory xlsx with N independent tables side-by-side.

    One table per breakdown; each table has its own label col + group_header
    merge + cat sub-headers + counts row + option rows with DataBarRule.
    Spacer column between tables.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Datos"

    question = getattr(source_chart, "question", None)
    options = list(getattr(question, "options", []) or [])
    all_bds = getattr(source_chart, "all_breakdowns_data", {}) or {}

    bds = [(bd_id, all_bds.get(bd_id, {})) for bd_id in breakdown_groups if bd_id in all_bds]

    show_legend = bool(getattr(source_chart, "show_legend", False))

    header_fill = PatternFill("solid", fgColor=HEADER_FILL_HEX)
    body_fill = PatternFill("solid", fgColor=BODY_FILL_HEX)
    header_font_bold_11 = Font(color=HEADER_FONT_HEX, bold=True, name="Calibri", size=11)
    header_font_bold_10 = Font(color=HEADER_FONT_HEX, bold=True, name="Calibri", size=10)
    body_font_10 = Font(color=BODY_FONT_HEX, name="Calibri", size=10)
    body_font_bold_11 = Font(color=BODY_FONT_HEX, bold=True, name="Calibri", size=11)
    center = Alignment(horizontal="center", vertical="center")
    right = Alignment(horizontal="right", vertical="center")
    left = Alignment(horizontal="left", vertical="center")

    cur_col = 1
    for bd_id, bd in bds:
        cats = bd.get("categories", {}) or {}
        n_cats = len(cats)
        if n_cats == 0:
            continue

        if show_legend:
            label_col = cur_col
            data_start = cur_col + 1
        else:
            data_start = cur_col
            label_col = None  # no label col
        data_end = data_start + n_cats - 1

        # Row 2: merged group_header
        header_start = label_col if show_legend else data_start
        ws.merge_cells(
            start_row=HEADER_ROW, start_column=header_start,
            end_row=HEADER_ROW, end_column=data_end,
        )
        gh = ws.cell(row=HEADER_ROW, column=header_start,
                     value=bd.get("label") or bd_id)
        gh.fill = header_fill
        gh.font = header_font_bold_11
        gh.alignment = center

        # Row 3: cat sub-headers (data cols only)
        for i, (cat_label, _) in enumerate(cats.items()):
            ch = ws.cell(row=CAT_ROW, column=data_start + i, value=cat_label)
            ch.fill = header_fill
            ch.font = header_font_bold_10
            ch.alignment = center

        # Row 4: counts row — label col = "Observaciones" (only if show_legend), data cols = totals
        if show_legend:
            obs = ws.cell(row=COUNTS_ROW, column=label_col, value="Observaciones")
            obs.fill = body_fill
            obs.font = body_font_bold_11
            obs.alignment = right

        for i, (_, opt_cells) in enumerate(cats.items()):
            total = sum(int((opt_cells.get(o) or {}).get("count") or 0) for o in options)
            cc = ws.cell(row=COUNTS_ROW, column=data_start + i, value=total)
            cc.fill = body_fill
            cc.font = body_font_bold_11
            cc.alignment = center

        # Rows 5+: option rows
        for j, opt in enumerate(options):
            row = FIRST_OPT_ROW + j

            if show_legend:
                lbl = ws.cell(row=row, column=label_col, value=opt)
                lbl.fill = body_fill
                lbl.font = body_font_bold_11
                lbl.alignment = right

            for i, (_, opt_cells) in enumerate(cats.items()):
                pct = float((opt_cells.get(opt) or {}).get("pct") or 0)
                oc = ws.cell(row=row, column=data_start + i, value=pct)
                oc.number_format = "0.0%"
                oc.fill = body_fill
                oc.font = body_font_10
                oc.alignment = Alignment(horizontal="right", indent=1, vertical="center")

        # DataBarRule per OPTION ROW spanning this bd's data cols only
        for j in range(len(options)):
            row = FIRST_OPT_ROW + j
            start_letter = get_column_letter(data_start)
            end_letter = get_column_letter(data_end)
            range_str = f"{start_letter}{row}:{end_letter}{row}"
            rule = DataBarRule(
                start_type="num", start_value=0,
                end_type="num", end_value=1,
                color=DATABAR_HEX,
                showValue=True,
            )
            ws.conditional_formatting.add(range_str, rule)

        # Column widths for this bd
        if show_legend:
            ws.column_dimensions[get_column_letter(label_col)].width = LABEL_COL_W
        for c in range(data_start, data_end + 1):
            ws.column_dimensions[get_column_letter(c)].width = DATA_COL_W

        # Explicit narrow width for spacer col between bds
        ws.column_dimensions[get_column_letter(data_end + 1)].width = 2
        cur_col = data_end + 2

    ws.row_dimensions[HEADER_ROW].height = 24
    ws.row_dimensions[CAT_ROW].height = 22
    ws.row_dimensions[COUNTS_ROW].height = 18
    for j in range(len(options)):
        ws.row_dimensions[FIRST_OPT_ROW + j].height = 28

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
