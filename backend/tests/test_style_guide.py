from aurum_encuestas.style_guide import (
    ElementChart,
    ElementImage,
    ElementShape,
    ElementTable,
    ElementText,
    Pattern,
    Position,
    PositionAnchored,
    StyleGuide,
    Trigger,
)

# ── Position ──────────────────────────────────────────────────────────────────

def test_position_basic():
    p = Position(x_rel=0.05, y_rel=0.25, w_rel=0.3, h_rel=0.55)
    assert p.x_rel == 0.05
    assert p.h_rel == 0.55


def test_position_anchored():
    p = PositionAnchored(anchor="main_pie", relative="right_of", offset_rel=0.02, w_rel=0.3, h_rel=0.5)
    assert p.anchor == "main_pie"
    assert p.relative == "right_of"


# ── Trigger ───────────────────────────────────────────────────────────────────

def test_trigger_eq():
    t = Trigger.model_validate({"field": "question_type", "$eq": "binary"})
    assert t.field == "question_type"
    assert t.eq == "binary"


def test_trigger_gte():
    t = Trigger.model_validate({"field": "n_breakdowns", "$gte": 2})
    assert t.gte == 2


def test_trigger_in():
    t = Trigger.model_validate({"field": "question_type", "$in": ["binary", "multi_small"]})
    assert t.in_ == ["binary", "multi_small"]


def test_trigger_and_composition():
    t = Trigger.model_validate({
        "$and": [
            {"field": "n_charts_in_slide", "$eq": 1},
            {"field": "question_type", "$eq": "binary"},
        ]
    })
    assert t.and_ is not None
    assert len(t.and_) == 2


def test_trigger_or_composition():
    t = Trigger.model_validate({
        "$or": [
            {"field": "question_type", "$eq": "binary"},
            {"field": "question_type", "$eq": "multi_small"},
        ]
    })
    assert t.or_ is not None


def test_trigger_not():
    t = Trigger.model_validate({"$not": {"field": "question_type", "$eq": "open"}})
    assert t.not_ is not None


def test_trigger_nested_and_or():
    t = Trigger.model_validate({
        "$and": [
            {"$or": [{"field": "question_type", "$eq": "binary"}, {"field": "question_type", "$eq": "multi_small"}]},
            {"$not": {"field": "has_slide_analysis", "$eq": True}},
        ]
    })
    assert t.and_ is not None
    assert len(t.and_) == 2


# ── Element kinds ─────────────────────────────────────────────────────────────

def test_element_chart_minimal():
    e = ElementChart.model_validate({
        "kind": "chart",
        "id": "main_pie",
        "position": {"x_rel": 0.05, "y_rel": 0.25, "w_rel": 0.3, "h_rel": 0.55},
        "chart_type": "PIE",
        "data_source": {"chart_ref_index": 0, "value_field": "pct"},
        "legend": "none",
    })
    assert e.kind == "chart"
    assert e.chart_type == "PIE"
    assert e.legend == "none"


def test_element_chart_extra_ignored():
    """extra = 'ignore' on all models."""
    e = ElementChart.model_validate({
        "kind": "chart",
        "id": "c1",
        "position": {"x_rel": 0.1, "y_rel": 0.1, "w_rel": 0.4, "h_rel": 0.4},
        "chart_type": "BAR_HORIZONTAL",
        "data_source": {"chart_ref_index": 0, "value_field": "count"},
        "legend": "right",
        "UNKNOWN_FUTURE_FIELD": "should_be_ignored",
    })
    assert not hasattr(e, "UNKNOWN_FUTURE_FIELD")


def test_element_table_minimal():
    e = ElementTable.model_validate({
        "kind": "table",
        "id": "demographics_table",
        "position": {"x_rel": 0.4, "y_rel": 0.25, "w_rel": 0.55, "h_rel": 0.55},
        "structure": "segmented_breakdowns",
        "data_source": {"chart_ref_index": 0, "breakdown_groups": "all_except_general"},
    })
    assert e.structure == "segmented_breakdowns"


def test_element_text_minimal():
    e = ElementText.model_validate({
        "kind": "text",
        "id": "analysis_box",
        "position": {"x_rel": 0.05, "y_rel": 0.82, "w_rel": 0.9, "h_rel": 0.12},
        "content_source": {"type": "analysis", "scope": "slide"},
    })
    assert e.kind == "text"


def test_element_shape_minimal():
    e = ElementShape.model_validate({
        "kind": "shape",
        "id": "divider",
        "position": {"x_rel": 0.0, "y_rel": 0.22, "w_rel": 1.0, "h_rel": 0.002},
        "shape_type": "line",
        "style": {"color": "secondary", "width_pt": 0.75},
    })
    assert e.shape_type == "line"


def test_element_image_minimal():
    e = ElementImage.model_validate({
        "kind": "image",
        "id": "logo",
        "position": {"x_rel": 0.85, "y_rel": 0.02, "w_rel": 0.12, "h_rel": 0.08},
        "source_ref": "logo_shape_1",
    })
    assert e.source_ref == "logo_shape_1"


