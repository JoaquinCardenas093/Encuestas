import { describe, expect, it, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import ConfigPanel from "../src/pages/Editor/ConfigPanel"
import { useProjectStore } from "../src/store/project"
import type { ParsedDB } from "../src/types"

const DB: ParsedDB = {
  questions: [{ id: "q1", code: "P1", text: "?", options: ["a"], confidence: 1.0 }],
  breakdowns: [{ id: "general", label: "General", categories: ["Total"] }],
  sample_size: 500,
  data_blocks: { counts_cols: [], pct_row_cols: [], pct_col_cols: [] },
}

describe("ConfigPanel", () => {
  beforeEach(() => {
    useProjectStore.setState({ state: null, parsedDb: DB })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    useProjectStore.getState().addSeparator("Sec")
    useProjectStore.getState().addShell()
  })

  it("shows title (read-only) for shell from separator", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    render(<ConfigPanel slideId={shellId} />)
    expect(screen.getByDisplayValue("Sec")).toBeDisabled()
  })

  it("allows separator title edit", () => {
    const sepId = useProjectStore.getState().state!.slides[0].id
    render(<ConfigPanel slideId={sepId} />)
    expect(screen.getByDisplayValue("Sec")).not.toBeDisabled()
  })

  it("clicking + Chart opens modal", async () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    render(<ConfigPanel slideId={shellId} />)
    await userEvent.click(screen.getByRole("button", { name: /Chart/i }))
    expect(screen.getByText(/Agregar chart/i)).toBeInTheDocument()
  })

  it("chart list shows added charts with type override select", async () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addCharts(shellId, "q1", ["general"], "PIE")
    render(<ConfigPanel slideId={shellId} />)
    const selects = screen.getAllByRole("combobox")
    expect(selects.some((sel) => (sel as HTMLSelectElement).value === "PIE")).toBe(true)
  })
})
