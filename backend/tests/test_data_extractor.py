from openpyxl import Workbook, load_workbook
from aurum_encuestas.data_extractor import extract_chart_data, _resolve_breakdown_cols
from aurum_encuestas.xlsx_parser import parse_xlsx


def test_extract_chart_data_general(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    q1 = db.questions[0]
    data = extract_chart_data(str(valid_xlsx_path), q1, "general", db.data_blocks)
    assert "Total" in data
    # data is {breakdown_category: {option: {count, pct}}}
    assert data["Total"]["Sí"]["count"] == 458


def test_extract_chart_data_sexo(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    q1 = db.questions[0]
    data = extract_chart_data(str(valid_xlsx_path), q1, "sexo", db.data_blocks)
    assert "Hombre" in data
    assert "Mujer" in data


def _ws_custom(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.cell(1, 6, "Religión")        # unknown header at col 6
    ws.cell(2, 3, "General")
    ws.cell(2, 6, "Católico")
    ws.cell(2, 7, "Evangélico")
    out = tmp_path / "res.xlsx"
    wb.save(out)
    return load_workbook(out, data_only=True).worksheets[0]


def test_resolve_breakdown_cols_generic(tmp_path):
    ws = _ws_custom(tmp_path)
    cols = _resolve_breakdown_cols(ws, "religión", block_start_col=3)
    assert cols == {"Católico": 6, "Evangélico": 7}
