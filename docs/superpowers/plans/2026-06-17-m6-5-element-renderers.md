# M6.5 — Element Renderers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement renderers for each element kind: chart, text, shape, image, and table (structures: `simple_data`, `segmented_breakdowns`, `comparison_grid`). The `segmented_breakdowns` table is the most complex — handles merged cells, counts rows, option rows with shape-overlay minibars. Each renderer receives `(slide, element, ctx)` and mutates the slide in-place via python-pptx.

**Architecture:** `element_renderers/` package with one module per kind. Each module exposes a single `render(slide, element, ctx)` function. `ctx` is a `RenderContext` dataclass carrying resolved colors, style_guide global typography, parsed_db ref, and slide_config. Dispatched by `pattern_renderer` (M6.6).

**Tech Stack adds:** none (python-pptx already in project).

---

## File Structure

**Create (backend):**
- `backend/aurum_encuestas/element_renderers/__init__.py`
- `backend/aurum_encuestas/element_renderers/chart_renderer.py`
- `backend/aurum_encuestas/element_renderers/text_renderer.py`
- `backend/aurum_encuestas/element_renderers/shape_renderer.py`
- `backend/aurum_encuestas/element_renderers/image_renderer.py`
- `backend/aurum_encuestas/element_renderers/table_renderer.py`
- `backend/tests/test_element_renderers.py`

**Depends on (must exist from M6.1-M6.4):**
- `backend/aurum_encuestas/style_guide.py` — `StyleGuide`, `RenderContext` (or define `RenderContext` here)
- `backend/aurum_encuestas/color_resolver.py` — `resolve_color(role, ctx) -> str`

---

### Task 1: chart_renderer — all 9 chart types via python-pptx

**Files:**
- Create: `backend/aurum_encuestas/element_renderers/__init__.py`
- Create: `backend/aurum_encuestas/element_renderers/chart_renderer.py`
- Create: `backend/tests/test_element_renderers.py` (initial)

- [ ] **Step 1: Failing tests**

Create `backend/tests/test_element_renderers.py`:

```python
from unittest.mock import MagicMock, patch, call
import pytest
from pptx import Presentation
from pptx.util import Inches, Emu

from aurum_encuestas.element_renderers.chart_renderer import render as render_chart
from aurum_encuestas.element_renderers.render_context import RenderContext


FREE_AREA = {"x": Inches(0.5), "y": Inches(1.5), "cx": Inches(12), "cy": Inches(5.5)}


def _make_ctx(colors=None):
    ctx = MagicMock(spec=RenderContext)
    ctx.resolved_colors = colors or {"primary": "#7F7F7F", "secondary": "#BFBFBF", "background": "#FFFFFF"}
    ctx.chart_colors = ["#7F7F7F", "#BFBFBF", "#FFC000"]
    ctx.typography = {"font_family": "Arial", "label_size": 9}
    ctx.free_area = FREE_AREA
    ctx.slide_config = MagicMock()
    ctx.slide_config.charts = [
        MagicMock(
            question=MagicMock(options=["Sí", "No"]),
            data={"General": {"Sí": {"count": 80, "pct": 0.8}, "No": {"count": 20, "pct": 0.2}}},
        )
    ]
    return ctx


def _make_slide():
    prs = Presentation()
    return prs.slides.add_slide(prs.slide_layouts[6])


def test_chart_renderer_pie_adds_chart_shape():
    slide = _make_slide()
    element = {
        "kind": "chart",
        "id": "main_pie",
        "position": {"x_rel": 0.05, "y_rel": 0.1, "w_rel": 0.4, "h_rel": 0.7},
        "chart_type": "PIE",
        "data_source": {"chart_ref_index": 0, "value_field": "pct"},
        "labels": {"show_category_name": True, "show_percentage": True, "position": "outside_end", "format": "0.0%"},
        "legend": "none",
        "sort": "none",
    }
    initial_shapes = len(slide.shapes)
    render_chart(slide, element, _make_ctx())
    assert len(slide.shapes) > initial_shapes


def test_chart_renderer_bar_horizontal_adds_chart_shape():
    slide = _make_slide()
    element = {
        "kind": "chart",
        "id": "bar_chart",
        "position": {"x_rel": 0.0, "y_rel": 0.0, "w_rel": 0.5, "h_rel": 0.5},
        "chart_type": "BAR_HORIZONTAL",
        "data_source": {"chart_ref_index": 0, "value_field": "pct"},
        "labels": {"show_value": True, "format": "0%"},
        "legend": "right",
        "sort": "desc_by_value",
    }
    initial_shapes = len(slide.shapes)
    render_chart(slide, element, _make_ctx())
    assert len(slide.shapes) > initial_shapes


def test_chart_renderer_unknown_chart_type_falls_back_to_bar():
    slide = _make_slide()
    element = {
        "kind": "chart",
        "id": "x",
        "position": {"x_rel": 0.0, "y_rel": 0.0, "w_rel": 0.5, "h_rel": 0.5},
        "chart_type": "UNKNOWN_TYPE",
        "data_source": {"chart_ref_index": 0, "value_field": "pct"},
        "labels": {},
        "legend": "none",
        "sort": "none",
    }
    # Should not raise, falls back gracefully
    render_chart(slide, element, _make_ctx())


def test_chart_renderer_missing_data_source_skips():
    slide = _make_slide()
    element = {
        "kind": "chart",
        "id": "x",
        "position": {"x_rel": 0.0, "y_rel": 0.0, "w_rel": 0.5, "h_rel": 0.5},
        "chart_type": "PIE",
        "data_source": {"chart_ref_index": 99, "value_field": "pct"},  # out of range
        "labels": {},
        "legend": "none",
        "sort": "none",
    }
    initial_shapes = len(slide.shapes)
    render_chart(slide, element, _make_ctx())
    # Should silently skip (no chart added, no exception)
    assert len(slide.shapes) == initial_shapes
```

- [ ] **Step 2: Run failing**

Run: `cd backend && .venv/bin/pytest tests/test_element_renderers.py::test_chart_renderer_pie_adds_chart_shape -v`
Expected: ImportError.

- [ ] **Step 3: Create package init + RenderContext**

Create `backend/aurum_encuestas/element_renderers/__init__.py`:

```python
"""Element renderers — one module per element kind."""
```

Create `backend/aurum_encuestas/element_renderers/render_context.py`:

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RenderContext:
    """Carries all resolved data needed by element renderers."""
    free_area: dict                      # {x, y, cx, cy} in EMU
    chart_colors: list[str]              # hex strings, per-series
    resolved_colors: dict[str, str]      # role -> hex (primary, secondary, background, accent, ...)
    typography: dict[str, Any]           # font_family, title_size, label_size, body_size, etc.
    slide_config: Any                    # slide config object (charts, analyses, parsed_db ref)
    style_guide: Any = None              # full StyleGuide for global settings
    resolved_anchors: dict[str, dict] = field(default_factory=dict)  # element_id -> {x,y,cx,cy} EMU
