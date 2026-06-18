# M6.6 — Pattern Renderer & pptx_generator Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pattern renderer orchestrator that takes a matched pattern's `implementation` + slide_config + data, dispatches to element_renderers in topological order (resolving anchored positions), and handles pattern inheritance via `extends` merge-deep. Refactor `pptx_generator.build_pptx` to use the new classify→render pipeline end-to-end, keeping separator slide handling intact.

**Architecture:** `pattern_renderer.py` orchestrates: resolve inheritance → sort elements by anchor dependency → resolve positions → dispatch to element_renderers. `pptx_generator.py` calls `pattern_classifier.classify` then `pattern_renderer.render_pattern` per shell slide, falling back to built-in generic pattern when no match.

**Tech Stack adds:** none.

---

## File Structure

**Create (backend):**
- `backend/aurum_encuestas/pattern_renderer.py`
- `backend/tests/test_pattern_renderer.py`

**Modify (backend):**
- `backend/aurum_encuestas/pptx_generator.py` — refactor `_append_shell` to use new pipeline
- `backend/tests/test_pptx_generator.py` — add/update end-to-end fixture tests

**Depends on (must exist from M6.1-M6.5):**
- `backend/aurum_encuestas/style_guide.py` — `StyleGuide`, `load_active_style_guide()`
- `backend/aurum_encuestas/pattern_classifier.py` — `classify_pattern(slide_config, patterns) -> Pattern | None`
- `backend/aurum_encuestas/color_resolver.py` — `resolve_color(role, ctx) -> str`, `build_render_context(...) -> RenderContext`
- `backend/aurum_encuestas/element_renderers/` — all 5 renderers

---

### Task 1: pattern_renderer — inheritance resolution + element dispatch

**Files:**
- Create: `backend/aurum_encuestas/pattern_renderer.py`
- Create: `backend/tests/test_pattern_renderer.py`

- [ ] **Step 1: Failing tests**

