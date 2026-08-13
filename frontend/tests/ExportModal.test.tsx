import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import ExportModal from "../src/pages/Editor/modals/ExportModal"
import * as api from "../src/api/client"
import { useProjectStore } from "../src/store/project"

describe("ExportModal", () => {
  it("has no folder field and downloads via exportPptx", async () => {
    useProjectStore.setState({ state: null })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    const spy = vi.spyOn(api, "exportPptx").mockResolvedValue(undefined)
    render(<ExportModal open={true} onClose={() => {}} />)
    expect(screen.queryByText(/Carpeta/i)).toBeNull()
    await userEvent.click(screen.getByRole("button", { name: /Descargar/i }))
    expect(spy).toHaveBeenCalled()
    expect(typeof spy.mock.calls[0][1]).toBe("string")
  })
})
