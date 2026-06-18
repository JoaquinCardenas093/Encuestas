# M6.9 — Training Tab Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the Training tab with a flat corpus list, style guide section, "Re-analizar con AI" button with async progress tracking, style guide JSON viewer, and manual pattern edit modal. Replaces the M4 layout-bank Training page entirely.

**Architecture:** New `styleGuide.ts` zustand slice manages style guide state and corpus, polling `analysis-status` while a job runs. New `StyleGuideViewer.tsx` renders the style guide tree with `react-json-view-lite` and exposes per-pattern edit modals. New `AnalysisProgressModal.tsx` shows live spinner + cost preview. `TrainingPage.tsx` is fully rewritten.

**Spec refs:** Section 10 (TrainingPage), Section 8 (AI Analyzer pipeline), Section 14 (API endpoints), Section 11 (validation/error handling).

**Predecessor:** M6.8 (API endpoints complete and tested).

---

## File Structure

**Install:**
- `react-json-view-lite` npm package

**Create (frontend):**
- `frontend/src/api/training.ts` — rewrite with new M6 endpoint types and fetch wrappers
- `frontend/src/store/styleGuide.ts` — zustand slice for corpus + style guide + analysis job
- `frontend/src/pages/Training/TrainingPage.tsx` — full rewrite
- `frontend/src/pages/Training/StyleGuideViewer.tsx` — JSON tree viewer + per-pattern edit modal
- `frontend/src/pages/Training/AnalysisProgressModal.tsx` — spinner + cost + error display
- `frontend/tests/training-api.test.ts`
- `frontend/tests/styleGuide.store.test.ts`
- `frontend/tests/TrainingPage.test.tsx` — rewrite
- `frontend/tests/StyleGuideViewer.test.tsx`
- `frontend/tests/AnalysisProgressModal.test.tsx`

---

### Task 1: Install react-json-view-lite

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install dependency**

```bash
cd frontend && npm install react-json-view-lite
```

Expected: `react-json-view-lite` appears in `frontend/package.json` `dependencies`.

- [ ] **Step 2: Verify import compiles**

Add a quick smoke import to verify the package resolves. In any temp file or directly in a future component check:

```bash
cd frontend && node -e "require('./node_modules/react-json-view-lite')" 2>&1 | head -5
```

Expected: no error (or at most an ES module info warning, not an import failure).

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "$(cat <<'EOF'
feat(frontend): install react-json-view-lite for style guide tree viewer

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Rewrite frontend/src/api/training.ts

**Files:**
- Rewrite: `frontend/src/api/training.ts`
- Create: `frontend/tests/training-api.test.ts`

- [ ] **Step 1: Failing tests**

Create `frontend/tests/training-api.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from "vitest"
import {
  listCorpus, addCorpusPPT, deleteCorpusPPT,
  triggerAnalyzeWithAI, getAnalysisStatus,
  getStyleGuide, putPattern, clearCache,
} from "../src/api/training"

// Mock global fetch
const mockFetch = vi.fn()
vi.stubGlobal("fetch", mockFetch)

function mockOk(body: unknown) {
  mockFetch.mockResolvedValueOnce({
    ok: true,
    json: () => Promise.resolve(body),
  })
}

function mockError(status: number, body: unknown) {
  mockFetch.mockResolvedValueOnce({
    ok: false,
    status,
    json: () => Promise.resolve(body),
  })
}

beforeEach(() => mockFetch.mockReset())

describe("listCorpus", () => {
  it("GET /api/training/corpus/list and returns pptxs", async () => {
    const payload = { pptxs: [{ filename: "a.pptx", slides_with_charts: 5, added_at: "2026-06-17T00:00:00Z" }] }
    mockOk(payload)
    const res = await listCorpus()
    expect(res.pptxs).toHaveLength(1)
    expect(res.pptxs[0].filename).toBe("a.pptx")
    expect(mockFetch).toHaveBeenCalledWith("/api/training/corpus/list")
  })

  it("throws on non-ok response", async () => {
    mockError(500, { detail: "Server error" })
    await expect(listCorpus()).rejects.toBeDefined()
  })
})

describe("addCorpusPPT", () => {
  it("POST multipart to /api/training/corpus/add", async () => {
    mockOk({ filename: "b.pptx", slides_with_charts: 3 })
    const file = new File(["data"], "b.pptx", { type: "application/vnd.ms-powerpoint" })
    const res = await addCorpusPPT(file)
    expect(res.filename).toBe("b.pptx")
    const [url, opts] = mockFetch.mock.calls[0]
    expect(url).toBe("/api/training/corpus/add")
    expect(opts.method).toBe("POST")
    expect(opts.body).toBeInstanceOf(FormData)
  })
})

describe("deleteCorpusPPT", () => {
  it("POST JSON to /api/training/corpus/delete", async () => {
    mockOk({ deleted: true })
    const res = await deleteCorpusPPT("a.pptx")
    expect(res.deleted).toBe(true)
    const [url, opts] = mockFetch.mock.calls[0]
    expect(url).toBe("/api/training/corpus/delete")
    expect(JSON.parse(opts.body)).toEqual({ filename: "a.pptx" })
  })
})

describe("triggerAnalyzeWithAI", () => {
  it("POST to /api/training/analyze-with-ai returns job_id", async () => {
    mockOk({ job_id: "job-123" })
    const res = await triggerAnalyzeWithAI()
    expect(res.job_id).toBe("job-123")
  })
})

describe("getAnalysisStatus", () => {
  it("GET /api/training/analysis-status/{job_id}", async () => {
    mockOk({ progress: 50, status: "running", message: "Analyzing slide 5/10" })
    const res = await getAnalysisStatus("job-123")
    expect(res.progress).toBe(50)
    expect(res.status).toBe("running")
    expect(mockFetch).toHaveBeenCalledWith("/api/training/analysis-status/job-123")
  })
})

describe("getStyleGuide", () => {
  it("GET /api/training/style-guide returns StyleGuide", async () => {
    mockOk({ version: 1, is_builtin: false, patterns: [], global: {}, available_chart_types: [] })
    const res = await getStyleGuide()
    expect(res.version).toBe(1)
  })
})

describe("putPattern", () => {
  it("PUT /api/training/style-guide/pattern/{id} with pattern body", async () => {
    mockOk({ ok: true })
    const pattern = { id: "pat_1", priority: 0, trigger: {}, implementation: { elements: [] } }
    const res = await putPattern("pat_1", pattern)
    expect(res.ok).toBe(true)
    const [url, opts] = mockFetch.mock.calls[0]
    expect(url).toBe("/api/training/style-guide/pattern/pat_1")
    expect(opts.method).toBe("PUT")
  })
})

describe("clearCache", () => {
  it("POST /api/training/clear-cache with cache_type", async () => {
    mockOk({ cleared: true })
    const res = await clearCache("all")
    expect(res.cleared).toBe(true)
    const [, opts] = mockFetch.mock.calls[0]
    expect(JSON.parse(opts.body)).toEqual({ cache_type: "all" })
  })
})
```

