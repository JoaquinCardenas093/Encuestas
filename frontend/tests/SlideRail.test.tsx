import { describe, expect, it, beforeEach, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import SlideRail from "../src/pages/Editor/SlideRail"
import { useProjectStore } from "../src/store/project"

describe("SlideRail", () => {
  beforeEach(() => {
    useProjectStore.setState({ state: null })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
  })

  it("disables + Slide when no separator exists", () => {
    render(<SlideRail selectedId={null} onSelect={() => {}} onDelete={() => {}} />)
    const btn = screen.getByRole("button", { name: /^Slide$/i })
    expect(btn).toBeDisabled()
  })

  it("enables + Slide once separator added", async () => {
    useProjectStore.getState().addSeparator("Sec")
    render(<SlideRail selectedId={null} onSelect={() => {}} onDelete={() => {}} />)
    const btn = screen.getByRole("button", { name: /^Slide$/i })
    expect(btn).not.toBeDisabled()
  })

  it("clicking + Separador opens modal", async () => {
    render(<SlideRail selectedId={null} onSelect={() => {}} onDelete={() => {}} />)
    await userEvent.click(screen.getByRole("button", { name: /Separador/i }))
    expect(screen.getByLabelText(/Título sección/i)).toBeInTheDocument()
  })

  it("creating separator adds it to the rail", async () => {
    render(<SlideRail selectedId={null} onSelect={() => {}} onDelete={() => {}} />)
    await userEvent.click(screen.getByRole("button", { name: /Separador/i }))
    await userEvent.type(screen.getByLabelText(/Título sección/i), "Nueva")
    await userEvent.click(screen.getByRole("button", { name: /^Crear$/i }))
    expect(useProjectStore.getState().state!.slides.length).toBe(1)
  })

  it("rail thumbnails distinguish separator vs shell by class", async () => {
    useProjectStore.getState().addSeparator("S")
    useProjectStore.getState().addShell()
    render(<SlideRail selectedId={null} onSelect={() => {}} onDelete={() => {}} />)
    const thumbs = screen.getAllByTestId(/thumb-/)
    expect(thumbs.length).toBe(2)
    expect(thumbs[0]).toHaveClass("border-accent")
  })

  it("clicking thumbnail X calls onDelete with slide id after confirm", async () => {
    useProjectStore.getState().addSeparator("S")
    const id = useProjectStore.getState().state!.slides[0].id
    vi.spyOn(window, "confirm").mockReturnValue(true)
    const onDelete = vi.fn()
    render(<SlideRail selectedId={id} onSelect={() => {}} onDelete={onDelete} />)
    await userEvent.click(screen.getByTestId(`delete-slide-${id}`))
    expect(onDelete).toHaveBeenCalledWith(id)
  })

  it("cancelling confirm does not call onDelete", async () => {
    useProjectStore.getState().addSeparator("S")
    const id = useProjectStore.getState().state!.slides[0].id
    vi.spyOn(window, "confirm").mockReturnValue(false)
    const onDelete = vi.fn()
    render(<SlideRail selectedId={id} onSelect={() => {}} onDelete={onDelete} />)
    await userEvent.click(screen.getByTestId(`delete-slide-${id}`))
    expect(onDelete).not.toHaveBeenCalled()
  })
})
