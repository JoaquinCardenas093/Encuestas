"""Pattern renderer — orchestrates element rendering for a matched pattern.

Responsibilities:
  1. Resolve pattern inheritance (extends → merge-deep parent implementation)
  2. Sort elements in topological order (anchored elements after their anchors)
  3. For each element, resolve position (relative → absolute EMU) and dispatch
     to the correct element_renderer
  4. Track resolved_anchors dict so later anchored elements can reference prior ones
"""
from __future__ import annotations

import copy
import importlib
import logging
from typing import Any

from .element_renderers.render_context import RenderContext

log = logging.getLogger(__name__)

# Registry of element kind → renderer module path
_KIND_RENDERERS: dict[str, str] = {
    "chart": "aurum_encuestas.element_renderers.chart_renderer",
    "text": "aurum_encuestas.element_renderers.text_renderer",
    "shape": "aurum_encuestas.element_renderers.shape_renderer",
    "image": "aurum_encuestas.element_renderers.image_renderer",
    "table": "aurum_encuestas.element_renderers.table_renderer",
}


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────

def render_pattern(
    pattern: Any,
    slide: Any,
    ctx: RenderContext,
    style_guide: Any,
    all_patterns: list[Any],
) -> None:
    """Render all elements in pattern.implementation onto slide.

    Args:
        pattern: matched Pattern pydantic model (has .extends, .implementation.elements)
        slide: python-pptx Slide object (mutated in-place)
        ctx: RenderContext with resolved colors, typography, free_area, slide_config
        style_guide: active StyleGuide (for inheritance lookups)
        all_patterns: full list of patterns (needed to resolve .extends chain)
    """
    implementation = _resolve_inheritance(pattern, all_patterns)
    elements = implementation.get("elements", [])
    ordered_elements = _topological_sort(elements)

    # Fan out elements marked with "_repeat": "per_chart" — one copy per
    # chart in slide_config.charts. Used by n_charts_grid pattern.
    charts_list = getattr(ctx.slide_config, "charts", []) or []
    expanded: list[dict] = []
    for el in ordered_elements:
        if el.get("_repeat") == "per_chart" and charts_list:
            n = len(charts_list)
            cols = 3 if n <= 3 else (3 if n <= 6 else 3)  # always 3 cols
            rows = (n + cols - 1) // cols
            base_pos = el.get("position", {})
            base_x = base_pos.get("x_rel", 0.03)
            base_y = base_pos.get("y_rel", 0.14)
            base_h = base_pos.get("h_rel", 0.74)
            gap_x = 0.02
            gap_y = 0.04
            # Recompute w/h so the row fits inside free_area horizontally / vertically.
            # x_rel is relative to free_area (0.0 = left edge, 1.0 = right edge), so
            # 2*base_x accounts for equal left and right margins.
            cell_w = (1.0 - 2 * base_x - gap_x * (cols - 1)) / cols
            cell_h = (base_h - gap_y * (rows - 1)) / rows
            for i in range(n):
                r, c = divmod(i, cols)
                new_el = copy.deepcopy(el)
                new_el.pop("_repeat", None)
                new_el["id"] = f"{el['id']}_{i}"
                new_el["position"] = {
                    "x_rel": base_x + c * (cell_w + gap_x),
                    "y_rel": base_y + r * (cell_h + gap_y),
                    "w_rel": cell_w,
                    "h_rel": cell_h,
                }
                ds = dict(new_el.get("data_source", {}))
                ds["chart_ref_index"] = i
                new_el["data_source"] = ds
                expanded.append(new_el)
        else:
            expanded.append(el)
    ordered_elements = expanded

    # Ensure resolved_anchors is mutable on ctx
    if not hasattr(ctx, "resolved_anchors") or ctx.resolved_anchors is None:
        ctx.resolved_anchors = {}

    for element in ordered_elements:
        kind = element.get("kind")
        renderer_module_path = _KIND_RENDERERS.get(kind)
        if renderer_module_path is None:
            log.warning(
                "render_pattern: unknown element kind %r — skipping element %r",
                kind,
                element.get("id"),
            )
            continue

        try:
            renderer_mod = importlib.import_module(renderer_module_path)
            renderer_mod.render(slide, element, ctx)

            # Record resolved position for anchor resolution by later elements
            el_id = element.get("id")
            if el_id:
                x, y, cx, cy = resolve_position(
                    element.get("position", {}), ctx.free_area, ctx.resolved_anchors
                )
                ctx.resolved_anchors[el_id] = {"x": x, "y": y, "cx": cx, "cy": cy}
        except Exception as exc:
            log.error(
                "render_pattern: error rendering element %r (kind=%r): %s",
                element.get("id"),
                kind,
                exc,
                exc_info=True,
            )


