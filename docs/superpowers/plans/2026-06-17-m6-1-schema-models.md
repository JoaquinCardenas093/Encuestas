# M6.1 — Pydantic Schemas + Built-in Style Guide + Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define all Pydantic schemas for the M6 style guide system (StyleGuide, Pattern, Trigger, Implementation, Element kinds, Position). Define the `BUILTIN_STYLE_GUIDE` constant with 5 baseline patterns. Extend `models.py` with `Chart.colors` and `ProjectState.palette`. Write `migrate_legacy_files()` idempotent migration helper. Write `load_active()` helper.

**Architecture:** New module `style_guide.py` holds all schemas, built-in constant, and helpers. `models.py` gains two new fields; `style_set` (if present from earlier exploration) is never added. Migration runs once on backend startup via `api.py` lifespan event.

**Tech Stack adds:** None. Pure pydantic v2 + stdlib pathlib.

---

## File Structure

**Create (backend):**
- `backend/aurum_encuestas/style_guide.py` — all pydantic models + BUILTIN_STYLE_GUIDE + helpers
- `backend/tests/test_style_guide.py`

**Modify (backend):**
- `backend/aurum_encuestas/models.py` — add `Chart.colors`, `ProjectState.palette`
- `backend/tests/test_models.py` — new field tests

---

### Task 1: Pydantic models — Position, Trigger, Element kinds, Implementation, Pattern, StyleGuide

**Files:**
- Create: `backend/aurum_encuestas/style_guide.py`
- Create: `backend/tests/test_style_guide.py`

- [ ] **Step 1: Failing tests**

Create `backend/tests/test_style_guide.py`:

```python
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
```

