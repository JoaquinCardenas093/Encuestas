# M6.3 — Pattern Classifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the full pattern classifier: extract slide context fields (question_type, n_charts, n_breakdowns, etc.), evaluate all 9 trigger operators (including recursive composition with $and/$or/$not), classify a slide_config against a StyleGuide's patterns (first match wins by priority asc), and cache results in-memory (LRU 200 entries).

**Architecture:** `pattern_classifier.py` is the single module. Internal helpers live in the same file (no sub-package needed at this stage). The LRU cache uses a simple ordered dict; Python's `functools.lru_cache` cannot be used because args are mutable dicts — we compute a deterministic hash manually.

**Tech Stack adds:** None. Pure stdlib.

---

## File Structure

**Modify (backend):**
- `backend/aurum_encuestas/pattern_classifier.py` — replace stub with full implementation
- `backend/tests/test_pattern_classifier.py` — new test file

---

### Task 1: Field extractors — slide_config → context dict

**Files:**
- Modify: `backend/aurum_encuestas/pattern_classifier.py`
- Create: `backend/tests/test_pattern_classifier.py`

- [ ] **Step 1: Failing tests**

Create `backend/tests/test_pattern_classifier.py`:

```python
"""Tests for pattern_classifier module — field extractors, trigger evaluation, classify, LRU cache."""
import pytest
from aurum_encuestas.pattern_classifier import (
    extract_context,
    evaluate_trigger,
    classify,
    clear_cache,
)
from aurum_encuestas.style_guide import Trigger, Pattern, Implementation, StyleGuide, BUILTIN_STYLE_GUIDE


# ────────────────────────────────────────────────────────────────────────────
# Helper builders
# ────────────────────────────────────────────────────────────────────────────

def _chart(question_id="q1", breakdown_id="general", chart_type="PIE"):
    return {"id": "c1", "question_id": question_id, "breakdown_id": breakdown_id, "chart_type": chart_type, "multi_series": False, "colors": []}


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
```

- [ ] **Step 2: Run failing**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_pattern_classifier.py::TestExtractContext -v 2>&1 | head -30
```
Expected: ImportError or AttributeError (stub has no `extract_context`).

- [ ] **Step 3: Implement extract_context**

Replace the stub content of `backend/aurum_encuestas/pattern_classifier.py` with:

```python
"""M6 Pattern Classifier.

Evaluates trigger operators against a slide context dict and returns the first
matching Pattern from the style guide (sorted by priority asc).

Trigger operators supported:
    Leaf:        $eq, $neq, $gt, $gte, $lt, $lte, $in, $nin
    Composition: $and, $or, $not

Context fields:
    n_charts_in_slide         int
    all_charts_share_question bool
    question_type             "binary"|"multi_small"|"multi_large"|"ranking"|"open"
    n_options_per_question    int
    breakdowns_used           list[str]
    n_breakdowns              int
    n_analyses                int
    n_chart_analyses          int
    n_question_analyses       int
    has_slide_analysis        bool
"""
from __future__ import annotations

import hashlib
import json
import logging
from collections import OrderedDict
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .style_guide import Pattern, StyleGuide, Trigger

log = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# LRU cache — (slide_config_hash, style_guide_hash) → Optional[str] pattern id
# ────────────────────────────────────────────────────────────────────────────

_LRU_MAX = 200
_cache: OrderedDict[tuple[str, str], Optional[str]] = OrderedDict()


def clear_cache() -> None:
    _cache.clear()


def _hash_dict(d: dict) -> str:
    return hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _hash_style_guide(sg) -> str:
    try:
        return hashlib.sha256(sg.model_dump_json().encode()).hexdigest()[:16]
    except Exception:
        return "builtin"


# ────────────────────────────────────────────────────────────────────────────
# Question type detection
# ────────────────────────────────────────────────────────────────────────────

_RANKING_KEYWORDS = {"ranking", "ordenar", "orden", "preferir", "preferencia", "priorizar", "clasificar"}


def _detect_question_type(n_options: int, question_text: str) -> str:
    text_lower = question_text.lower()
    if any(kw in text_lower for kw in _RANKING_KEYWORDS):
        return "ranking"
    if n_options == 0:
        return "open"
    if n_options == 2:
        return "binary"
    if n_options <= 5:
        return "multi_small"
    return "multi_large"


# ────────────────────────────────────────────────────────────────────────────
# Field extractors
# ────────────────────────────────────────────────────────────────────────────