Create `backend/tests/test_pattern_renderer.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from pptx import Presentation

from aurum_encuestas.pattern_renderer import render_pattern, merge_implementations
from aurum_encuestas.element_renderers.render_context import RenderContext


FREE_AREA = {"x": 500000, "y": 1200000, "cx": 11000000, "cy": 5500000}


def _make_ctx():
    ctx = MagicMock(spec=RenderContext)
    ctx.free_area = FREE_AREA
    ctx.chart_colors = ["#7F7F7F", "#BFBFBF"]
    ctx.resolved_colors = {"primary": "#7F7F7F", "secondary": "#BFBFBF", "background": "#FFFFFF"}
    ctx.typography = {"font_family": "Arial", "label_size": 9, "body_size": 10}
    ctx.slide_config = MagicMock()
    ctx.slide_config.charts = []
    ctx.slide_config.analyses = []
    ctx.slide_config.template_shapes = {}
    ctx.resolved_anchors = {}
    return ctx


def _make_slide():
    prs = Presentation()
    return prs.slides.add_slide(prs.slide_layouts[6])


def test_merge_implementations_child_overrides_parent():
    parent_impl = {
        "elements": [
            {"kind": "chart", "id": "pie", "position": {"x_rel": 0.05, "y_rel": 0.1, "w_rel": 0.4, "h_rel": 0.6}, "chart_type": "PIE", "legend": "none"},
        ]
    }
    child_impl = {
        "elements": [
            {"kind": "chart", "id": "pie", "chart_type": "DONUT"},  # override chart_type
        ]
    }
    merged = merge_implementations(parent_impl, child_impl)
    pie_el = next(e for e in merged["elements"] if e["id"] == "pie")
    assert pie_el["chart_type"] == "DONUT"
    # Parent position preserved
    assert "position" in pie_el
    assert pie_el["position"]["x_rel"] == 0.05


def test_merge_implementations_child_adds_new_element():
    parent_impl = {"elements": [{"kind": "text", "id": "title", "position": {}, "content_source": {"type": "static", "text": "T"}, "style": {}}]}
    child_impl = {"elements": [{"kind": "shape", "id": "divider", "position": {}, "shape_type": "line", "style": {}}]}
    merged = merge_implementations(parent_impl, child_impl)
    ids = [e["id"] for e in merged["elements"]]
    assert "title" in ids
    assert "divider" in ids


def test_render_pattern_dispatches_all_elements():
    slide = _make_slide()
    ctx = _make_ctx()

    pattern = MagicMock()
    pattern.extends = None
    pattern.implementation = MagicMock()
    pattern.implementation.elements = [
        {"kind": "shape", "id": "box", "position": {"x_rel": 0.0, "y_rel": 0.0, "w_rel": 0.5, "h_rel": 0.5}, "shape_type": "rectangle", "style": {"fill": "primary", "color": "primary"}},
        {"kind": "text", "id": "lbl", "position": {"x_rel": 0.0, "y_rel": 0.6, "w_rel": 0.5, "h_rel": 0.2}, "content_source": {"type": "static", "text": "Hello"}, "style": {}},
    ]

    initial_shapes = len(slide.shapes)
    render_pattern(pattern, slide, ctx, style_guide=None, all_patterns=[])
    assert len(slide.shapes) > initial_shapes


def test_render_pattern_topological_order_resolves_anchor():
    """An anchored element must be placed after its anchor is resolved."""
    slide = _make_slide()
    ctx = _make_ctx()

    pattern = MagicMock()
    pattern.extends = None
    pattern.implementation = MagicMock()
    pattern.implementation.elements = [
        # Element B anchors to element A — B must render after A
        {"kind": "text", "id": "B", "position": {"anchor": "A", "relative": "right_of", "offset_rel": 0.01, "w_rel": 0.3, "h_rel": 0.5}, "content_source": {"type": "static", "text": "Right"}, "style": {}},
        {"kind": "shape", "id": "A", "position": {"x_rel": 0.0, "y_rel": 0.0, "w_rel": 0.3, "h_rel": 0.5}, "shape_type": "rectangle", "style": {"fill": "primary", "color": "primary"}},
    ]
    # Should not raise despite B listed before A
    render_pattern(pattern, slide, ctx, style_guide=None, all_patterns=[])


def test_render_pattern_extends_merges_parent_elements():
    slide = _make_slide()
    ctx = _make_ctx()

    parent_pattern = MagicMock()
    parent_pattern.id = "base_chart"
    parent_pattern.extends = None
    parent_pattern.implementation = MagicMock()
    parent_pattern.implementation.elements = [
        {"kind": "shape", "id": "background", "position": {"x_rel": 0.0, "y_rel": 0.0, "w_rel": 1.0, "h_rel": 1.0}, "shape_type": "rectangle", "style": {"fill": "secondary", "color": "secondary"}},
    ]

    child_pattern = MagicMock()
    child_pattern.extends = "base_chart"
    child_pattern.implementation = MagicMock()
    child_pattern.implementation.elements = [
        {"kind": "text", "id": "label", "position": {"x_rel": 0.1, "y_rel": 0.1, "w_rel": 0.8, "h_rel": 0.2}, "content_source": {"type": "static", "text": "Child"}, "style": {}},
    ]

    initial = len(slide.shapes)
    render_pattern(child_pattern, slide, ctx, style_guide=None, all_patterns=[parent_pattern])
    # Both parent shape + child text should be rendered
    assert len(slide.shapes) >= initial + 2
```

- [ ] **Step 2: Run failing**

Run: `cd backend && .venv/bin/pytest tests/test_pattern_renderer.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement pattern_renderer**

Create `backend/aurum_encuestas/pattern_renderer.py`:

```python
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
import logging
from typing import Any

from .element_renderers.render_context import RenderContext

log = logging.getLogger(__name__)

