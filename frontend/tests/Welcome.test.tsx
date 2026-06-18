import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import Welcome from "../src/pages/Welcome"

// Mock styleGuide store
const mockStyleGuide = {
  styleGuide: null as null | { is_builtin: boolean },
  corpus: [] as unknown[],
  isLoading: false,
  loadStyleGuide: vi.fn(),
  loadCorpus: vi.fn(),
}

vi.mock("../src/store/styleGuide", () => ({
  useStyleGuideStore: (sel: (s: typeof mockStyleGuide) => unknown) => sel(mockStyleGuide),
}))

// Mock project store (basic)
vi.mock("../src/store/project", () => ({
  useProjectStore: (sel: (s: unknown) => unknown) =>
    sel({
      state: null,
      setNewProject: vi.fn(),
      loadProjectState: vi.fn(),
      setParsedDb: vi.fn(),
      setTemplateInfo: vi.fn(),
    }),
}))

// Mock hooks
vi.mock("../src/hooks/useUpload", () => ({
  useFileUpload: () => ({ upload: vi.fn(), loading: false, error: null }),
}))

// Mock api client
vi.mock("../src/api/client", () => ({
  parseXlsx: vi.fn(),
  parseTemplate: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
  mockStyleGuide.styleGuide = null
  mockStyleGuide.corpus = []
})

describe("WelcomePage", () => {
  it("renders without training set selector", () => {
    render(
      <MemoryRouter>
        <Welcome />
      </MemoryRouter>,
    )
    expect(screen.queryByText(/training set/i)).toBeNull()
    expect(screen.queryByText(/Seleccionar set/i)).toBeNull()
  })

  it("shows empty-corpus banner when corpus is empty and no style guide", () => {
    mockStyleGuide.styleGuide = null
    mockStyleGuide.corpus = []
    render(
      <MemoryRouter>
        <Welcome />
      </MemoryRouter>,
    )
    expect(screen.getByText(/Cargá training PPTs/i)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Configurar/i })).toBeInTheDocument()
  })

  it("shows builtin banner when style guide is_builtin = true", () => {
    mockStyleGuide.styleGuide = { is_builtin: true }
    mockStyleGuide.corpus = [{ filename: "a.pptx" }]
    render(
      <MemoryRouter>
        <Welcome />
      </MemoryRouter>,
    )
    expect(screen.getByText(/Cargá training PPTs/i)).toBeInTheDocument()
  })

  it("does NOT show banner when style guide is AI-generated and corpus has PPTs", () => {
    mockStyleGuide.styleGuide = { is_builtin: false }
    mockStyleGuide.corpus = [{ filename: "a.pptx" }]
    render(
      <MemoryRouter>
        <Welcome />
      </MemoryRouter>,
    )
    expect(screen.queryByText(/Cargá training PPTs/i)).toBeNull()
  })

  it("calls loadStyleGuide and loadCorpus on mount", () => {
    render(
      <MemoryRouter>
        <Welcome />
      </MemoryRouter>,
    )
    expect(mockStyleGuide.loadStyleGuide).toHaveBeenCalled()
    expect(mockStyleGuide.loadCorpus).toHaveBeenCalled()
  })
})