def extract_context(slide_config: dict, parsed_db: dict) -> dict:
    """Derive trigger-evaluable context fields from a slide_config + parsed_db.

    slide_config shape:
        {
            "charts": [{"question_id": ..., "breakdown_id": ..., ...}, ...],
            "analyses": [{"scope": "chart"|"question"|"slide", ...}, ...],
            "_meta": {                         # optional pre-computed hints
                "n_options": int,
                "question_text": str,
                "breakdowns": list[str],
            }
        }
    parsed_db shape (subset used here):
        {
            "questions": [{"id": ..., "options": [...], "text": ...}, ...],
            "breakdowns": [{"id": ..., ...}, ...],
        }
    """
    charts = slide_config.get("charts", [])
    analyses = slide_config.get("analyses", [])
    meta = slide_config.get("_meta", {})

    # n_charts_in_slide
    n_charts = len(charts)

    # all_charts_share_question
    question_ids = list({c.get("question_id") for c in charts if c.get("question_id")})
    all_share = len(question_ids) <= 1

    # question_type + n_options_per_question
    # Use _meta if provided (pre-computed by pptx_generator or test), else look up in parsed_db
    n_options = int(meta.get("n_options", 0))
    question_text = str(meta.get("question_text", ""))
    if n_options == 0 and question_ids and parsed_db.get("questions"):
        primary_qid = question_ids[0]
        q_obj = next((q for q in parsed_db["questions"] if q.get("id") == primary_qid), None)
        if q_obj:
            n_options = len(q_obj.get("options", []))
            question_text = q_obj.get("text", question_text)
    question_type = _detect_question_type(n_options, question_text)

    # breakdowns_used
    breakdowns_used: list[str] = list(meta.get("breakdowns", []))
    if not breakdowns_used:
        # derive from charts
        breakdowns_used = list({c.get("breakdown_id") for c in charts if c.get("breakdown_id")})
    if not breakdowns_used and parsed_db.get("breakdowns"):
        breakdowns_used = [b["id"] for b in parsed_db["breakdowns"]]

    n_breakdowns = len(breakdowns_used)

    # analysis counts
    n_chart_an = sum(1 for a in analyses if a.get("scope") == "chart")
    n_q_an = sum(1 for a in analyses if a.get("scope") == "question")
    has_slide_an = any(a.get("scope") == "slide" for a in analyses)
    n_analyses = len(analyses)

    return {
        "n_charts_in_slide": n_charts,
        "all_charts_share_question": all_share,
        "question_type": question_type,
        "n_options_per_question": n_options,
        "breakdowns_used": breakdowns_used,
        "n_breakdowns": n_breakdowns,
        "n_analyses": n_analyses,
        "n_chart_analyses": n_chart_an,
        "n_question_analyses": n_q_an,
        "has_slide_analysis": has_slide_an,
    }
```

- [ ] **Step 4: Run field extractor tests**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_pattern_classifier.py::TestExtractContext -v
```
Expected: 11 PASS.

- [ ] **Step 5: Commit**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git add backend/aurum_encuestas/pattern_classifier.py backend/tests/test_pattern_classifier.py
git commit -m "$(cat <<'EOF'
feat(backend/m6.3): pattern_classifier field extractors — question_type detection + context dict

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: evaluate_trigger — all 9 operators + recursive composition

**Files:**
- Modify: `backend/aurum_encuestas/pattern_classifier.py`
- Modify: `backend/tests/test_pattern_classifier.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_pattern_classifier.py`:

```python
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
```

- [ ] **Step 2: Implement evaluate_trigger**

Append to `backend/aurum_encuestas/pattern_classifier.py` (after `extract_context`):

```python
# ────────────────────────────────────────────────────────────────────────────
# Trigger evaluation — recursive descent
# ────────────────────────────────────────────────────────────────────────────

def evaluate_trigger(trigger: "Trigger", context: dict) -> bool:
    """Evaluate a Trigger node against a context dict.

    Recursive: $and/$or/$not contain child Trigger nodes.
    Leaf: field + one comparison operator ($eq/$neq/$gt/$gte/$lt/$lte/$in/$nin).
    """
    # ── Composition operators ────────────────────────────────────────────────
    if trigger.and_ is not None:
        return all(evaluate_trigger(child, context) for child in trigger.and_)

    if trigger.or_ is not None:
        return any(evaluate_trigger(child, context) for child in trigger.or_)

    if trigger.not_ is not None:
        return not evaluate_trigger(trigger.not_, context)

    # ── Leaf evaluation ──────────────────────────────────────────────────────
    field = trigger.field
    if field is None:
        log.warning("evaluate_trigger: trigger has no field and no composition operator — returning False")
        return False

    value = context.get(field)
    if value is None and field not in context:
        log.debug("evaluate_trigger: unknown field %r — returning False", field)
        return False

    # $eq
    if trigger.eq is not None:
        return value == trigger.eq

    # $neq
    if trigger.neq is not None:
        return value != trigger.neq

    # $gt
    if trigger.gt is not None:
        try:
            return float(value) > float(trigger.gt)
        except (TypeError, ValueError):
            return False

    # $gte
    if trigger.gte is not None:
        try:
            return float(value) >= float(trigger.gte)
        except (TypeError, ValueError):
            return False

    # $lt
    if trigger.lt is not None:
        try:
            return float(value) < float(trigger.lt)
        except (TypeError, ValueError):
            return False

    # $lte
    if trigger.lte is not None:
        try:
            return float(value) <= float(trigger.lte)
        except (TypeError, ValueError):
            return False

    # $in
    if trigger.in_ is not None:
        return value in trigger.in_

    # $nin
    if trigger.nin is not None:
        return value not in trigger.nin

    log.warning("evaluate_trigger: leaf trigger for field %r has no operator — returning False", field)
    return False
```

