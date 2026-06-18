from typing import Literal

from pydantic import BaseModel, Field

ChartType = Literal[
    "PIE", "DONUT",
    "BAR", "COLUMN", "BAR_HORIZONTAL",
    "BAR_STACKED", "COLUMN_STACKED",
    "LINE", "AREA", "RADAR",
    "TABLE_WITH_MINIBARS", "TABLE_SIMPLE",
]

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
    breakdown_id: str
    chart_type: ChartType
    multi_series: bool = False
    colors: list[str] = []          # per-slice/series hex; [] = auto cascade


class Analysis(BaseModel):
    id: str
    scope: AnalysisScope
    target_id: str | None = None
    text: str
    ai_generated: bool = False
    edited: bool = False


class Slide(BaseModel):
    id: str
    type: SlideType
    title: str | None = None
    charts: list[Chart] = []
    analyses: list[Analysis] = []
    auto_notes: str | None = None


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