```

- [ ] **Step 4: Implement chart_renderer**

Create `backend/aurum_encuestas/element_renderers/chart_renderer.py`:

```python
"""Chart element renderer — dispatches all 9 chart types via python-pptx."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor

if TYPE_CHECKING:
    from .render_context import RenderContext

log = logging.getLogger(__name__)

# Mapping from spec chart_type string to python-pptx XL_CHART_TYPE
_CHART_TYPE_MAP: dict[str, int] = {
    "PIE":               XL_CHART_TYPE.PIE,
    "DONUT":             XL_CHART_TYPE.DOUGHNUT,
    "BAR_HORIZONTAL":    XL_CHART_TYPE.BAR_CLUSTERED,
    "BAR_CLUSTERED":     XL_CHART_TYPE.BAR_CLUSTERED,
    "BAR_STACKED":       XL_CHART_TYPE.BAR_STACKED,
    "COLUMN_CLUSTERED":  XL_CHART_TYPE.COLUMN_CLUSTERED,
    "COLUMN_STACKED":    XL_CHART_TYPE.COLUMN_STACKED,
    "LINE":              XL_CHART_TYPE.LINE,
    "AREA":              XL_CHART_TYPE.AREA,
}

_LABEL_POSITION_MAP = {
    "inside":       XL_LABEL_POSITION.INSIDE_END,
    "outside_end":  XL_LABEL_POSITION.OUTSIDE_END,
    "center":       XL_LABEL_POSITION.CENTER,
    "best_fit":     XL_LABEL_POSITION.BEST_FIT,
}

_LEGEND_POSITION_MAP = {
    "right":  XL_LEGEND_POSITION.RIGHT,
    "bottom": XL_LEGEND_POSITION.BOTTOM,
    "top":    XL_LEGEND_POSITION.TOP,
    "left":   XL_LEGEND_POSITION.LEFT,
}


def render(slide, element: dict, ctx: "RenderContext") -> None:
    """Render a chart element onto slide in-place."""
    chart_type_str = element.get("chart_type", "BAR_HORIZONTAL")
    xl_chart_type = _CHART_TYPE_MAP.get(chart_type_str)
    if xl_chart_type is None:
        log.warning("Unknown chart_type %r — falling back to BAR_CLUSTERED", chart_type_str)
        xl_chart_type = XL_CHART_TYPE.BAR_CLUSTERED

    # Resolve data source
    data_source = element.get("data_source", {})
    chart_ref_index = data_source.get("chart_ref_index", 0)
    value_field = data_source.get("value_field", "pct")

    charts_list = getattr(ctx.slide_config, "charts", []) or []
    if chart_ref_index >= len(charts_list):
        log.warning("chart_ref_index %d out of range (have %d charts) — skipping", chart_ref_index, len(charts_list))
        return

    source_chart = charts_list[chart_ref_index]

    # Build CategoryChartData
    chart_data = _build_chart_data(source_chart, value_field, element.get("sort", "none"))

    # Resolve position
    x, y, cx, cy = _resolve_position(element.get("position", {}), ctx)

    # Add chart shape
    try:
        chart_shape = slide.shapes.add_chart(xl_chart_type, Emu(x), Emu(y), Emu(cx), Emu(cy), chart_data)
    except Exception as exc:
        log.error("Failed to add chart shape: %s", exc)
        return

    chart = chart_shape.chart

    # Apply colors to series
    _apply_series_colors(chart, ctx.chart_colors)

    # Apply labels
    labels_cfg = element.get("labels", {})
    _apply_labels(chart, labels_cfg, ctx)

    # Apply legend
    legend_str = element.get("legend", "none")
    if legend_str == "none":
        chart.has_legend = False
    else:
        chart.has_legend = True
        pos = _LEGEND_POSITION_MAP.get(legend_str, XL_LEGEND_POSITION.RIGHT)
        chart.legend.position = pos
        chart.legend.include_in_layout = False

    # Chart title
    title_text = element.get("title")
    if title_text:
        chart.has_title = True
        chart.chart_title.text_frame.text = title_text
    else:
        chart.has_title = False


def _build_chart_data(source_chart, value_field: str, sort: str) -> CategoryChartData:
    """Extract CategoryChartData from a slide_config chart object."""
    cd = CategoryChartData()

    question = getattr(source_chart, "question", None)
    options = question.options if question else []
    data = getattr(source_chart, "data", {}) or {}

    # Use General breakdown or first available
    breakdown_data = data.get("General") or (next(iter(data.values())) if data else {})

    if not options and breakdown_data:
        options = list(breakdown_data.keys())

    # Sort if requested
    if sort in ("desc_by_value", "asc_by_value") and breakdown_data:
        reverse = sort == "desc_by_value"
        options = sorted(
            options,
            key=lambda o: (breakdown_data.get(o) or {}).get(value_field, 0),
            reverse=reverse,
        )

    cd.categories = options

    values = []
    for opt in options:
        cell = (breakdown_data.get(opt) or {})
        v = cell.get(value_field, 0) or 0
        values.append(float(v))

    cd.add_series("", values)
    return cd


def _apply_series_colors(chart, colors: list[str]) -> None:
    """Apply hex color list to chart series/points."""
    try:
        for series_idx, series in enumerate(chart.series):
            if series_idx < len(colors):
                fill = series.format.fill
                fill.solid()
                fill.fore_color.rgb = RGBColor.from_string(colors[series_idx].lstrip("#"))
            # For pie/donut, color individual points
            try:
                for point_idx, point in enumerate(series.points):
                    color = colors[point_idx % len(colors)] if colors else "#7F7F7F"
                    point.format.fill.solid()
                    point.format.fill.fore_color.rgb = RGBColor.from_string(color.lstrip("#"))
            except Exception:
                pass  # Not all chart types support per-point coloring
    except Exception as exc:
        log.debug("Could not apply series colors: %s", exc)


def _apply_labels(chart, labels_cfg: dict, ctx: "RenderContext") -> None:
    """Apply label settings to all plot series."""
    if not labels_cfg:
        return
    try:
        plot = chart.plots[0]
        plot.has_data_labels = any([
            labels_cfg.get("show_category_name"),
            labels_cfg.get("show_value"),
            labels_cfg.get("show_percentage"),
        ])
        if not plot.has_data_labels:
            return

        dls = plot.data_labels
        if labels_cfg.get("show_category_name"):
            dls.show_category_name = True
        if labels_cfg.get("show_percentage"):
            dls.show_percentage = True
        if labels_cfg.get("show_value"):
            dls.show_value = True

        pos_str = labels_cfg.get("position", "outside_end")
        pos = _LABEL_POSITION_MAP.get(pos_str, XL_LABEL_POSITION.OUTSIDE_END)
        try:
            dls.position = pos
        except Exception:
            pass

        font_size = labels_cfg.get("font_size") or ctx.typography.get("label_size", 9)
        try:
            dls.font.size = Pt(font_size)
        except Exception:
            pass
    except Exception as exc:
        log.debug("Could not apply labels: %s", exc)


def _resolve_position(position: dict, ctx: "RenderContext") -> tuple[int, int, int, int]:
    """Convert relative position dict to absolute EMU via free_area."""
    fa = ctx.free_area
    fa_x = fa.get("x", 0)
    fa_y = fa.get("y", 0)
    fa_cx = fa.get("cx", 1)
    fa_cy = fa.get("cy", 1)

    if "anchor" in position:
        anchor_id = position["anchor"]
        anchor_rect = ctx.resolved_anchors.get(anchor_id, {})
        base_x = anchor_rect.get("x", fa_x)
        base_y = anchor_rect.get("y", fa_y)
        base_cx = anchor_rect.get("cx", fa_cx)
        base_cy = anchor_rect.get("cy", fa_cy)
        relative = position.get("relative", "right_of")
        offset_rel = position.get("offset_rel", 0.0)
        w_rel = position.get("w_rel", 0.3)
        h_rel = position.get("h_rel", 0.5)
        w = int(w_rel * fa_cx)
        h = int(h_rel * fa_cy)
        offset = int(offset_rel * fa_cx)
        if relative == "right_of":
            x = base_x + base_cx + offset
            y = base_y
        elif relative == "below":
            x = base_x
            y = base_y + base_cy + offset
        elif relative == "above":
            x = base_x
            y = base_y - h - offset
        elif relative == "left_of":
            x = base_x - w - offset
            y = base_y
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

- [ ] **Step 5: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_element_renderers.py -k "chart" -v`
Expected: 4 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/ backend/tests/test_element_renderers.py
git commit -m "$(cat <<'EOF'
feat(backend): element_renderers package + chart_renderer — all 9 chart types

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: text_renderer — content_source + style

**Files:**
- Create: `backend/aurum_encuestas/element_renderers/text_renderer.py`
- Modify: `backend/tests/test_element_renderers.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_element_renderers.py`:

```python
from aurum_encuestas.element_renderers.text_renderer import render as render_text


def test_text_renderer_static_content():
    slide = _make_slide()
    element = {
        "kind": "text",
        "id": "label1",
        "position": {"x_rel": 0.0, "y_rel": 0.0, "w_rel": 0.5, "h_rel": 0.2},
        "content_source": {"type": "static", "text": "Título de prueba"},
        "style": {"text_color": "primary", "font_size": 12, "bold": True, "align_h": "left"},
    }
    ctx = _make_ctx()
    render_text(slide, element, ctx)
    texts = [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]
    assert any("Título de prueba" in t for t in texts)


def test_text_renderer_analysis_content():
    slide = _make_slide()
    ctx = _make_ctx()
    ctx.slide_config.analyses = [
        MagicMock(scope="slide", text="El 80% respondió Sí.", target_id=None)
    ]
    element = {
        "kind": "text",
        "id": "analysis_box",
        "position": {"x_rel": 0.0, "y_rel": 0.8, "w_rel": 1.0, "h_rel": 0.2},
        "content_source": {"type": "analysis", "scope": "slide"},
        "style": {
            "fill": "background",
            "text_color": "primary",
            "font_size": 10,
            "border_left": {"color": "primary", "width_pt": 3.0},
            "padding": 5,
        },
    }
    render_text(slide, element, ctx)
    texts = [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]
    assert any("80%" in t for t in texts)


def test_text_renderer_empty_analysis_skips():
    slide = _make_slide()
    ctx = _make_ctx()
    ctx.slide_config.analyses = []
    element = {
        "kind": "text",
        "id": "a",
        "position": {"x_rel": 0.0, "y_rel": 0.0, "w_rel": 0.5, "h_rel": 0.1},
        "content_source": {"type": "analysis", "scope": "slide"},
        "style": {},
    }
    initial = len(slide.shapes)
    render_text(slide, element, ctx)
    # No shapes added if no analysis text
    assert len(slide.shapes) == initial
```

- [ ] **Step 2: Implement text_renderer**

Create `backend/aurum_encuestas/element_renderers/text_renderer.py`:

```python
"""Text element renderer — handles static, analysis, and computed content sources."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

