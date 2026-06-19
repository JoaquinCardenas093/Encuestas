"""Tests for pattern_classifier module — field extractors, trigger evaluation, classify, LRU cache."""
from aurum_encuestas.pattern_classifier import (
    classify,
    clear_cache,
    evaluate_trigger,
    extract_context,
)
from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE, Pattern, StyleGuide, Trigger

# ────────────────────────────────────────────────────────────────────────────
# Helper builders
# ────────────────────────────────────────────────────────────────────────────

def _chart(question_id="q1", breakdown_id="general", chart_type="PIE"):
    bids = [] if breakdown_id == "general" else [breakdown_id]
    return {"id": "c1", "question_id": question_id, "breakdown_ids": bids, "chart_type": chart_type, "colors": []}


def _slide_config(
    charts=None,
    analyses=None,
    n_options=2,
    question_text="¿Cuál es tu opinión?",
    breakdowns=None,
):
    if charts is None:
        charts = [_chart()]
    if analyses is None:
        analyses = []
    if breakdowns is None:
        breakdowns = ["general"]
    return {
        "charts": charts,
        "analyses": analyses,
        "free_area": {"x": 600000, "y": 1200000, "cx": 11000000, "cy": 5000000},
        "_meta": {
            "n_options": n_options,
            "question_text": question_text,
            "breakdowns": breakdowns,
        },
    }


def _parsed_db(n_options=2, question_text="¿Cuál es?", breakdowns=None):
    if breakdowns is None:
        breakdowns = ["general"]
    return {
        "questions": [{"id": "q1", "code": "P1", "text": question_text, "options": [f"Opción {i}" for i in range(n_options)], "confidence": 1.0}],
        "breakdowns": [{"id": bd, "label": bd.capitalize(), "categories": ["Total"]} for bd in breakdowns],
    }


# ────────────────────────────────────────────────────────────────────────────
# Field extractors
# ────────────────────────────────────────────────────────────────────────────

class TestExtractContext:
    def test_n_charts_in_slide(self):
        cfg = _slide_config(charts=[_chart(), _chart()])
        db = _parsed_db()
        ctx = extract_context(cfg, db)
        assert ctx["n_charts_in_slide"] == 2

    def test_question_type_binary(self):
        ctx = extract_context(_slide_config(n_options=2), _parsed_db(n_options=2))
        assert ctx["question_type"] == "binary"

    def test_question_type_multi_small(self):
        ctx = extract_context(_slide_config(n_options=4), _parsed_db(n_options=4))
        assert ctx["question_type"] == "multi_small"

    def test_question_type_multi_large(self):
        ctx = extract_context(_slide_config(n_options=7), _parsed_db(n_options=7))
        assert ctx["question_type"] == "multi_large"

    def test_question_type_ranking_by_keyword(self):
        ctx = extract_context(
            _slide_config(n_options=3, question_text="Por favor ordenar las siguientes opciones"),
            _parsed_db(n_options=3, question_text="Por favor ordenar las siguientes opciones"),
        )
        assert ctx["question_type"] == "ranking"

    def test_question_type_open_when_no_options(self):
        ctx = extract_context(_slide_config(n_options=0), _parsed_db(n_options=0))
        assert ctx["question_type"] == "open"

    def test_n_breakdowns(self):
        bds = ["general", "sexo", "edad"]
        ctx = extract_context(_slide_config(breakdowns=bds), _parsed_db(breakdowns=bds))
        assert ctx["n_breakdowns"] == 3

    def test_n_analyses_by_scope(self):
        analyses = [
            {"id": "a1", "scope": "chart", "target_id": "c1", "text": "x", "ai_generated": True, "edited": False},
            {"id": "a2", "scope": "slide", "target_id": None, "text": "y", "ai_generated": True, "edited": False},
        ]
        ctx = extract_context(_slide_config(analyses=analyses), _parsed_db())
        assert ctx["n_analyses"] == 2
        assert ctx["n_chart_analyses"] == 1
        assert ctx["n_question_analyses"] == 0
        assert ctx["has_slide_analysis"] is True

    def test_all_charts_share_question_true(self):
        charts = [_chart(question_id="q1"), _chart(question_id="q1")]
        ctx = extract_context(_slide_config(charts=charts), _parsed_db())
        assert ctx["all_charts_share_question"] is True

    def test_all_charts_share_question_false(self):
        charts = [_chart(question_id="q1"), _chart(question_id="q2")]
        ctx = extract_context(_slide_config(charts=charts), _parsed_db())
        assert ctx["all_charts_share_question"] is False

    def test_n_options_per_question(self):
        ctx = extract_context(_slide_config(n_options=5), _parsed_db(n_options=5))
        assert ctx["n_options_per_question"] == 5

    def test_breakdowns_used(self):
        bds = ["general", "sexo"]
        ctx = extract_context(_slide_config(breakdowns=bds), _parsed_db(breakdowns=bds))
        assert set(ctx["breakdowns_used"]) == {"general", "sexo"}


