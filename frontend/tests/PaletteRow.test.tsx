import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import PaletteRow from "../src/components/ColorPicker/PaletteRow"

const COLORS = ["#7F7F7F", "#BFBFBF", "#FFC000", "#404040", "#D9D9D9"]

describe("PaletteRow", () => {
  it("renders label", () => {
    render(<PaletteRow label="Defaults" colors={COLORS} onSelect={vi.fn()} />)
    expect(screen.getByText("Defaults")).toBeInTheDocument()
  })

  it("renders one swatch per color", () => {
    render(<PaletteRow label="Sugeridas" colors={COLORS} onSelect={vi.fn()} />)
    const buttons = screen.getAllByRole("button")
    expect(buttons).toHaveLength(COLORS.length)
  })

  it("calls onSelect with the correct color when a swatch is clicked", async () => {
    const onSelect = vi.fn()
    render(<PaletteRow label="Defaults" colors={COLORS} onSelect={onSelect} />)
    await userEvent.click(screen.getByLabelText(/Seleccionar color #FFC000/i))
    expect(onSelect).toHaveBeenCalledWith("#FFC000")
  })

  it("marks selected color swatch", () => {
    render(<PaletteRow label="Defaults" colors={COLORS} onSelect={vi.fn()} selectedColor="#BFBFBF" />)
    // The #BFBFBF button should have ring class
    const btn = screen.getByLabelText(/Seleccionar color #BFBFBF/i)
    expect(btn.className).toMatch(/ring/)
  })

  it("renders empty row with no swatches when colors is empty", () => {
    render(<PaletteRow label="Recientes" colors={[]} onSelect={vi.fn()} />)
    const buttons = screen.queryAllByRole("button")
    expect(buttons).toHaveLength(0)
    expect(screen.getByText(/sin recientes/i)).toBeInTheDocument()
  })
})
