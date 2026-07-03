import type { ParsedDB, ProjectState, TemplateInfo } from "../types"

const BASE = "http://localhost:8000/api"

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, init || { method: "GET" })
  if (!r.ok) {
    let payload: any
    try {
      payload = await r.json()
    } catch {
      payload = { code: "unknown", message: r.statusText }
    }
    throw payload
  }
  return r.json() as Promise<T>
}

async function uploadFile<T>(path: string, file: File): Promise<T> {
  const fd = new FormData()
  fd.append("file", file)
  return request<T>(path, { method: "POST", body: fd })
}

export async function health(): Promise<{ status: string }> {
  return request("/health")
}

export async function parseXlsx(file: File): Promise<ParsedDB> {
  return uploadFile("/parse-xlsx", file)
}

export async function parseTemplate(file: File): Promise<TemplateInfo> {
  return uploadFile("/parse-template", file)
}

export async function saveProject(path: string, state: ProjectState): Promise<{ saved: boolean; path: string }> {
  return request("/save-project", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, state }),
  })
}

export async function loadProject(path: string): Promise<ProjectState> {
  return request("/load-project", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  })
}

export async function previewSlide(state: ProjectState, slideIndex: number): Promise<{ png_base64: string }> {
  return request("/preview-slide", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state, slide_index: slideIndex }),
  })
}

export async function exportPptx(state: ProjectState, path: string): Promise<{ exported: boolean; path: string; size: number }> {
  return request("/export-pptx", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state, path }),
  })
}

export interface GenerateAnalysisContext {
  section_title: string
  question_text: string
  options: string[]
  breakdown_label: string
  data: Record<string, Record<string, { count: number; pct: number | null }>>
}

export async function generateAnalysis(
  scope: "slide" | "chart",
  context: GenerateAnalysisContext,
  opts?: { state?: any; slide_id?: string; target_id?: string | null; user_hint?: string },
): Promise<{ text: string; fallback: boolean }> {
  return request("/generate-analysis", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scope,
      context,
      state: opts?.state ?? null,
      slide_id: opts?.slide_id ?? null,
      target_id: opts?.target_id ?? null,
      user_hint: opts?.user_hint ?? null,
    }),
  })
}

export interface SuggestLayoutRequest {
  n_charts: number
  chart_types: string[]
  n_chart_an: number
  n_q_an: number
  has_slide_an: boolean
  free_area: { x: number; y: number; cx: number; cy: number }
}

export async function suggestLayout(req: SuggestLayoutRequest): Promise<{ source: string; layout_id: string | null; elements: any[] }> {
  return request("/suggest-layout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })
}

export interface SuggestSlideLayoutResponse {
  positions?: Record<string, { x_emu: number; y_emu: number; cx_emu: number; cy_emu: number; font_pt?: number | null; callout?: boolean }>
  extras?: Array<{ kind: "line"; x_emu: number; y_emu: number; cx_emu: number; cy_emu: number; style?: string | null; color?: string | null }>
  changes?: string[]
  error?: string
}

export async function suggestSlideLayout(
  state: any,
  slide_id: string,
  user_hint?: string | null,
): Promise<SuggestSlideLayoutResponse> {
  return request("/suggest-slide-layout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state, slide_id, user_hint: user_hint ?? null }),
  })
}

export interface SheetGridResponse {
  n_rows: number
  n_cols: number
  cells: string[][]
  truncated?: boolean
  error?: string
}

export async function fetchSheetGrid(db_path: string): Promise<SheetGridResponse> {
  return request("/sheet-grid", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ db_path }),
  })
}

export interface CellValuesResponse {
  options: string[]
  categories: string[]
  cells: Record<string, Record<string, { count: number; pct: number | null }>>
  error?: string
}

export async function fetchCellValues(state: any, question_id: string, breakdown_id: string): Promise<CellValuesResponse> {
  return request<CellValuesResponse>("/cell-values", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state, question_id, breakdown_id }),
  })
}

export interface CountCellsResponse {
  cells: { row: number; col: number }[]
  error?: string
}

export async function fetchCountCells(state: any): Promise<CountCellsResponse> {
  return request<CountCellsResponse>("/count-cells", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state }),
  })
}
