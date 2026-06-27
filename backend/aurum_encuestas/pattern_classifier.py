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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .style_guide import Pattern, StyleGuide, Trigger

log = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# LRU cache — (slide_config_hash, style_guide_hash) → Optional[str] pattern id
# ────────────────────────────────────────────────────────────────────────────

_LRU_MAX = 200
_cache: OrderedDict[tuple[str, str], str | None] = OrderedDict()

# Public alias for cache clearing via API (M6.8)
_classifier_cache: dict = _cache  # type: ignore[assignment]


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


# Aliases for AI-generated vocabulary (AI uses single_choice/multiple_choice)
# Map them to our internal names + accept both in trigger evaluation
_QUESTION_TYPE_ALIASES = {
    "single_choice": ("binary", "multi_small", "multi_large"),
    "multiple_choice": ("multi_small", "multi_large"),
    "binary": ("binary",),
    "multi_small": ("multi_small",),
    "multi_large": ("multi_large",),
    "ranking": ("ranking",),
    "open": ("open",),
}


def _question_type_matches(actual: str, expected: str) -> bool:
    """True if actual question_type satisfies expected (with AI alias mapping)."""
    return actual in _QUESTION_TYPE_ALIASES.get(expected, (expected,))


# ────────────────────────────────────────────────────────────────────────────
# Field extractors
# ────────────────────────────────────────────────────────────────────────────

def extract_context(slide_config: dict, db: dict = None) -> dict:
    """Derive trigger-evaluable context fields from a slide_config + parsed_db.

    slide_config shape:
        {
            "charts": [{"question_id": ..., "breakdown_ids": [...], ...}, ...],
            "analyses": [{"scope": "chart"|"question"|"slide", ...}, ...],
            "_meta": {                         # optional pre-computed hints
                "n_options": int,
                "question_text": str,
                "breakdowns": list[str],
            }
        }
    db shape (subset used here):
        {
            "questions": [{"id": ..., "options": [...], "text": ...}, ...],
            "breakdowns": [{"id": ..., ...}, ...],
        }
    """
    parsed_db = db or {}
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
    breakdowns_used: list[str] = [b for b in meta.get("breakdowns", []) if b and b.lower() != "general"]
    if not breakdowns_used:
        # derive from charts using breakdown_ids list
        bd_set: set[str] = set()
        for c in charts:
            for bd in (c.get("breakdown_ids") or []):
                if bd and bd.lower() != "general":
                    bd_set.add(bd)
        breakdowns_used = sorted(bd_set)
    if not breakdowns_used and not charts and parsed_db.get("breakdowns"):
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

    # $eq (with question_type alias mapping)
    if trigger.eq is not None:
        if field == "question_type" and isinstance(value, str) and isinstance(trigger.eq, str):
            return _question_type_matches(value, trigger.eq)
        return value == trigger.eq

    # $neq
    if trigger.neq is not None:
        if field == "question_type" and isinstance(value, str) and isinstance(trigger.neq, str):
            return not _question_type_matches(value, trigger.neq)
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

    # $in (with question_type alias mapping)
    if trigger.in_ is not None:
        if field == "question_type" and isinstance(value, str):
            return any(_question_type_matches(value, expected) for expected in trigger.in_ if isinstance(expected, str))
        return value in trigger.in_

    # $nin
    if trigger.nin is not None:
        if field == "question_type" and isinstance(value, str):
            return not any(_question_type_matches(value, expected) for expected in trigger.nin if isinstance(expected, str))
        return value not in trigger.nin

    log.warning("evaluate_trigger: leaf trigger for field %r has no operator — returning False", field)
    return False


# ────────────────────────────────────────────────────────────────────────────
# classify — main entry point
# ────────────────────────────────────────────────────────────────────────────

def _pattern_has_chart(pattern) -> bool:
    """True if pattern's implementation contains at least one element with kind=='chart'."""
    impl = getattr(pattern, "implementation", None)
    if impl is None:
        return False
    elements = getattr(impl, "elements", None) or []
    for el in elements:
        kind = getattr(el, "kind", None) if not isinstance(el, dict) else el.get("kind")
        if kind == "chart":
            return True
    return False