- [ ] **Step 3: Run trigger tests**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_pattern_classifier.py::TestEvaluateTrigger -v
```
Expected: all PASS (24 tests).

- [ ] **Step 4: Commit**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git add backend/aurum_encuestas/pattern_classifier.py backend/tests/test_pattern_classifier.py
git commit -m "$(cat <<'EOF'
feat(backend/m6.3): evaluate_trigger — all 9 operators + recursive composition ($and/$or/$not)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: classify() — first match by priority asc

**Files:**
- Modify: `backend/aurum_encuestas/pattern_classifier.py`
- Modify: `backend/tests/test_pattern_classifier.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_pattern_classifier.py`:

```python
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


def _make_style_guide(patterns: list[Pattern]) -> StyleGuide:
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
```

- [ ] **Step 2: Implement classify**

Append to `backend/aurum_encuestas/pattern_classifier.py`:

```python
# ────────────────────────────────────────────────────────────────────────────
# classify — main entry point
# ────────────────────────────────────────────────────────────────────────────

def classify(slide_config: dict, parsed_db: dict, style_guide: "StyleGuide") -> Optional["Pattern"]:
    """Match slide_config against style_guide.patterns, return first match (priority asc).

    Returns None if no pattern matches → caller should use generic fallback layout.
    """
    # Cache lookup
    cfg_hash = _hash_dict(slide_config)
    sg_hash = _hash_style_guide(style_guide)
    cache_key = (cfg_hash, sg_hash)

    if cache_key in _cache:
        _cache.move_to_end(cache_key)
        cached_id = _cache[cache_key]
        if cached_id is None:
            return None
        for p in style_guide.patterns:
            if p.id == cached_id:
                return p
        return None

    # Evaluate patterns sorted by priority asc
    context = extract_context(slide_config, parsed_db)
    sorted_patterns = sorted(style_guide.patterns, key=lambda p: p.priority)

    matched: Optional["Pattern"] = None
    for pattern in sorted_patterns:
        try:
            if evaluate_trigger(pattern.trigger, context):
                matched = pattern
                break
        except Exception as exc:
            log.warning("classify: error evaluating trigger for pattern %r: %s — skipping", pattern.id, exc)
            continue

    # Update cache
    _cache[cache_key] = matched.id if matched else None
    if len(_cache) > _LRU_MAX:
        _cache.popitem(last=False)  # evict oldest

    return matched
```

- [ ] **Step 3: Run classify tests**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_pattern_classifier.py::TestClassify -v
```
Expected: all PASS (6 tests).

- [ ] **Step 4: Commit**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git add backend/aurum_encuestas/pattern_classifier.py backend/tests/test_pattern_classifier.py
git commit -m "$(cat <<'EOF'
feat(backend/m6.3): classify — first-match by priority asc + graceful error skip on bad triggers

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: LRU cache — 200-entry cache with hash keys + cache hit tests

**Files:**
- Modify: `backend/tests/test_pattern_classifier.py`

(Cache implementation is already included in the `classify` function above. This task adds explicit cache hit/miss tests.)

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_pattern_classifier.py`:

```python
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
```

- [ ] **Step 2: Run cache tests**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_pattern_classifier.py::TestLRUCache -v
```
Expected: all PASS (4 tests).

- [ ] **Step 3: Run full pattern_classifier test suite**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_pattern_classifier.py -v
```
Expected: all PASS (~45 tests total).

- [ ] **Step 4: Run full backend suite (regression)**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest -v
```
Expected: all PASS.

- [ ] **Step 5: Commit + tag**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git add backend/tests/test_pattern_classifier.py
git commit -m "$(cat <<'EOF'
test(backend/m6.3): LRU cache tests — hit/miss, no collision, eviction at 200 entries

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git tag m6.3-pattern-classifier
git log --oneline | head -10
```

---

## M6.3 Done When

- [ ] `extract_context(slide_config, parsed_db)` returns dict with all 10 trigger fields
- [ ] `question_type` detection: 0→open, 2→binary, 3-5→multi_small, 6+→multi_large, keyword→ranking
- [ ] `evaluate_trigger` handles all 9 operators ($eq/$neq/$gt/$gte/$lt/$lte/$in/$nin/$and/$or/$not) + nested composition + unknown field → False + exception → False
- [ ] `classify` iterates patterns sorted by priority asc, returns first match or None, gracefully skips patterns with broken triggers
- [ ] LRU cache: 200 entries, evicts oldest, `clear_cache()` resets it, distinct configs don't collide
- [ ] All pattern_classifier tests pass (~45 tests)
- [ ] No regressions in full backend test suite
- [ ] Git tag `m6.3-pattern-classifier` created
