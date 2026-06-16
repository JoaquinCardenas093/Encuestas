import { describe, expect, it, beforeEach } from "vitest"
import { useProjectStore } from "../src/store/project"

describe("project store", () => {
  beforeEach(() => {
    useProjectStore.setState({
      state: null,
      projectPath: null,
    })
  })

  it("initial state is null", () => {
    expect(useProjectStore.getState().state).toBeNull()
  })

  it("setNewProject creates blank state", () => {
    useProjectStore.getState().setNewProject({
      name: "Test",
      db_path: "./x.xlsx",
      template_path: "./t.pptx",
    })
    const s = useProjectStore.getState().state
    expect(s).not.toBeNull()
    expect(s!.project_name).toBe("Test")
    expect(s!.slides).toEqual([])
  })

  it("addSeparator appends a separator slide", () => {
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    useProjectStore.getState().addSeparator("Sección 1")
    const slides = useProjectStore.getState().state!.slides
    expect(slides.length).toBe(1)
    expect(slides[0].type).toBe("separator")
    expect(slides[0].title).toBe("Sección 1")
  })

  it("addShell requires a previous separator", () => {
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    expect(() => useProjectStore.getState().addShell()).toThrow(/separador/)
  })

  it("addShell inherits last separator title", () => {
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    useProjectStore.getState().addSeparator("Sección A")
    useProjectStore.getState().addShell()
    const slides = useProjectStore.getState().state!.slides
    expect(slides[1].type).toBe("shell")
    expect(slides[1].title).toBe("Sección A")
  })
})
