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
