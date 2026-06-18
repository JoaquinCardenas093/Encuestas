import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import Topbar from "../src/components/Topbar"
import { useProjectStore } from "../src/store/project"

describe("Topbar", () => {
  it("renders app name + tabs", () => {
    render(
      <MemoryRouter>
        <Topbar />
      </MemoryRouter>,
    )
    expect(screen.getByText(/AurumEncuestas/i)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Editor/i })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Entrenamiento/i })).toBeInTheDocument()
  })

  it("shows pill with DB filename when project loaded", () => {
    useProjectStore.getState().setNewProject({
      name: "X",
      db_path: "/path/to/BD.xlsx",
      template_path: "/path/to/tpl.pptx",
    })
    render(
      <MemoryRouter>
        <Topbar />
      </MemoryRouter>,
    )
    expect(screen.getByText(/BD\.xlsx/)).toBeInTheDocument()
  })
})