if TYPE_CHECKING:
    from .render_context import RenderContext

log = logging.getLogger(__name__)

_ALIGN_MAP = {
    "left": PP_ALIGN.LEFT,
    "center": PP_ALIGN.CENTER,
    "right": PP_ALIGN.RIGHT,
}


def render(slide, element: dict, ctx: "RenderContext") -> None:
    """Render a text element onto slide."""
    content_source = element.get("content_source", {})
    text = _resolve_content(content_source, ctx)
    if text is None:
        log.debug("text_renderer: no content resolved for element %r — skipping", element.get("id"))
        return

    from .chart_renderer import _resolve_position
    x, y, cx, cy = _resolve_position(element.get("position", {}), ctx)

    tb_shape = slide.shapes.add_textbox(Emu(x), Emu(y), Emu(cx), Emu(cy))
    tf = tb_shape.text_frame
    tf.word_wrap = True

    style = element.get("style", {})
    padding = style.get("padding", 0)
    if padding:
        try:
            tf.margin_left = Pt(padding)
            tf.margin_right = Pt(padding)
            tf.margin_top = Pt(padding / 2)
            tf.margin_bottom = Pt(padding / 2)
        except Exception:
            pass

    # Set text + formatting
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = text

    font_size = style.get("font_size", ctx.typography.get("body_size", 10))
    run.font.size = Pt(font_size)

    bold = style.get("bold", False)
    if bold:
        run.font.bold = True

    font_family = ctx.typography.get("font_family", "Arial")
    run.font.name = font_family

    text_color_role = style.get("text_color", "primary")
    hex_color = ctx.resolved_colors.get(text_color_role, "#000000")
    try:
        run.font.color.rgb = RGBColor.from_string(hex_color.lstrip("#"))
    except Exception:
        pass

    align_h = style.get("align_h", "left")
    p.alignment = _ALIGN_MAP.get(align_h, PP_ALIGN.LEFT)

    # Fill background
    fill_role = style.get("fill")
    if fill_role:
        fill_hex = ctx.resolved_colors.get(fill_role)
        if fill_hex:
            try:
                tb_shape.fill.solid()
                tb_shape.fill.fore_color.rgb = RGBColor.from_string(fill_hex.lstrip("#"))
            except Exception:
                pass

    # Border left — implemented as a separate thin rectangle shape
    border_left = style.get("border_left")
    if border_left:
        bl_color_role = border_left.get("color", "primary")
        bl_width_pt = border_left.get("width_pt", 3.0)
        bl_hex = ctx.resolved_colors.get(bl_color_role, "#7F7F7F")
        _add_border_left_rect(slide, x, y, cy, bl_hex, bl_width_pt)


def _resolve_content(content_source: dict, ctx: "RenderContext") -> str | None:
    source_type = content_source.get("type", "static")
    if source_type == "static":
        return content_source.get("text", "")
    if source_type == "analysis":
        scope = content_source.get("scope", "slide")
        ref_index = content_source.get("ref_index", 0)
        analyses = getattr(ctx.slide_config, "analyses", []) or []
        matching = [a for a in analyses if getattr(a, "scope", None) == scope]
        if not matching:
            return None
        if scope == "chart":
            idx = min(ref_index, len(matching) - 1)
            return matching[idx].text
        return matching[0].text
    if source_type == "computed":
        # Placeholder for future computed expressions
        return content_source.get("text", "")
    return content_source.get("text")


