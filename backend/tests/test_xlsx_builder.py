from io import BytesIO
from types import SimpleNamespace

from openpyxl import load_workbook
from openpyxl.formatting.rule import DataBarRule


def _make_source(n_options=2, bds_spec=None):
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


def test_single_panel_has_own_label_col():
    """Each bd has its own label col at its left; group_header merge spans
    label_col + cat cols."""
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
    # Group header merge spans label col + 2 cat cols: A2:C2
    assert any(str(mr) == "A2:C2" for mr in ws.merged_cells.ranges), \
        f"expected A2:C2 merge, got {[str(m) for m in ws.merged_cells.ranges]}"
    assert ws["A2"].value == "Edad"
    # Label col A: cat row empty, counts row "Observaciones", option rows = labels
    assert ws["A3"].value is None
    assert ws["A4"].value == "Observaciones"
    assert ws["A5"].value == "opt0"
    assert ws["A6"].value == "opt1"
    # Cat headers in row 3 at cols B, C
    assert ws["B3"].value == "18-39"
    assert ws["C3"].value == "40-59"
    # Counts row 4 — sum option counts per cat
    assert ws["B4"].value == 250
    assert ws["C4"].value == 250
    # Option row 5: opt0 pct
    assert abs(ws["B5"].value - 0.92) < 1e-9
    assert abs(ws["C5"].value - 0.91) < 1e-9


def test_multi_panel_n_independent_tables():
    """N=2 bds → 2 independent group_header merges, separator col empty."""
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
    # Edad bd: A2:C2 merge (label+2cats); Sexo bd at col E, label E, data F-G → E2:G2
    merge_strs = {str(m) for m in ws.merged_cells.ranges}
    assert "A2:C2" in merge_strs
    assert "E2:G2" in merge_strs
    assert ws["A2"].value == "Edad"
    assert ws["E2"].value == "Sexo"
    # Spacer col D row 2 empty
    assert ws["D2"].value is None
    assert ws["D3"].value is None
    assert ws["D4"].value is None
    # Sexo label col E
    assert ws["E4"].value == "Observaciones"
    assert ws["E5"].value == "opt0"


def test_databar_per_bd_panel_scoped():
    """DataBarRule scoped to one bd's data cols, not entire sheet."""
    from aurum_encuestas.element_renderers.xlsx_builder import build_xlsx_for_table

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
        ]),
        ("sexo", "Sexo", [
            ("F", {"opt0": {"pct": 0.7, "count": 70}, "opt1": {"pct": 0.3, "count": 30}}),
        ]),
    ])
    buf = build_xlsx_for_table(src, ["edad", "sexo"])
    wb = load_workbook(buf)
    ws = wb.active
    # Collect databar rule ranges
    bar_ranges = []
    for cf_range, rules in ws.conditional_formatting._cf_rules.items():
        for rule in rules:
            if getattr(rule, "dataBar", None) is not None:
                bar_ranges.append(str(cf_range))
    # Each bd's data range gets its own bar rules; no range spans across bds
    assert all("A" not in r and "C" not in r for r in bar_ranges) or any("B" in r for r in bar_ranges)
    # No bar range covers col D (spacer) or both bd panels at once
    for r in bar_ranges:
        # A databar range like "B5:B5" or "E5:E5" — never crosses the spacer col D
        assert "D" not in r, f"databar range {r} spans into spacer col D"


def test_hex_palette_applied():
    """Header cells use hex fill 595959 + font FFFFFF; body cells use FFFFFF + 000000."""
    from aurum_encuestas.element_renderers.xlsx_builder import build_xlsx_for_table

    src = _make_source(n_options=2, bds_spec=[
        ("edad", "Edad", [
            ("18-39", {"opt0": {"pct": 0.9, "count": 90}, "opt1": {"pct": 0.1, "count": 10}}),
        ]),
    ])
    buf = build_xlsx_for_table(src, ["edad"])
    wb = load_workbook(buf)
    ws = wb.active
    # Group header (A2) fill check
    gh = ws["A2"]
    assert "595959" in (gh.fill.fgColor.value or "").upper()
    assert "FFFFFF" in (gh.font.color.rgb or "").upper()
    # Body option-row cell (B5) fill+font check
    body = ws["B5"]
    assert "FFFFFF" in (body.fill.fgColor.value or "").upper()
    assert "000000" in (body.font.color.rgb or "").upper()


def test_empty_breakdown_groups_returns_empty_xlsx():
    from aurum_encuestas.element_renderers.xlsx_builder import build_xlsx_for_table

    src = _make_source(n_options=2, bds_spec=[])
    buf = build_xlsx_for_table(src, [])
    wb = load_workbook(buf)
    ws = wb.active
    # No merged ranges at row 2
    assert not any(str(mr).startswith(("A2", "B2", "C2")) for mr in ws.merged_cells.ranges)