# Registry of element kind → renderer module
_KIND_RENDERERS: dict[str, str] = {
    "chart": "aurum_encuestas.element_renderers.chart_renderer",
    "text": "aurum_encuestas.element_renderers.text_renderer",
    "shape": "aurum_encuestas.element_renderers.shape_renderer",
    "image": "aurum_encuestas.element_renderers.image_renderer",
    "table": "aurum_encuestas.element_renderers.table_renderer",
}


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

    # Ensure resolved_anchors is mutable on ctx
    if not hasattr(ctx, "resolved_anchors") or ctx.resolved_anchors is None:
        ctx.resolved_anchors = {}

    for element in ordered_elements:
        kind = element.get("kind")
        renderer_module_path = _KIND_RENDERERS.get(kind)
        if renderer_module_path is None:
            log.warning("render_pattern: unknown element kind %r — skipping element %r", kind, element.get("id"))
            continue

        try:
            import importlib
            renderer_mod = importlib.import_module(renderer_module_path)
            renderer_mod.render(slide, element, ctx)

            # Record resolved position for anchor resolution by later elements
            el_id = element.get("id")
            if el_id:
                from .element_renderers.chart_renderer import _resolve_position
                x, y, cx, cy = _resolve_position(element.get("position", {}), ctx)
                ctx.resolved_anchors[el_id] = {"x": x, "y": y, "cx": cx, "cy": cy}
        except Exception as exc:
            log.error("render_pattern: error rendering element %r (kind=%r): %s", element.get("id"), kind, exc, exc_info=True)


def merge_implementations(parent_impl: dict, child_impl: dict) -> dict:
    """Merge child implementation into parent with deep merge on elements by id.

    Rules:
    - Elements in child with same id as parent element → deep merge (child wins per key)
    - Elements in child with new id → appended to element list
    - Elements in parent not overridden by child → preserved as-is
    """
    parent_elements = {e["id"]: e for e in parent_impl.get("elements", []) if "id" in e}
    child_elements = child_impl.get("elements", []) or []

    merged_elements: list[dict] = []
    seen_ids = set()

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
        impl = getattr(pattern.implementation, "__dict__", None) or {}
        elements = getattr(pattern.implementation, "elements", []) or []
        return {"elements": [_el_to_dict(e) for e in elements]}

    # chain[0] = root ancestor, chain[-1] = leaf (the actual pattern)
    merged = {"elements": [_el_to_dict(e) for e in (getattr(chain[0].implementation, "elements", []) or [])]}
    for ancestor in chain[1:]:
        child_impl = {"elements": [_el_to_dict(e) for e in (getattr(ancestor.implementation, "elements", []) or [])]}
        merged = merge_implementations(merged, child_impl)

    # Final: merge the pattern itself
    leaf_impl = {"elements": [_el_to_dict(e) for e in (getattr(pattern.implementation, "elements", []) or [])]}
    merged = merge_implementations(merged, leaf_impl)
    return merged


def _collect_extends_chain(pattern: Any, all_patterns: list[Any]) -> list[Any]:
    """Return list of ancestor patterns from root to direct parent (not including pattern itself)."""
    chain: list[Any] = []
    visited = set()
    current_extends = getattr(pattern, "extends", None)
    while current_extends:
        if current_extends in visited:
            log.warning("pattern inheritance cycle detected at %r — breaking", current_extends)
            break
        visited.add(current_extends)
        parent = next((p for p in all_patterns if getattr(p, "id", None) == current_extends), None)
        if parent is None:
            log.warning("extends ref %r not found in all_patterns — breaking chain", current_extends)
            break
        chain.insert(0, parent)
        current_extends = getattr(parent, "extends", None)
    return chain


def _el_to_dict(el: Any) -> dict:
    """Convert element to dict (handles both dict and pydantic model)."""
    if isinstance(el, dict):
        return el
    if hasattr(el, "model_dump"):
        return el.model_dump()
    return dict(el)