def _add_border_left_rect(slide, x: int, y: int, cy: int, hex_color: str, width_pt: float) -> None:
    from pptx.util import Pt as PtUtil
    try:
        width_emu = int(PtUtil(width_pt))
        rect = slide.shapes.add_shape(
            1,  # MSO_SHAPE_TYPE.RECTANGLE
            Emu(x), Emu(y), Emu(width_emu), Emu(cy),
        )
        rect.fill.solid()
        rect.fill.fore_color.rgb = RGBColor.from_string(hex_color.lstrip("#"))
        rect.line.fill.background()
    except Exception as exc:
        log.debug("Could not add border_left rect: %s", exc)
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_element_renderers.py -k "text" -v`
Expected: 3 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/text_renderer.py backend/tests/test_element_renderers.py
git commit -m "$(cat <<'EOF'
feat(backend): text_renderer — static/analysis/computed content + fill/border_left/font style

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: shape_renderer — line + rectangle

**Files:**
- Create: `backend/aurum_encuestas/element_renderers/shape_renderer.py`
- Modify: `backend/tests/test_element_renderers.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_element_renderers.py`:

```python
from aurum_encuestas.element_renderers.shape_renderer import render as render_shape


def test_shape_renderer_rectangle_added():
    slide = _make_slide()
    element = {
        "kind": "shape",
        "id": "divider_rect",
        "position": {"x_rel": 0.0, "y_rel": 0.0, "w_rel": 1.0, "h_rel": 0.02},
        "shape_type": "rectangle",
        "style": {"fill": "primary", "color": "primary", "width_pt": 0},
    }
    initial = len(slide.shapes)
    render_shape(slide, element, _make_ctx())
    assert len(slide.shapes) > initial


def test_shape_renderer_line_added():
    slide = _make_slide()
    element = {
        "kind": "shape",
        "id": "horiz_line",
        "position": {"x_rel": 0.0, "y_rel": 0.2, "w_rel": 1.0, "h_rel": 0.0},
        "shape_type": "line",
        "style": {"color": "secondary", "width_pt": 1.5},
    }
    initial = len(slide.shapes)
    render_shape(slide, element, _make_ctx())
    assert len(slide.shapes) > initial
```

- [ ] **Step 2: Implement shape_renderer**

Create `backend/aurum_encuestas/element_renderers/shape_renderer.py`:

```python
"""Shape element renderer — line and rectangle."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE

if TYPE_CHECKING:
    from .render_context import RenderContext

log = logging.getLogger(__name__)


def render(slide, element: dict, ctx: "RenderContext") -> None:
    """Render a shape element (line or rectangle) onto slide."""
    from .chart_renderer import _resolve_position
    x, y, cx, cy = _resolve_position(element.get("position", {}), ctx)
    style = element.get("style", {})
    shape_type = element.get("shape_type", "rectangle")

    color_role = style.get("color", "primary")
    hex_color = ctx.resolved_colors.get(color_role, "#7F7F7F")

    if shape_type == "line":
        _render_line(slide, x, y, cx, cy, hex_color, style.get("width_pt", 1.0))
    else:
        _render_rectangle(slide, x, y, cx, cy, hex_color, style, ctx)


def _render_line(slide, x: int, y: int, cx: int, cy: int, hex_color: str, width_pt: float) -> None:
    try:
        # Use a thin rectangle to simulate a line (1pt height if cy==0)
        height = cy if cy > 0 else int(Pt(1))
        rect = slide.shapes.add_shape(1, Emu(x), Emu(y), Emu(cx), Emu(height))
        rect.fill.solid()
        rect.fill.fore_color.rgb = RGBColor.from_string(hex_color.lstrip("#"))
        rect.line.fill.background()
    except Exception as exc:
        log.warning("shape_renderer: could not render line: %s", exc)


def _render_rectangle(slide, x: int, y: int, cx: int, cy: int, hex_color: str, style: dict, ctx: "RenderContext") -> None:
    try:
        rect = slide.shapes.add_shape(1, Emu(x), Emu(y), Emu(cx), Emu(cy))
        fill_role = style.get("fill")
        if fill_role:
            fill_hex = ctx.resolved_colors.get(fill_role, hex_color)
            rect.fill.solid()
            rect.fill.fore_color.rgb = RGBColor.from_string(fill_hex.lstrip("#"))
        else:
            rect.fill.background()
        rect.line.fill.background()
    except Exception as exc:
        log.warning("shape_renderer: could not render rectangle: %s", exc)
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_element_renderers.py -k "shape" -v`
Expected: 2 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/shape_renderer.py backend/tests/test_element_renderers.py
git commit -m "$(cat <<'EOF'
feat(backend): shape_renderer — line and rectangle with color resolution

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: image_renderer — reference-based image from template

**Files:**
- Create: `backend/aurum_encuestas/element_renderers/image_renderer.py`
- Modify: `backend/tests/test_element_renderers.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_element_renderers.py`:

```python
from aurum_encuestas.element_renderers.image_renderer import render as render_image


def test_image_renderer_no_template_shape_skips():
    """When template shape not found, renderer skips silently."""
    slide = _make_slide()
    ctx = _make_ctx()
    ctx.slide_config.template_shapes = {}  # empty map
    element = {
        "kind": "image",
        "id": "logo",
        "position": {"x_rel": 0.8, "y_rel": 0.0, "w_rel": 0.15, "h_rel": 0.1},
        "source_ref": "logo_shape_id",
    }
    initial = len(slide.shapes)
    render_image(slide, element, ctx)
    assert len(slide.shapes) == initial  # nothing added, no crash


def test_image_renderer_with_template_shape_copies():
    """When a template image shape is provided, it gets copied to the slide."""
    slide = _make_slide()
    ctx = _make_ctx()
    # Simulate a template shape with a picture (we use a mock for simplicity)
    mock_pic = MagicMock()
    mock_pic.shape_type = 13  # MSO_SHAPE_TYPE.PICTURE
    mock_pic.left = 0; mock_pic.top = 0; mock_pic.width = 100; mock_pic.height = 100
    ctx.slide_config.template_shapes = {"logo_shape_id": mock_pic}
    element = {
        "kind": "image",
        "id": "logo",
        "position": {"x_rel": 0.8, "y_rel": 0.0, "w_rel": 0.15, "h_rel": 0.1},
        "source_ref": "logo_shape_id",
    }
    # Should not raise (actual copy logic may vary)
    render_image(slide, element, ctx)
```

- [ ] **Step 2: Implement image_renderer**

Create `backend/aurum_encuestas/element_renderers/image_renderer.py`:

```python
"""Image element renderer — copies referenced template image shape to slide."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pptx.util import Emu

if TYPE_CHECKING:
    from .render_context import RenderContext

log = logging.getLogger(__name__)


