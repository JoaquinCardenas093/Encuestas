import pytest
from aurum_encuestas.style_guide import (
    StyleGuide,
    Pattern,
    Trigger,
    Implementation,
    ElementChart,
    ElementTable,
    ElementText,
    ElementShape,
    ElementImage,
    Position,
    PositionAnchored,
    GlobalConfig,
    Typography,
    TextPatterns,
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
