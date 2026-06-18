from aurum_encuestas.data_extractor import extract_chart_data
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