def classify(slide_config: dict, parsed_db: dict, style_guide: StyleGuide, require_chart: bool = False) -> Pattern | None:
    """Match slide_config against style_guide.patterns, return first match (priority asc).

    Returns None if no pattern matches → caller should use generic fallback layout.

    Args:
        require_chart: when True, patterns whose implementation has no element of
            kind "chart" are skipped. Prevents chart-less overlay patterns (e.g.
            logo-only headers with a permissive trigger) from outranking real
            layout patterns for slides that actually have charts.
    """
    # Cache lookup
    cfg_hash = _hash_dict(slide_config)
    sg_hash = _hash_style_guide(style_guide)
    cache_key = (cfg_hash, sg_hash, bool(require_chart))

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
        if require_chart and not _pattern_has_chart(pattern):
            continue
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


def classify_pattern(slide_config: Any, patterns: list) -> Pattern | None:
    """Classify a slide_config against a list of patterns (no parsed_db required).

    Convenience alias used by pptx_generator. Builds a dict-compatible slide_config
    from a SlideConfig object and delegates to classify().
    """
    from .style_guide import BUILTIN_STYLE_GUIDE, StyleGuide

    # Build a minimal slide_config dict for extract_context
    if hasattr(slide_config, "charts"):
        # It's a SlideConfig object — convert to dict
        charts_dicts = []
        for c in (slide_config.charts or []):
            if hasattr(c, "model_dump"):
                charts_dicts.append(c.model_dump())
            elif hasattr(c, "__dict__"):
                charts_dicts.append(dict(c.__dict__))
            else:
                charts_dicts.append(c)
        analyses_dicts = []
        for a in (slide_config.analyses or []):
            if hasattr(a, "model_dump"):
                analyses_dicts.append(a.model_dump())
            elif hasattr(a, "__dict__"):
                analyses_dicts.append(dict(a.__dict__))
            else:
                analyses_dicts.append(a)
        sc_dict = {"charts": charts_dicts, "analyses": analyses_dicts}
    elif isinstance(slide_config, dict):
        sc_dict = slide_config
    else:
        sc_dict = {}

    # Build a temporary StyleGuide wrapping the patterns list
    try:
        sg = StyleGuide.model_validate({"patterns": [p.model_dump() for p in patterns]})
    except Exception:
        # If patterns are already StyleGuide Pattern objects or unserialisable, use built-in
        sg = BUILTIN_STYLE_GUIDE
        if not patterns:
            return None

    return classify(sc_dict, {}, sg)


def classify_slide(slide_config: Any, style_guide: "StyleGuide") -> "Pattern | None":
    """Classify a slide_config object (or dict) against a StyleGuide.

    Convenience wrapper used by tests and pptx_generator when a full StyleGuide
    is available but no parsed_db is needed (context is derived solely from
    slide_config.charts / analyses counts).

    Args:
        slide_config: any object with .charts (list) and .analyses (list), or a dict.
        style_guide: StyleGuide instance to classify against.

    Returns:
        Matched Pattern or None.
    """
    if hasattr(slide_config, "charts"):
        charts_list = slide_config.charts or []
        # Convert to list of dicts for extract_context
        charts_dicts = []
        for c in charts_list:
            if hasattr(c, "model_dump"):
                charts_dicts.append(c.model_dump())
            elif hasattr(c, "__dict__"):
                charts_dicts.append(dict(c.__dict__))
            elif isinstance(c, dict):
                charts_dicts.append(c)
            else:
                charts_dicts.append({})
        analyses_list = getattr(slide_config, "analyses", []) or []
        analyses_dicts = []
        for a in analyses_list:
            if hasattr(a, "model_dump"):
                analyses_dicts.append(a.model_dump())
            elif hasattr(a, "__dict__"):
                analyses_dicts.append(dict(a.__dict__))
            elif isinstance(a, dict):
                analyses_dicts.append(a)
            else:
                analyses_dicts.append({})
        sc_dict: dict = {"charts": charts_dicts, "analyses": analyses_dicts}
    elif isinstance(slide_config, dict):
        sc_dict = slide_config
    else:
        sc_dict = {}

    return classify(sc_dict, {}, style_guide)


