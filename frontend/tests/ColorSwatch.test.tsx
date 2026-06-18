import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import ColorSwatch from "../src/components/ColorPicker/ColorSwatch"

describe("ColorSwatch", () => {
  it("renders a button with the given background color", () => {
    render(<ColorSwatch color="#7F7F7F" onSelect={vi.fn()} />)
    const btn = screen.getByRole("button")
    expect(btn).toBeInTheDocument()
    // Inner color square should carry inline style
    const square = btn.querySelector("[style]")
    expect(square).not.toBeNull()
  })

  it("shows selected ring when isSelected true", () => {
    render(<ColorSwatch color="#FFC000" onSelect={vi.fn()} isSelected />)
    const btn = screen.getByRole("button")
    expect(btn.className).toMatch(/ring/)
  })

  it("does not show selected ring when isSelected false", () => {
    render(<ColorSwatch color="#FFC000" onSelect={vi.fn()} isSelected={false} />)
    const btn = screen.getByRole("button")
    expect(btn.className).not.toMatch(/ring-2/)
  })

  it("calls onSelect with color when clicked", async () => {
    const onSelect = vi.fn()
    render(<ColorSwatch color="#404040" onSelect={onSelect} />)
    await userEvent.click(screen.getByRole("button"))
    expect(onSelect).toHaveBeenCalledWith("#404040")
  })

  it("shows tooltip with hex color on hover (aria-label)", () => {
    render(<ColorSwatch color="#D9D9D9" onSelect={vi.fn()} />)
    expect(screen.getByRole("button")).toHaveAttribute("aria-label", expect.stringContaining("#D9D9D9"))
  })
})
