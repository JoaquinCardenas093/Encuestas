import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import ColorPicker from "../src/components/ColorPicker/ColorPicker"

// Mock styleGuide store
vi.mock("../src/store/styleGuide", () => ({
  useStyleGuideStore: (sel: (s: unknown) => unknown) => sel({
    styleGuide: {
      global: { suggested_palette: ["#7F7F7F", "#BFBFBF", "#FFC000"] },
    },
  }),
}))

// Mock fetch for recent colors (config endpoint)
const mockFetch = vi.fn()
vi.stubGlobal("fetch", mockFetch)

beforeEach(() => {
  mockFetch.mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ recent_colors: ["#404040", "#D9D9D9"] }),
  })
})

describe("ColorPicker", () => {
  it("renders when open=true", () => {
    render(<ColorPicker open value="#7F7F7F" onChange={vi.fn()} onClose={vi.fn()} />)
    expect(screen.getByText(/Sugeridas del training/i)).toBeInTheDocument()
  })

  it("does not render when open=false", () => {
    render(<ColorPicker open={false} value="#7F7F7F" onChange={vi.fn()} onClose={vi.fn()} />)
    expect(screen.queryByText(/Sugeridas del training/i)).toBeNull()
  })

  it("renders Defaults row with built-in colors", () => {
    render(<ColorPicker open value="#7F7F7F" onChange={vi.fn()} onClose={vi.fn()} />)
    expect(screen.getByText(/Defaults/i)).toBeInTheDocument()
  })

  it("renders Recientes row from config", async () => {
    render(<ColorPicker open value="#7F7F7F" onChange={vi.fn()} onClose={vi.fn()} />)
    await waitFor(() => expect(screen.getByText(/Recientes/i)).toBeInTheDocument())
  })

  it("calls onChange when a swatch is clicked", async () => {
    const onChange = vi.fn()
    render(<ColorPicker open value="#7F7F7F" onChange={onChange} onClose={vi.fn()} />)
    // Click the first suggested palette swatch (#7F7F7F)
    const swatches = screen.getAllByRole("button", { name: /Seleccionar color/i })
    await userEvent.click(swatches[0])
    expect(onChange).toHaveBeenCalled()
  })

  it("calls onChange when valid hex entered and OK clicked", async () => {
    const onChange = vi.fn()
    render(<ColorPicker open value="" onChange={onChange} onClose={vi.fn()} />)
    const input = screen.getByRole("textbox")
    await userEvent.clear(input)
    await userEvent.type(input, "FFC000")
    await userEvent.click(screen.getByRole("button", { name: /OK/i }))
    expect(onChange).toHaveBeenCalledWith("#FFC000")
  })

  it("calls onChange with empty string when Auto clicked", async () => {
    const onChange = vi.fn()
    render(<ColorPicker open value="#7F7F7F" onChange={onChange} onClose={vi.fn()} />)
    await userEvent.click(screen.getByRole("button", { name: /Auto/i }))
    expect(onChange).toHaveBeenCalledWith("")
  })

  it("calls onClose when Cancelar clicked", async () => {
    const onClose = vi.fn()
    render(<ColorPicker open value="#7F7F7F" onChange={vi.fn()} onClose={onClose} />)
    await userEvent.click(screen.getByRole("button", { name: /Cancelar/i }))
    expect(onClose).toHaveBeenCalled()
  })
})