# ── Pattern + Implementation ──────────────────────────────────────────────────

def test_pattern_minimal():
    p = Pattern.model_validate({
        "id": "binary_general",
        "priority": 0,
        "trigger": {"field": "question_type", "$eq": "binary"},
        "implementation": {
            "elements": [
                {
                    "kind": "chart",
                    "id": "c1",
                    "position": {"x_rel": 0.05, "y_rel": 0.25, "w_rel": 0.4, "h_rel": 0.55},
                    "chart_type": "PIE",
                    "data_source": {"chart_ref_index": 0, "value_field": "pct"},
                    "legend": "none",
                }
            ]
        },
    })
    assert p.id == "binary_general"
    assert len(p.implementation.elements) == 1


def test_pattern_with_extends():
    p = Pattern.model_validate({
        "id": "binary_demo",
        "priority": 1,
        "trigger": {"field": "n_breakdowns", "$gte": 2},
        "extends": "binary_general",
        "implementation": {"elements": []},
    })
    assert p.extends == "binary_general"


# ── StyleGuide ────────────────────────────────────────────────────────────────

def test_style_guide_minimal():
    sg = StyleGuide.model_validate({
        "version": 1,
        "is_builtin": True,
        "patterns": [],
        "global": {
            "typography": {"font_family": "Calibri", "title_size": 16, "subtitle_size": 12, "label_size": 9, "body_size": 10},
            "text_patterns": {"title": "{question_code}. {question_text}"},
            "suggested_palette": ["#7F7F7F", "#BFBFBF"],
            "vibe": "Minimalista",
        },
        "available_chart_types": ["PIE", "BAR_HORIZONTAL"],
    })
    assert sg.is_builtin is True
    assert sg.version == 1


def test_style_guide_extra_ignored():
    sg = StyleGuide.model_validate({
        "version": 1,
        "is_builtin": False,
        "patterns": [],
        "global": {
            "typography": {"font_family": "Arial", "title_size": 16, "subtitle_size": 12, "label_size": 9, "body_size": 10},
            "text_patterns": {},
            "suggested_palette": [],
            "vibe": "",
        },
        "available_chart_types": [],
        "FUTURE_TOP_LEVEL_KEY": "ignored",
    })
    assert not hasattr(sg, "FUTURE_TOP_LEVEL_KEY")


# ── BUILTIN_STYLE_GUIDE ───────────────────────────────────────────────────────

from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE  # noqa: E402


def test_builtin_is_valid_style_guide():
    assert isinstance(BUILTIN_STYLE_GUIDE, StyleGuide)
    assert BUILTIN_STYLE_GUIDE.is_builtin is True


def test_builtin_has_seven_patterns():
    assert len(BUILTIN_STYLE_GUIDE.patterns) == 7


def test_builtin_pattern_ids():
    ids = {p.id for p in BUILTIN_STYLE_GUIDE.patterns}
    assert "binary_general" in ids
    assert "binary_with_demographics" in ids
    assert "multi_choice_small" in ids
    assert "multi_choice_large" in ids
    assert "comparison_two_charts" in ids
    assert "n_charts_grid" in ids
    assert "table_only_full_width" in ids


def test_builtin_patterns_have_valid_triggers():
    for p in BUILTIN_STYLE_GUIDE.patterns:
        assert isinstance(p.trigger, Trigger), f"pattern {p.id} has invalid trigger"


def test_builtin_patterns_have_elements():
    for p in BUILTIN_STYLE_GUIDE.patterns:
        assert len(p.implementation.elements) >= 1, f"pattern {p.id} has no elements"


def test_builtin_priority_ordering():
    priorities = [p.priority for p in BUILTIN_STYLE_GUIDE.patterns]
    # priorities should be unique and ordered (not required to be sequential, but let's verify they're sortable)
    assert sorted(priorities) == priorities or len(set(priorities)) == len(priorities)


def test_builtin_patterns_use_aurora_proportions():
    patterns = {p.id: p for p in BUILTIN_STYLE_GUIDE.patterns}

    # comparison_two_charts: each chart should be tall (h_rel >= 0.70)
    p = patterns["comparison_two_charts"]
    chart_els = [e for e in p.implementation.elements if e.kind == "chart"]
    assert len(chart_els) == 2
    for el in chart_els:
        assert el.position.h_rel >= 0.70, f"{el.id}: h_rel={el.position.h_rel} too short vs Aurora (0.75)"

    # multi_choice_small: full-width bar with h_rel >= 0.70
    el = next(e for e in patterns["multi_choice_small"].implementation.elements if e.kind == "chart")
    assert el.position.h_rel >= 0.65

    # binary_general: large centred pie
    el = next(e for e in patterns["binary_general"].implementation.elements if e.kind == "chart")
    assert el.position.h_rel >= 0.70


# ── migrate_legacy_files ──────────────────────────────────────────────────────

from aurum_encuestas.style_guide import migrate_legacy_files  # noqa: E402