- [ ] **Step 2: Run failing**

```bash
cd frontend && npm test -- training-api
```

Expected: import errors (file does not exist yet).

- [ ] **Step 3: Implement training.ts**

Rewrite `frontend/src/api/training.ts`:

```ts
// Types matching M6 backend schema

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
  const r = await fetch(path)
  if (!r.ok) throw await r.json()
  return r.json()
}

async function _post<T>(path: string, body: unknown, isFormData = false): Promise<T> {
  const opts: RequestInit = { method: "POST" }
  if (isFormData) {
    opts.body = body as FormData
  } else {
    opts.headers = { "Content-Type": "application/json" }
    opts.body = JSON.stringify(body)
  }
  const r = await fetch(path, opts)
  if (!r.ok) throw await r.json()
  return r.json()
}

async function _put<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
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
```

- [ ] **Step 4: Run, verify pass**

```bash
cd frontend && npm test -- training-api
```

Expected: all 8 test cases PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/training.ts frontend/tests/training-api.test.ts
git commit -m "$(cat <<'EOF'
feat(frontend): rewrite training.ts API wrappers for M6 corpus+style-guide endpoints

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Create styleGuide.ts zustand slice

**Files:**
- Create: `frontend/src/store/styleGuide.ts`
- Create: `frontend/tests/styleGuide.store.test.ts`

- [ ] **Step 1: Failing tests**

Create `frontend/tests/styleGuide.store.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from "vitest"
import { act } from "@testing-library/react"
import { useStyleGuideStore } from "../src/store/styleGuide"

// Mock api/training
vi.mock("../src/api/training", () => ({
  listCorpus: vi.fn(() => Promise.resolve({
    pptxs: [{ filename: "a.pptx", slides_with_charts: 3, added_at: "2026-06-17T00:00:00Z" }],
  })),
  getStyleGuide: vi.fn(() => Promise.resolve({
    version: 1, is_builtin: false, source_pptxs: ["a.pptx"],
    manual_edits: {}, global: {
      typography: { font_family: "Arial", title_size: 16, subtitle_size: 12, label_size: 9, body_size: 10 },
      text_patterns: { title: "", notes: "", analysis_style: "", tone: "" },
      suggested_palette: ["#7F7F7F"],
      vibe: "Minimalista",
    },
    available_chart_types: ["PIE", "BAR_HORIZONTAL"],
    patterns: [{ id: "pat_1", priority: 0, trigger: {}, implementation: { elements: [] } }],
  })),
  addCorpusPPT: vi.fn(() => Promise.resolve({ filename: "b.pptx", slides_with_charts: 2 })),
  deleteCorpusPPT: vi.fn(() => Promise.resolve({ deleted: true })),
  triggerAnalyzeWithAI: vi.fn(() => Promise.resolve({ job_id: "job-abc" })),
  getAnalysisStatus: vi.fn(() => Promise.resolve({ progress: 100, status: "done", message: "Done", result_summary: { patterns_valid: 5, patterns_dropped: 0, patterns_repaired: 0, estimated_cost_usd: 0.22 } })),
}))

beforeEach(() => {
  useStyleGuideStore.setState({
    styleGuide: null,
    isLoading: false,
    corpus: [],
    analysisJob: null,
  })
})

describe("loadStyleGuide", () => {
  it("fetches and stores style guide", async () => {
    await act(() => useStyleGuideStore.getState().loadStyleGuide())
    const sg = useStyleGuideStore.getState().styleGuide
    expect(sg).not.toBeNull()
    expect(sg?.version).toBe(1)
    expect(sg?.patterns).toHaveLength(1)
  })
})

describe("loadCorpus", () => {
  it("fetches and stores corpus list", async () => {
    await act(() => useStyleGuideStore.getState().loadCorpus())
    expect(useStyleGuideStore.getState().corpus).toHaveLength(1)
    expect(useStyleGuideStore.getState().corpus[0].filename).toBe("a.pptx")
  })
})

describe("addPPT", () => {
  it("uploads file and refreshes corpus", async () => {
    const file = new File(["data"], "b.pptx")
    await act(() => useStyleGuideStore.getState().addPPT(file))
    // Should re-fetch corpus after add
    const { listCorpus } = await import("../src/api/training")
    expect(listCorpus).toHaveBeenCalled()
  })
})

describe("deletePPT", () => {
  it("deletes and refreshes corpus", async () => {
    await act(() => useStyleGuideStore.getState().deletePPT("a.pptx"))
    const { deleteCorpusPPT } = await import("../src/api/training")
    expect(deleteCorpusPPT).toHaveBeenCalledWith("a.pptx")
  })
})

describe("analyzeWithAI", () => {
  it("triggers job, polls status, sets analysisJob done", async () => {
    vi.useFakeTimers()
    const analyzePromise = useStyleGuideStore.getState().analyzeWithAI()
    // Let the trigger and first poll happen
    await act(() => Promise.resolve())
    vi.runAllTimers()
    await act(() => analyzePromise)
    vi.useRealTimers()
    const job = useStyleGuideStore.getState().analysisJob
    expect(job?.status).toBe("done")
  })
})
```

