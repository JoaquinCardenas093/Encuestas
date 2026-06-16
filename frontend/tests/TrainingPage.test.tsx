import { describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import TrainingPage from "../src/pages/Training/TrainingPage"

vi.mock("../src/api/training", () => ({
  listTraining: vi.fn(() => Promise.resolve({ pptxs: [{ filename: "deck_a.pptx", added_at: "2026-06-16T20:00:00Z", layouts_extracted: 5, status: "ok" }], bank_size: 5 })),
  addTraining: vi.fn(),
  deleteTraining: vi.fn(),
  reprocessTraining: vi.fn(),
  getBank: vi.fn(() => Promise.resolve({ layouts: [], source_pptxs: [] })),
}))

describe("TrainingPage", () => {
  it("lists training pptxs", async () => {
    render(<TrainingPage />)
    await waitFor(() => expect(screen.getByText("deck_a.pptx")).toBeInTheDocument())
    expect(screen.getByText(/Banco: 5 layouts/i)).toBeInTheDocument()
  })
})
