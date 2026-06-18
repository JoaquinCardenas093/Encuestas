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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .style_guide import Pattern, StyleGuide, Trigger

log = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# LRU cache — (slide_config_hash, style_guide_hash) → Optional[str] pattern id
# ────────────────────────────────────────────────────────────────────────────

_LRU_MAX = 200
_cache: OrderedDict[tuple[str, str], str | None] = OrderedDict()


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


# ────────────────────────────────────────────────────────────────────────────
# Trigger evaluation — recursive descent
# ────────────────────────────────────────────────────────────────────────────

def evaluate_trigger(trigger: Trigger, context: dict) -> bool:
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


# ────────────────────────────────────────────────────────────────────────────
# classify — main entry point
# ────────────────────────────────────────────────────────────────────────────

def classify(slide_config: dict, parsed_db: dict, style_guide: StyleGuide) -> Pattern | None:
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

    matched: Pattern | None = None
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
