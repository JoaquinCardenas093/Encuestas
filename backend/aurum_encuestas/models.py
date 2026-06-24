from typing import Literal

from pydantic import BaseModel, Field, model_validator

ChartType = Literal[
    "PIE", "PIE_GROUPED",
    "BAR_HORIZONTAL", "BAR_HORIZONTAL_GROUPED",
    "TABLE_WITH_MINIBARS",
]

_ALLOWED_CHART_TYPES = {
    "PIE", "PIE_GROUPED",
    "BAR_HORIZONTAL", "BAR_HORIZONTAL_GROUPED",
    "TABLE_WITH_MINIBARS",
}

AnalysisScope = Literal["slide", "question", "chart"]
SlideType = Literal["separator", "shell"]


class Question(BaseModel):
    id: str
    code: str
    text: str
    options: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class Breakdown(BaseModel):
    id: str
    label: str
    categories: list[str]


class DataBlocks(BaseModel):
    counts_cols: list[int]
    pct_row_cols: list[int]
    pct_col_cols: list[int]


class ParsedDB(BaseModel):
    questions: list[Question]
    breakdowns: list[Breakdown]
    sample_size: int
    data_blocks: dict


class Chart(BaseModel):
    id: str
    question_id: str
    breakdown_ids: list[str] = Field(default_factory=list)
    chart_type: ChartType
    show_legend: bool = False
    grid_cols: int | None = Field(default=None, ge=1)
    title: str | None = None
    cat_titles: dict[str, str] | None = None
    colors: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _reject_legacy(cls, data):
        if not isinstance(data, dict):
            return data
        if "breakdown_id" in data:
            raise ValueError(
                "Chart.breakdown_id (str) was removed in the 2026-06-19 catalog "
                "overhaul. Migrate to breakdown_ids: list[str]. Examples: "
                "breakdown_id='edad' → breakdown_ids=['edad']; "
                "breakdown_id='general' → breakdown_ids=[]."
            )
        ct = data.get("chart_type")
        if ct is not None and ct not in _ALLOWED_CHART_TYPES:
            raise ValueError(
                f"chart_type {ct!r} was removed from the catalog. "
                f"Allowed types: {sorted(_ALLOWED_CHART_TYPES)}."
            )
        return data


class Analysis(BaseModel):
    id: str
    scope: AnalysisScope
    target_id: str | None = None
    text: str
    ai_generated: bool = False
    edited: bool = False


class LayoutBox(BaseModel):
    x_emu: int
    y_emu: int
    cx_emu: int
    cy_emu: int
    font_pt: float | None = None


class LayoutExtra(BaseModel):
    """AI-created extra visual shape: line separator or callout box.
    No standalone narrative text — user constraint."""
    kind: Literal["line", "callout"]
    x_emu: int
    y_emu: int
    cx_emu: int = 0
    cy_emu: int = 0
    text: str | None = None
    font_pt: float | None = None
    bold: bool = False
    style: str | None = None  # line: dotted|dashed|solid
    color: str | None = None  # hex no #
    fill: str | None = None   # hex no # (callout bg)


class SlideLayout(BaseModel):
    """AI-corrected positions per element id (chart_id or analysis_id)."""
    positions: dict[str, LayoutBox] = {}
    extras: list[LayoutExtra] = []
    changes: list[str] = []


class Slide(BaseModel):
    id: str
    type: SlideType
    title: str | None = None
    charts: list[Chart] = []
    analyses: list[Analysis] = []
    auto_notes: str | None = None
    layout: SlideLayout | None = None


class ProjectInputs(BaseModel):
    db_path: str
    template_path: str
    font_override: str | None = None


class ProjectState(BaseModel):
    version: int = 1
    app_name: str = "AurumEncuestas"
    project_name: str
    created_at: str | None = None
    updated_at: str | None = None
    inputs: ProjectInputs
    parsed_db: ParsedDB | None = None
    slides: list[Slide] = []
    history: dict = Field(default_factory=lambda: {"past": [], "future": []})
    palette: dict | None = None  # project-level color defaults; None = use style_guide


class TemplateInfo(BaseModel):
    shell_slide_index: int
    separator_slide_index: int
    free_area: dict
    placeholders: list[str]
    default_font: str | None = None


class LayoutElement(BaseModel):
    role: str
    x: int
    y: int
    cx: int
    cy: int
    chart_type: ChartType | None = None
    anchor_chart: int | None = None


class LearnedLayout(BaseModel):
    id: str
    signature: str
    source: str
    free_area: dict
    elements: list[LayoutElement]
    chart_style: dict = {}
    text_style: dict = {}


class LayoutBank(BaseModel):
    extracted_at: str | None = None
    source_pptxs: list[str] = []
    layouts: list[LearnedLayout] = []


class TrainingPPT(BaseModel):
    filename: str
    added_at: str
    layouts_extracted: int
    status: str = "ok"  # ok | error | pending
    error: str | None = None
