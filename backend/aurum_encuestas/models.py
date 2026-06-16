from typing import Literal, Optional
from pydantic import BaseModel, Field

ChartType = Literal[
    "PIE", "DONUT", "BAR", "COLUMN",
    "BAR_STACKED", "COLUMN_STACKED",
    "LINE", "AREA", "RADAR",
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


class Analysis(BaseModel):
    id: str
    scope: AnalysisScope
    target_id: Optional[str] = None
    text: str
    ai_generated: bool = False
    edited: bool = False


class Slide(BaseModel):
    id: str
    type: SlideType
    title: Optional[str] = None
    charts: list[Chart] = []
    analyses: list[Analysis] = []
    auto_notes: Optional[str] = None


class ProjectInputs(BaseModel):
    db_path: str
    template_path: str
    font_override: Optional[str] = None


class ProjectState(BaseModel):
    version: int = 1
    app_name: str = "AurumEncuestas"
    project_name: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    inputs: ProjectInputs
    parsed_db: Optional[ParsedDB] = None
    slides: list[Slide] = []
    history: dict = Field(default_factory=lambda: {"past": [], "future": []})


class TemplateInfo(BaseModel):
    shell_slide_index: int
    separator_slide_index: int
    free_area: dict
    placeholders: list[str]
    default_font: Optional[str] = None
