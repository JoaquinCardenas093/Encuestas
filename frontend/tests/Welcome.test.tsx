import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import Welcome from "../src/pages/Welcome"

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

  it("does not show the training-corpus banner", () => {
    render(
      <MemoryRouter>
        <Welcome />
      </MemoryRouter>,
    )
    expect(screen.queryByText(/Cargá training PPTs/i)).toBeNull()
    expect(screen.queryByRole("link", { name: /Configurar/i })).toBeNull()
  })
})
