// Types matching M6 backend schema
import { sessionHeader } from "./session"

export interface CorpusPPT {
  filename: string
  slides_with_charts: number
  added_at: string
}

export interface CorpusListResponse {
  pptxs: CorpusPPT[]
}

export interface AddCorpusResponse {
  filename: string
  slides_with_charts: number
}

export interface DeleteCorpusResponse {
  deleted: boolean
}

export interface AnalyzeJobResponse {
  job_id: string
}

export type AnalysisStatusValue = "running" | "done" | "error"

export interface AnalysisStatusResponse {
  progress: number  // 0-100
  status: AnalysisStatusValue
  message: string
  result_summary?: {
    patterns_valid: number
    patterns_dropped: number
    patterns_repaired: number
    estimated_cost_usd?: number
  }
}

export interface StyleGuideGlobal {
  typography: {
    font_family: string
    title_size: number
    subtitle_size: number
    label_size: number
    body_size: number
  }
  text_patterns: {
    title: string
    notes: string
    analysis_style: string
    tone: string
  }
  suggested_palette: string[]
  vibe: string
}

export interface Pattern {
  id: string
  priority: number
  trigger: Record<string, unknown>
  extends?: string | null
  best_example?: string
  why_picked?: string
  implementation: {
    elements: unknown[]
  }
}

export interface StyleGuide {
  version: number
  is_builtin: boolean
  generated_at?: string
  ai_prompt_version?: string
  source_pptxs: string[]
  manual_edits: Record<string, string>
  global: StyleGuideGlobal
  available_chart_types: string[]
  patterns: Pattern[]
}

export interface PutPatternResponse {
  ok: boolean
}

export interface ClearCacheResponse {
  cleared: boolean
}

// -- Fetch helpers --

async function _get<T>(path: string): Promise<T> {
  const r = await fetch(path, { headers: { ...sessionHeader() } })
  if (!r.ok) throw await r.json()
  return r.json()
}

async function _post<T>(path: string, body: unknown, isFormData = false): Promise<T> {
  const opts: RequestInit = { method: "POST" }
  if (isFormData) {
    opts.body = body as FormData
    opts.headers = { ...sessionHeader() }
  } else {
    opts.headers = { "Content-Type": "application/json", ...sessionHeader() }
    opts.body = JSON.stringify(body)
  }
  const r = await fetch(path, opts)
  if (!r.ok) throw await r.json()
  return r.json()
}

async function _put<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...sessionHeader() },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw await r.json()
  return r.json()
}

// -- Corpus endpoints --

export function listCorpus(): Promise<CorpusListResponse> {
  return _get("/api/training/corpus/list")
}

export function addCorpusPPT(file: File): Promise<AddCorpusResponse> {
  const fd = new FormData()
  fd.append("file", file)
  return _post("/api/training/corpus/add", fd, true)
}

export function deleteCorpusPPT(filename: string): Promise<DeleteCorpusResponse> {
  return _post("/api/training/corpus/delete", { filename })
}

// -- AI Analyze endpoints --

export function triggerAnalyzeWithAI(): Promise<AnalyzeJobResponse> {
  return _post("/api/training/analyze-with-ai", {})
}

export function getAnalysisStatus(jobId: string): Promise<AnalysisStatusResponse> {
  return _get(`/api/training/analysis-status/${jobId}`)
}

// -- Style Guide endpoints --

export function getStyleGuide(): Promise<StyleGuide> {
  return _get("/api/training/style-guide")
}

export function putPattern(patternId: string, pattern: Pattern): Promise<PutPatternResponse> {
  return _put(`/api/training/style-guide/pattern/${patternId}`, pattern)
}

export function clearCache(cacheType: "render" | "classifier" | "all"): Promise<ClearCacheResponse> {
  return _post("/api/training/clear-cache", { cache_type: cacheType })
}