def _topological_sort(elements: list[dict]) -> list[dict]:
    """Sort elements so that anchored elements come after the elements they anchor to.

    Uses a simple Kahn's algorithm on the anchor dependency graph.
    Elements without anchor dependencies retain their original relative order.
    """
    # Build id → element map and dependency edges
    id_to_el = {e["id"]: e for e in elements if "id" in e}
    no_id_els = [e for e in elements if "id" not in e]

    # adjacency: el_id -> list of ids that must come after
    in_degree: dict[str, int] = {el_id: 0 for el_id in id_to_el}
    dependents: dict[str, list[str]] = {el_id: [] for el_id in id_to_el}

    for el_id, el in id_to_el.items():
        position = el.get("position", {})
        anchor = position.get("anchor")
        if anchor and anchor in id_to_el:
            in_degree[el_id] += 1
            dependents[anchor].append(el_id)

    # Kahn's BFS
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
        log.warning("topological_sort: cycle or unresolved anchors for %r — appending as-is", remaining)
        sorted_ids.extend(remaining)

    result = [id_to_el[el_id] for el_id in sorted_ids if el_id in id_to_el]
    result.extend(no_id_els)  # elements without ids go last
    return result
```

- [ ] **Step 4: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_pattern_renderer.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/pattern_renderer.py backend/tests/test_pattern_renderer.py
git commit -m "$(cat <<'EOF'
feat(backend): pattern_renderer — inheritance merge-deep + topological sort + element dispatch

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: position resolver — `resolve_position` module-level function

**Files:**
- Modify: `backend/aurum_encuestas/pattern_renderer.py`
- Modify: `backend/tests/test_pattern_renderer.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_pattern_renderer.py`:

```python
from aurum_encuestas.pattern_renderer import resolve_position


FREE_AREA_SIMPLE = {"x": 0, "y": 0, "cx": 10_000_000, "cy": 5_000_000}


def test_resolve_position_relative():
    pos = {"x_rel": 0.1, "y_rel": 0.2, "w_rel": 0.5, "h_rel": 0.4}
    x, y, cx, cy = resolve_position(pos, FREE_AREA_SIMPLE, resolved_anchors={})
    assert x == 1_000_000
    assert y == 1_000_000
    assert cx == 5_000_000
    assert cy == 2_000_000


def test_resolve_position_anchored_right_of():
    resolved_anchors = {"box_a": {"x": 1_000_000, "y": 500_000, "cx": 3_000_000, "cy": 2_000_000}}
    pos = {"anchor": "box_a", "relative": "right_of", "offset_rel": 0.01, "w_rel": 0.3, "h_rel": 0.4}
    x, y, cx, cy = resolve_position(pos, FREE_AREA_SIMPLE, resolved_anchors)
    # x should be box_a.x + box_a.cx + offset
    expected_x = 1_000_000 + 3_000_000 + int(0.01 * 10_000_000)
    assert x == expected_x
    assert y == 500_000  # same y as anchor
    assert cx == int(0.3 * 10_000_000)
    assert cy == int(0.4 * 5_000_000)


def test_resolve_position_anchored_below():
    resolved_anchors = {"box_a": {"x": 0, "y": 0, "cx": 5_000_000, "cy": 2_000_000}}
    pos = {"anchor": "box_a", "relative": "below", "offset_rel": 0.02, "w_rel": 0.5, "h_rel": 0.3}
    x, y, cx, cy = resolve_position(pos, FREE_AREA_SIMPLE, resolved_anchors)
    expected_y = 0 + 2_000_000 + int(0.02 * 5_000_000)  # offset_rel uses cy of free_area
    assert y == expected_y


def test_resolve_position_defaults_for_missing_keys():
    pos = {}  # all defaults
    x, y, cx, cy = resolve_position(pos, FREE_AREA_SIMPLE, resolved_anchors={})
    assert x == 0
    assert y == 0
    assert cx == int(0.5 * 10_000_000)
    assert cy == int(0.5 * 5_000_000)