# ────────────────────────────────────────────────────────────────────────────
# evaluate_trigger tests
# ────────────────────────────────────────────────────────────────────────────

class TestEvaluateTrigger:
    def _ctx(self, **kwargs):
        """Minimal context for trigger evaluation."""
        base = {
            "n_charts_in_slide": 1,
            "all_charts_share_question": True,
            "question_type": "binary",
            "n_options_per_question": 2,
            "breakdowns_used": ["general"],
            "n_breakdowns": 1,
            "n_analyses": 0,
            "n_chart_analyses": 0,
            "n_question_analyses": 0,
            "has_slide_analysis": False,
        }
        base.update(kwargs)
        return base

    # ── Leaf operators ───────────────────────────────────────────────────────

    def test_eq_true(self):
        t = Trigger.model_validate({"field": "question_type", "$eq": "binary"})
        assert evaluate_trigger(t, self._ctx(question_type="binary")) is True

    def test_eq_false(self):
        t = Trigger.model_validate({"field": "question_type", "$eq": "multi_small"})
        assert evaluate_trigger(t, self._ctx(question_type="binary")) is False

    def test_neq_true(self):
        t = Trigger.model_validate({"field": "question_type", "$neq": "open"})
        assert evaluate_trigger(t, self._ctx(question_type="binary")) is True

    def test_neq_false(self):
        t = Trigger.model_validate({"field": "question_type", "$neq": "binary"})
        assert evaluate_trigger(t, self._ctx(question_type="binary")) is False

    def test_gt_true(self):
        t = Trigger.model_validate({"field": "n_breakdowns", "$gt": 1})
        assert evaluate_trigger(t, self._ctx(n_breakdowns=3)) is True

    def test_gt_false(self):
        t = Trigger.model_validate({"field": "n_breakdowns", "$gt": 3})
        assert evaluate_trigger(t, self._ctx(n_breakdowns=3)) is False

    def test_gte_equal(self):
        t = Trigger.model_validate({"field": "n_breakdowns", "$gte": 2})
        assert evaluate_trigger(t, self._ctx(n_breakdowns=2)) is True

    def test_lt_true(self):
        t = Trigger.model_validate({"field": "n_charts_in_slide", "$lt": 3})
        assert evaluate_trigger(t, self._ctx(n_charts_in_slide=2)) is True

    def test_lte_equal(self):
        t = Trigger.model_validate({"field": "n_charts_in_slide", "$lte": 1})
        assert evaluate_trigger(t, self._ctx(n_charts_in_slide=1)) is True

    def test_in_true(self):
        t = Trigger.model_validate({"field": "question_type", "$in": ["binary", "multi_small"]})
        assert evaluate_trigger(t, self._ctx(question_type="multi_small")) is True

    def test_in_false(self):
        t = Trigger.model_validate({"field": "question_type", "$in": ["binary", "multi_small"]})
        assert evaluate_trigger(t, self._ctx(question_type="multi_large")) is False

    def test_nin_true(self):
        t = Trigger.model_validate({"field": "question_type", "$nin": ["open", "ranking"]})
        assert evaluate_trigger(t, self._ctx(question_type="binary")) is True

    def test_nin_false(self):
        t = Trigger.model_validate({"field": "question_type", "$nin": ["binary"]})
        assert evaluate_trigger(t, self._ctx(question_type="binary")) is False

    # ── Composition operators ────────────────────────────────────────────────

    def test_and_all_true(self):
        t = Trigger.model_validate({
            "$and": [
                {"field": "n_charts_in_slide", "$eq": 1},
                {"field": "question_type", "$eq": "binary"},
            ]
        })
        assert evaluate_trigger(t, self._ctx()) is True

    def test_and_one_false(self):
        t = Trigger.model_validate({
            "$and": [
                {"field": "n_charts_in_slide", "$eq": 1},
                {"field": "question_type", "$eq": "multi_small"},
            ]
        })
        assert evaluate_trigger(t, self._ctx()) is False

    def test_and_empty_true(self):
        """Empty $and = vacuously true."""
        t = Trigger.model_validate({"$and": []})
        assert evaluate_trigger(t, self._ctx()) is True

    def test_or_any_true(self):
        t = Trigger.model_validate({
            "$or": [
                {"field": "question_type", "$eq": "binary"},
                {"field": "question_type", "$eq": "multi_small"},
            ]
        })
        assert evaluate_trigger(t, self._ctx(question_type="multi_small")) is True

    def test_or_all_false(self):
        t = Trigger.model_validate({
            "$or": [
                {"field": "question_type", "$eq": "open"},
                {"field": "question_type", "$eq": "ranking"},
            ]
        })
        assert evaluate_trigger(t, self._ctx(question_type="binary")) is False

    def test_or_empty_false(self):
        """Empty $or = vacuously false."""
        t = Trigger.model_validate({"$or": []})
        assert evaluate_trigger(t, self._ctx()) is False

    def test_not_inverts_true(self):
        t = Trigger.model_validate({"$not": {"field": "question_type", "$eq": "open"}})
        assert evaluate_trigger(t, self._ctx(question_type="binary")) is True

    def test_not_inverts_false(self):
        t = Trigger.model_validate({"$not": {"field": "question_type", "$eq": "binary"}})
        assert evaluate_trigger(t, self._ctx(question_type="binary")) is False

    # ── Nested composition ───────────────────────────────────────────────────

    def test_and_containing_or(self):
        t = Trigger.model_validate({
            "$and": [
                {"$or": [
                    {"field": "question_type", "$eq": "binary"},
                    {"field": "question_type", "$eq": "multi_small"},
                ]},
                {"field": "n_breakdowns", "$gte": 2},
            ]
        })
        ctx = self._ctx(question_type="binary", n_breakdowns=3)
        assert evaluate_trigger(t, ctx) is True
        ctx_fail = self._ctx(question_type="binary", n_breakdowns=1)
        assert evaluate_trigger(t, ctx_fail) is False

    def test_not_containing_and(self):
        t = Trigger.model_validate({
            "$not": {
                "$and": [
                    {"field": "question_type", "$eq": "binary"},
                    {"field": "n_charts_in_slide", "$eq": 1},
                ]
            }
        })
        assert evaluate_trigger(t, self._ctx()) is False  # binary+1chart → and=True → not=False
        assert evaluate_trigger(t, self._ctx(n_charts_in_slide=2)) is True  # and=False → not=True

    def test_missing_field_returns_false(self):
        """Unknown field should not raise — just return False."""
        t = Trigger.model_validate({"field": "nonexistent_field", "$eq": "value"})
        assert evaluate_trigger(t, self._ctx()) is False

    def test_bool_field_eq_true(self):
        t = Trigger.model_validate({"field": "has_slide_analysis", "$eq": True})
        assert evaluate_trigger(t, self._ctx(has_slide_analysis=True)) is True
        assert evaluate_trigger(t, self._ctx(has_slide_analysis=False)) is False


