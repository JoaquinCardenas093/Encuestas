import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import AddChartModal from "../src/pages/Editor/modals/AddChartModal"
import type { ParsedDB } from "../src/types"


const DB: ParsedDB = {
  questions: [
    { id: "q1", code: "P1", text: "¿X?", options: ["a", "b"], confidence: 1.0 },
    { id: "q2", code: "P2", text: "¿Y?", options: ["c"], confidence: 1.0 },
  ],
  breakdowns: [
    { id: "general", label: "General", categories: ["Total"] },
    { id: "sexo", label: "Sexo", categories: ["H", "M"] },
  ],
  sample_size: 500,
  data_blocks: { counts_cols: [], pct_row_cols: [], pct_col_cols: [] },
}

describe("AddChartModal", () => {
  it("renders question + breakdown selectors", () => {
    render(<AddChartModal open onClose={() => {}} onApply={() => {}} db={DB} />)
    expect(screen.getByLabelText(/Pregunta/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/General/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Sexo/i)).toBeInTheDocument()
  })

  it("Apply calls onApply with selected (real breakdowns only)", async () => {
    let result: any = null
    render(
      <AddChartModal
        open
        onClose={() => {}}
        onApply={(r) => {
          result = r
        }}
        db={DB}
      />,
    )
    await userEvent.click(screen.getByLabelText(/Sexo/i))
    await userEvent.click(screen.getByRole("button", { name: /Aplicar/i }))
    expect(result.questionId).toBe("q1")
    expect(result.breakdownIds).toContain("sexo")
    expect(result.breakdownIds).not.toContain("general")
  })
})

