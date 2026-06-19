import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import AddAnalysisModal from "../src/pages/Editor/modals/AddAnalysisModal"
import type { Slide, ParsedDB } from "../src/types"

const DB: ParsedDB = {
  questions: [{ id: "q1", code: "P1", text: "?", options: ["a"], confidence: 1.0 }],
  breakdowns: [{ id: "general", label: "General", categories: ["Total"] }],
  sample_size: 500,
  data_blocks: { counts_cols: [], pct_row_cols: [], pct_col_cols: [] },
}
const SLIDE: Slide = {
  id: "sl1", type: "shell", title: "Sec",
  charts: [{ id: "c1", question_id: "q1", breakdown_ids: [], chart_type: "PIE", show_legend: false, grid_cols: null, title: null, colors: [] }],
  analyses: [], auto_notes: null,
}

describe("AddAnalysisModal", () => {
  it("renders scope radios", () => {
    render(<AddAnalysisModal open slide={SLIDE} db={DB} onClose={() => {}} onAdd={() => {}} />)
    expect(screen.getByLabelText(/slide/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/question/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/chart/i)).toBeInTheDocument()
  })

  it("generating calls api and shows text", async () => {
    const onAdd = vi.fn()
    vi.mock("../src/api/client", () => ({
      generateAnalysis: () => Promise.resolve({ text: "Generated text", fallback: false }),
    }))
    render(<AddAnalysisModal open slide={SLIDE} db={DB} onClose={() => {}} onAdd={onAdd} />)
    await userEvent.click(screen.getByRole("button", { name: /Generar/i }))
    // wait for textarea to fill
    await screen.findByDisplayValue(/Generated text/i)
  })
})