- [ ] **Step 2: Run failing**

```bash
cd frontend && npm test -- styleGuide.store
```

Expected: import errors.

- [ ] **Step 3: Implement styleGuide.ts**

Create `frontend/src/store/styleGuide.ts`:

```ts
import { create } from "zustand"
import * as tapi from "../api/training"
import type { StyleGuide, CorpusPPT, AnalysisStatusResponse } from "../api/training"

interface AnalysisJobState {
  jobId: string
  progress: number
  status: tapi.AnalysisStatusValue
  message: string
  resultSummary?: AnalysisStatusResponse["result_summary"]
  error?: string
}

interface StyleGuideStore {
  styleGuide: StyleGuide | null
  isLoading: boolean
  corpus: CorpusPPT[]
  analysisJob: AnalysisJobState | null

  loadStyleGuide(): Promise<void>
  loadCorpus(): Promise<void>
  addPPT(file: File): Promise<void>
  deletePPT(filename: string): Promise<void>
  analyzeWithAI(): Promise<void>
  clearAnalysisJob(): void
}

const POLL_INTERVAL_MS = 2000

export const useStyleGuideStore = create<StyleGuideStore>((set, get) => ({
  styleGuide: null,
  isLoading: false,
  corpus: [],
  analysisJob: null,

  async loadStyleGuide() {
    set({ isLoading: true })
    try {
      const sg = await tapi.getStyleGuide()
      set({ styleGuide: sg })
    } catch {
      // Style guide unavailable — leave null (will show built-in indicator in UI)
    } finally {
      set({ isLoading: false })
    }
  },

  async loadCorpus() {
    set({ isLoading: true })
    try {
      const res = await tapi.listCorpus()
      set({ corpus: res.pptxs })
    } catch {
      // Silently fail; UI shows empty corpus
    } finally {
      set({ isLoading: false })
    }
  },

  async addPPT(file: File) {
    set({ isLoading: true })
    try {
      await tapi.addCorpusPPT(file)
      await get().loadCorpus()
    } finally {
      set({ isLoading: false })
    }
  },

  async deletePPT(filename: string) {
    set({ isLoading: true })
    try {
      await tapi.deleteCorpusPPT(filename)
      await get().loadCorpus()
    } finally {
      set({ isLoading: false })
    }
  },

  async analyzeWithAI() {
    set({ isLoading: true })
    let jobId: string
    try {
      const res = await tapi.triggerAnalyzeWithAI()
      jobId = res.job_id
      set({ analysisJob: { jobId, progress: 0, status: "running", message: "Iniciando análisis..." } })
    } catch (e) {
      set({
        isLoading: false,
        analysisJob: { jobId: "", progress: 0, status: "error", message: "Error al iniciar análisis" },
      })
      return
    } finally {
      set({ isLoading: false })
    }

    // Poll until done or error
    await new Promise<void>((resolve) => {
      const poll = async () => {
        try {
          const status = await tapi.getAnalysisStatus(jobId)
          set({
            analysisJob: {
              jobId,
              progress: status.progress,
              status: status.status,
              message: status.message,
              resultSummary: status.result_summary,
            },
          })
          if (status.status === "done") {
            // Reload style guide with fresh AI result
            await get().loadStyleGuide()
            resolve()
            return
          }
          if (status.status === "error") {
            resolve()
            return
          }
        } catch {
          set((s) => ({
            analysisJob: s.analysisJob
              ? { ...s.analysisJob, status: "error", message: "Error al consultar estado" }
              : null,
          }))
          resolve()
          return
        }
        setTimeout(poll, POLL_INTERVAL_MS)
      }
      setTimeout(poll, POLL_INTERVAL_MS)
    })
  },

  clearAnalysisJob() {
    set({ analysisJob: null })
  },
}))
```

- [ ] **Step 4: Run, verify pass**

```bash
cd frontend && npm test -- styleGuide.store
```

Expected: 5 test cases PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/store/styleGuide.ts frontend/tests/styleGuide.store.test.ts
git commit -m "$(cat <<'EOF'
feat(frontend): styleGuide zustand slice — corpus + style guide + analyzeWithAI polling

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Rewrite TrainingPage.tsx

**Files:**
- Rewrite: `frontend/src/pages/Training/TrainingPage.tsx`
- Rewrite: `frontend/tests/TrainingPage.test.tsx`

- [ ] **Step 1: Failing tests**