describe("AddChartModal — TABLE_WITH_MINIBARS visibility", () => {
  const baseDb = {
    questions: [{ id: "q1", code: "Q1", text: "Test", options: ["Sí", "No"], confidence: 0.9 }],
    breakdowns: [
      { id: "general", label: "General", categories: ["Total"] },
      { id: "edad", label: "Rango de edad", categories: ["18-39", "40-59"] },
      { id: "sexo", label: "Sexo", categories: ["H", "M"] },
    ],
    sample_size: 500,
    data_blocks: { counts_cols: [], pct_row_cols: [], pct_col_cols: [] },
  }

  it("one real breakdown shows all 5 chart_types", async () => {
    const u = userEvent.setup()
    render(<AddChartModal open={true} onClose={() => {}} onApply={() => {}} db={baseDb as any} />)
    await u.click(screen.getByLabelText(/Rango de edad/i))
    const dropdown = screen.getByLabelText(/Tipo de chart/i) as HTMLSelectElement
    const values = Array.from(dropdown.options).map((o) => o.value)
    expect(values).toEqual([
      "PIE", "PIE_GROUPED",
      "BAR_HORIZONTAL", "BAR_HORIZONTAL_GROUPED",
      "TABLE_WITH_MINIBARS",
    ])
  })

  it("no real breakdown hides grouped types and TABLE", () => {
    render(<AddChartModal open={true} onClose={() => {}} onApply={() => {}} db={baseDb as any} />)
    const dropdown = screen.getByLabelText(/Tipo de chart/i) as HTMLSelectElement
    const values = Array.from(dropdown.options).map((o) => o.value)
    expect(values).not.toContain("TABLE_WITH_MINIBARS")
    expect(values).not.toContain("PIE_GROUPED")
    expect(values).not.toContain("BAR_HORIZONTAL_GROUPED")
  })

  it("show_legend checkbox renders only for BAR_HORIZONTAL_GROUPED or TABLE_WITH_MINIBARS", async () => {
    const u = userEvent.setup()
    render(<AddChartModal open={true} onClose={() => {}} onApply={() => {}} db={baseDb as any} />)
    expect(screen.queryByLabelText(/Mostrar leyenda/i)).toBeNull()
    await u.click(screen.getByLabelText(/Rango de edad/i))
    const dropdown = screen.getByLabelText(/Tipo de chart/i) as HTMLSelectElement
    await u.selectOptions(dropdown, "BAR_HORIZONTAL_GROUPED")
    expect(screen.getByLabelText(/Mostrar leyenda/i)).toBeInTheDocument()
    await u.selectOptions(dropdown, "PIE_GROUPED")
    expect(screen.queryByLabelText(/Mostrar leyenda/i)).toBeNull()
  })

  it("grid_cols input renders only for PIE_GROUPED", async () => {
    const u = userEvent.setup()
    render(<AddChartModal open={true} onClose={() => {}} onApply={() => {}} db={baseDb as any} />)
    await u.click(screen.getByLabelText(/Rango de edad/i))
    const dropdown = screen.getByLabelText(/Tipo de chart/i) as HTMLSelectElement
    await u.selectOptions(dropdown, "PIE_GROUPED")
    expect(screen.getByLabelText(/Columnas por fila/i)).toBeInTheDocument()
    await u.selectOptions(dropdown, "PIE")
    expect(screen.queryByLabelText(/Columnas por fila/i)).toBeNull()
  })

  it("apply sends new fields", async () => {
    const u = userEvent.setup()
    const applied: any[] = []
    render(<AddChartModal open={true} onClose={() => {}} onApply={(r) => applied.push(r)} db={baseDb as any} />)
    await u.click(screen.getByLabelText(/Rango de edad/i))
    const dropdown = screen.getByLabelText(/Tipo de chart/i) as HTMLSelectElement
    await u.selectOptions(dropdown, "BAR_HORIZONTAL_GROUPED")
    await u.type(screen.getByPlaceholderText(/Ej: Plazo/i), "Plazo del crédito")
    await u.click(screen.getByLabelText(/Mostrar leyenda/i))
    await u.click(screen.getByText(/Aplicar/i))
    expect(applied[0].title).toBe("Plazo del crédito")
    expect(applied[0].show_legend).toBe(true)
    expect(applied[0].chartType).toBe("BAR_HORIZONTAL_GROUPED")
  })

  it("hides TABLE_WITH_MINIBARS when no breakdown is selected", () => {
    render(<AddChartModal open={true} onClose={() => {}} onApply={() => {}} db={baseDb as any} />)
    const dropdown = screen.getByLabelText(/Tipo de chart/i) as HTMLSelectElement
    const optionTexts = Array.from(dropdown.options).map((o) => o.value)
    expect(optionTexts).not.toContain("TABLE_WITH_MINIBARS")
  })

  it("no real breakdown hides TABLE_WITH_MINIBARS from dropdown", () => {
    render(<AddChartModal open={true} onClose={() => {}} onApply={() => {}} db={baseDb as any} />)
    const dropdown = screen.getByLabelText(/Tipo de chart/i) as HTMLSelectElement
    const values = Array.from(dropdown.options).map((o) => o.value)
    expect(values).not.toContain("TABLE_WITH_MINIBARS")
  })

  it("two real breakdowns locks dropdown to TABLE_WITH_MINIBARS", async () => {
    const u = userEvent.setup()
    render(<AddChartModal open={true} onClose={() => {}} onApply={() => {}} db={baseDb as any} />)
    await u.click(screen.getByLabelText(/Rango de edad/i))
    await u.click(screen.getByLabelText(/Sexo/i))
    const dropdown = screen.getByLabelText(/Tipo de chart/i) as HTMLSelectElement
    expect(dropdown.disabled).toBe(true)
    const values = Array.from(dropdown.options).map((o) => o.value)
    expect(values).toEqual(["TABLE_WITH_MINIBARS"])
  })

  it("apply creates one chart with breakdown_ids list", async () => {
    const u = userEvent.setup()
    const applied: any[] = []
    render(<AddChartModal open={true} onClose={() => {}} onApply={(r) => applied.push(r)} db={baseDb as any} />)
    await u.click(screen.getByLabelText(/Rango de edad/i))
    await u.click(screen.getByLabelText(/Sexo/i))
    await u.click(screen.getByText(/Aplicar/i))
    expect(applied.length).toBe(1)
    expect(applied[0].breakdownIds).toEqual(["edad", "sexo"])
    expect(applied[0].chartType).toBe("TABLE_WITH_MINIBARS")
  })
})
