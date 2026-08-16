import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import AddChartModal from "../src/pages/Editor/modals/AddChartModal"
import type { ParsedDB } from "../src/types"

const DB: ParsedDB = {
  questions: [
    { id: "q1", code: "P1", text: "¿Usa el producto?", options: ["Sí", "No"], confidence: 1.0 },
  ],
  breakdowns: [
    { id: "general", label: "General", categories: ["Total"] },
    { id: "sexo", label: "Sexo", categories: ["H", "M"] },
  ],
  sample_size: 500,
  data_blocks: { counts_cols: [], pct_row_cols: [], pct_col_cols: [] },
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe("AddChartModal — M6 chart types", () => {
  it("shows chart type options sourced from builtin list", async () => {
    render(<AddChartModal open db={DB} onClose={vi.fn()} onApply={vi.fn()} />)
    const select = screen.getByRole("combobox", { name: /tipo de chart/i })
    expect(select).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "PIE" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "BAR_HORIZONTAL" })).toBeInTheDocument()
    // Grouped types hidden until a real (non-general) breakdown is selected
    expect(screen.queryByRole("option", { name: "PIE_GROUPED" })).toBeNull()
    expect(screen.queryByRole("option", { name: "BAR_HORIZONTAL_GROUPED" })).toBeNull()
    // TABLE_WITH_MINIBARS is hidden until a real (non-general) breakdown is selected
    expect(screen.queryByRole("option", { name: "TABLE_WITH_MINIBARS" })).toBeNull()
    // Select a real breakdown — all segmented types should now appear
    await userEvent.click(screen.getByLabelText(/Sexo/i))
    expect(screen.getByRole("option", { name: "PIE_GROUPED" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "BAR_HORIZONTAL_GROUPED" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "TABLE_WITH_MINIBARS" })).toBeInTheDocument()
  })

  it("shows only general chart types when no real breakdown selected", () => {
    render(<AddChartModal open db={DB} onClose={vi.fn()} onApply={vi.fn()} />)
    // General types (no real breakdown): PIE, BAR_HORIZONTAL
    expect(screen.getByRole("option", { name: "PIE" })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "BAR_HORIZONTAL" })).toBeInTheDocument()
    expect(screen.queryByRole("option", { name: "PIE_GROUPED" })).toBeNull()
    expect(screen.queryByRole("option", { name: "BAR_HORIZONTAL_GROUPED" })).toBeNull()
    expect(screen.queryByRole("option", { name: "TABLE_WITH_MINIBARS" })).toBeNull()
  })
})