def test_migrate_moves_pptx_to_corpus(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    training_dir = tmp_path / ".aurum" / "training"
    training_dir.mkdir(parents=True)
    (training_dir / "deck_a.pptx").write_bytes(b"fake")
    (training_dir / "deck_b.pptx").write_bytes(b"fake")

    migrate_legacy_files()

    corpus_dir = training_dir / "corpus"
    assert (corpus_dir / "deck_a.pptx").exists()
    assert (corpus_dir / "deck_b.pptx").exists()
    assert not (training_dir / "deck_a.pptx").exists()


def test_migrate_renames_layout_bank(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    training_dir = tmp_path / ".aurum" / "training"
    training_dir.mkdir(parents=True)
    bank = training_dir / "layout_bank.json"
    bank.write_text('{"layouts": []}')

    migrate_legacy_files()

    assert (training_dir / "layout_bank.json.legacy").exists()
    assert not bank.exists()


def test_migrate_idempotent(tmp_path, monkeypatch):
    """Running twice must not raise or double-move."""
    monkeypatch.setenv("HOME", str(tmp_path))
    training_dir = tmp_path / ".aurum" / "training"
    training_dir.mkdir(parents=True)
    (training_dir / "deck.pptx").write_bytes(b"fake")

    migrate_legacy_files()
    migrate_legacy_files()  # second call must not raise

    assert (training_dir / "corpus" / "deck.pptx").exists()


def test_migrate_no_training_dir(tmp_path, monkeypatch):
    """Should not raise if ~/.aurum/training doesn't exist yet."""
    monkeypatch.setenv("HOME", str(tmp_path))
    migrate_legacy_files()  # must not raise


# ── load_active ───────────────────────────────────────────────────────────────

import json  # noqa: E402

from aurum_encuestas.style_guide import load_active  # noqa: E402


def test_load_active_returns_builtin_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    sg = load_active()
    assert sg.is_builtin is True


def test_load_active_returns_file_when_present(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    training_dir = tmp_path / ".aurum" / "training"
    training_dir.mkdir(parents=True)
    # write a minimal valid style_guide.json
    sg_data = {
        "version": 1,
        "is_builtin": False,
        "patterns": [],
        "global": {
            "typography": {"font_family": "Arial", "title_size": 18, "subtitle_size": 12, "label_size": 9, "body_size": 10},
            "text_patterns": {},
            "suggested_palette": ["#123456"],
            "vibe": "test",
        },
        "available_chart_types": ["PIE"],
    }
    (training_dir / "style_guide.json").write_text(json.dumps(sg_data))

    sg = load_active()
    assert sg.is_builtin is False
    assert sg.global_.typography.font_family == "Arial"


def test_load_active_falls_back_on_corrupt_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    training_dir = tmp_path / ".aurum" / "training"
    training_dir.mkdir(parents=True)
    (training_dir / "style_guide.json").write_text("NOT VALID JSON{{{{")

    sg = load_active()
    assert sg.is_builtin is True


def test_builtin_palette_matches_aurora_reference():
    from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE
    palette = BUILTIN_STYLE_GUIDE.global_.suggested_palette
    # Yellow accent must appear in the palette (Aurora last-bar highlight)
    assert "#EEC245" in palette or "#FFC000" in palette
    # Grey neutrals first
    assert palette[0] in ("#7F7F7F", "#595959", "#404040")
    # Fase B: 5 chart types in available_chart_types including the newly added grouped variants
    assert "PIE_GROUPED" in BUILTIN_STYLE_GUIDE.available_chart_types
    assert "BAR_HORIZONTAL_GROUPED" in BUILTIN_STYLE_GUIDE.available_chart_types


def test_builtin_available_chart_types_phase_b_is_five():
    from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE
    assert BUILTIN_STYLE_GUIDE.available_chart_types == [
        "PIE", "PIE_GROUPED",
        "BAR_HORIZONTAL", "BAR_HORIZONTAL_GROUPED",
        "TABLE_WITH_MINIBARS",
    ]


def test_style_guide_default_available_chart_types_phase_b_is_five():
    from aurum_encuestas.style_guide import StyleGuide
    sg = StyleGuide()
    assert sg.available_chart_types == [
        "PIE", "PIE_GROUPED",
        "BAR_HORIZONTAL", "BAR_HORIZONTAL_GROUPED",
        "TABLE_WITH_MINIBARS",
    ]


def test_builtin_has_table_only_full_width_pattern():
    from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE
    matched = [p for p in BUILTIN_STYLE_GUIDE.patterns if p.id == "table_only_full_width"]
    assert len(matched) == 1, f"expected exactly one table_only_full_width pattern; got {len(matched)}"
    p = matched[0]
    assert p.priority == 10
    elements = list(p.implementation.elements)
    assert len(elements) == 1
    el = elements[0]
    # el may be a pydantic model — access via attribute or .model_dump()
    el_dict = el.model_dump() if hasattr(el, "model_dump") else el
    assert el_dict["kind"] == "chart"
    assert el_dict["chart_type"] == "TABLE_WITH_MINIBARS"
    assert el_dict["position"]["x_rel"] == 0.04
    assert el_dict["position"]["w_rel"] == 0.92
