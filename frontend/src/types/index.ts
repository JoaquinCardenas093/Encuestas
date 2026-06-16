export type ChartType =
  | "PIE" | "DONUT" | "BAR" | "COLUMN"
  | "BAR_STACKED" | "COLUMN_STACKED"
  | "LINE" | "AREA" | "RADAR"

export type AnalysisScope = "slide" | "question" | "chart"
export type SlideType = "separator" | "shell"

export interface Question {
  id: string
  code: string
  text: string
  options: string[]
  confidence: number
}

export interface Breakdown {
  id: string
  label: string
  categories: string[]
}

export interface ParsedDB {
  questions: Question[]
  breakdowns: Breakdown[]
  sample_size: number
  data_blocks: { counts_cols: number[]; pct_row_cols: number[]; pct_col_cols: number[] }
}

export interface Chart {
  id: string
  question_id: string
  breakdown_id: string
  chart_type: ChartType
  multi_series: boolean
}

export interface Analysis {
  id: string
  scope: AnalysisScope
  target_id: string | null
  text: string
  ai_generated: boolean
  edited: boolean
}

export interface Slide {
  id: string
  type: SlideType
  title: string | null
  charts: Chart[]
  analyses: Analysis[]
  auto_notes: string | null
}

export interface ProjectInputs {
  db_path: string
  template_path: string
  font_override: string | null
}

export interface ProjectState {
  version: number
  app_name: string
  project_name: string
  created_at: string | null
  updated_at: string | null
  inputs: ProjectInputs
  parsed_db: ParsedDB | null
  slides: Slide[]
  history: { past: unknown[]; future: unknown[] }
}

export interface TemplateInfo {
  shell_slide_index: number
  separator_slide_index: number
  free_area: { x: number; y: number; cx: number; cy: number }
  placeholders: string[]
  default_font: string | null
}

export interface ApiError {
  code: string
  message: string
}
