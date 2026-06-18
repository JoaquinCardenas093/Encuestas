import pytest

from aurum_encuestas.errors import XlsxParseError
from aurum_encuestas.xlsx_parser import parse_xlsx


def test_parse_detects_sample_size(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    assert db.sample_size == 500


def test_parse_detects_breakdowns(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    ids = [b.id for b in db.breakdowns]
    assert "general" in ids
    assert "sexo" in ids
    assert "edad" in ids
    assert "nse" in ids
    assert "punto" in ids


def test_parse_breakdown_sexo_categories(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    sexo = next(b for b in db.breakdowns if b.id == "sexo")
    assert "Hombre" in sexo.categories
    assert "Mujer" in sexo.categories


def test_parse_invalid_file_raises(tmp_path):
    bad = tmp_path / "bad.xlsx"
    bad.write_bytes(b"not an xlsx")
    with pytest.raises(XlsxParseError):
        parse_xlsx(str(bad))


def test_parse_detects_questions(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    assert len(db.questions) >= 1
    q1 = db.questions[0]
    assert q1.code == "P1"
    assert q1.text  # non-empty
    assert "Sí" in q1.options
    assert "No" in q1.options


def test_parse_question_confidence(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    q1 = db.questions[0]
    assert q1.confidence >= 0.9  # $pN.label marker = high confidence


def test_parse_detects_three_column_blocks(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    blocks = db.data_blocks
    assert "counts_cols" in blocks
    assert "pct_row_cols" in blocks
    # counts block starts at col 3
    assert blocks["counts_cols"][0] == 3
    # second block detected
    assert blocks["pct_row_cols"][0] >= 19
