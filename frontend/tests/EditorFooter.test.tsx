import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import EditorFooter from "../src/pages/Editor/EditorFooter"
import { useProjectStore } from "../src/store/project"

describe("EditorFooter", () => {
  it("renders undo/redo/reset buttons", () => {
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    render(<EditorFooter />)
    expect(screen.getByRole("button", { name: /undo/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /redo/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /reset todo/i })).toBeInTheDocument()
  })

  it("Reset todo clears slides", async () => {
    useProjectStore.setState({ state: null })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    useProjectStore.getState().addSeparator("X")
    vi.spyOn(window, "confirm").mockReturnValue(true)
    render(<EditorFooter />)
    await userEvent.click(screen.getByRole("button", { name: /reset todo/i }))
    expect(useProjectStore.getState().state!.slides).toEqual([])
  })

  it("Eliminar slide is disabled when nothing selected", () => {
    useProjectStore.setState({ state: null })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    render(<EditorFooter selectedId={null} onDeleteSlide={() => {}} />)
    expect(screen.getByRole("button", { name: /eliminar slide/i })).toBeDisabled()
  })

  it("Eliminar slide calls onDeleteSlide with selected id after confirm", async () => {
    useProjectStore.setState({ state: null })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    vi.spyOn(window, "confirm").mockReturnValue(true)
    const onDelete = vi.fn()
    render(<EditorFooter selectedId={"sl-1"} onDeleteSlide={onDelete} />)
    await userEvent.click(screen.getByRole("button", { name: /eliminar slide/i }))
    expect(onDelete).toHaveBeenCalledWith("sl-1")
  })
})