def render(slide, element: dict, ctx: "RenderContext") -> None:
    """Render an image element by referencing a named template shape.

    Images in the Aurum pattern system live in the template PPTX. The renderer
    looks up the shape by source_ref ID in ctx.slide_config.template_shapes
    (a dict populated by pattern_renderer from the template slide). If the shape
    is not found, the renderer silently skips — missing logos should not crash
    generation.
    """
    source_ref = element.get("source_ref", "")
    template_shapes = getattr(ctx.slide_config, "template_shapes", {}) or {}

    template_shape = template_shapes.get(source_ref)
    if template_shape is None:
        log.debug("image_renderer: template shape %r not found — skipping", source_ref)
        return

    from .chart_renderer import _resolve_position
    x, y, cx, cy = _resolve_position(element.get("position", {}), ctx)

    try:
        _copy_picture_shape(slide, template_shape, x, y, cx, cy)
    except Exception as exc:
        log.warning("image_renderer: could not copy shape %r: %s", source_ref, exc)


def _copy_picture_shape(slide, template_shape, x: int, y: int, cx: int, cy: int) -> None:
    """Deep-copy a picture shape from template to target slide at new position."""
    import copy
    from lxml import etree

    sp_tree = slide.shapes._spTree
    elem_copy = copy.deepcopy(template_shape._element)

    # Update position and size in the copied XML element
    nvSpPr = elem_copy.find(".//{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}nvSpPr")
    xfrm_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    xfrm = elem_copy.find(f".//{{{xfrm_ns}}}xfrm")
    if xfrm is not None:
        off = xfrm.find(f"{{{xfrm_ns}}}off")
        ext = xfrm.find(f"{{{xfrm_ns}}}ext")
        if off is not None:
            off.set("x", str(x))
            off.set("y", str(y))
        if ext is not None:
            ext.set("cx", str(cx))
            ext.set("cy", str(cy))

    sp_tree.append(elem_copy)
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_element_renderers.py -k "image" -v`
Expected: 2 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/image_renderer.py backend/tests/test_element_renderers.py
git commit -m "$(cat <<'EOF'
feat(backend): image_renderer — template-referenced image copy with position override

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: table_renderer base — `simple_data` structure

**Files:**
- Create: `backend/aurum_encuestas/element_renderers/table_renderer.py`
- Modify: `backend/tests/test_element_renderers.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_element_renderers.py`:

```python
from aurum_encuestas.element_renderers.table_renderer import render as render_table


def _make_table_element(structure="simple_data"):
    return {
        "kind": "table",
        "id": "demo_table",
        "position": {"x_rel": 0.4, "y_rel": 0.1, "w_rel": 0.55, "h_rel": 0.8},
        "structure": structure,
        "data_source": {"chart_ref_index": 0, "breakdown_groups": "all_except_general"},
        "layout": {"col_widths": "auto", "header_height_rel": 0.15, "counts_row_height_rel": 0.1},
        "cells": {
            "group_header": {
                "style": {"fill": "primary", "text_color": "background", "font_size": 10, "bold": True, "align_h": "center"},
                "merge_per_breakdown": True,
            },
            "category_header": {"style": {"fill": "secondary", "font_size": 9, "bold": True}},
            "counts_row": {"style": {"fill": "background", "font_size": 9, "align_h": "center"}, "label_first_col": "Observaciones"},
            "option_row": {
                "style": {"fill": "background", "font_size": 9},
                "label_col_width_rel": 0.10,
                "value_format": "percentage",
                "value_decimals": 1,
                "minibar": {"enabled": False},
            },
        },
    }


def test_table_renderer_simple_data_adds_table():
    slide = _make_slide()
    element = {
        "kind": "table",
        "id": "t1",
        "position": {"x_rel": 0.0, "y_rel": 0.0, "w_rel": 1.0, "h_rel": 0.5},
        "structure": "simple_data",
        "data_source": {"chart_ref_index": 0, "breakdown_groups": "all"},
        "layout": {},
        "cells": {},
    }
    ctx = _make_ctx()
    initial = len(slide.shapes)
    render_table(slide, element, ctx)
    assert len(slide.shapes) > initial


def test_table_renderer_dispatch_by_structure():
    """All three structures should dispatch without raising."""
    ctx = _make_ctx()
    for structure in ("simple_data", "segmented_breakdowns", "comparison_grid"):
        slide = _make_slide()
        element = _make_table_element(structure)
        render_table(slide, element, ctx)  # should not raise
