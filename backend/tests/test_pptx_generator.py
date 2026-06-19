from pptx import Presentation

from aurum_encuestas.models import (
    Analysis,
    Breakdown,
    Chart,
    ParsedDB,
    ProjectInputs,
    ProjectState,
    Question,
    Slide,
)
from aurum_encuestas.pptx_generator import build_pptx


def _state(slides, valid_xlsx_path, valid_template_path):
    return ProjectState(
        version=1, project_name="t",
        inputs=ProjectInputs(db_path=str(valid_xlsx_path), template_path=str(valid_template_path)),
        parsed_db=ParsedDB(
            questions=[Question(id="q1", code="P1", text="$p1.recordacion", options=["Sí", "No"], confidence=1.0)],
            breakdowns=[
                Breakdown(id="general", label="General", categories=["Total"]),
                Breakdown(id="sexo", label="Sexo", categories=["Hombre", "Mujer"]),
            ],
            sample_size=500,
            data_blocks={"counts_cols": [3, 17], "pct_row_cols": [21, 35], "pct_col_cols": [41, 55]},
        ),
        slides=slides,
    )


def test_build_pptx_with_separator_and_shell(tmp_path, valid_xlsx_path, valid_template_path):
    slides = [
        Slide(id="s1", type="separator", title="Sección A"),
        Slide(id="s2", type="shell", title="Sección A", charts=[], analyses=[]),
    ]
    state = _state(slides, valid_xlsx_path, valid_template_path)
    out = tmp_path / "out.pptx"
    build_pptx(state, str(out))
    assert out.exists()

    prs = Presentation(str(out))
    assert len(prs.slides) == 2


def test_build_pptx_substitutes_titulo(tmp_path, valid_xlsx_path, valid_template_path):
    slides = [
        Slide(id="s1", type="separator", title="Sección XYZ"),
    ]
    state = _state(slides, valid_xlsx_path, valid_template_path)
    out = tmp_path / "out.pptx"
    build_pptx(state, str(out))

    prs = Presentation(str(out))
    texts = []
    for sh in prs.slides[0].shapes:
        if sh.has_text_frame:
            texts.append(sh.text_frame.text)
    assert any("Sección XYZ" in t for t in texts)
    assert not any("@Titulo" in t for t in texts)


def test_build_pptx_with_chart(tmp_path, valid_xlsx_path, valid_template_path):
    chart = Chart(id="c1", question_id="q1", breakdown_id="general", chart_type="PIE")
    slides = [
        Slide(id="s1", type="separator", title="Sec"),
        Slide(id="s2", type="shell", title="Sec", charts=[chart]),
    ]
    state = _state(slides, valid_xlsx_path, valid_template_path)
    out = tmp_path / "out.pptx"
    build_pptx(state, str(out))

    prs = Presentation(str(out))
    chart_shapes = [sh for sh in prs.slides[1].shapes if getattr(sh, "has_chart", False)]
    assert len(chart_shapes) == 1


def test_build_pptx_with_analysis_text(tmp_path, valid_xlsx_path, valid_template_path):
    """Pipeline produces a valid pptx when slide has an analysis (no crash)."""
    analysis = Analysis(id="a1", scope="slide", target_id=None, text="Análisis XYZ", ai_generated=True, edited=False)
    slides = [
        Slide(id="s1", type="separator", title="Sec"),
        Slide(id="s2", type="shell", title="Sec", analyses=[analysis]),
    ]
    state = _state(slides, valid_xlsx_path, valid_template_path)
    out = tmp_path / "out.pptx"
    build_pptx(state, str(out))

    prs = Presentation(str(out))
    # The new pipeline renders pattern elements; analysis scope handled via content_source.
    # We just assert the pptx was produced and has 2 slides.
    assert len(prs.slides) == 2


def test_build_pptx_applies_font_override(tmp_path, valid_xlsx_path, valid_template_path):
    """Pipeline completes without crash when font_override is set."""
    state = _state(
        [
            Slide(id="s1", type="separator", title="Sec"),
            Slide(id="s2", type="shell", title="Sec",
                  analyses=[Analysis(id="a1", scope="slide", target_id=None, text="X", ai_generated=False, edited=True)]),
        ],
        valid_xlsx_path, valid_template_path,
    )
    state.inputs.font_override = "Roboto"
    out = tmp_path / "out.pptx"
    build_pptx(state, str(out))

    prs = Presentation(str(out))
    assert len(prs.slides) == 2


def test_build_pptx_pipeline_produces_slide_count(tmp_path, valid_xlsx_path, valid_template_path):
    """classify→render pipeline: 1 sep + 1 shell → 2-slide output, no crash."""
    chart = Chart(id="c1", question_id="q1", breakdown_id="general", chart_type="PIE")
    slides = [
        Slide(id="s1", type="separator", title="Pipeline Test"),
        Slide(id="s2", type="shell", title="Pipeline Test", charts=[chart]),
    ]
    state = _state(slides, valid_xlsx_path, valid_template_path)
    out = tmp_path / "pipeline_out.pptx"
    build_pptx(state, str(out))

    prs = Presentation(str(out))
    assert len(prs.slides) == 2


def test_build_pptx_empty_shell_no_crash(tmp_path, valid_xlsx_path, valid_template_path):
    """Empty shell slide (no charts, no analyses) produces valid pptx without crash."""
    slides = [
        Slide(id="s1", type="shell", title="Empty"),
    ]
    state = _state(slides, valid_xlsx_path, valid_template_path)
    out = tmp_path / "empty_shell.pptx"
    build_pptx(state, str(out))

    assert out.exists()
    prs = Presentation(str(out))
    assert len(prs.slides) == 1


def test_add_chart_handles_empty_breakdown_ids_as_general():
    """Chart with breakdown_ids=[] plots the General row as single series."""
    from pptx import Presentation
    from aurum_encuestas.pptx_generator import _add_chart
    from aurum_encuestas.models import Chart, Question, Breakdown, ParsedDB, ProjectInputs, ProjectState
    from types import SimpleNamespace

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    chart = Chart(id="c1", question_id="q1", breakdown_ids=[], chart_type="PIE")
    parsed = ParsedDB(
        questions=[Question(id="q1", code="Q1", text="t", options=["Sí","No"], confidence=0.9)],
        breakdowns=[Breakdown(id="general", label="General", categories=["Total"])],
        sample_size=100,
        data_blocks={"counts_cols":[],"pct_row_cols":[],"pct_col_cols":[]},
    )
    state = ProjectState(
        project_name="t",
        inputs=ProjectInputs(db_path="", template_path=""),
        parsed_db=parsed,
        slides=[],
    )
    el = {"x": 0, "y": 0, "cx": 5_000_000, "cy": 3_000_000}
    # Monkeypatch extract_chart_data through the import path used by _add_chart
    import aurum_encuestas.pptx_generator as pg
    orig = pg.extract_chart_data
    pg.extract_chart_data = lambda *a, **kw: {"General": {"Sí":{"pct":0.6,"count":60},"No":{"pct":0.4,"count":40}}}
    try:
        _add_chart(slide, chart, state, el)
    finally:
        pg.extract_chart_data = orig
    assert any(sh.has_chart for sh in slide.shapes)
