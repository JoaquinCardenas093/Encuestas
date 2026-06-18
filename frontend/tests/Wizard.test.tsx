import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import XlsxVerifyWizard from "../src/pages/Wizard/XlsxVerifyWizard"
import { useProjectStore } from "../src/store/project"
import type { ParsedDB } from "../src/types"

const FAKE_DB: ParsedDB = {
  questions: [
    { id: "q1", code: "P1", text: "¿Recuerda?", options: ["Sí", "No"], confidence: 1.0 },
    { id: "q2", code: "P2", text: "$p2.label", options: ["a", "b", "c"], confidence: 1.0 },
  ],
  breakdowns: [
    { id: "general", label: "General", categories: ["Total"] },
    { id: "sexo", label: "Sexo", categories: ["Hombre", "Mujer"] },
  ],
  sample_size: 500,
  data_blocks: { counts_cols: [3, 17], pct_row_cols: [21, 35], pct_col_cols: [41, 55] },
}

describe("XlsxVerifyWizard", () => {
  it("lists questions and breakdowns from store.parsedDb", () => {
    useProjectStore.setState({ parsedDb: FAKE_DB })
    render(
      <MemoryRouter>
        <XlsxVerifyWizard onConfirm={() => {}} />
      </MemoryRouter>,
    )
    expect(screen.getByText(/P1/)).toBeInTheDocument()
    expect(screen.getByText(/¿Recuerda\?/)).toBeInTheDocument()
    expect(screen.getByText(/Sexo/)).toBeInTheDocument()
    expect(screen.getByText("500")).toBeInTheDocument()
  })

  it("Confirm button calls onConfirm", async () => {
    useProjectStore.setState({ parsedDb: FAKE_DB })
    let called = false
    render(
      <MemoryRouter>
        <XlsxVerifyWizard onConfirm={() => { called = true }} />
      </MemoryRouter>,
    )
    await userEvent.click(screen.getByRole("button", { name: /Confirmar/i }))
    expect(called).toBe(true)
  })

  it("renders font dropdown with curated list", () => {
    useProjectStore.setState({ parsedDb: FAKE_DB })
    render(
      <MemoryRouter>
        <XlsxVerifyWizard onConfirm={() => {}} />
      </MemoryRouter>,
    )
    const select = screen.getByLabelText(/Fuente/i) as HTMLSelectElement
    expect(select.options.length).toBeGreaterThan(5)
  })
})
