export type ChartType =
  | "PIE"
  | "PIE_GROUPED"
  | "BAR_HORIZONTAL"
  | "BAR_HORIZONTAL_GROUPED"
  | "TABLE_WITH_MINIBARS"

export type AnalysisScope = "slide" | "chart"
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
  total_row?: number | null
  value_overrides?: Record<string, { count?: number | null; pct?: number | null }>
  count_cells?: number[][]
}

export interface Chart {
  id: string
  question_id: string
  breakdown_ids: string[]    // [] = general
  chart_type: ChartType
  show_legend: boolean
  grid_cols: number | null
  title: string | null
  cat_titles: Record<string, string> | null
  colors: string[]
}

export interface Analysis {
  id: string
  scope: AnalysisScope
  target_id: string | null
  text: string
  ai_generated: boolean
  edited: boolean
}

export interface LayoutBox {
  x_emu: number
  y_emu: number
  cx_emu: number
  cy_emu: number
  font_pt?: number | null
  callout?: boolean
  box_style?: "dashed" | null
}

export interface LayoutExtra {
  kind: "line"
  x_emu: number
  y_emu: number
  cx_emu: number
  cy_emu: number
  text?: string | null
  font_pt?: number | null
  bold?: boolean
  style?: string | null
  color?: string | null
  fill?: string | null
}

export interface SlideLayout {
  positions: Record<string, LayoutBox>
  extras?: LayoutExtra[]
  changes: string[]
}

export interface Subtitle {
  id: string
  text: string
}

export interface Slide {
  id: string
  type: SlideType
  title: string | null
  charts: Chart[]
  analyses: Analysis[]
  subtitles: Subtitle[]
  auto_notes: string | null
  layout?: SlideLayout | null
  matched_pattern?: string | null   // set by backend on preview; null = fallback heurístico
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
  palette: Record<string, string> | null  // optional project-level color role defaults
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
