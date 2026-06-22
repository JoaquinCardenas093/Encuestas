"""Build embedded xlsx for OLE TABLE_WITH_MINIBARS render."""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# Hex palette (no role mapping — direct hex to avoid color_resolver remapping)
HEADER_FILL_HEX = "FF999999"   # medium gray ARGB (alpha FF for full opacity)
HEADER_FONT_HEX = "FFFFFFFF"   # white ARGB
BODY_FILL_HEX = "FFFFFFFF"     # white ARGB
BODY_FONT_HEX = "FF000000"     # black ARGB
DATABAR_HEX = "FFD9D9D9"       # light gray bar ARGB
BORDER_HEX = "FFBFBFBF"        # cell borders ARGB

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
    # Hide worksheet gridlines (rely on explicit cell borders).
    ws.sheet_view.showGridLines = False

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
    _thin = Side(style="thin", color=BORDER_HEX)
    cell_border = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)

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

        # Row 2: merged group_header — DATA cols only (excludes label col per design target)
        ws.merge_cells(
            start_row=HEADER_ROW, start_column=data_start,
            end_row=HEADER_ROW, end_column=data_end,
        )
        gh = ws.cell(row=HEADER_ROW, column=data_start,
                     value=bd.get("label") or bd_id)
        gh.fill = header_fill
        gh.font = header_font_bold_11
        gh.alignment = center
        gh.border = cell_border

        # Row 3: cat sub-headers (data cols only)
        for i, (cat_label, _) in enumerate(cats.items()):
            ch = ws.cell(row=CAT_ROW, column=data_start + i, value=cat_label)
            ch.fill = header_fill
            ch.font = header_font_bold_10
            ch.alignment = center
            ch.border = cell_border

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
            cc.border = cell_border

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
                oc.border = cell_border

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
            # gradient=False matches target design (solid bar fill).
            if rule.dataBar is not None:
                rule.dataBar.gradient = False
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
    return _force_databar_solid(buf)


def _force_databar_solid(xlsx_buf: BytesIO) -> BytesIO:
    """Post-process xlsx to force DataBar solid fill (gradient=False).

    openpyxl 3.1.5 doesn't expose the x14 dataBar extension `gradient` attribute.
    Bare <dataBar> defaults to gradient=true in Excel; the x14:dataBar override
    must be added via worksheet-level <extLst> with paired <x14:id> inside each
    cfRule's <extLst>.
    """
    import re
    import zipfile

    xlsx_buf.seek(0)
    out = BytesIO()
    with zipfile.ZipFile(xlsx_buf, "r") as zin:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.namelist():
                data = zin.read(item)
                if item.startswith("xl/worksheets/sheet") and item.endswith(".xml"):
                    try:
                        data = _inject_solid_databar_ext(data.decode("utf-8")).encode("utf-8")
                    except Exception:
                        pass  # Fall back to gradient bars if injection fails.
                zout.writestr(item, data)
    out.seek(0)
    return out


def _inject_solid_databar_ext(sheet_xml: str) -> str:
    """Inject x14 namespace + per-cfRule extLst id + worksheet extLst with
    gradient="0" override. Idempotent: short-circuits if no <dataBar> present."""
    import re

    if "<dataBar" not in sheet_xml:
        return sheet_xml

    # Add x14 + xm namespaces on worksheet root if missing.
    if 'xmlns:x14=' not in sheet_xml:
        sheet_xml = sheet_xml.replace(
            "<worksheet ",
            '<worksheet xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" '
            'xmlns:xm="http://schemas.microsoft.com/office/excel/2006/main" ',
            1,
        )

    # Locate each <conditionalFormatting sqref="..."> block containing a dataBar.
    # Inject <extLst><ext uri="{B025...}"><x14:id>{GUID}</x14:id></ext></extLst>
    # inside each cfRule (right before </cfRule>). Build a global x14 block at end.
    cf_pattern = re.compile(
        r'(<conditionalFormatting sqref="([^"]+)">)(.*?)(</conditionalFormatting>)',
        re.DOTALL,
    )

    x14_blocks: list[tuple[str, str]] = []
    counter = [0]

    def _replace_cf(match: "re.Match[str]") -> str:
        open_tag, sqref, body, close_tag = match.group(1), match.group(2), match.group(3), match.group(4)
        if "<dataBar" not in body:
            return match.group(0)
        counter[0] += 1
        guid = "{B025F937-C7B1-47D3-B67F-A62EFF66%04dE}" % counter[0]
        # Inject inside cfRule's child dataBar's tail (before </cfRule>)
        new_body = re.sub(
            r"(</cfRule>)",
            '<extLst><ext uri="{B025F937-C7B1-47D3-B67F-A62EFF666E3E}" '
            'xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main">'
            '<x14:id>' + guid + '</x14:id></ext></extLst>\\1',
            body,
            count=1,
        )
        x14_blocks.append((sqref, guid))
        return open_tag + new_body + close_tag

    sheet_xml = cf_pattern.sub(_replace_cf, sheet_xml)

    if not x14_blocks:
        return sheet_xml

    parts = []
    for sqref, guid in x14_blocks:
        parts.append(
            '<x14:conditionalFormatting xmlns:xm="http://schemas.microsoft.com/office/excel/2006/main">'
            '<x14:cfRule type="dataBar" id="' + guid + '">'
            '<x14:dataBar minLength="0" maxLength="100" gradient="0">'
            '<x14:cfvo type="num"><xm:f>0</xm:f></x14:cfvo>'
            '<x14:cfvo type="num"><xm:f>1</xm:f></x14:cfvo>'
            '</x14:dataBar>'
            '</x14:cfRule>'
            '<xm:sqref>' + sqref + '</xm:sqref>'
            '</x14:conditionalFormatting>'
        )

    ext_block = (
        '<extLst><ext uri="{78C0D931-6437-407D-A8EE-F0AAD7539E65}" '
        'xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main">'
        '<x14:conditionalFormattings>' + "".join(parts) + '</x14:conditionalFormattings>'
        '</ext></extLst>'
    )

    if re.search(r"<extLst\s*>", sheet_xml):
        sheet_xml = re.sub(r"<extLst\s*>.*?</extLst>", ext_block, sheet_xml, count=1, flags=re.DOTALL)
    else:
        sheet_xml = sheet_xml.replace("</worksheet>", ext_block + "</worksheet>")

    return sheet_xml
