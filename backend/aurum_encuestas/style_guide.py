"""M6 Style Guide — pydantic schemas, built-in constant, and helpers.

All models use `extra = "ignore"` so future AI-generated fields don't break parsing.

Public API:
    StyleGuide, Pattern, Trigger, Implementation, ElementChart, ElementTable,
    ElementText, ElementShape, ElementImage, Position, PositionAnchored,
    GlobalConfig, Typography, TextPatterns, BUILTIN_STYLE_GUIDE,
    migrate_legacy_files, load_active
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

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


AnyPosition = Position | PositionAnchored


# ────────────────────────────────────────────────────────────────────────────
# Trigger
# Operators: $eq/$neq/$gt/$gte/$lt/$lte/$in/$nin/$and/$or/$not
# All are optional; at least one must be set (validated at classify time).
# ────────────────────────────────────────────────────────────────────────────

class Trigger(_Base):
    # Leaf fields
    field: str | None = None

    # Comparison operators (stored without $ prefix for pydantic compat)
    eq: Any = Field(None, alias="$eq")
    neq: Any = Field(None, alias="$neq")
    gt: float | None = Field(None, alias="$gt")
    gte: float | None = Field(None, alias="$gte")
    lt: float | None = Field(None, alias="$lt")
    lte: float | None = Field(None, alias="$lte")
    in_: list | None = Field(None, alias="$in")
    nin: list | None = Field(None, alias="$nin")

    # Composition operators
    and_: list[Trigger] | None = Field(None, alias="$and")
    or_: list[Trigger] | None = Field(None, alias="$or")
    not_: Trigger | None = Field(None, alias="$not")

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
    breakdown_groups: list[str] | Literal["all", "all_except_general"] = "all"


class _Labels(_Base):
    show_category_name: bool = False
    show_value: bool = False
    show_percentage: bool = False
    position: Literal["inside", "outside_end", "center", "best_fit"] = "outside_end"
    format: str = "0%"
    font_size: int | None = None


class ElementChart(_Base):
    kind: Literal["chart"]
    id: str
    position: Position | PositionAnchored
    chart_type: str | None = None   # ← layout-only; UI's source_chart.chart_type wins at render
    data_source: _DataSourceChart
    labels: _Labels | None = None
    legend: Literal["none", "right", "bottom", "top", "left"] = "none"
    title: str | None = None
    sort: Literal["none", "desc_by_value", "asc_by_value", "category_order"] = "none"
    # Fan-out marker: when set to "per_chart", pattern_renderer replicates this
    # element once per chart in slide_config.charts (n_charts_grid pattern).
    repeat: str | None = Field(None, alias="_repeat")


class _CellStyle(_Base):
    fill: str | None = None
    text_color: str | None = None
    font_size: int | None = None
    bold: bool = False
    align_h: Literal["left", "center", "right", "justify"] = "left"


class _MinibarSpec(_Base):
    enabled: bool = False
    color_role: str = "primary"
    track_color_role: str | None = None
    height_rel_to_cell: float = 0.4
    align: Literal["left", "center", "right"] = "left"
    show_percent_text: bool = True
    percent_text_position: Literal["left_of_bar", "inside_bar", "right_of_bar", "right_of_label", "above_bar", "below_bar"] = "left_of_bar"


class _OptionRowSpec(_Base):
    style: _CellStyle | None = None
    label_style: _CellStyle | None = None
    label_col_width_rel: float = 0.10
    value_format: Literal["percentage", "count", "both"] = "percentage"
    value_decimals: int = 1
    minibar: _MinibarSpec | None = None


class _TableCells(_Base):
    group_header: dict | None = None
    category_header: dict | None = None
    counts_row: dict | None = None
    option_row: _OptionRowSpec | None = None


class _TableLayout(_Base):
    col_widths: Literal["auto", "equal"] | list[float] = "auto"
    header_height_rel: float = 0.12
    counts_row_height_rel: float = 0.08


class ElementTable(_Base):
    kind: Literal["table"]
    id: str
    position: Position | PositionAnchored
    structure: Literal["segmented_breakdowns", "comparison_grid", "simple_data"] = "simple_data"
    data_source: _DataSourceTable
    layout: _TableLayout | None = None
    cells: _TableCells | None = None


class _ContentSource(_Base):
    type: Literal["analysis", "static", "computed"]
    scope: Literal["slide", "question", "chart"] | None = None
    ref_index: int | None = None
    text: str | None = None


class _TextStyle(_Base):
    fill: str | None = None
    text_color: str | None = None
    font_size: int | None = None
    border_left: dict | None = None
    padding: int | None = None
    align_h: Literal["left", "center", "right", "justify"] = "left"
    bold: bool = False


class ElementText(_Base):
    kind: Literal["text"]
    id: str
    position: Position | PositionAnchored
    content_source: _ContentSource
    style: _TextStyle | None = None


class _ShapeStyle(_Base):
    color: str = "secondary"
    fill: str | None = None
    width_pt: float = 0.75


class ElementShape(_Base):
    kind: Literal["shape"]
    id: str
    position: Position | PositionAnchored
    shape_type: Literal["line", "rectangle"] = "line"
    style: _ShapeStyle | None = None


class ElementImage(_Base):
    kind: Literal["image"]
    id: str
    position: Position | PositionAnchored
    source_ref: str


AnyElement = Annotated[
    ElementChart | ElementTable | ElementText | ElementShape | ElementImage,
    Field(discriminator="kind"),
]


# ────────────────────────────────────────────────────────────────────────────
# Implementation + Pattern
# ────────────────────────────────────────────────────────────────────────────

class Implementation(_Base):
    elements: list[AnyElement] = Field(default_factory=list)


class Pattern(_Base):
    id: str
    priority: int = 0
    trigger: Trigger
    extends: str | None = None
    best_example: str | None = None
    why_picked: str | None = None
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
    suggested_palette: list[str] = Field(default_factory=lambda: ["#7F7F7F", "#404040", "#EEC245", "#C00000", "#FFC000"])
    vibe: str = "Minimalista profesional. Greys dominan. Yellow accent puntual. Layouts limpios."


# ────────────────────────────────────────────────────────────────────────────
# StyleGuide (top-level)
# ────────────────────────────────────────────────────────────────────────────

class StyleGuide(_Base):
    version: int = 1
    is_builtin: bool = False
    generated_at: str | None = None
    ai_prompt_version: str | None = None
    source_pptxs: list[str] = Field(default_factory=list)
    manual_edits: dict[str, str] = Field(default_factory=dict)
    global_: GlobalConfig = Field(default_factory=GlobalConfig, alias="global")
    available_chart_types: list[str] = Field(
        default_factory=lambda: ["PIE", "BAR_HORIZONTAL", "TABLE_WITH_MINIBARS"]
    )
    patterns: list[Pattern] = Field(default_factory=list)

    model_config = {"extra": "ignore", "populate_by_name": True}


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
        "suggested_palette": ["#7F7F7F", "#404040", "#EEC245", "#C00000", "#FFC000"],
        "vibe": "Minimalista profesional. Greys dominan, yellow #EEC245 acentúa la barra destacada (último bar). Red+Yellow para PIEs binarios.",
    },
    "available_chart_types": ["PIE", "BAR_HORIZONTAL", "TABLE_WITH_MINIBARS"],
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
                        "position": {"x_rel": 0.12, "y_rel": 0.12, "w_rel": 0.76, "h_rel": 0.76},
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
                        "position": {"x_rel": 0.04, "y_rel": 0.12, "w_rel": 0.30, "h_rel": 0.76},
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
                        "position": {"x_rel": 0.38, "y_rel": 0.12, "w_rel": 0.58, "h_rel": 0.76},
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
                        "position": {"x_rel": 0.17, "y_rel": 0.20, "w_rel": 0.65, "h_rel": 0.65},
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
                        "position": {"x_rel": 0.03, "y_rel": 0.14, "w_rel": 0.94, "h_rel": 0.74},
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
                        "position": {"x_rel": 0.04, "y_rel": 0.12, "w_rel": 0.42, "h_rel": 0.76},
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
                        "position": {"x_rel": 0.495, "y_rel": 0.10, "w_rel": 0.002, "h_rel": 0.78},
                        "shape_type": "line",
                        "style": {"color": "secondary", "width_pt": 0.5},
                    },
                    {
                        "kind": "chart",
                        "id": "right_chart",
                        "position": {"x_rel": 0.54, "y_rel": 0.12, "w_rel": 0.42, "h_rel": 0.76},
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
        # ── 5: n_charts_grid ──────────────────────────────────────────────
        # 3+ charts in one slide → auto-tile (1×3, 2×3, etc.).
        # The single chart element below is replicated by pattern_renderer
        # based on slide_config.charts count; position is the FIRST cell.
        {
            "id": "n_charts_grid",
            "priority": 5,
            "trigger": {"field": "n_charts_in_slide", "$gte": 3},
            "why_picked": "3+ charts — auto grid de N celdas iguales.",
            "implementation": {
                "elements": [
                    {
                        "kind": "chart",
                        "id": "grid_chart",
                        "position": {"x_rel": 0.03, "y_rel": 0.14, "w_rel": 0.30, "h_rel": 0.74},
                        "data_source": {"chart_ref_index": 0, "value_field": "pct"},
                        "labels": {
                            "show_percentage": True,
                            "position": "outside_end",
                            "format": "0.0%",
                            "font_size": 8,
                        },
                        "legend": "none",
                        "sort": "desc_by_value",
                        "_repeat": "per_chart",
                    },
                ]
            },
        },
    ],
})


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


# ────────────────────────────────────────────────────────────────────────────
# load_active helper
# ────────────────────────────────────────────────────────────────────────────

def save_style_guide(sg: StyleGuide) -> None:
    """Persist a StyleGuide to ~/.aurum/training/style_guide.json."""
    import logging
    log = logging.getLogger(__name__)

    sg_path = _get_aurum_dir() / "training" / "style_guide.json"
    sg_path.parent.mkdir(parents=True, exist_ok=True)
    data = sg.model_dump(by_alias=True)
    sg_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("save_style_guide: saved %d patterns to %s", len(sg.patterns), sg_path)


def load_active_style_guide() -> StyleGuide:
    """Alias for load_active — returns the active StyleGuide."""
    return load_active()


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