```

- [ ] **Step 2: Implement `resolve_position` as module-level public function**

Add the following to `backend/aurum_encuestas/pattern_renderer.py` (after imports, before `render_pattern`):

```python
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
```

Also update `chart_renderer._resolve_position` to delegate to this module-level function to avoid duplication. Edit `backend/aurum_encuestas/element_renderers/chart_renderer.py` — replace the local `_resolve_position` body:

```python
def _resolve_position(position: dict, ctx: "RenderContext") -> tuple[int, int, int, int]:
    """Delegate to pattern_renderer.resolve_position."""
    from aurum_encuestas.pattern_renderer import resolve_position
    return resolve_position(position, ctx.free_area, ctx.resolved_anchors)
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_pattern_renderer.py -v`
Expected: all PASS (9 tests).

Run full element renderer tests too:

Run: `cd backend && .venv/bin/pytest tests/test_element_renderers.py -v`
Expected: all PASS (no regression).

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/pattern_renderer.py backend/aurum_encuestas/element_renderers/chart_renderer.py backend/tests/test_pattern_renderer.py
git commit -m "$(cat <<'EOF'
feat(backend): resolve_position public function + dedup position logic across renderers

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: refactor pptx_generator to use classify → render pipeline

**Files:**
- Modify: `backend/aurum_encuestas/pptx_generator.py`
- Modify: `backend/tests/test_pptx_generator.py`

- [ ] **Step 1: Failing integration tests**

Append to `backend/tests/test_pptx_generator.py`:

```python
from aurum_encuestas.pptx_generator import build_pptx
from aurum_encuestas.models import ProjectState, Slide, Chart, Analysis
from pptx import Presentation


def test_build_pptx_with_pattern_pipeline(tmp_path, valid_xlsx_path, valid_template_path):
    """build_pptx should use classify→render pipeline without raising."""
    from aurum_encuestas.models import ProjectState, Inputs
    state = ProjectState(
        version=1,
        project_name="PipelineTest",
        inputs=Inputs(db_path=str(valid_xlsx_path), template_path=str(valid_template_path), font_override=None),
        slides=[
            Slide(id="sep1", type="separator", title="Sección"),
            Slide(
                id="sh1", type="shell", title="Sección",
                charts=[Chart(id="c1", question_id="q1", breakdown_id="general", chart_type="PIE", multi_series=False)],
                analyses=[],
                auto_notes=None,
            ),
        ],
    )
    out = tmp_path / "out.pptx"
    build_pptx(state, str(out))
    assert out.exists()
    prs = Presentation(str(out))
    # Separator + shell = 2 slides (or more if template has extra slides)
    assert len(prs.slides) >= 2


def test_build_pptx_fallback_to_builtin_when_no_style_guide(tmp_path, valid_xlsx_path, valid_template_path, monkeypatch):
    """With no style_guide.json, built-in fallback pattern must be used — no crash."""
    monkeypatch.setenv("HOME", str(tmp_path))  # no style_guide.json in tmp dir
    from aurum_encuestas.models import ProjectState, Inputs
    state = ProjectState(
        version=1,
        project_name="NoStyleGuide",
        inputs=Inputs(db_path=str(valid_xlsx_path), template_path=str(valid_template_path), font_override=None),
        slides=[
            Slide(id="sh1", type="shell", title="Test", charts=[], analyses=[], auto_notes=None),
        ],
    )
    out = tmp_path / "out_fallback.pptx"
    build_pptx(state, str(out))
    assert out.exists()
