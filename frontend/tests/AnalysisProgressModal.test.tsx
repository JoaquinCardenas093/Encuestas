import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import AnalysisProgressModal from "../src/pages/Training/AnalysisProgressModal"

const baseJob = {
  jobId: "job-1",
  progress: 50,
  status: "running" as const,
  message: "Analizando slide 5 de 10...",
}

describe("AnalysisProgressModal", () => {
  it("renders running state with spinner and progress message", () => {
    render(<AnalysisProgressModal job={baseJob} onClose={vi.fn()} />)
    expect(screen.getByText(/Analizando slide 5 de 10/i)).toBeInTheDocument()
    expect(screen.getByText(/50%/)).toBeInTheDocument()
    // Spinner present — check for an aria-busy element or spinner class
    expect(screen.getByRole("status")).toBeInTheDocument()
  })

  it("renders done state with cost preview and close button", () => {
    const doneJob = {
      ...baseJob,
      progress: 100,
      status: "done" as const,
      message: "Análisis completado.",
      resultSummary: {
        patterns_valid: 12,
        patterns_dropped: 1,
        patterns_repaired: 2,
        estimated_cost_usd: 0.22,
      },
    }
    render(<AnalysisProgressModal job={doneJob} onClose={vi.fn()} />)
    expect(screen.getByText(/12 patterns válidos/i)).toBeInTheDocument()
    expect(screen.getByText(/\$0\.22/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /cerrar/i })).toBeInTheDocument()
  })

  it("renders error state with error message", () => {
    const errorJob = {
      ...baseJob,
      progress: 0,
      status: "error" as const,
      message: "Error: JSON inválido del modelo.",
    }
    render(<AnalysisProgressModal job={errorJob} onClose={vi.fn()} />)
    expect(screen.getByText(/Error: JSON inválido/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /cerrar/i })).toBeInTheDocument()
  })

  it("calls onClose when close button clicked on done state", async () => {
    const onClose = vi.fn()
    const doneJob = {
      ...baseJob, progress: 100, status: "done" as const, message: "Listo",
      resultSummary: { patterns_valid: 5, patterns_dropped: 0, patterns_repaired: 0 },
    }
    render(<AnalysisProgressModal job={doneJob} onClose={onClose} />)
    await userEvent.click(screen.getByRole("button", { name: /cerrar/i }))
    expect(onClose).toHaveBeenCalled()
  })

  it("does not show close button while running", () => {
    render(<AnalysisProgressModal job={baseJob} onClose={vi.fn()} />)
    expect(screen.queryByRole("button", { name: /cerrar/i })).toBeNull()
  })
})