# ────────────────────────────────────────────────────────────────────────────
# classify tests
# ────────────────────────────────────────────────────────────────────────────

def _make_pattern(pattern_id: str, priority: int, trigger_dict: dict) -> Pattern:
    return Pattern.model_validate({
        "id": pattern_id,
        "priority": priority,
        "trigger": trigger_dict,
        "implementation": {"elements": []},
    })


def _make_style_guide(patterns: list) -> StyleGuide:
    return StyleGuide.model_validate({
        "version": 1,
        "is_builtin": False,
        "patterns": [p.model_dump(by_alias=True) for p in patterns],
        "global": {
            "typography": {"font_family": "Arial", "title_size": 16, "subtitle_size": 12, "label_size": 9, "body_size": 10},
            "text_patterns": {},
            "suggested_palette": [],
            "vibe": "",
        },
        "available_chart_types": ["PIE"],
    })


class TestClassify:
    def _db(self):
        return _parsed_db(n_options=2)

    def test_returns_first_priority_match(self):
        clear_cache()
        p0 = _make_pattern("match_0", 0, {"field": "question_type", "$eq": "binary"})
        p1 = _make_pattern("match_1", 1, {"field": "question_type", "$eq": "binary"})
        sg = _make_style_guide([p1, p0])  # out of order — classify must sort
        cfg = _slide_config(n_options=2)
        result = classify(cfg, self._db(), sg)
        assert result is not None
        assert result.id == "match_0"

    def test_returns_none_when_no_pattern_matches(self):
        clear_cache()
        p = _make_pattern("multi_only", 0, {"field": "question_type", "$eq": "multi_large"})
        sg = _make_style_guide([p])
        cfg = _slide_config(n_options=2)  # binary — won't match multi_large
        result = classify(cfg, self._db(), sg)
        assert result is None

    def test_skips_patterns_with_invalid_triggers_gracefully(self):
        """A trigger that raises during evaluation should be skipped (log warning)."""
        clear_cache()
        p_bad = _make_pattern("bad", 0, {"field": "question_type", "$eq": "binary"})
        p_good = _make_pattern("good", 1, {"field": "n_charts_in_slide", "$eq": 1})
        sg = _make_style_guide([p_bad, p_good])

        # Monkeypatch evaluate_trigger to raise on "bad"
        import aurum_encuestas.pattern_classifier as pc
        original = pc.evaluate_trigger
        def _patched(trigger, ctx):
            # raise only on the trigger for p_bad (which has field=question_type, eq=binary)
            if trigger.field == "question_type" and trigger.eq == "binary":
                raise RuntimeError("simulated eval error")
            return original(trigger, ctx)

        pc.evaluate_trigger = _patched
        try:
            result = classify(_slide_config(n_options=2), self._db(), sg)
            assert result is not None
            assert result.id == "good"
        finally:
            pc.evaluate_trigger = original

    def test_uses_builtin_style_guide(self):
        """classify against BUILTIN_STYLE_GUIDE with binary single chart should match binary_general."""
        clear_cache()
        cfg = _slide_config(n_options=2, breakdowns=["general"])
        db = _parsed_db(n_options=2)
        result = classify(cfg, db, BUILTIN_STYLE_GUIDE)
        assert result is not None
        assert result.id == "binary_general"

    def test_builtin_multi_small_matches(self):
        clear_cache()
        cfg = _slide_config(n_options=4, breakdowns=["general"])
        db = _parsed_db(n_options=4)
        result = classify(cfg, db, BUILTIN_STYLE_GUIDE)
        assert result is not None
        assert result.id == "multi_choice_small"

    def test_builtin_two_charts_comparison(self):
        clear_cache()
        cfg = _slide_config(charts=[_chart(), _chart()], n_options=2)
        db = _parsed_db(n_options=2)
        result = classify(cfg, db, BUILTIN_STYLE_GUIDE)
        assert result is not None
        assert result.id == "comparison_two_charts"