Rewrite `frontend/tests/TrainingPage.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import TrainingPage from "../src/pages/Training/TrainingPage"

// Mock the zustand store
const mockStore = {
  styleGuide: {
    version: 1,
    is_builtin: false,
    generated_at: "2026-06-17T10:00:00Z",
    source_pptxs: ["Aurora.pptx"],
    manual_edits: {},
    global: { typography: { font_family: "Arial", title_size: 16, subtitle_size: 12, label_size: 9, body_size: 10 }, text_patterns: { title: "", notes: "", analysis_style: "", tone: "" }, suggested_palette: ["#7F7F7F"], vibe: "Minimalista" },
    available_chart_types: ["PIE", "BAR_HORIZONTAL"],
    patterns: [
      { id: "pat_1", priority: 0, trigger: {}, implementation: { elements: [] } },
      { id: "pat_2", priority: 1, trigger: {}, implementation: { elements: [] } },
    ],
  },
  isLoading: false,
  corpus: [
    { filename: "Aurora.pptx", slides_with_charts: 15, added_at: "2026-06-17T08:00:00Z" },
    { filename: "Precanc.pptx", slides_with_charts: 20, added_at: "2026-06-17T09:00:00Z" },
  ],
  analysisJob: null,
  loadStyleGuide: vi.fn(),
  loadCorpus: vi.fn(),
  addPPT: vi.fn(),
  deletePPT: vi.fn(),
  analyzeWithAI: vi.fn(),
  clearAnalysisJob: vi.fn(),
}

vi.mock("../src/store/styleGuide", () => ({
  useStyleGuideStore: (selector: (s: typeof mockStore) => unknown) => selector(mockStore),
}))

beforeEach(() => {
  vi.clearAllMocks()
  mockStore.analysisJob = null
  mockStore.isLoading = false
})

describe("TrainingPage", () => {
  it("renders corpus list with filenames and chart counts", async () => {
    render(<TrainingPage />)
    expect(screen.getByText("Aurora.pptx")).toBeInTheDocument()
    expect(screen.getByText("Precanc.pptx")).toBeInTheDocument()
    expect(screen.getByText(/15 charts/i)).toBeInTheDocument()
  })

  it("renders style guide summary when style guide loaded", () => {
    render(<TrainingPage />)
    expect(screen.getByText(/2 patterns/i)).toBeInTheDocument()
    expect(screen.getByText(/PIE/i)).toBeInTheDocument()
  })

  it("calls analyzeWithAI on Re-analizar button click", async () => {
    render(<TrainingPage />)
    await userEvent.click(screen.getByRole("button", { name: /Re-analizar/i }))
    expect(mockStore.analyzeWithAI).toHaveBeenCalled()
  })

  it("calls deletePPT when trash button clicked", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true)
    render(<TrainingPage />)
    const deleteButtons = screen.getAllByRole("button", { name: /eliminar/i })
    await userEvent.click(deleteButtons[0])
    expect(mockStore.deletePPT).toHaveBeenCalledWith("Aurora.pptx")
  })

  it("calls loadStyleGuide and loadCorpus on mount", () => {
    render(<TrainingPage />)
    expect(mockStore.loadStyleGuide).toHaveBeenCalled()
    expect(mockStore.loadCorpus).toHaveBeenCalled()
  })

  it("shows builtin indicator when is_builtin true", () => {
    const builtinStore = { ...mockStore, styleGuide: { ...mockStore.styleGuide, is_builtin: true } }
    vi.mock("../src/store/styleGuide", () => ({
      useStyleGuideStore: (selector: (s: typeof builtinStore) => unknown) => selector(builtinStore),
    }))
    render(<TrainingPage />)
    // Component should render built-in indicator
    expect(screen.getByText(/built-in/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run failing**

```bash
cd frontend && npm test -- TrainingPage
```

Expected: import/render errors.

- [ ] **Step 3: Implement TrainingPage**

Rewrite `frontend/src/pages/Training/TrainingPage.tsx`:

```tsx
import { useEffect, useRef, useState } from "react"
import { Plus, Trash2, RefreshCw, Eye, Database } from "lucide-react"
import { useStyleGuideStore } from "../../store/styleGuide"
import StyleGuideViewer from "./StyleGuideViewer"
import AnalysisProgressModal from "./AnalysisProgressModal"

