import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import AddChartModal from "../src/pages/Editor/modals/AddChartModal"
import type { ParsedDB } from "../src/types"

// Mock styleGuide store — with AI-generated style guide
const mockStyleGuideWithTypes = {
  styleGuide: {
    available_chart_types: ["PIE", "DONUT", "TABLE_WITH_MINIBARS"],
    global: { suggested_palette: [] },
    is_builtin: false,
  },
  corpus: [{ filename: "a.pptx" }],
}

const mockStyleGuideBuiltin = {
  styleGuide: null,
  corpus: [],
}

let currentMock = mockStyleGuideWithTypes

vi.mock("../src/store/styleGuide", () => ({
  useStyleGuideStore: (sel: (s: typeof mockStyleGuideWithTypes) => unknown) =>
    sel(currentMock as typeof mockStyleGuideWithTypes),
}))

const DB: ParsedDB = {
  questions: [
    { id: "q1", code: "P1", text: "¿Usa el producto?", options: ["Sí", "No"], confidence: 1.0 },
  ],
  breakdowns: [{ id: "general", label: "General", categories: ["Total"] }],
  sample_size: 500,
  data_blocks: { counts_cols: [], pct_row_cols: [], pct_col_cols: [] },
}

beforeEach(() => {
  currentMock = mockStyleGuideWithTypes
})

describe("AddChartModal — M6 chart types", () => {
  it("shows chart type options sourced from styleGuide.available_chart_types", () => {
    render(<AddChartModal open db={DB} onClose={vi.fn()} onApply={vi.fn()} />)
    const select = screen.getByRole("combobox", { name: /tipo de chart/i })
    expect(select).toBeInTheDocument()
    expect(screen.getByRole("option", { name: /PIE/i })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: /DONUT/i })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: /TABLE_WITH_MINIBARS/i })).toBeInTheDocument()
    // BAR_HORIZONTAL not in styleGuide — should NOT appear
    expect(screen.queryByRole("option", { name: /BAR_HORIZONTAL/i })).toBeNull()
  })

  it("falls back to 5 built-in chart types when styleGuide not loaded", () => {
    currentMock = mockStyleGuideBuiltin as typeof mockStyleGuideWithTypes
    render(<AddChartModal open db={DB} onClose={vi.fn()} onApply={vi.fn()} />)
    // Should have PIE as at minimum (fallback)
    expect(screen.getByRole("option", { name: /PIE/i })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: /DONUT/i })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: /BAR_HORIZONTAL/i })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: /BAR_CLUSTERED/i })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: /COLUMN_CLUSTERED/i })).toBeInTheDocument()
  })

  it("includes ColorPicker trigger button", () => {
    render(<AddChartModal open db={DB} onClose={vi.fn()} onApply={vi.fn()} />)
    // Should have the primary color button (Auto or swatch)
    const colorTriggers = screen.getAllByRole("button", { name: /auto|color/i })
    expect(colorTriggers.length).toBeGreaterThan(0)
  })
})