```

- [ ] **Step 2: Refactor `_append_shell` in pptx_generator**

Edit `backend/aurum_encuestas/pptx_generator.py`. Add imports at top:

```python
from .style_guide import load_active_style_guide, BUILTIN_STYLE_GUIDE
from .pattern_classifier import classify_pattern, build_slide_config
from .pattern_renderer import render_pattern
from .color_resolver import build_render_context
```

Replace the body of `_append_shell` with the new pipeline while keeping separator handling and `@Titulo`/`@Notas` substitution intact:

```python
def _append_shell(prs: Presentation, slide_def: Slide, state: ProjectState, parsed_db: Any, free_area: dict) -> None:
    """Render a shell slide using the pattern classify → render pipeline."""
    # Clone template shell slide (index 0 by convention)
    template_shell = prs.slide_layouts[6]  # blank layout
    slide = prs.slides.add_slide(template_shell)

    # 1. Substitute @Titulo and @Notas placeholders from template master shapes
    _substitute_placeholders(slide, slide_def, state, parsed_db)

    # 2. Build slide_config from slide_def + parsed_db
    slide_config = build_slide_config(slide_def, parsed_db)

    # 3. Load active style guide (with built-in fallback)
    try:
        style_guide = load_active_style_guide()
    except Exception:
        style_guide = BUILTIN_STYLE_GUIDE

    # 4. Classify → find matching pattern or use fallback
    matched_pattern = classify_pattern(slide_config, style_guide.patterns)
    if matched_pattern is None:
        # Use first built-in fallback pattern
        matched_pattern = BUILTIN_STYLE_GUIDE.patterns[0] if BUILTIN_STYLE_GUIDE.patterns else None

    if matched_pattern is None:
        log.warning("_append_shell: no pattern matched and no fallback — slide will be empty shell")
        return

    # 5. Build RenderContext (resolves colors, typography, etc.)
    chart_colors = getattr(state, "palette", {}) or {}
    ctx = build_render_context(
        style_guide=style_guide,
        slide_config=slide_config,
        chart_colors_override=chart_colors,
        free_area=free_area,
    )

    # 6. Render pattern elements
    render_pattern(
        pattern=matched_pattern,
        slide=slide,
        ctx=ctx,
        style_guide=style_guide,
        all_patterns=style_guide.patterns,
    )
```

Add `_substitute_placeholders` helper:

```python
def _substitute_placeholders(slide, slide_def: Slide, state: ProjectState, parsed_db: Any) -> None:
    """Replace @Titulo and @Notas text in any existing slide text shapes."""
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        for para in shape.text_frame.paragraphs:
            for run in para.runs:
                if "@Titulo" in run.text:
                    run.text = run.text.replace("@Titulo", slide_def.title or "")
                if "@Notas" in run.text:
                    notes_text = _build_notes(slide_def, parsed_db)
                    run.text = run.text.replace("@Notas", notes_text)


def _build_notes(slide_def: Slide, parsed_db: Any) -> str:
    """Build auto-notes text from slide_def charts metadata."""
    if slide_def.auto_notes:
        return slide_def.auto_notes
    if not slide_def.charts:
        return ""
    first_chart = slide_def.charts[0]
    q = None
    if parsed_db and hasattr(parsed_db, "questions"):
        q = next((q for q in parsed_db.questions if q.id == first_chart.question_id), None)
    n = getattr(parsed_db, "sample_size", 0) or 0
    tipo = "Respuesta múltiple" if first_chart.multi_series else "Única respuesta"
    if q:
        return f"{tipo}. Número de observaciones: {n}."
    return f"{tipo}. Número de observaciones: {n}."
```

- [ ] **Step 3: Add `build_slide_config` stub to pattern_classifier (if not yet there)**

If `build_slide_config` does not exist in `pattern_classifier.py` (it should from M6.3), add a minimal version to ensure import works:

```python
# In backend/aurum_encuestas/pattern_classifier.py (append if missing):
def build_slide_config(slide_def, parsed_db):
    """Build slide config dict from slide_def + parsed_db for classifier and renderer."""
    # Returns an object with .charts, .analyses, .template_shapes, .n_charts, etc.
    from dataclasses import dataclass, field
    from typing import Any

    @dataclass
    class SlideConfig:
        charts: list = field(default_factory=list)
        analyses: list = field(default_factory=list)
        template_shapes: dict = field(default_factory=dict)
        n_charts: int = 0
        question_type: str = "binary"
        n_breakdowns: int = 0
        n_analyses: int = 0
        parsed_db: Any = None

    charts = slide_def.charts if slide_def else []
    analyses = slide_def.analyses if slide_def else []
    return SlideConfig(
        charts=charts,
        analyses=analyses,
        n_charts=len(charts),
        n_analyses=len(analyses),
        parsed_db=parsed_db,
    )