def resolve_position(
    position: dict,
    free_area: dict,
    resolved_anchors: dict[str, dict],
) -> tuple[int, int, int, int]:
    """Convert position dict to absolute (x, y, cx, cy) in EMU.

    Two modes:
    1. Relative: x_rel/y_rel/w_rel/h_rel — fractions of free_area
    2. Anchored: anchor (element id) + relative (direction) + offset_rel + w_rel/h_rel

    Returns: (x_emu, y_emu, cx_emu, cy_emu) all as int.
    """
    fa_x = free_area.get("x", 0)
    fa_y = free_area.get("y", 0)
    fa_cx = free_area.get("cx", 1)
    fa_cy = free_area.get("cy", 1)

    anchor_id = position.get("anchor")
    if anchor_id:
        anchor_rect = resolved_anchors.get(anchor_id, {})
        base_x = anchor_rect.get("x", fa_x)
        base_y = anchor_rect.get("y", fa_y)
        base_cx = anchor_rect.get("cx", 0)
        base_cy = anchor_rect.get("cy", 0)

        relative = position.get("relative", "right_of")
        offset_rel = position.get("offset_rel", 0.0)
        w_rel = position.get("w_rel", 0.3)
        h_rel = position.get("h_rel", 0.5)
        w = int(w_rel * fa_cx)
        h = int(h_rel * fa_cy)

        # offset uses fa_cx for horizontal directions, fa_cy for vertical
        if relative in ("right_of", "left_of"):
            offset = int(offset_rel * fa_cx)
        else:
            offset = int(offset_rel * fa_cy)

        if relative == "right_of":
            x, y = base_x + base_cx + offset, base_y
        elif relative == "below":
            x, y = base_x, base_y + base_cy + offset
        elif relative == "above":
            x, y = base_x, base_y - h - offset
        elif relative == "left_of":
            x, y = base_x - w - offset, base_y
        else:
            x, y = base_x, base_y
        return x, y, w, h

    x_rel = position.get("x_rel", 0.0)
    y_rel = position.get("y_rel", 0.0)
    w_rel = position.get("w_rel", 0.5)
    h_rel = position.get("h_rel", 0.5)
    x = fa_x + int(x_rel * fa_cx)
    y = fa_y + int(y_rel * fa_cy)
    w = int(w_rel * fa_cx)
    h = int(h_rel * fa_cy)
    return x, y, w, h


def resolve_data_source(data_source: dict, slide_config: Any) -> dict | None:
    """Resolve a data_source dict to concrete chart data reference.

    Returns dict with keys:
      - "chart": the source chart object from slide_config.charts
      - "value_field": "pct" or "count"
      - "breakdown_keys": list of breakdown label strings to include
    Returns None if chart_ref_index is out of range.
    """
    chart_ref_index = data_source.get("chart_ref_index", 0)
    charts_list = getattr(slide_config, "charts", []) or []
    if chart_ref_index >= len(charts_list):
        log.warning(
            "resolve_data_source: chart_ref_index %d out of range (have %d)",
            chart_ref_index,
            len(charts_list),
        )
        return None

    source_chart = charts_list[chart_ref_index]
    data = getattr(source_chart, "data", {}) or {}
    all_breakdown_keys = list(data.keys())

    breakdown_groups = data_source.get("breakdown_groups", "all")
    if breakdown_groups == "all":
        breakdown_keys = all_breakdown_keys
    elif breakdown_groups == "all_except_general":
        breakdown_keys = [k for k in all_breakdown_keys if k.lower() != "general"]
    elif isinstance(breakdown_groups, list):
        breakdown_keys = breakdown_groups
    else:
        breakdown_keys = all_breakdown_keys

    return {
        "chart": source_chart,
        "value_field": data_source.get("value_field", "pct"),
        "breakdown_keys": breakdown_keys,
    }


def merge_implementations(parent_impl: dict, child_impl: dict) -> dict:
    """Merge child implementation into parent with deep merge on elements by id.

    Rules:
    - Elements in child with same id as parent element → deep merge (child wins per key)
    - Elements in child with new id → appended to element list
    - Elements in parent not overridden by child → preserved as-is
    """
    child_elements = child_impl.get("elements", []) or []

    merged_elements: list[dict] = []
    seen_ids: set[str] = set()

    # Merge parent elements, applying child overrides where id matches
    for parent_el in parent_impl.get("elements", []):
        el_id = parent_el.get("id")
        if el_id is None:
            merged_elements.append(copy.deepcopy(parent_el))
            continue

        child_override = next((e for e in child_elements if e.get("id") == el_id), None)
        if child_override:
            # Deep merge: start from parent, override with child keys recursively
            merged_el = _deep_merge(copy.deepcopy(parent_el), child_override)
        else:
            merged_el = copy.deepcopy(parent_el)
        merged_elements.append(merged_el)
        seen_ids.add(el_id)

    # Append child-only elements (new ids not in parent)
    for child_el in child_elements:
        if child_el.get("id") not in seen_ids:
            merged_elements.append(copy.deepcopy(child_el))

    return {"elements": merged_elements}