# ────────────────────────────────────────────────────────────────────────────
# LRU Cache tests
# ────────────────────────────────────────────────────────────────────────────

class TestLRUCache:
    def test_cache_hit_returns_same_result(self):
        clear_cache()
        sg = BUILTIN_STYLE_GUIDE
        cfg = _slide_config(n_options=2)
        db = _parsed_db(n_options=2)

        result1 = classify(cfg, db, sg)
        result2 = classify(cfg, db, sg)  # should hit cache
        assert (result1 is None) == (result2 is None)
        if result1 is not None:
            assert result1.id == result2.id

    def test_cache_different_configs_dont_collide(self):
        clear_cache()
        sg = BUILTIN_STYLE_GUIDE
        cfg_binary = _slide_config(n_options=2)
        cfg_multi = _slide_config(n_options=4)
        db_binary = _parsed_db(n_options=2)
        db_multi = _parsed_db(n_options=4)

        r1 = classify(cfg_binary, db_binary, sg)
        r2 = classify(cfg_multi, db_multi, sg)
        # They should be different patterns
        if r1 and r2:
            assert r1.id != r2.id

    def test_clear_cache_works(self):
        clear_cache()
        sg = BUILTIN_STYLE_GUIDE
        cfg = _slide_config(n_options=2)
        db = _parsed_db(n_options=2)
        classify(cfg, db, sg)  # populate cache
        clear_cache()

        import aurum_encuestas.pattern_classifier as pc
        assert len(pc._cache) == 0

    def test_cache_evicts_oldest_at_200(self):
        clear_cache()
        import aurum_encuestas.pattern_classifier as pc

        sg = BUILTIN_STYLE_GUIDE
        # Insert 201 distinct configs to trigger eviction
        for i in range(201):
            cfg = _slide_config(charts=[_chart(question_id=f"q{i}")])
            db = _parsed_db()
            classify(cfg, db, sg)

        assert len(pc._cache) <= 200


