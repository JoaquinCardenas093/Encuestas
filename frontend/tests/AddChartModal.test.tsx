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

  it("Apply calls onApply with selected", async () => {
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
    await userEvent.click(screen.getByLabelText(/General/i))
    await userEvent.click(screen.getByRole("button", { name: /Aplicar/i }))
    expect(result.questionId).toBe("q1")
    expect(result.breakdownIds).toContain("general")
  })
})
