from aurum_encuestas.models import Analysis, Breakdown, Chart, ParsedDB, ProjectState, Question, Slide


def test_question_basic():
    q = Question(id="q1", code="P1", text="¿Recuerda?", options=["Sí", "No"], confidence=1.0)
    assert q.id == "q1"
    assert q.confidence == 1.0


def test_breakdown_basic():
    b = Breakdown(id="sexo", label="Sexo", categories=["Hombre", "Mujer"])
    assert b.categories == ["Hombre", "Mujer"]


def test_parsed_db_basic():
    db = ParsedDB(
        questions=[Question(id="q1", code="P1", text="?", options=["a"], confidence=1.0)],
        breakdowns=[Breakdown(id="general", label="General", categories=["Total"])],
        sample_size=500,
        data_blocks={"counts_cols": [3, 17], "pct_row_cols": [21, 35], "pct_col_cols": [41, 55]},
    )
    assert db.sample_size == 500


def test_slide_separator():
    s = Slide(id="s1", type="separator", title="Sección 1")
    assert s.type == "separator"
    assert s.charts == []
    assert s.analyses == []


def test_slide_shell_with_chart():
    chart = Chart(id="c1", question_id="q1", breakdown_id="sexo", chart_type="PIE", multi_series=False)
    s = Slide(id="s2", type="shell", charts=[chart])
    assert len(s.charts) == 1
    assert s.charts[0].chart_type == "PIE"


def test_analysis_scopes():
    for scope in ("slide", "question", "chart"):
        a = Analysis(id="a1", scope=scope, target_id=None, text="x", ai_generated=True, edited=False)
        assert a.scope == scope


def test_project_state_roundtrip():
    state = ProjectState(
        version=1,
        project_name="Test",
        inputs={"db_path": "./x.xlsx", "template_path": "./t.pptx", "font_override": None},
        slides=[Slide(id="s1", type="separator", title="A")],
    )
    dumped = state.model_dump()
    restored = ProjectState.model_validate(dumped)
    assert restored.project_name == "Test"
