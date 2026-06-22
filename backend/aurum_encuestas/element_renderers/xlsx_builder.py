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
    label_border = Border(bottom=_thin)  # Observaciones col: bottom border only

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
            obs.border = label_border

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
                lbl.border = label_border

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
    """Post-process xlsx to add x14:dataBar gradient="0" override.

    openpyxl 3.1.5 emits bare <dataBar>; Excel renders gradient by default
    unless x14 extension overrides. Parse via lxml, inject extension cleanly.
    """
    import zipfile
    from lxml import etree

    xlsx_buf.seek(0)
    out = BytesIO()
    with zipfile.ZipFile(xlsx_buf, "r") as zin:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.namelist():
                data = zin.read(item)
                if item.startswith("xl/worksheets/sheet") and item.endswith(".xml"):
                    try:
                        data = _inject_x14_solid_databar(data)
                    except Exception:
                        pass  # Fall back silently to gradient bars.
                zout.writestr(item, data)
    out.seek(0)
    return out


_NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS_X14 = "http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"
_NS_XM = "http://schemas.microsoft.com/office/excel/2006/main"
_EXT_URI_CF_RULE = "{B025F937-C7B1-47D3-B67F-A62EFF666E3E}"
_EXT_URI_CF_LIST = "{78C0D931-6437-407D-A8EE-F0AAD7539E65}"


def _inject_x14_solid_databar(sheet_bytes: bytes) -> bytes:
    """Add x14:dataBar gradient="0" override via lxml. Returns serialized bytes."""
    from lxml import etree

    parser = etree.XMLParser(remove_blank_text=False)
    root = etree.fromstring(sheet_bytes, parser=parser)
    ns = {"main": _NS_MAIN}

    # Find all <cfRule type="dataBar"> inside <conditionalFormatting>
    cf_blocks = root.findall("main:conditionalFormatting", ns)
    if not cf_blocks:
        return sheet_bytes

    x14_pairs: list[tuple[str, str]] = []
    seq = 0
    for cf in cf_blocks:
        sqref = cf.get("sqref")
        for rule in cf.findall('main:cfRule[@type="dataBar"]', ns):
            seq += 1
            guid = "{B025F937-C7B1-47D3-B67F-A62EFF66%04dE}" % seq
            # Append <extLst><ext uri="..."><x14:id>GUID</x14:id></ext></extLst> to cfRule
            extlst = etree.SubElement(rule, f"{{{_NS_MAIN}}}extLst")
            ext = etree.SubElement(
                extlst,
                f"{{{_NS_MAIN}}}ext",
                attrib={"uri": _EXT_URI_CF_RULE},
                nsmap={"x14": _NS_X14},
            )
            x14_id = etree.SubElement(ext, f"{{{_NS_X14}}}id")
            x14_id.text = guid
            x14_pairs.append((sqref, guid))

    if not x14_pairs:
        return sheet_bytes

    # Append worksheet-level <extLst><ext uri="..."><x14:conditionalFormattings>...</...>
    # Drop any existing extLst first (openpyxl doesn't emit one for sheets without ext).
    existing_extlst = root.find("main:extLst", ns)
    if existing_extlst is not None:
        root.remove(existing_extlst)

    extlst = etree.SubElement(root, f"{{{_NS_MAIN}}}extLst")
    ext = etree.SubElement(
        extlst,
        f"{{{_NS_MAIN}}}ext",
        attrib={"uri": _EXT_URI_CF_LIST},
        nsmap={"x14": _NS_X14},
    )
    x14_cfs = etree.SubElement(ext, f"{{{_NS_X14}}}conditionalFormattings")
    for sqref, guid in x14_pairs:
        x14_cf = etree.SubElement(
            x14_cfs,
            f"{{{_NS_X14}}}conditionalFormatting",
            nsmap={"xm": _NS_XM},
        )
        x14_rule = etree.SubElement(
            x14_cf,
            f"{{{_NS_X14}}}cfRule",
            attrib={"type": "dataBar", "id": guid},
        )
        x14_databar = etree.SubElement(
            x14_rule,
            f"{{{_NS_X14}}}dataBar",
            attrib={"minLength": "0", "maxLength": "100", "gradient": "0"},
        )
        for v in ("0", "1"):
            cfvo = etree.SubElement(
                x14_databar,
                f"{{{_NS_X14}}}cfvo",
                attrib={"type": "num"},
            )
            f = etree.SubElement(cfvo, f"{{{_NS_XM}}}f")
            f.text = v
        xm_sqref = etree.SubElement(x14_cf, f"{{{_NS_XM}}}sqref")
        xm_sqref.text = sqref

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
