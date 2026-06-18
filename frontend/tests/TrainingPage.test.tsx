import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
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

// Mock child components to avoid complex rendering
vi.mock("../src/pages/Training/StyleGuideViewer", () => ({
  default: () => <div data-testid="style-guide-viewer">StyleGuideViewer</div>,
}))

vi.mock("../src/pages/Training/AnalysisProgressModal", () => ({
  default: () => <div data-testid="analysis-progress-modal">AnalysisProgressModal</div>,
}))

beforeEach(() => {
  vi.clearAllMocks()
  mockStore.analysisJob = null
  mockStore.isLoading = false
  mockStore.styleGuide = {
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
  }
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
    mockStore.styleGuide = { ...mockStore.styleGuide, is_builtin: true }
    render(<TrainingPage />)
    expect(screen.getByText(/built-in/i)).toBeInTheDocument()
  })
})