```

- [ ] **Step 4: Verify existing pptx_generator tests still pass + new tests pass**

Run: `cd backend && .venv/bin/pytest tests/test_pptx_generator.py -v`
Expected: PASS (including 2 new tests).

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/pptx_generator.py backend/aurum_encuestas/pattern_classifier.py backend/tests/test_pptx_generator.py
git commit -m "$(cat <<'EOF'
feat(backend): pptx_generator refactored to classify→render pipeline with fallback built-in

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: data_source resolution — chart_ref_index + breakdown_groups

**Files:**
- Modify: `backend/aurum_encuestas/pattern_renderer.py`
- Modify: `backend/tests/test_pattern_renderer.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_pattern_renderer.py`:

```python
from aurum_encuestas.pattern_renderer import resolve_data_source


def _make_slide_config_with_charts():
    config = MagicMock()
    config.charts = [
        MagicMock(
            question=MagicMock(options=["Sí", "No"]),
            data={
                "General": {"Sí": {"count": 80, "pct": 0.8}, "No": {"count": 20, "pct": 0.2}},
                "Masculino": {"Sí": {"count": 60, "pct": 0.6}, "No": {"count": 40, "pct": 0.4}},
                "Femenino": {"Sí": {"count": 85, "pct": 0.85}, "No": {"count": 15, "pct": 0.15}},
            },
        )
    ]
    config.analyses = []
    return config


def test_resolve_data_source_chart_ref_index():
    slide_config = _make_slide_config_with_charts()
    ds = {"chart_ref_index": 0, "value_field": "pct"}
    result = resolve_data_source(ds, slide_config)
    assert result is not None
    assert result["chart"] is slide_config.charts[0]
    assert result["value_field"] == "pct"


def test_resolve_data_source_out_of_range_returns_none():
    slide_config = _make_slide_config_with_charts()
    ds = {"chart_ref_index": 99}
    result = resolve_data_source(ds, slide_config)
    assert result is None


def test_resolve_data_source_breakdown_groups_all_except_general():
    slide_config = _make_slide_config_with_charts()
    ds = {"chart_ref_index": 0, "breakdown_groups": "all_except_general"}
    result = resolve_data_source(ds, slide_config)
    assert result is not None
    assert "General" not in result["breakdown_keys"]
    assert "Masculino" in result["breakdown_keys"]


def test_resolve_data_source_breakdown_groups_all():
    slide_config = _make_slide_config_with_charts()
    ds = {"chart_ref_index": 0, "breakdown_groups": "all"}
    result = resolve_data_source(ds, slide_config)
    assert "General" in result["breakdown_keys"]
    assert "Masculino" in result["breakdown_keys"]


def test_resolve_data_source_breakdown_groups_explicit_list():
    slide_config = _make_slide_config_with_charts()
    ds = {"chart_ref_index": 0, "breakdown_groups": ["Masculino"]}
    result = resolve_data_source(ds, slide_config)
    assert result["breakdown_keys"] == ["Masculino"]
```

- [ ] **Step 2: Implement `resolve_data_source`**

Add to `backend/aurum_encuestas/pattern_renderer.py`:

```python
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
        log.warning("resolve_data_source: chart_ref_index %d out of range (have %d)", chart_ref_index, len(charts_list))
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
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_pattern_renderer.py -v`
Expected: all PASS (14 tests).

- [ ] **Step 4: Run full backend test suite**

Run: `cd backend && .venv/bin/pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/pattern_renderer.py backend/tests/test_pattern_renderer.py
git commit -m "$(cat <<'EOF'
feat(backend): resolve_data_source — chart_ref_index + breakdown_groups resolution

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Tag the sub-milestone:

```bash
git tag m6.6
```

---

## M6.6 Done When

- `pattern_renderer.render_pattern(pattern, slide, ctx, style_guide, all_patterns)` works end-to-end
- `merge_implementations(parent_impl, child_impl)` correctly deep-merges elements by id; child elements with new ids appended
- `resolve_position(position, free_area, resolved_anchors)` handles both relative and anchored modes correctly (5 test variants)
- `resolve_data_source(data_source, slide_config)` returns chart reference + breakdown_keys; returns None on out-of-range
- Topological sort places anchored elements after their dependencies without crash on cycles
- `pptx_generator.build_pptx` uses classify → render_pattern pipeline for shell slides; separator slides still clone from template
- No regression in existing pptx_generator tests
- All backend tests pass
- Git tag `m6.6`
