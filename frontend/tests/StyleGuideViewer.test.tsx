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

// Mock react-json-view-lite since it may have CSS import issues in test env
vi.mock("react-json-view-lite", () => ({
  JsonView: ({ data }: { data: unknown }) => (
    <pre data-testid="json-view">{JSON.stringify(data)}</pre>
  ),
  allExpanded: () => true,
  defaultStyles: {},
}))

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