# ────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ────────────────────────────────────────────────────────────────────────────

def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. override wins on conflicts."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def _resolve_inheritance(pattern: Any, all_patterns: list[Any]) -> dict:
    """Walk the extends chain and merge implementations bottom-up.

    Returns merged implementation dict with a top-level "elements" list.
    """
    chain = _collect_extends_chain(pattern, all_patterns)
    if not chain:
        elements = getattr(pattern.implementation, "elements", []) or []
        return {"elements": [_el_to_dict(e) for e in elements]}

    # chain[0] = root ancestor, chain[-1] = direct parent (leaf is pattern itself)
    merged = {
        "elements": [_el_to_dict(e) for e in (getattr(chain[0].implementation, "elements", []) or [])]
    }
    for ancestor in chain[1:]:
        child_impl = {
            "elements": [_el_to_dict(e) for e in (getattr(ancestor.implementation, "elements", []) or [])]
        }
        merged = merge_implementations(merged, child_impl)

    # Final: merge the pattern itself
    leaf_impl = {
        "elements": [_el_to_dict(e) for e in (getattr(pattern.implementation, "elements", []) or [])]
    }
    merged = merge_implementations(merged, leaf_impl)
    return merged


def _collect_extends_chain(pattern: Any, all_patterns: list[Any]) -> list[Any]:
    """Return list of ancestor patterns from root to direct parent (not including pattern itself)."""
    chain: list[Any] = []
    visited: set[str] = set()
    current_extends = getattr(pattern, "extends", None)
    while current_extends:
        if current_extends in visited:
            log.warning(
                "pattern inheritance cycle detected at %r — breaking", current_extends
            )
            break
        visited.add(current_extends)
        parent = next(
            (p for p in all_patterns if getattr(p, "id", None) == current_extends), None
        )
        if parent is None:
            log.warning(
                "extends ref %r not found in all_patterns — breaking chain", current_extends
            )
            break
        chain.insert(0, parent)
        current_extends = getattr(parent, "extends", None)
    return chain


def _el_to_dict(el: Any) -> dict:
    """Convert element to dict (handles both dict and pydantic model).

    Uses by_alias=True so that fields with aliases (e.g. _repeat) are exported
    under their alias keys, preserving round-trip compatibility with the raw
    BUILTIN_STYLE_GUIDE dict literals.
    """
    if isinstance(el, dict):
        return el
    if hasattr(el, "model_dump"):
        return el.model_dump(by_alias=True)
    return dict(el)


def _topological_sort(elements: list[dict]) -> list[dict]:
    """Sort elements so that anchored elements come after the elements they anchor to.

    Uses Kahn's algorithm on the anchor dependency graph.
    Elements without anchor dependencies retain their original relative order.
    """
    id_to_el = {e["id"]: e for e in elements if "id" in e}
    no_id_els = [e for e in elements if "id" not in e]

    # in_degree[el_id] = number of unsatisfied dependencies
    in_degree: dict[str, int] = {el_id: 0 for el_id in id_to_el}
    # dependents[el_id] = list of ids that come after el_id
    dependents: dict[str, list[str]] = {el_id: [] for el_id in id_to_el}

    for el_id, el in id_to_el.items():
        position = el.get("position", {})
        anchor = position.get("anchor")
        if anchor and anchor in id_to_el:
            in_degree[el_id] += 1
            dependents[anchor].append(el_id)

    # Kahn's BFS — process zero-in-degree nodes first
    queue = [el_id for el_id, deg in in_degree.items() if deg == 0]
    sorted_ids: list[str] = []
    while queue:
        current = queue.pop(0)
        sorted_ids.append(current)
        for dep in dependents.get(current, []):
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    # If cycle detected (remaining in_degree > 0), append them anyway with a warning
    remaining = [el_id for el_id, deg in in_degree.items() if deg > 0]
    if remaining:
        log.warning(
            "topological_sort: cycle or unresolved anchors for %r — appending as-is",
            remaining,
        )
        sorted_ids.extend(remaining)

    result = [id_to_el[el_id] for el_id in sorted_ids if el_id in id_to_el]
    result.extend(no_id_els)  # elements without ids go last
    return result