- [ ] **Step 2: Run failing**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_style_guide.py -v 2>&1 | head -30
```
Expected: ImportError (module not yet created).

- [ ] **Step 3: Implement style_guide.py — Position + PositionAnchored**

Create `backend/aurum_encuestas/style_guide.py`:

```python
"""M6 Style Guide — pydantic schemas, built-in constant, and helpers.

All models use `extra = "ignore"` so future AI-generated fields don't break parsing.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator


# ────────────────────────────────────────────────────────────────────────────
# Config
# ────────────────────────────────────────────────────────────────────────────

class _Base(BaseModel):
    model_config = {"extra": "ignore"}


# ────────────────────────────────────────────────────────────────────────────
# Position
# ────────────────────────────────────────────────────────────────────────────

class Position(_Base):
    x_rel: float
    y_rel: float
    w_rel: float
    h_rel: float


class PositionAnchored(_Base):
    anchor: str
    relative: Literal["right_of", "below", "above", "left_of"]
    offset_rel: float = 0.0
    w_rel: float
    h_rel: float


AnyPosition = Union[Position, PositionAnchored]


# ────────────────────────────────────────────────────────────────────────────
# Trigger
# Operators: $eq/$neq/$gt/$gte/$lt/$lte/$in/$nin/$and/$or/$not
# All are optional; at least one must be set (validated at classify time).
# ────────────────────────────────────────────────────────────────────────────

class Trigger(_Base):
    # Leaf fields
    field: Optional[str] = None

    # Comparison operators (stored without $ prefix for pydantic compat)
    eq: Any = Field(None, alias="$eq")
    neq: Any = Field(None, alias="$neq")
    gt: Optional[float] = Field(None, alias="$gt")
    gte: Optional[float] = Field(None, alias="$gte")
    lt: Optional[float] = Field(None, alias="$lt")
    lte: Optional[float] = Field(None, alias="$lte")
    in_: Optional[list] = Field(None, alias="$in")
    nin: Optional[list] = Field(None, alias="$nin")

    # Composition operators
    and_: Optional[list["Trigger"]] = Field(None, alias="$and")
    or_: Optional[list["Trigger"]] = Field(None, alias="$or")
    not_: Optional["Trigger"] = Field(None, alias="$not")

    model_config = {"extra": "ignore", "populate_by_name": True}

Trigger.model_rebuild()


# ────────────────────────────────────────────────────────────────────────────
# Element kinds
# ────────────────────────────────────────────────────────────────────────────

class _DataSourceChart(_Base):
    chart_ref_index: int
    value_field: Literal["pct", "count"] = "pct"


class _DataSourceTable(_Base):
    chart_ref_index: int
    breakdown_groups: Union[list[str], Literal["all", "all_except_general"]] = "all"


class _Labels(_Base):
    show_category_name: bool = False
    show_value: bool = False
    show_percentage: bool = False
    position: Literal["inside", "outside_end", "center", "best_fit"] = "outside_end"
    format: str = "0%"
    font_size: Optional[int] = None


class ElementChart(_Base):
    kind: Literal["chart"]
    id: str
    position: Union[Position, PositionAnchored]
    chart_type: str
    data_source: _DataSourceChart
    labels: Optional[_Labels] = None
    legend: Literal["none", "right", "bottom", "top", "left"] = "none"
    title: Optional[str] = None
    sort: Literal["none", "desc_by_value", "asc_by_value", "category_order"] = "none"


class _CellStyle(_Base):
    fill: Optional[str] = None
    text_color: Optional[str] = None
    font_size: Optional[int] = None
    bold: bool = False
    align_h: Literal["left", "center", "right"] = "left"


class _MinibarSpec(_Base):
    enabled: bool = False
    color_role: str = "primary"
    track_color_role: Optional[str] = None
    height_rel_to_cell: float = 0.4
    align: Literal["left", "center", "right"] = "left"
    show_percent_text: bool = True
    percent_text_position: Literal["left_of_bar", "inside_bar", "right_of_bar"] = "left_of_bar"


class _OptionRowSpec(_Base):
    style: Optional[_CellStyle] = None
    label_style: Optional[_CellStyle] = None
    label_col_width_rel: float = 0.10
    value_format: Literal["percentage", "count", "both"] = "percentage"
    value_decimals: int = 1
    minibar: Optional[_MinibarSpec] = None


class _TableCells(_Base):
    group_header: Optional[dict] = None
    category_header: Optional[dict] = None
    counts_row: Optional[dict] = None
    option_row: Optional[_OptionRowSpec] = None


class _TableLayout(_Base):
    col_widths: Union[Literal["auto", "equal"], list[float]] = "auto"
    header_height_rel: float = 0.12
    counts_row_height_rel: float = 0.08


class ElementTable(_Base):
    kind: Literal["table"]
    id: str
    position: Union[Position, PositionAnchored]
    structure: Literal["segmented_breakdowns", "comparison_grid", "simple_data"] = "simple_data"
    data_source: _DataSourceTable
    layout: Optional[_TableLayout] = None
    cells: Optional[_TableCells] = None


class _ContentSource(_Base):
    type: Literal["analysis", "static", "computed"]
    scope: Optional[Literal["slide", "question", "chart"]] = None
    ref_index: Optional[int] = None
    text: Optional[str] = None


class _TextStyle(_Base):
    fill: Optional[str] = None
    text_color: Optional[str] = None
    font_size: Optional[int] = None
    border_left: Optional[dict] = None
    padding: Optional[int] = None
    align_h: Literal["left", "center", "right"] = "left"
    bold: bool = False


class ElementText(_Base):
    kind: Literal["text"]
    id: str
    position: Union[Position, PositionAnchored]
    content_source: _ContentSource
    style: Optional[_TextStyle] = None


class _ShapeStyle(_Base):
    color: str = "secondary"
    fill: Optional[str] = None
    width_pt: float = 0.75


class ElementShape(_Base):
    kind: Literal["shape"]
    id: str
    position: Union[Position, PositionAnchored]
    shape_type: Literal["line", "rectangle"] = "line"
    style: Optional[_ShapeStyle] = None


class ElementImage(_Base):
    kind: Literal["image"]
    id: str
    position: Union[Position, PositionAnchored]
    source_ref: str


AnyElement = Union[ElementChart, ElementTable, ElementText, ElementShape, ElementImage]


# ────────────────────────────────────────────────────────────────────────────
# Implementation + Pattern
# ────────────────────────────────────────────────────────────────────────────

class Implementation(_Base):
    elements: list[AnyElement] = Field(default_factory=list, discriminator="kind")


class Pattern(_Base):
    id: str
    priority: int = 0
    trigger: Trigger
    extends: Optional[str] = None
    best_example: Optional[str] = None
    why_picked: Optional[str] = None
    implementation: Implementation


# ────────────────────────────────────────────────────────────────────────────
# Global config
# ────────────────────────────────────────────────────────────────────────────

class Typography(_Base):
    font_family: str = "Calibri"
    title_size: int = 16
    subtitle_size: int = 12
    label_size: int = 9
    body_size: int = 10


class TextPatterns(_Base):
    title: str = "{question_code}. {question_text}"
    notes: str = "{tipo_respuesta}. Número de observaciones: {sample_size}."
    analysis_style: str = "El {X}% de los encuestados {finding}. {context}."
    tone: str = "formal técnico español neutral"


class GlobalConfig(_Base):
    typography: Typography = Field(default_factory=Typography)
    text_patterns: TextPatterns = Field(default_factory=TextPatterns)
    suggested_palette: list[str] = Field(default_factory=lambda: ["#7F7F7F", "#BFBFBF", "#FFC000", "#404040", "#D9D9D9"])
    vibe: str = "Minimalista profesional. Greys dominan. Yellow accent puntual. Layouts limpios."


# ────────────────────────────────────────────────────────────────────────────
# StyleGuide (top-level)
# ────────────────────────────────────────────────────────────────────────────

class StyleGuide(_Base):
    version: int = 1
    is_builtin: bool = False
    generated_at: Optional[str] = None
    ai_prompt_version: Optional[str] = None
    source_pptxs: list[str] = Field(default_factory=list)
    manual_edits: dict[str, str] = Field(default_factory=dict)
    global_: GlobalConfig = Field(default_factory=GlobalConfig, alias="global")
    available_chart_types: list[str] = Field(
        default_factory=lambda: ["PIE", "DONUT", "BAR_HORIZONTAL", "BAR_CLUSTERED", "COLUMN_CLUSTERED", "TABLE_WITH_MINIBARS"]
    )
    patterns: list[Pattern] = Field(default_factory=list)

    model_config = {"extra": "ignore", "populate_by_name": True}
```

- [ ] **Step 4: Run, verify pass**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_style_guide.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git add backend/aurum_encuestas/style_guide.py backend/tests/test_style_guide.py
git commit -m "$(cat <<'EOF'
feat(backend/m6.1): style_guide pydantic schemas — Position, Trigger operators, Element kinds, StyleGuide

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: BUILTIN_STYLE_GUIDE constant — 5 baseline patterns

**Files:**
- Modify: `backend/aurum_encuestas/style_guide.py`
- Modify: `backend/tests/test_style_guide.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_style_guide.py`:

```python
from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE


def test_builtin_is_valid_style_guide():
    assert isinstance(BUILTIN_STYLE_GUIDE, StyleGuide)
    assert BUILTIN_STYLE_GUIDE.is_builtin is True


def test_builtin_has_five_patterns():
    assert len(BUILTIN_STYLE_GUIDE.patterns) == 5


def test_builtin_pattern_ids():
    ids = {p.id for p in BUILTIN_STYLE_GUIDE.patterns}
    assert "binary_general" in ids
    assert "binary_with_demographics" in ids
    assert "multi_choice_small" in ids
    assert "multi_choice_large" in ids
    assert "comparison_two_charts" in ids


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
```

- [ ] **Step 2: Append BUILTIN_STYLE_GUIDE to style_guide.py**

Append to `backend/aurum_encuestas/style_guide.py`:

```python
# ────────────────────────────────────────────────────────────────────────────
# Built-in fallback style guide (5 baseline patterns, Calibri, generic greys)
# Used when corpus is empty or AI analysis fails.
# ────────────────────────────────────────────────────────────────────────────

BUILTIN_STYLE_GUIDE = StyleGuide.model_validate({
    "version": 1,
    "is_builtin": True,
    "generated_at": "2026-06-17T00:00:00Z",
    "ai_prompt_version": "builtin-v1",
    "source_pptxs": [],
    "global": {
        "typography": {
            "font_family": "Calibri",
            "title_size": 16,
            "subtitle_size": 12,
            "label_size": 9,
            "body_size": 10,
        },
        "text_patterns": {
            "title": "{question_code}. {question_text}",
            "notes": "{tipo_respuesta}. Número de observaciones: {sample_size}.",
            "analysis_style": "El {X}% de los encuestados {finding}. {context}.",
            "tone": "formal técnico español neutral",
        },
        "suggested_palette": ["#7F7F7F", "#BFBFBF", "#FFC000", "#404040", "#D9D9D9"],
        "vibe": "Minimalista profesional. Greys dominan. Yellow accent puntual.",
    },
    "available_chart_types": [
        "PIE", "DONUT", "BAR_HORIZONTAL", "BAR_CLUSTERED", "COLUMN_CLUSTERED", "TABLE_WITH_MINIBARS"
    ],
    "patterns": [
        # ── 0: binary_general ─────────────────────────────────────────────
        # Single binary question, no breakdowns (or only General)
        {
            "id": "binary_general",
            "priority": 0,
            "trigger": {
                "$and": [
                    {"field": "n_charts_in_slide", "$eq": 1},
                    {"field": "question_type", "$eq": "binary"},
                    {"field": "n_breakdowns", "$lte": 1},
                ]
            },
            "why_picked": "Single binary question — large centred pie with outside labels.",
            "implementation": {
                "elements": [
                    {
                        "kind": "chart",
                        "id": "main_pie",
                        "position": {"x_rel": 0.15, "y_rel": 0.20, "w_rel": 0.70, "h_rel": 0.65},
                        "chart_type": "PIE",
                        "data_source": {"chart_ref_index": 0, "value_field": "pct"},
                        "labels": {
                            "show_category_name": True,
                            "show_percentage": True,
                            "position": "outside_end",
                            "format": "0.0%",
                        },
                        "legend": "bottom",
                        "sort": "desc_by_value",
                    },
                ]
            },
        },
        # ── 1: binary_with_demographics ───────────────────────────────────
        # Single binary question + ≥2 demographic breakdowns → pie left + table right
        {
            "id": "binary_with_demographics",
            "priority": 1,
            "trigger": {
                "$and": [
                    {"field": "n_charts_in_slide", "$eq": 1},
                    {"field": "question_type", "$eq": "binary"},
                    {"field": "n_breakdowns", "$gte": 2},
                ]
            },
            "why_picked": "Pie izquierda + tabla demographics derecha con mini-bars.",
            "implementation": {
                "elements": [
                    {
                        "kind": "chart",
                        "id": "main_pie",
                        "position": {"x_rel": 0.03, "y_rel": 0.22, "w_rel": 0.30, "h_rel": 0.58},
                        "chart_type": "PIE",
                        "data_source": {"chart_ref_index": 0, "value_field": "pct"},
                        "labels": {
                            "show_category_name": True,
                            "show_percentage": True,
                            "position": "outside_end",
                            "format": "0.0%",
                        },
                        "legend": "none",
                        "sort": "desc_by_value",
                    },
                    {
                        "kind": "table",
                        "id": "demographics_table",
                        "position": {"x_rel": 0.38, "y_rel": 0.22, "w_rel": 0.58, "h_rel": 0.58},
                        "structure": "segmented_breakdowns",
                        "data_source": {"chart_ref_index": 0, "breakdown_groups": "all_except_general"},
                        "cells": {
                            "group_header": {
                                "style": {"fill": "primary", "text_color": "background", "font_size": 10, "bold": True, "align_h": "center"},
                                "merge_per_breakdown": True,
                            },
                            "category_header": {
                                "style": {"fill": "secondary", "font_size": 9, "bold": True},
                            },
                            "counts_row": {
                                "style": {"fill": "background", "font_size": 9, "align_h": "center"},
                                "label_first_col": "Observaciones",
                            },
                            "option_row": {
                                "style": {"fill": "background", "font_size": 9},
                                "label_col_width_rel": 0.10,
                                "value_format": "percentage",
                                "value_decimals": 1,
                                "minibar": {
                                    "enabled": True,
                                    "color_role": "primary",
                                    "height_rel_to_cell": 0.4,
                                    "show_percent_text": True,
                                    "percent_text_position": "left_of_bar",
                                },
                            },
                        },
                    },
                ]
            },
        },
        # ── 2: multi_choice_small ─────────────────────────────────────────
        # 3-5 options, single question — horizontal bar chart full width
        {
            "id": "multi_choice_small",
            "priority": 2,
            "trigger": {
                "$and": [
                    {"field": "question_type", "$eq": "multi_small"},
                    {"field": "n_charts_in_slide", "$lte": 2},
                ]
            },
            "why_picked": "3-5 opciones — horizontal bar aprovecha ancho completo; categorías legibles.",
            "implementation": {
                "elements": [
                    {
                        "kind": "chart",
                        "id": "main_bar",
                        "position": {"x_rel": 0.05, "y_rel": 0.20, "w_rel": 0.90, "h_rel": 0.65},
                        "chart_type": "BAR_HORIZONTAL",
                        "data_source": {"chart_ref_index": 0, "value_field": "pct"},
                        "labels": {
                            "show_percentage": True,
                            "position": "outside_end",
                            "format": "0.0%",
                            "font_size": 9,
                        },
                        "legend": "bottom",
                        "sort": "desc_by_value",
                    },
                ]
            },
        },
        # ── 3: multi_choice_large ─────────────────────────────────────────
        # 6+ options — clustered column chart, more compact
        {
            "id": "multi_choice_large",
            "priority": 3,
            "trigger": {
                "$and": [
                    {"field": "question_type", "$eq": "multi_large"},
                    {"field": "n_charts_in_slide", "$lte": 2},
                ]
            },
            "why_picked": "6+ opciones — column clustered muestra ranking sin truncar etiquetas.",
            "implementation": {
                "elements": [
                    {
                        "kind": "chart",
                        "id": "main_column",
                        "position": {"x_rel": 0.03, "y_rel": 0.18, "w_rel": 0.94, "h_rel": 0.68},
                        "chart_type": "COLUMN_CLUSTERED",
                        "data_source": {"chart_ref_index": 0, "value_field": "pct"},
                        "labels": {
                            "show_percentage": True,
                            "position": "outside_end",
                            "format": "0%",
                            "font_size": 8,
                        },
                        "legend": "bottom",
                        "sort": "desc_by_value",
                    },
                ]
            },
        },
        # ── 4: comparison_two_charts ──────────────────────────────────────
        # Two charts side-by-side (any question type)
        {
            "id": "comparison_two_charts",
            "priority": 4,
            "trigger": {"field": "n_charts_in_slide", "$eq": 2},
            "why_picked": "2 charts — side-by-side 50/50 layout con separador central.",
            "implementation": {
                "elements": [
                    {
                        "kind": "chart",
                        "id": "left_chart",
                        "position": {"x_rel": 0.02, "y_rel": 0.20, "w_rel": 0.46, "h_rel": 0.65},
                        "chart_type": "PIE",
                        "data_source": {"chart_ref_index": 0, "value_field": "pct"},
                        "labels": {
                            "show_percentage": True,
                            "position": "outside_end",
                            "format": "0.0%",
                        },
                        "legend": "bottom",
                        "sort": "desc_by_value",
                    },
                    {
                        "kind": "shape",
                        "id": "center_divider",
                        "position": {"x_rel": 0.495, "y_rel": 0.18, "w_rel": 0.002, "h_rel": 0.70},
                        "shape_type": "line",
                        "style": {"color": "secondary", "width_pt": 0.5},
                    },
                    {
                        "kind": "chart",
                        "id": "right_chart",
                        "position": {"x_rel": 0.52, "y_rel": 0.20, "w_rel": 0.46, "h_rel": 0.65},
                        "chart_type": "PIE",
                        "data_source": {"chart_ref_index": 1, "value_field": "pct"},
                        "labels": {
                            "show_percentage": True,
                            "position": "outside_end",
                            "format": "0.0%",
                        },
                        "legend": "bottom",
                        "sort": "desc_by_value",
                    },
                ]
            },
        },
    ],
})
```

- [ ] **Step 3: Run, verify pass**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_style_guide.py -v -k "builtin"
```
Expected: 6 PASS.

- [ ] **Step 4: Commit**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git add backend/aurum_encuestas/style_guide.py backend/tests/test_style_guide.py
git commit -m "$(cat <<'EOF'
feat(backend/m6.1): BUILTIN_STYLE_GUIDE — 5 baseline patterns (binary, multi_small, multi_large, comparison)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: models.py — Chart.colors + ProjectState.palette

**Files:**
- Modify: `backend/aurum_encuestas/models.py`
- Modify: `backend/tests/test_models.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_models.py`:

```python
from aurum_encuestas.models import Chart, ProjectState


def test_chart_colors_defaults_to_empty_list():
    c = Chart(id="c1", question_id="q1", breakdown_id="general", chart_type="PIE", multi_series=False)
    assert c.colors == []


def test_chart_colors_accepts_hex_list():
    c = Chart(id="c1", question_id="q1", breakdown_id="general", chart_type="PIE", multi_series=False, colors=["#7F7F7F", "#BFBFBF"])
    assert len(c.colors) == 2
    assert c.colors[0] == "#7F7F7F"


def test_project_state_palette_defaults_none():
    # minimal valid ProjectState construction
    from aurum_encuestas.models import ProjectInputs
    ps = ProjectState(
        project_name="Test",
        inputs=ProjectInputs(db_path="./x.xlsx", template_path="./t.pptx", font_override=None),
        slides=[],
    )
    assert ps.palette is None


def test_project_state_palette_accepts_dict():
    from aurum_encuestas.models import ProjectInputs
    ps = ProjectState(
        project_name="Test",
        inputs=ProjectInputs(db_path="./x.xlsx", template_path="./t.pptx", font_override=None),
        slides=[],
        palette={"primary": "#7F7F7F", "secondary": "#BFBFBF", "accent": "#FFC000"},
    )
    assert ps.palette["primary"] == "#7F7F7F"


def test_project_state_no_style_set_field():
    """style_set must NOT exist on ProjectState (sets concept dropped in M6)."""
    from aurum_encuestas.models import ProjectInputs
    ps = ProjectState(
        project_name="Test",
        inputs=ProjectInputs(db_path="./x.xlsx", template_path="./t.pptx", font_override=None),
        slides=[],
    )
    assert not hasattr(ps, "style_set")
```

- [ ] **Step 2: Modify models.py**

In `backend/aurum_encuestas/models.py`, locate the `Chart` class and add `colors` field:

```python
class Chart(BaseModel):
    id: str
    question_id: str
    breakdown_id: str
    chart_type: ChartType
    multi_series: bool = False
    colors: list[str] = []          # per-slice/series hex; [] = auto cascade
```

Locate the `ProjectState` class and add `palette` field (do NOT add `style_set`):

```python
class ProjectState(BaseModel):
    version: int = 1
    project_name: str
    inputs: ProjectInputs
    slides: list[Slide] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    palette: Optional[dict] = None  # project-level color defaults; None = use style_guide
```

- [ ] **Step 3: Run, verify pass**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_models.py -v
```
Expected: all PASS including new tests.

- [ ] **Step 4: Commit**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git add backend/aurum_encuestas/models.py backend/tests/test_models.py
git commit -m "$(cat <<'EOF'
feat(backend/m6.1): models — Chart.colors list[str] + ProjectState.palette dict|None (no style_set)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: migrate_legacy_files() — idempotent M6 migration

**Files:**
- Modify: `backend/aurum_encuestas/style_guide.py`
- Modify: `backend/tests/test_style_guide.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_style_guide.py`:

```python
import os
from pathlib import Path
from aurum_encuestas.style_guide import migrate_legacy_files


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
```

- [ ] **Step 2: Implement migrate_legacy_files**

Append to `backend/aurum_encuestas/style_guide.py`:

```python
# ────────────────────────────────────────────────────────────────────────────
# Migration helper
# ────────────────────────────────────────────────────────────────────────────

def _get_aurum_dir() -> Path:
    import os
    return Path(os.environ.get("HOME", Path.home())) / ".aurum"


def migrate_legacy_files() -> None:
    """One-shot idempotent M6 migration.

    - Moves ~/.aurum/training/*.pptx → ~/.aurum/training/corpus/
    - Renames layout_bank.json → layout_bank.json.legacy

    Safe to call on every startup; does nothing if already migrated.
    """
    import logging
    log = logging.getLogger(__name__)

    training_dir = _get_aurum_dir() / "training"
    if not training_dir.exists():
        return

    # Move stray *.pptx files from training/ root → corpus/
    corpus_dir = training_dir / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)

    for pptx in list(training_dir.glob("*.pptx")):
        dest = corpus_dir / pptx.name
        if not dest.exists():
            pptx.rename(dest)
            log.info("migrate_legacy_files: moved %s → %s", pptx, dest)
        else:
            log.info("migrate_legacy_files: skipped %s (already exists in corpus)", pptx.name)

    # Rename layout_bank.json → layout_bank.json.legacy
    bank = training_dir / "layout_bank.json"
    legacy = training_dir / "layout_bank.json.legacy"
    if bank.exists() and not legacy.exists():
        bank.rename(legacy)
        log.info("migrate_legacy_files: renamed layout_bank.json → layout_bank.json.legacy")
```

- [ ] **Step 3: Run, verify pass**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_style_guide.py -v -k "migrate"
```
Expected: 4 PASS.

- [ ] **Step 4: Commit**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git add backend/aurum_encuestas/style_guide.py backend/tests/test_style_guide.py
git commit -m "$(cat <<'EOF'
feat(backend/m6.1): migrate_legacy_files — idempotent M6 migration (corpus dir + layout_bank.legacy)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: load_active() helper — returns style_guide.json or BUILTIN

**Files:**
- Modify: `backend/aurum_encuestas/style_guide.py`
- Modify: `backend/tests/test_style_guide.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_style_guide.py`:

```python
import json
from aurum_encuestas.style_guide import load_active, BUILTIN_STYLE_GUIDE


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
```

- [ ] **Step 2: Implement load_active**

Append to `backend/aurum_encuestas/style_guide.py`:

```python
# ────────────────────────────────────────────────────────────────────────────
# load_active helper
# ────────────────────────────────────────────────────────────────────────────

def load_active() -> StyleGuide:
    """Return the active StyleGuide.

    Precedence:
    1. ~/.aurum/training/style_guide.json  (AI-generated or manually edited)
    2. BUILTIN_STYLE_GUIDE  (fallback when file absent or corrupt)
    """
    import logging
    log = logging.getLogger(__name__)

    sg_path = _get_aurum_dir() / "training" / "style_guide.json"
    if sg_path.exists():
        try:
            raw = json.loads(sg_path.read_text(encoding="utf-8"))
            return StyleGuide.model_validate(raw)
        except Exception as exc:
            log.warning("load_active: failed to load style_guide.json (%s), falling back to built-in", exc)

    return BUILTIN_STYLE_GUIDE
```

- [ ] **Step 3: Run, verify pass**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_style_guide.py -v -k "load_active"
```
Expected: 3 PASS.

- [ ] **Step 4: Commit**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git add backend/aurum_encuestas/style_guide.py backend/tests/test_style_guide.py
git commit -m "$(cat <<'EOF'
feat(backend/m6.1): load_active() — returns style_guide.json or BUILTIN_STYLE_GUIDE fallback

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Run all M6.1 tests + full test suite sanity check

**Files:** none

- [ ] **Step 1: Run M6.1 tests**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_style_guide.py tests/test_models.py -v
```
Expected: all PASS.

- [ ] **Step 2: Run full backend test suite (regression check)**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest -v
```
Expected: all PASS. No regressions from model changes.

- [ ] **Step 3: Tag M6.1**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git tag m6.1-schema-models
git log --oneline | head -10
```

---

## M6.1 Done When

- [ ] `StyleGuide`, `Pattern`, `Trigger` (all 9 operators), `Implementation`, `ElementChart`, `ElementTable`, `ElementText`, `ElementShape`, `ElementImage`, `Position`, `PositionAnchored` pydantic models exist in `style_guide.py` with `extra = "ignore"`
- [ ] `BUILTIN_STYLE_GUIDE` constant validated at import time — 5 patterns (binary_general, binary_with_demographics, multi_choice_small, multi_choice_large, comparison_two_charts)
- [ ] `Chart.colors: list[str] = []` field present; `ProjectState.palette: dict | None = None` present; `style_set` never added
- [ ] `migrate_legacy_files()` tested with 4 scenarios (move pptx, rename bank, idempotent, no-dir)
- [ ] `load_active()` tested with 3 scenarios (builtin fallback, file present, corrupt file fallback)
- [ ] All backend tests pass — no regressions
- [ ] Git tag `m6.1-schema-models` created