def build_slide_config(slide_def: Any, parsed_db: Any, db_path: str = "") -> Any:
    """Build a SlideConfig object from a Slide model + ParsedDB for classifier and renderer.

    Returns an object with .charts (enriched with .question and .data), .analyses,
    .n_charts, .n_analyses, .parsed_db.

    Enriched chart objects have:
      .question — Question model from parsed_db (with .options)
      .data     — {breakdown_category: {option: {count, pct}}} dict
    """
    from dataclasses import dataclass, field
    from typing import Any as _Any

    @dataclass
    class SlideConfig:
        charts: list = field(default_factory=list)
        analyses: list = field(default_factory=list)
        template_shapes: dict = field(default_factory=dict)
        n_charts: int = 0
        question_type: str = "binary"
        n_breakdowns: int = 0
        n_analyses: int = 0
        parsed_db: _Any = None
        layout: _Any = None  # SlideLayout from AI corrector — propagates to renderers

    @dataclass
    class EnrichedChart:
        """Chart with resolved question + data for use by element_renderers."""
        id: str
        question_id: str
        breakdown_ids: list[str]
        chart_type: str
        colors: list
        question: _Any = None   # Question model from parsed_db
        data: dict = field(default_factory=dict)
        # Nested: {bd_id: {"label": str, "categories": {cat: {opt: {count,pct}}}}}
        # Populated for every chart so segmented tables can render group-merged
        # headers without needing N separate chart_ref_index queries.
        all_breakdowns_data: dict = field(default_factory=dict)
        show_legend: bool = False
        grid_cols: int | None = None
        title: str | None = None
        cat_titles: dict | None = None

    raw_charts = getattr(slide_def, "charts", []) or []
    analyses = getattr(slide_def, "analyses", []) or []

    # Enrich charts with question + data from parsed_db
    enriched_charts = []
    for chart in raw_charts:
        question = None
        chart_data: dict = {}
        all_bds: dict = {}
        if parsed_db and hasattr(parsed_db, "questions"):
            question = next(
                (q for q in parsed_db.questions if q.id == chart.question_id), None
            )
        if question is not None and db_path and parsed_db and hasattr(parsed_db, "data_blocks"):
            data_blocks = parsed_db.data_blocks if isinstance(parsed_db.data_blocks, dict) else {}
            try:
                from .data_extractor import extract_all_breakdowns_data, extract_chart_data
                primary_bd = chart.breakdown_ids[0] if chart.breakdown_ids else "general"
                bd_obj_primary = next(
                    (b for b in (getattr(parsed_db, "breakdowns", []) or []) if b.id == primary_bd),
                    None,
                )
                chart_data = extract_chart_data(
                    db_path, question, primary_bd, data_blocks,
                    allowed_categories=(bd_obj_primary.categories if bd_obj_primary else None),
                )
                bd_list = getattr(parsed_db, "breakdowns", []) or []
                all_bds = extract_all_breakdowns_data(db_path, question, bd_list, data_blocks)
            except Exception as exc:
                log.debug("build_slide_config: could not extract chart data for %r: %s", chart.id, exc)
        enriched_charts.append(
            EnrichedChart(
                id=chart.id,
                question_id=chart.question_id,
                breakdown_ids=list(chart.breakdown_ids),
                chart_type=chart.chart_type,
                colors=getattr(chart, "colors", []),
                question=question,
                data=chart_data,
                all_breakdowns_data=all_bds,
                show_legend=getattr(chart, "show_legend", False),
                grid_cols=getattr(chart, "grid_cols", None),
                title=getattr(chart, "title", None),
                cat_titles=getattr(chart, "cat_titles", None),
            )
        )

    return SlideConfig(
        charts=enriched_charts,
        analyses=analyses,
        n_charts=len(enriched_charts),
        n_analyses=len(analyses),
        parsed_db=parsed_db,
        layout=getattr(slide_def, "layout", None),
    )
