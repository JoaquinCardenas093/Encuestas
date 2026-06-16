from aurum_encuestas.pptx_generator import build_pptx
from aurum_encuestas.models import (
    ProjectState, ProjectInputs, Slide, Chart, Analysis, ParsedDB, Question, Breakdown,
)
from pptx import Presentation


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
    chart = Chart(id="c1", question_id="q1", breakdown_id="general", chart_type="PIE", multi_series=False)
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
    analysis = Analysis(id="a1", scope="slide", target_id=None, text="Análisis XYZ", ai_generated=True, edited=False)
    slides = [
        Slide(id="s1", type="separator", title="Sec"),
        Slide(id="s2", type="shell", title="Sec", analyses=[analysis]),
    ]
    state = _state(slides, valid_xlsx_path, valid_template_path)
    out = tmp_path / "out.pptx"
    build_pptx(state, str(out))

    prs = Presentation(str(out))
    texts = [sh.text_frame.text for sh in prs.slides[1].shapes if sh.has_text_frame]
    assert any("Análisis XYZ" in t for t in texts)
