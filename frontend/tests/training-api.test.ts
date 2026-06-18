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