# ────────────────────────────────────────────────────────────────────────────
# Task 4: n_charts_grid pattern
# ────────────────────────────────────────────────────────────────────────────

def test_three_charts_matches_n_charts_grid_pattern():
    from aurum_encuestas.pattern_classifier import classify_slide
    from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE
    from types import SimpleNamespace

    slide_config = SimpleNamespace(
        charts=[
            SimpleNamespace(question_id="q1", breakdown_ids=["sexo"], chart_type="PIE"),
            SimpleNamespace(question_id="q2", breakdown_ids=[], chart_type="BAR_HORIZONTAL"),
            SimpleNamespace(question_id="q3", breakdown_ids=[], chart_type="BAR_HORIZONTAL"),
        ],
        n_charts=3,
        analyses=[],
    )
    pattern = classify_slide(slide_config, BUILTIN_STYLE_GUIDE)
    assert pattern is not None and pattern.id == "n_charts_grid"


def test_enriched_chart_carries_breakdown_ids_list():
    """build_slide_config propagates Chart.breakdown_ids list verbatim."""
    from aurum_encuestas.pattern_classifier import build_slide_config
    from aurum_encuestas.models import Chart, ParsedDB, Question, Breakdown
    from types import SimpleNamespace

    chart = Chart(id="c1", question_id="q1", breakdown_ids=["edad", "sexo"], chart_type="TABLE_WITH_MINIBARS")
    slide_def = SimpleNamespace(charts=[chart], analyses=[])
    parsed = ParsedDB(
        questions=[Question(id="q1", code="Q1", text="t", options=["Sí","No"], confidence=0.9)],
        breakdowns=[Breakdown(id="edad", label="Edad", categories=["18-39","40-59"]),
                    Breakdown(id="sexo", label="Sexo", categories=["F","M"])],
        sample_size=500, data_blocks={"counts_cols":[],"pct_row_cols":[],"pct_col_cols":[]},
    )
    cfg = build_slide_config(slide_def, parsed_db=parsed, db_path=None)
    assert len(cfg.charts) == 1
    assert cfg.charts[0].breakdown_ids == ["edad", "sexo"]


def test_n_breakdowns_uses_breakdown_ids_length():
    """Trigger context n_breakdowns reflects total unique non-general breakdown_ids
    across all charts on the slide."""
    from aurum_encuestas.pattern_classifier import extract_context
    cfg = {
        "charts": [
            {"question_id": "q1", "breakdown_ids": ["edad"]},
            {"question_id": "q1", "breakdown_ids": ["sexo", "nse"]},
            {"question_id": "q2", "breakdown_ids": []},
        ],
        "analyses": [],
    }
    ctx = extract_context(cfg, db=None)
    # 3 unique real breakdowns across slide: edad, sexo, nse
    assert ctx["n_breakdowns"] == 3