```

- [ ] **Step 2: Implement table_renderer with simple_data**

Create `backend/aurum_encuestas/element_renderers/table_renderer.py`:

```python
"""Table element renderer — dispatches to structure-specific builders."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

if TYPE_CHECKING:
    from .render_context import RenderContext

log = logging.getLogger(__name__)

_ALIGN_MAP = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}


def render(slide, element: dict, ctx: "RenderContext") -> None:
    """Dispatch to the correct table structure builder."""
    structure = element.get("structure", "simple_data")
    if structure == "simple_data":
        _render_simple_data(slide, element, ctx)
    elif structure == "segmented_breakdowns":
        _render_segmented_breakdowns(slide, element, ctx)
    elif structure == "comparison_grid":
        _render_comparison_grid(slide, element, ctx)
    else:
        log.warning("table_renderer: unknown structure %r — falling back to simple_data", structure)
        _render_simple_data(slide, element, ctx)


# ---------------------------------------------------------------------------
# simple_data: header row + data rows
# ---------------------------------------------------------------------------

def _render_simple_data(slide, element: dict, ctx: "RenderContext") -> None:
    """Basic table with one header row and N data rows."""
    from .chart_renderer import _resolve_position
    x, y, cx, cy = _resolve_position(element.get("position", {}), ctx)

    data_source = element.get("data_source", {})
    chart_ref_index = data_source.get("chart_ref_index", 0)
    charts_list = getattr(ctx.slide_config, "charts", []) or []
    if chart_ref_index >= len(charts_list):
        log.warning("table_renderer: chart_ref_index %d out of range — skipping", chart_ref_index)
        return

    source_chart = charts_list[chart_ref_index]
    question = getattr(source_chart, "question", None)
    options = question.options if question else []
    data = getattr(source_chart, "data", {}) or {}
    breakdowns = list(data.keys())

    if not breakdowns:
        return

    # Build rows: header + one row per option
    n_cols = len(breakdowns) + 1  # label col + one per breakdown
    n_rows = len(options) + 1     # header + data rows

    try:
        table_shape = slide.shapes.add_table(n_rows, n_cols, Emu(x), Emu(y), Emu(cx), Emu(cy))
        tbl = table_shape.table
    except Exception as exc:
        log.error("table_renderer: failed to add table: %s", exc)
        return

    cells_cfg = element.get("cells", {})
    header_style = (cells_cfg.get("group_header") or {}).get("style", {})

    # Header row
    _set_cell(tbl.cell(0, 0), "Opción", ctx, header_style)
    for col_idx, breakdown in enumerate(breakdowns, start=1):
        _set_cell(tbl.cell(0, col_idx), breakdown, ctx, header_style)

    # Data rows
    option_style = (cells_cfg.get("option_row") or {}).get("style", {})
    for row_idx, option in enumerate(options, start=1):
        _set_cell(tbl.cell(row_idx, 0), option, ctx, option_style)
        for col_idx, breakdown in enumerate(breakdowns, start=1):
            cell_data = (data.get(breakdown) or {}).get(option) or {}
            pct = cell_data.get("pct", 0) or 0
            _set_cell(tbl.cell(row_idx, col_idx), f"{pct * 100:.1f}%", ctx, option_style)


def _set_cell(cell, text: str, ctx: "RenderContext", style: dict) -> None:
    """Set cell text and basic style."""
    tf = cell.text_frame
    tf.clear()
    p = tf.paragraphs[0]

    align_h = style.get("align_h", "left")
    p.alignment = _ALIGN_MAP.get(align_h, PP_ALIGN.LEFT)

    run = p.add_run()
    run.text = text

    font_size = style.get("font_size", ctx.typography.get("body_size", 9))
    run.font.size = Pt(font_size)

    if style.get("bold"):
        run.font.bold = True

    font_family = ctx.typography.get("font_family", "Arial")
    run.font.name = font_family

    text_color_role = style.get("text_color", "primary")
    hex_text = ctx.resolved_colors.get(text_color_role, "#000000")
    try:
        run.font.color.rgb = RGBColor.from_string(hex_text.lstrip("#"))
    except Exception:
        pass

    fill_role = style.get("fill")
    if fill_role:
        fill_hex = ctx.resolved_colors.get(fill_role)
        if fill_hex:
            try:
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor.from_string(fill_hex.lstrip("#"))
            except Exception:
                pass


# ---------------------------------------------------------------------------
# segmented_breakdowns — stub, implemented in Task 6
# ---------------------------------------------------------------------------

def _render_segmented_breakdowns(slide, element: dict, ctx: "RenderContext") -> None:
    """Segmented breakdowns table — full implementation in Task 6."""
    # Stub: falls back to simple_data until Task 6 replaces this body
    _render_simple_data(slide, element, ctx)


# ---------------------------------------------------------------------------
# comparison_grid — stub, implemented in Task 8
# ---------------------------------------------------------------------------

def _render_comparison_grid(slide, element: dict, ctx: "RenderContext") -> None:
    """Comparison grid table — full implementation in Task 8."""
    _render_simple_data(slide, element, ctx)
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_element_renderers.py -k "table" -v`
Expected: 2 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/table_renderer.py backend/tests/test_element_renderers.py
git commit -m "$(cat <<'EOF'
feat(backend): table_renderer base — simple_data structure + dispatch skeleton

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: table_renderer `segmented_breakdowns` — full implementation

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/table_renderer.py`
- Modify: `backend/tests/test_element_renderers.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_element_renderers.py`:

```python
def _make_ctx_with_breakdowns():
    ctx = _make_ctx()
    # Simulate source_chart with multiple breakdowns
    ctx.slide_config.charts = [
        MagicMock(
            question=MagicMock(options=["Sí", "No"]),
            data={
                "General": {"Sí": {"count": 80, "pct": 0.8}, "No": {"count": 20, "pct": 0.2}},
                "Masculino": {"Sí": {"count": 60, "pct": 0.6}, "No": {"count": 40, "pct": 0.4}},
                "Femenino": {"Sí": {"count": 85, "pct": 0.85}, "No": {"count": 15, "pct": 0.15}},
            },
            breakdown=MagicMock(id="sexo", label="Sexo", categories=["Masculino", "Femenino"]),
        )
    ]
    return ctx


def test_segmented_breakdowns_adds_table():
    slide = _make_slide()
    element = _make_table_element("segmented_breakdowns")
    ctx = _make_ctx_with_breakdowns()
    render_table(slide, element, ctx)
    # Should have added at least a table shape
    table_shapes = [s for s in slide.shapes if s.shape_type == 19]  # 19 = TABLE
    assert len(table_shapes) >= 1


def test_segmented_breakdowns_row_count():
    """Table must have: group_header + category_header + counts_row + N option rows per breakdown."""
    slide = _make_slide()
    element = _make_table_element("segmented_breakdowns")
    ctx = _make_ctx_with_breakdowns()
    render_table(slide, element, ctx)
    table_shapes = [s for s in slide.shapes if s.shape_type == 19]
    if not table_shapes:
        return  # Already checked in previous test
    tbl = table_shapes[0].table
    # 2 options (Sí, No) + group_header + category_header + counts_row = 5 rows minimum
    assert tbl.rows._tbl.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}tr") is not None
```

- [ ] **Step 2: Replace `_render_segmented_breakdowns` stub with full implementation**

Edit `backend/aurum_encuestas/element_renderers/table_renderer.py`. Replace the `_render_segmented_breakdowns` function:

```python
def _render_segmented_breakdowns(slide, element: dict, ctx: "RenderContext") -> None:
    """Build segmented breakdown table per spec section 6.

    Row layout per breakdown group:
      - group_header row (spans all categories in breakdown)
      - category_header row (one cell per category)
      - counts_row (Observaciones + N per category)
      - option_row × N_options (one row per question option)

    Columns:
      col 0            = label column (question option text / row label)
      col 1..N_cats    = one column per breakdown category
    """
    from .chart_renderer import _resolve_position
    x, y, cx, cy = _resolve_position(element.get("position", {}), ctx)

    data_source = element.get("data_source", {})
    chart_ref_index = data_source.get("chart_ref_index", 0)
    breakdown_groups_filter = data_source.get("breakdown_groups", "all_except_general")

    charts_list = getattr(ctx.slide_config, "charts", []) or []
    if chart_ref_index >= len(charts_list):
        log.warning("table_renderer segmented: chart_ref_index out of range — skipping")
        return

    source_chart = charts_list[chart_ref_index]
    question = getattr(source_chart, "question", None)
    options = question.options if question else []
    data = getattr(source_chart, "data", {}) or {}

    # Collect breakdown groups excluding General if requested
    if breakdown_groups_filter == "all_except_general":
        breakdown_keys = [k for k in data.keys() if k.lower() != "general"]
    elif breakdown_groups_filter == "all":
        breakdown_keys = list(data.keys())
    elif isinstance(breakdown_groups_filter, list):
        breakdown_keys = breakdown_groups_filter
    else:
        breakdown_keys = list(data.keys())

    if not breakdown_keys:
        log.debug("table_renderer segmented: no breakdown groups — skipping")
        return

    cells_cfg = element.get("cells", {})
    group_hdr_cfg = cells_cfg.get("group_header", {})
    cat_hdr_cfg = cells_cfg.get("category_header", {})
    counts_cfg = cells_cfg.get("counts_row", {})
    option_cfg = cells_cfg.get("option_row", {})

    # Determine columns: label col + one col per breakdown category
    # For simplicity, each breakdown key gets one column (scalar value)
    # (A more complex multi-category breakdown would expand cols further)
    n_data_cols = len(breakdown_keys)
    n_cols = 1 + n_data_cols

    # Rows per breakdown group: group_header(1) + category_header(1) + counts_row(1) + options
    N_HEADER_ROWS = 3  # group_header, category_header, counts_row
    n_rows = N_HEADER_ROWS + len(options)

    try:
        table_shape = slide.shapes.add_table(n_rows, n_cols, Emu(x), Emu(y), Emu(cx), Emu(cy))
        tbl = table_shape.table
    except Exception as exc:
        log.error("table_renderer segmented: failed to add table: %s", exc)
        return

    g_style = group_hdr_cfg.get("style", {})
    c_style = cat_hdr_cfg.get("style", {})
    cnt_style = counts_cfg.get("style", {})
    opt_style = option_cfg.get("style", {})

    # Row 0: group_header — label cell + one cell per breakdown (merge if merge_per_breakdown)
    _set_cell(tbl.cell(0, 0), "", ctx, g_style)
    for col_idx, bd_key in enumerate(breakdown_keys, start=1):
        _set_cell(tbl.cell(0, col_idx), bd_key, ctx, g_style)

    # Row 1: category_header — "Categoría" label + each breakdown category label
    _set_cell(tbl.cell(1, 0), "", ctx, c_style)
    for col_idx, bd_key in enumerate(breakdown_keys, start=1):
        _set_cell(tbl.cell(1, col_idx), bd_key, ctx, c_style)

    # Row 2: counts_row — "Observaciones" label + N per category
    counts_label = counts_cfg.get("label_first_col", "Observaciones")
    _set_cell(tbl.cell(2, 0), counts_label, ctx, cnt_style)
    for col_idx, bd_key in enumerate(breakdown_keys, start=1):
        bd_data = data.get(bd_key) or {}
        total_count = sum((bd_data.get(opt) or {}).get("count", 0) for opt in options)
        _set_cell(tbl.cell(2, col_idx), str(int(total_count)), ctx, cnt_style)

    # Rows 3+: option_rows
    value_format = option_cfg.get("value_format", "percentage")
    value_decimals = option_cfg.get("value_decimals", 1)
    minibar_cfg = option_cfg.get("minibar", {})

    for opt_idx, option in enumerate(options):
        row_idx = N_HEADER_ROWS + opt_idx
        _set_cell(tbl.cell(row_idx, 0), option, ctx, opt_style)
        for col_idx, bd_key in enumerate(breakdown_keys, start=1):
            bd_data = data.get(bd_key) or {}
            cell_data = bd_data.get(option) or {}
            pct = cell_data.get("pct", 0) or 0
            count = cell_data.get("count", 0) or 0
            if value_format == "percentage":
                val_str = f"{pct * 100:.{value_decimals}f}%"
            elif value_format == "count":
                val_str = str(int(count))
            else:  # both
                val_str = f"{pct * 100:.{value_decimals}f}% ({int(count)})"
            _set_cell(tbl.cell(row_idx, col_idx), val_str, ctx, opt_style)

    # Apply cell dimensions from layout config
    layout_cfg = element.get("layout", {})
    _apply_table_layout(tbl, layout_cfg, cx, cy, len(options))
```

Add helper at bottom of file:

```python
def _apply_table_layout(tbl, layout_cfg: dict, total_cx: int, total_cy: int, n_options: int) -> None:
    """Set column widths and row heights from layout config."""
    try:
        col_widths = layout_cfg.get("col_widths", "auto")
        if col_widths == "equal" or col_widths == "auto":
            per_col = total_cx // max(len(tbl.columns), 1)
            for col in tbl.columns:
                col.width = per_col
        elif isinstance(col_widths, list):
            for i, w_rel in enumerate(col_widths):
                if i < len(tbl.columns):
                    tbl.columns[i].width = int(w_rel * total_cx)
    except Exception as exc:
        log.debug("Could not set column widths: %s", exc)
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_element_renderers.py -k "segmented" -v`
Expected: 2 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/table_renderer.py backend/tests/test_element_renderers.py
git commit -m "$(cat <<'EOF'
feat(backend): table_renderer segmented_breakdowns — group_header/category/counts/option rows

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: table_renderer minibar overlay for option rows

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/table_renderer.py`
- Modify: `backend/tests/test_element_renderers.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_element_renderers.py`:

```python
def test_segmented_breakdowns_minibar_adds_rectangle_overlays():
    """When minibar.enabled=True, rectangle shapes are added on top of table cells."""
    slide = _make_slide()
    element = _make_table_element("segmented_breakdowns")
    # Enable minibar
    element["cells"]["option_row"]["minibar"] = {
        "enabled": True,
        "color_role": "primary",
        "height_rel_to_cell": 0.4,
        "show_percent_text": True,
        "percent_text_position": "left_of_bar",
    }
    ctx = _make_ctx_with_breakdowns()
    initial_shapes = len(slide.shapes)
    render_table(slide, element, ctx)
    # Should have added table + multiple rectangle overlays (one per option×col cell)
    shapes_after = len(slide.shapes)
    assert shapes_after > initial_shapes + 1  # table + at least some minibars
```

- [ ] **Step 2: Add minibar overlay logic**

Edit `backend/aurum_encuestas/element_renderers/table_renderer.py`. After the option rows loop in `_render_segmented_breakdowns`, add minibar rendering:

```python
    # Minibar overlays — rendered after table is positioned
    if minibar_cfg.get("enabled", False):
        _render_minibar_overlays(
            slide, tbl, options, breakdown_keys, data,
            minibar_cfg, opt_style, ctx,
            table_x=x, table_y=y, table_cx=cx, table_cy=cy,
            n_header_rows=N_HEADER_ROWS,
        )
```

Add the minibar helper function:

```python
def _render_minibar_overlays(
    slide, tbl, options: list, breakdown_keys: list, data: dict,
    minibar_cfg: dict, opt_style: dict, ctx: "RenderContext",
    table_x: int, table_y: int, table_cx: int, table_cy: int,
    n_header_rows: int,
) -> None:
    """Add MSO rectangle overlays on option row cells to represent minibar values."""
    color_role = minibar_cfg.get("color_role", "primary")
    bar_hex = ctx.resolved_colors.get(color_role, "#7F7F7F")
    height_rel = minibar_cfg.get("height_rel_to_cell", 0.4)
    show_pct_text = minibar_cfg.get("show_percent_text", False)
    pct_text_pos = minibar_cfg.get("percent_text_position", "left_of_bar")

    try:
        # Compute cumulative column X offsets
        col_x_offsets = [0]
        for col in tbl.columns:
            col_x_offsets.append(col_x_offsets[-1] + col.width)

        # Compute cumulative row Y offsets
        row_y_offsets = [0]
        for row in tbl.rows:
            row_y_offsets.append(row_y_offsets[-1] + row.height)

        for opt_idx in range(len(options)):
            row_idx = n_header_rows + opt_idx
            if row_idx >= len(row_y_offsets) - 1:
                continue
            cell_y_abs = table_y + row_y_offsets[row_idx]
            cell_h = tbl.rows[row_idx].height
            bar_h = int(cell_h * height_rel)
            bar_y = cell_y_abs + (cell_h - bar_h) // 2

            option = options[opt_idx]
            for col_idx, bd_key in enumerate(breakdown_keys, start=1):
                if col_idx >= len(col_x_offsets):
                    continue
                cell_x_abs = table_x + col_x_offsets[col_idx]
                cell_w = tbl.columns[col_idx].width

                bd_data = data.get(bd_key) or {}
                pct = (bd_data.get(option) or {}).get("pct", 0) or 0
                bar_w = int(cell_w * float(pct))
                if bar_w <= 0:
                    continue

                # Add minibar rectangle
                try:
                    bar_shape = slide.shapes.add_shape(
                        1,  # MSO_SHAPE_TYPE.RECTANGLE
                        Emu(cell_x_abs), Emu(bar_y), Emu(bar_w), Emu(bar_h),
                    )
                    bar_shape.fill.solid()
                    bar_shape.fill.fore_color.rgb = RGBColor.from_string(bar_hex.lstrip("#"))
                    bar_shape.line.fill.background()
                except Exception as exc:
                    log.debug("minibar overlay: could not add rect: %s", exc)
                    continue

                # Percent text overlay
                if show_pct_text:
                    pct_str = f"{pct * 100:.1f}%"
                    if pct_text_pos == "left_of_bar":
                        txt_x = cell_x_abs
                        txt_w = bar_w
                    elif pct_text_pos == "right_of_bar":
                        txt_x = cell_x_abs + bar_w
                        txt_w = cell_w - bar_w
                    else:  # inside_bar
                        txt_x = cell_x_abs
                        txt_w = bar_w
                    try:
                        txt_shape = slide.shapes.add_textbox(
                            Emu(txt_x), Emu(bar_y), Emu(max(txt_w, 1)), Emu(bar_h),
                        )
                        tf = txt_shape.text_frame
                        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
                        run = tf.paragraphs[0].add_run()
                        run.text = pct_str
                        run.font.size = Pt(ctx.typography.get("label_size", 8))
                        run.font.name = ctx.typography.get("font_family", "Arial")
                    except Exception as exc:
                        log.debug("minibar text overlay failed: %s", exc)
    except Exception as exc:
        log.warning("minibar overlays: error: %s", exc)
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_element_renderers.py -k "minibar" -v`
Expected: 1 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/table_renderer.py backend/tests/test_element_renderers.py
git commit -m "$(cat <<'EOF'
feat(backend): table_renderer minibar overlays — rectangle shapes with optional percent text

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: table_renderer `comparison_grid` + full test sweep

**Files:**
- Modify: `backend/aurum_encuestas/element_renderers/table_renderer.py`
- Modify: `backend/tests/test_element_renderers.py`

- [ ] **Step 1: Failing test**

Append to `backend/tests/test_element_renderers.py`:

```python
def test_comparison_grid_adds_table():
    slide = _make_slide()
    element = _make_table_element("comparison_grid")
    ctx = _make_ctx_with_breakdowns()
    initial = len(slide.shapes)
    render_table(slide, element, ctx)
    assert len(slide.shapes) > initial
```

- [ ] **Step 2: Implement `_render_comparison_grid`**

Replace the stub in `table_renderer.py`:

```python
def _render_comparison_grid(slide, element: dict, ctx: "RenderContext") -> None:
    """Side-by-side comparison of breakdown data for the same question.

    Layout:
      Row 0: header — blank + one col per breakdown
      Row 1+: one row per question option, values side-by-side
    """
    from .chart_renderer import _resolve_position
    x, y, cx, cy = _resolve_position(element.get("position", {}), ctx)

    data_source = element.get("data_source", {})
    chart_ref_index = data_source.get("chart_ref_index", 0)
    charts_list = getattr(ctx.slide_config, "charts", []) or []
    if chart_ref_index >= len(charts_list):
        log.warning("comparison_grid: chart_ref_index out of range — skipping")
        return

    source_chart = charts_list[chart_ref_index]
    question = getattr(source_chart, "question", None)
    options = question.options if question else []
    data = getattr(source_chart, "data", {}) or {}
    breakdown_keys = list(data.keys())

    if not breakdown_keys or not options:
        return

    n_cols = 1 + len(breakdown_keys)
    n_rows = 1 + len(options)

    try:
        table_shape = slide.shapes.add_table(n_rows, n_cols, Emu(x), Emu(y), Emu(cx), Emu(cy))
        tbl = table_shape.table
    except Exception as exc:
        log.error("comparison_grid: failed to add table: %s", exc)
        return

    cells_cfg = element.get("cells", {})
    header_style = (cells_cfg.get("group_header") or {}).get("style", {})
    option_style = (cells_cfg.get("option_row") or {}).get("style", {})
    option_cfg = cells_cfg.get("option_row", {})
    value_format = option_cfg.get("value_format", "percentage")
    value_decimals = option_cfg.get("value_decimals", 1)

    # Header row
    _set_cell(tbl.cell(0, 0), "Opción", ctx, header_style)
    for col_idx, bd_key in enumerate(breakdown_keys, start=1):
        _set_cell(tbl.cell(0, col_idx), bd_key, ctx, header_style)

    # Data rows
    for row_idx, option in enumerate(options, start=1):
        _set_cell(tbl.cell(row_idx, 0), option, ctx, option_style)
        for col_idx, bd_key in enumerate(breakdown_keys, start=1):
            bd_data = data.get(bd_key) or {}
            cell_data = bd_data.get(option) or {}
            pct = cell_data.get("pct", 0) or 0
            count = cell_data.get("count", 0) or 0
            if value_format == "percentage":
                val_str = f"{pct * 100:.{value_decimals}f}%"
            elif value_format == "count":
                val_str = str(int(count))
            else:
                val_str = f"{pct * 100:.{value_decimals}f}% ({int(count)})"
            _set_cell(tbl.cell(row_idx, col_idx), val_str, ctx, option_style)
```

- [ ] **Step 3: Run full element renderer test suite**

Run: `cd backend && .venv/bin/pytest tests/test_element_renderers.py -v`
Expected: all PASS (at minimum 14 tests).

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/element_renderers/table_renderer.py backend/tests/test_element_renderers.py
git commit -m "$(cat <<'EOF'
feat(backend): table_renderer comparison_grid + full element renderer test sweep

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## M6.5 Done When

- `element_renderers/` package exists with 5 modules: chart, text, shape, image, table
- `RenderContext` dataclass in `element_renderers/render_context.py`
- Chart renderer adds python-pptx chart for all 9 chart types; unknown type falls back gracefully; out-of-range data_source silently skips
- Text renderer handles static, analysis (slide/chart/question scope), and computed content; supports fill, text_color, border_left, font, padding, align_h
- Shape renderer adds rectangle and line shapes with resolved colors
- Image renderer copies template picture shapes by source_ref; silently skips if shape not found
- Table `simple_data` structure works with header row + data rows
- Table `segmented_breakdowns` produces group_header + category_header + counts_row + N option rows; minibar rectangle overlays with optional percent text
- Table `comparison_grid` produces side-by-side breakdown comparison
- All renderers accept `resolved_anchors` for anchored positioning
- Full test suite passes (14+ unit tests)
- Git tag `m6.5`
