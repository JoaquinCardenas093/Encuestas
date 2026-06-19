# backend/tests/test_xlsx_builder.py — new file
from io import BytesIO
from types import SimpleNamespace

from openpyxl import load_workbook
from openpyxl.formatting.rule import DataBarRule


def _make_source(n_options=2, bds_spec=None):
    """bds_spec: list of (bd_id, label, [(cat_label, {opt: {"pct": float, "count": int}})])"""
    q = SimpleNamespace(options=[f"opt{i}" for i in range(n_options)])
    all_bds = {}
    for bd_id, label, cats in (bds_spec or []):
        all_bds[bd_id] = {
            "label": label,
            "categories": {cat: opts for cat, opts in cats},
        }
    return SimpleNamespace(
        question=q,
        all_breakdowns_data=all_bds,
        breakdown_ids=[bd_id for bd_id, _, _ in (bds_spec or [])],
    )


def test_builds_single_panel_layout():
    from aurum_encuestas.element_renderers.xlsx_builder import build_xlsx_for_table

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.92, "count": 230}, "opt1": {"pct": 0.08, "count": 20}}),
            ("40-59", {"opt0": {"pct": 0.91, "count": 228}, "opt1": {"pct": 0.09, "count": 22}}),
        ]),
    ])
    buf = build_xlsx_for_table(src, ["edad"])
    wb = load_workbook(buf)
    ws = wb.active
    # Group header merged across cols C–D in row 2
    assert any(str(mr) == "C2:D2" for mr in ws.merged_cells.ranges)
    # Group header value
    assert ws["C2"].value == "Edad"
    # Cat headers in row 3
    assert ws["C3"].value == "18-39"
    assert ws["D3"].value == "40-59"
    # Counts row 4 — sum of option counts per cat (230+20=250)
    assert ws["C4"].value == 250
    assert ws["D4"].value == 250
    # Option rows 5+
    assert abs(ws["C5"].value - 0.92) < 1e-9
    assert abs(ws["D5"].value - 0.91) < 1e-9
    assert abs(ws["C6"].value - 0.08) < 1e-9
    # Label col B
    assert ws["B4"].value == "Observaciones"
    assert ws["B5"].value == "opt0"
    assert ws["B6"].value == "opt1"


def test_data_bar_rule_color_dark():
    from aurum_encuestas.element_renderers.xlsx_builder import build_xlsx_for_table

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
        ]),
    ])
    buf = build_xlsx_for_table(src, ["edad"])
    wb = load_workbook(buf)
    ws = wb.active
    # At least one DataBarRule applied to the cat column C5:C6 range
    rules_for_range = ws.conditional_formatting._cf_rules
    found_databar_color = None
    for cf_range, rules in rules_for_range.items():
        for rule in rules:
            db = getattr(rule, "dataBar", None)
            if db is not None and db.color is not None:
                found_databar_color = db.color.value
                break
    # openpyxl stores ARGB; "FF404040" or "404040" both acceptable
    assert found_databar_color is not None
    assert "404040" in found_databar_color.upper()


def test_builds_multi_panel_layout_with_spacers():
    from aurum_encuestas.element_renderers.xlsx_builder import build_xlsx_for_table

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
            ("40-59", {"opt0": {"pct": 0.8, "count": 80}, "opt1": {"pct": 0.2, "count": 20}}),
        ]),
        ("sexo", "Sexo", [
            ("F", {"opt0": {"pct": 0.7, "count": 70}, "opt1": {"pct": 0.3, "count": 30}}),
            ("M", {"opt0": {"pct": 0.85, "count": 85}, "opt1": {"pct": 0.15, "count": 15}}),
        ]),
    ])
    buf = build_xlsx_for_table(src, ["edad", "sexo"])
    wb = load_workbook(buf)
    ws = wb.active
    # Edad spans C2:D2; spacer at col E; Sexo spans F2:G2
    assert any(str(mr) == "C2:D2" for mr in ws.merged_cells.ranges)
    assert any(str(mr) == "F2:G2" for mr in ws.merged_cells.ranges)
    assert ws["C2"].value == "Edad"
    assert ws["F2"].value == "Sexo"
    # Spacer col E has no merged header
    assert ws["E2"].value is None


def test_empty_breakdown_groups_returns_valid_xlsx():
    from aurum_encuestas.element_renderers.xlsx_builder import build_xlsx_for_table

    src = _make_source(n_options=2, bds_spec=[])
    buf = build_xlsx_for_table(src, [])
    # No crash; openpyxl can read it
    wb = load_workbook(buf)
    ws = wb.active
    # Labels in col B are present even without data panels
    assert ws["B4"].value == "Observaciones"
    assert ws["B5"].value == "opt0"
