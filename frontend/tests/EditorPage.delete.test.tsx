import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import EditorPage from "../src/pages/Editor/EditorPage"
import { useProjectStore } from "../src/store/project"

function setup() {
  useProjectStore.setState({ state: null })
  useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
  useProjectStore.getState().addSeparator("Sec")
  useProjectStore.getState().addShell()
}

describe("EditorPage delete slide", () => {
  it("deleting a thumbnail removes it from the store", async () => {
    setup()
    const firstId = useProjectStore.getState().state!.slides[0].id
    vi.spyOn(window, "confirm").mockReturnValue(true)
    render(
      <MemoryRouter>
        <EditorPage />
      </MemoryRouter>,
    )
    expect(useProjectStore.getState().state!.slides.length).toBe(2)
    await userEvent.click(screen.getByTestId(`delete-slide-${firstId}`))
    const ids = useProjectStore.getState().state!.slides.map((s) => s.id)
    expect(ids).not.toContain(firstId)
    expect(ids.length).toBe(1)
  })
})