export default function TrainingPage() {
  const {
    styleGuide, isLoading, corpus, analysisJob,
    loadStyleGuide, loadCorpus, addPPT, deletePPT,
    analyzeWithAI, clearAnalysisJob,
  } = useStyleGuideStore((s) => s)

  const [showStyleGuide, setShowStyleGuide] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    loadStyleGuide()
    loadCorpus()
  }, [])

  const handleAddFile = async (file: File) => {
    await addPPT(file)
  }

  const handleDelete = async (filename: string) => {
    if (!window.confirm(`¿Eliminar ${filename} del corpus?`)) return
    await deletePPT(filename)
  }

  const hasManualEdits = styleGuide && Object.keys(styleGuide.manual_edits).length > 0

  return (
    <div className="p-6 max-w-5xl mx-auto text-neutral-100">
      {/* Header */}
      <header className="mb-6">
        <h2 className="text-lg font-semibold">Corpus de entrenamiento</h2>
        {styleGuide && (
          <p className="text-sm text-neutral-400 mt-1">
            Style guide {styleGuide.is_builtin ? (
              <span className="text-amber-400 font-semibold">built-in (fallback)</span>
            ) : (
              <span className="text-green-400 font-semibold">AI ✓</span>
            )}
            {" · "}
            {styleGuide.patterns.length} patterns
            {styleGuide.generated_at && (
              <> · actualizado {new Date(styleGuide.generated_at).toLocaleDateString()}</>
            )}
            {hasManualEdits && (
              <span className="ml-2 text-amber-400"
                title={`${Object.keys(styleGuide.manual_edits).length} patterns editados manualmente`}>
                ✎ edits manuales
              </span>
            )}
          </p>
        )}
      </header>

      {/* Corpus section */}
      <section className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Database size={16} />
            PPTs en corpus ({corpus.length})
          </h3>
          <button
            onClick={() => fileRef.current?.click()}
            disabled={isLoading}
            className="text-sm bg-accent text-neutral-900 font-semibold px-3 py-1.5 rounded flex items-center gap-1 disabled:opacity-40"
          >
            <Plus size={14} /> Agregar PPT al corpus
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".pptx"
            className="hidden"
            aria-label="Seleccionar PPT"
            onChange={(e) => e.target.files?.[0] && handleAddFile(e.target.files[0])}
          />
        </div>

        <div className="border border-neutral-700 rounded-lg overflow-hidden">
          {corpus.length === 0 && !isLoading && (
            <div className="text-center text-neutral-500 py-8 text-sm">
              Corpus vacío. Agregá PPTs de training para analizar el estilo.
            </div>
          )}
          {corpus.map((pptx) => (
            <div
              key={pptx.filename}
              className="flex items-center justify-between px-4 py-3 border-b border-neutral-800 last:border-b-0 hover:bg-neutral-800/50"
            >
              <div>
                <span className="text-sm font-medium">{pptx.filename}</span>
                <span className="text-xs text-neutral-500 ml-3">
                  {pptx.slides_with_charts} charts · agregado {new Date(pptx.added_at).toLocaleDateString()}
                </span>
              </div>
              <button
                onClick={() => handleDelete(pptx.filename)}
                aria-label="eliminar"
                className="text-neutral-500 hover:text-red-400 p-1"
              >
                <Trash2 size={15} />
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* Style Guide section */}
      <section className="mb-6">
        <div className="flex items-center gap-3 mb-3">
          <h3 className="text-sm font-semibold">Style guide</h3>
          <button
            onClick={() => setShowStyleGuide((v) => !v)}
            disabled={!styleGuide}
            className="text-xs text-neutral-400 hover:text-neutral-200 flex items-center gap-1 disabled:opacity-40"
          >
            <Eye size={12} />
            {showStyleGuide ? "Ocultar" : "Ver style guide"}
          </button>
          <button
            onClick={analyzeWithAI}
            disabled={isLoading || corpus.length === 0}
            className="ml-auto text-sm bg-purple-700 hover:bg-purple-600 text-white font-semibold px-3 py-1.5 rounded flex items-center gap-1 disabled:opacity-40"
          >
            <RefreshCw size={14} />
            Re-analizar con AI
          </button>
        </div>

        {styleGuide && (
          <div className="text-xs text-neutral-500 mb-3">
            <span className="font-medium text-neutral-300">Tipos disponibles:</span>{" "}
            {styleGuide.available_chart_types.join(", ") || "—"}
          </div>
        )}

        {showStyleGuide && styleGuide && (
          <StyleGuideViewer styleGuide={styleGuide} />
        )}
      </section>

      {/* Analysis Progress Modal */}
      {analysisJob && (
        <AnalysisProgressModal
          job={analysisJob}
          onClose={clearAnalysisJob}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run, verify pass**

```bash
cd frontend && npm test -- TrainingPage
```

Expected: 5+ tests PASS (note: the is_builtin test may need mock adjustment — fix as needed until all pass).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Training/TrainingPage.tsx frontend/tests/TrainingPage.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): rewrite TrainingPage — flat corpus list + style guide section + Re-analizar button

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Create StyleGuideViewer.tsx

**Files:**
- Create: `frontend/src/pages/Training/StyleGuideViewer.tsx`
- Create: `frontend/tests/StyleGuideViewer.test.tsx`

- [ ] **Step 1: Failing tests**

Create `frontend/tests/StyleGuideViewer.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import StyleGuideViewer from "../src/pages/Training/StyleGuideViewer"
import type { StyleGuide } from "../src/api/training"

const STYLE_GUIDE: StyleGuide = {
  version: 1,
  is_builtin: false,
  source_pptxs: ["Aurora.pptx"],
  manual_edits: {},
  global: {
    typography: { font_family: "Arial", title_size: 16, subtitle_size: 12, label_size: 9, body_size: 10 },
    text_patterns: { title: "{code}. {text}", notes: "Nota.", analysis_style: "El {X}%", tone: "formal" },
    suggested_palette: ["#7F7F7F", "#BFBFBF"],
    vibe: "Minimalista profesional.",
  },
  available_chart_types: ["PIE", "BAR_HORIZONTAL"],
  patterns: [
    {
      id: "binary_general",
      priority: 0,
      trigger: { "$and": [{ "field": "question_type", "$eq": "binary" }] },
      implementation: { elements: [{ kind: "chart", id: "main_pie" }] },
    },
    {
      id: "multi_small",
      priority: 1,
      trigger: { "field": "question_type", "$eq": "multi_small" },
      implementation: { elements: [] },
    },
  ],
}

vi.mock("../src/api/training", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/api/training")>()
  return { ...actual, putPattern: vi.fn(() => Promise.resolve({ ok: true })) }
})

describe("StyleGuideViewer", () => {
  it("renders pattern ids", () => {
    render(<StyleGuideViewer styleGuide={STYLE_GUIDE} />)
    expect(screen.getByText(/binary_general/)).toBeInTheDocument()
    expect(screen.getByText(/multi_small/)).toBeInTheDocument()
  })

  it("renders global typography info", () => {
    render(<StyleGuideViewer styleGuide={STYLE_GUIDE} />)
    expect(screen.getByText(/Arial/i)).toBeInTheDocument()
  })

  it("renders suggested palette swatches", () => {
    render(<StyleGuideViewer styleGuide={STYLE_GUIDE} />)
    // Palette row shows hex values or swatches
    expect(screen.getByText(/#7F7F7F/i)).toBeInTheDocument()
  })

  it("opens edit modal on pattern edit button click", async () => {
    render(<StyleGuideViewer styleGuide={STYLE_GUIDE} />)
    const editButtons = screen.getAllByRole("button", { name: /editar/i })
    await userEvent.click(editButtons[0])
    // Modal opens with textarea containing pattern JSON
    expect(screen.getByRole("dialog")).toBeInTheDocument()
    expect(screen.getByRole("textbox")).toBeInTheDocument()
  })

  it("calls putPattern on save from edit modal", async () => {
    const { putPattern } = await import("../src/api/training")
    render(<StyleGuideViewer styleGuide={STYLE_GUIDE} />)
    const editButtons = screen.getAllByRole("button", { name: /editar/i })
    await userEvent.click(editButtons[0])
    const textarea = screen.getByRole("textbox")
    // textarea already contains JSON, save as-is
    await userEvent.click(screen.getByRole("button", { name: /guardar/i }))
    await waitFor(() => expect(putPattern).toHaveBeenCalledWith("binary_general", expect.objectContaining({ id: "binary_general" })))
  })

  it("shows validation error if textarea has invalid JSON", async () => {
    render(<StyleGuideViewer styleGuide={STYLE_GUIDE} />)
    const editButtons = screen.getAllByRole("button", { name: /editar/i })
    await userEvent.click(editButtons[0])
    const textarea = screen.getByRole("textbox")
    await userEvent.clear(textarea)
    await userEvent.type(textarea, "not valid json")
    await userEvent.click(screen.getByRole("button", { name: /guardar/i }))
    expect(screen.getByText(/JSON inválido/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run failing**

```bash
cd frontend && npm test -- StyleGuideViewer
```

Expected: import errors.

- [ ] **Step 3: Implement StyleGuideViewer.tsx**

Create `frontend/src/pages/Training/StyleGuideViewer.tsx`:

```tsx
import { useState } from "react"
import { JsonView, allExpanded, defaultStyles } from "react-json-view-lite"
import "react-json-view-lite/dist/index.css"
import { Edit2, X } from "lucide-react"
import type { StyleGuide, Pattern } from "../../api/training"
import { putPattern } from "../../api/training"

interface Props {
  styleGuide: StyleGuide
}

interface EditState {
  pattern: Pattern
  jsonText: string
  error: string | null
  saving: boolean
}

export default function StyleGuideViewer({ styleGuide }: Props) {
  const [editState, setEditState] = useState<EditState | null>(null)

  const openEdit = (pattern: Pattern) => {
    setEditState({
      pattern,
      jsonText: JSON.stringify(pattern, null, 2),
      error: null,
      saving: false,
    })
  }

  const closeEdit = () => setEditState(null)

  const handleSave = async () => {
    if (!editState) return
    let parsed: Pattern
    try {
      parsed = JSON.parse(editState.jsonText)
    } catch {
      setEditState((s) => s ? { ...s, error: "JSON inválido. Corregí la sintaxis e intentá de nuevo." } : s)
      return
    }
    setEditState((s) => s ? { ...s, saving: true, error: null } : s)
    try {
      await putPattern(editState.pattern.id, parsed)
      closeEdit()
    } catch (e) {
      setEditState((s) => s ? { ...s, saving: false, error: `Error al guardar: ${(e as { message?: string }).message ?? "desconocido"}` } : s)
    }
  }

  return (
    <div className="space-y-4">
      {/* Global info */}
      <div className="border border-neutral-700 rounded-lg p-4">
        <h4 className="text-xs font-semibold uppercase text-neutral-400 mb-3">Global</h4>
        <div className="grid grid-cols-2 gap-4 text-sm mb-3">
          <div>
            <span className="text-neutral-400 text-xs">Fuente:</span>
            <span className="ml-2">{styleGuide.global.typography.font_family}</span>
          </div>
          <div>
            <span className="text-neutral-400 text-xs">Vibe:</span>
            <span className="ml-2 text-xs">{styleGuide.global.vibe}</span>
          </div>
        </div>
        <div>
          <span className="text-neutral-400 text-xs block mb-2">Paleta sugerida:</span>
          <div className="flex gap-2 flex-wrap">
            {styleGuide.global.suggested_palette.map((color) => (
              <div key={color} className="flex items-center gap-1">
                <div
                  className="w-5 h-5 rounded border border-neutral-600"
                  style={{ backgroundColor: color }}
                />
                <span className="text-xs text-neutral-400">{color}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Patterns */}
      <div className="border border-neutral-700 rounded-lg overflow-hidden">
        <div className="bg-neutral-800/50 px-4 py-2 border-b border-neutral-700">
          <span className="text-xs font-semibold uppercase text-neutral-400">
            Patterns ({styleGuide.patterns.length})
          </span>
        </div>
        {styleGuide.patterns.map((pattern) => {
          const isManuallyEdited = pattern.id in styleGuide.manual_edits
          return (
            <div key={pattern.id} className="border-b border-neutral-800 last:border-b-0">
              <div className="flex items-center justify-between px-4 py-3">
                <div>
                  <span className="text-sm font-mono">{pattern.id}</span>
                  <span className="text-xs text-neutral-500 ml-3">priority {pattern.priority}</span>
                  {pattern.extends && (
                    <span className="text-xs text-neutral-500 ml-2">extends {pattern.extends}</span>
                  )}
                  {isManuallyEdited && (
                    <span className="ml-2 text-xs text-amber-400">✎ editado</span>
                  )}
                </div>
                <button
                  onClick={() => openEdit(pattern)}
                  aria-label="editar"
                  className="text-neutral-500 hover:text-neutral-200 flex items-center gap-1 text-xs px-2 py-1 rounded hover:bg-neutral-700"
                >
                  <Edit2 size={12} /> editar
                </button>
              </div>
              <div className="px-4 pb-3">
                <JsonView
                  data={pattern.implementation}
                  shouldExpandNode={allExpanded}
                  style={defaultStyles}
                />
              </div>
            </div>
          )
        })}
      </div>

      {/* Edit Modal */}
      {editState && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
        >
          <div className="bg-neutral-900 border border-neutral-700 rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between px-5 py-4 border-b border-neutral-700">
              <h3 className="text-sm font-semibold">Editar pattern: {editState.pattern.id}</h3>
              <button onClick={closeEdit} className="text-neutral-400 hover:text-neutral-200">
                <X size={18} />
              </button>
            </div>
            <div className="flex-1 p-4 overflow-auto">
              <textarea
                value={editState.jsonText}
                onChange={(e) => setEditState((s) => s ? { ...s, jsonText: e.target.value, error: null } : s)}
                className="w-full h-64 bg-neutral-950 border border-neutral-700 rounded px-3 py-2 text-xs font-mono resize-none focus:outline-none focus:border-neutral-500"
                spellCheck={false}
              />
              {editState.error && (
                <p className="text-red-400 text-xs mt-2">{editState.error}</p>
              )}
            </div>
            <div className="flex justify-end gap-2 px-5 py-3 border-t border-neutral-700">
              <button onClick={closeEdit} className="px-3 py-1.5 text-sm rounded bg-neutral-700 hover:bg-neutral-600">
                Cancelar
              </button>
              <button
                onClick={handleSave}
                disabled={editState.saving}
                className="px-3 py-1.5 text-sm rounded bg-accent text-neutral-900 font-semibold disabled:opacity-40"
              >
                {editState.saving ? "Guardando..." : "Guardar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run, verify pass**

```bash
cd frontend && npm test -- StyleGuideViewer
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Training/StyleGuideViewer.tsx frontend/tests/StyleGuideViewer.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): StyleGuideViewer — JSON tree via react-json-view-lite + per-pattern edit modal

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Create AnalysisProgressModal.tsx

**Files:**
- Create: `frontend/src/pages/Training/AnalysisProgressModal.tsx`
- Create: `frontend/tests/AnalysisProgressModal.test.tsx`

- [ ] **Step 1: Failing tests**

Create `frontend/tests/AnalysisProgressModal.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import AnalysisProgressModal from "../src/pages/Training/AnalysisProgressModal"

const baseJob = {
  jobId: "job-1",
  progress: 50,
  status: "running" as const,
  message: "Analizando slide 5 de 10...",
}

describe("AnalysisProgressModal", () => {
  it("renders running state with spinner and progress message", () => {
    render(<AnalysisProgressModal job={baseJob} onClose={vi.fn()} />)
    expect(screen.getByText(/Analizando slide 5 de 10/i)).toBeInTheDocument()
    expect(screen.getByText(/50%/)).toBeInTheDocument()
    // Spinner present — check for an aria-busy element or spinner class
    expect(screen.getByRole("status")).toBeInTheDocument()
  })

  it("renders done state with cost preview and close button", () => {
    const doneJob = {
      ...baseJob,
      progress: 100,
      status: "done" as const,
      message: "Análisis completado.",
      resultSummary: {
        patterns_valid: 12,
        patterns_dropped: 1,
        patterns_repaired: 2,
        estimated_cost_usd: 0.22,
      },
    }
    render(<AnalysisProgressModal job={doneJob} onClose={vi.fn()} />)
    expect(screen.getByText(/12 patterns válidos/i)).toBeInTheDocument()
    expect(screen.getByText(/\$0\.22/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /cerrar/i })).toBeInTheDocument()
  })

  it("renders error state with error message", () => {
    const errorJob = {
      ...baseJob,
      progress: 0,
      status: "error" as const,
      message: "Error: JSON inválido del modelo.",
    }
    render(<AnalysisProgressModal job={errorJob} onClose={vi.fn()} />)
    expect(screen.getByText(/Error: JSON inválido/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /cerrar/i })).toBeInTheDocument()
  })

  it("calls onClose when close button clicked on done state", async () => {
    const onClose = vi.fn()
    const doneJob = {
      ...baseJob, progress: 100, status: "done" as const, message: "Listo",
      resultSummary: { patterns_valid: 5, patterns_dropped: 0, patterns_repaired: 0 },
    }
    render(<AnalysisProgressModal job={doneJob} onClose={onClose} />)
    await userEvent.click(screen.getByRole("button", { name: /cerrar/i }))
    expect(onClose).toHaveBeenCalled()
  })

  it("does not show close button while running", () => {
    render(<AnalysisProgressModal job={baseJob} onClose={vi.fn()} />)
    expect(screen.queryByRole("button", { name: /cerrar/i })).toBeNull()
  })
})
```

- [ ] **Step 2: Run failing**

```bash
cd frontend && npm test -- AnalysisProgressModal
```

Expected: import errors.

- [ ] **Step 3: Implement AnalysisProgressModal.tsx**

Create `frontend/src/pages/Training/AnalysisProgressModal.tsx`:

```tsx
import { CheckCircle, AlertCircle } from "lucide-react"

interface ResultSummary {
  patterns_valid: number
  patterns_dropped: number
  patterns_repaired: number
  estimated_cost_usd?: number
}

interface AnalysisJobState {
  jobId: string
  progress: number
  status: "running" | "done" | "error"
  message: string
  resultSummary?: ResultSummary
  error?: string
}

interface Props {
  job: AnalysisJobState
  onClose(): void
}

export default function AnalysisProgressModal({ job, onClose }: Props) {
  const isDone = job.status === "done"
  const isError = job.status === "error"
  const isRunning = job.status === "running"

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-neutral-900 border border-neutral-700 rounded-xl shadow-2xl w-full max-w-md p-6">
        {/* Title */}
        <div className="flex items-center gap-3 mb-4">
          {isRunning && (
            <div
              role="status"
              aria-label="Analizando"
              className="w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full animate-spin"
            />
          )}
          {isDone && <CheckCircle size={20} className="text-green-400" />}
          {isError && <AlertCircle size={20} className="text-red-400" />}
          <h3 className="text-sm font-semibold">
            {isRunning && "Analizando corpus con AI..."}
            {isDone && "Análisis completado"}
            {isError && "Error en el análisis"}
          </h3>
        </div>

        {/* Progress bar (running only) */}
        {isRunning && (
          <div className="mb-4">
            <div className="w-full bg-neutral-800 rounded-full h-2 mb-2">
              <div
                className="bg-purple-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${job.progress}%` }}
              />
            </div>
            <p className="text-xs text-neutral-400">{job.progress}% — {job.message}</p>
          </div>
        )}

        {/* Status message (done/error) */}
        {!isRunning && (
          <p className={`text-sm mb-4 ${isError ? "text-red-300" : "text-neutral-300"}`}>
            {job.message}
          </p>
        )}

        {/* Result summary (done only) */}
        {isDone && job.resultSummary && (
          <div className="bg-neutral-800 rounded-lg p-4 mb-4 text-sm space-y-1">
            <div className="flex justify-between">
              <span className="text-neutral-400">Patterns válidos</span>
              <span className="font-semibold text-green-400">{job.resultSummary.patterns_valid} patterns válidos</span>
            </div>
            {job.resultSummary.patterns_dropped > 0 && (
              <div className="flex justify-between">
                <span className="text-neutral-400">Eliminados (inválidos)</span>
                <span className="text-amber-400">{job.resultSummary.patterns_dropped}</span>
              </div>
            )}
            {job.resultSummary.patterns_repaired > 0 && (
              <div className="flex justify-between">
                <span className="text-neutral-400">Reparados</span>
                <span className="text-amber-400">{job.resultSummary.patterns_repaired}</span>
              </div>
            )}
            {job.resultSummary.estimated_cost_usd !== undefined && (
              <div className="flex justify-between pt-1 border-t border-neutral-700 mt-2">
                <span className="text-neutral-400">Costo estimado</span>
                <span className="font-mono">${job.resultSummary.estimated_cost_usd.toFixed(2)}</span>
              </div>
            )}
          </div>
        )}

        {/* Close button (done/error) */}
        {(isDone || isError) && (
          <div className="flex justify-end">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm rounded bg-neutral-700 hover:bg-neutral-600 font-medium"
            >
              Cerrar
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run, verify pass**

```bash
cd frontend && npm test -- AnalysisProgressModal
```

Expected: 5 tests PASS.

- [ ] **Step 5: Run full frontend test suite**

```bash
cd frontend && npm test
```

Expected: all tests PASS (no regressions).

- [ ] **Step 6: Commit**

```bash
git add \
  frontend/src/pages/Training/AnalysisProgressModal.tsx \
  frontend/tests/AnalysisProgressModal.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): AnalysisProgressModal — spinner + cost preview + error display

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Tag milestone:

```bash
git tag m6.9
```

---

## M6.9 Done When

- `react-json-view-lite` installed and importable in frontend
- `frontend/src/api/training.ts` fully rewritten with M6 endpoint types: `listCorpus`, `addCorpusPPT`, `deleteCorpusPPT`, `triggerAnalyzeWithAI`, `getAnalysisStatus`, `getStyleGuide`, `putPattern`, `clearCache`
- `frontend/src/store/styleGuide.ts` zustand slice manages corpus list, style guide, and analysis job state; `analyzeWithAI()` polls `getAnalysisStatus` until done/error then reloads style guide
- `frontend/src/pages/Training/TrainingPage.tsx` fully rewritten: flat corpus list with add/delete, style guide section with pattern count and chart types, "Re-analizar con AI" button, shows StyleGuideViewer on toggle
- `frontend/src/pages/Training/StyleGuideViewer.tsx` renders global info + per-pattern JSON tree via `react-json-view-lite`; per-pattern "editar" button opens textarea modal; save calls `putPattern`; invalid JSON shows inline error
- `frontend/src/pages/Training/AnalysisProgressModal.tsx` renders running spinner + progress bar, done state with result summary + cost, error state with message; close button only shown on done/error
- All frontend tests pass; no regressions from M6.8 or prior
- Git tag `m6.9` created
