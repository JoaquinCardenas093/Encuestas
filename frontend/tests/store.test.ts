import { describe, expect, it, beforeEach } from "vitest"
import { useProjectStore } from "../src/store/project"

describe("project store", () => {
  beforeEach(() => {
    useProjectStore.setState({
      state: null,
      projectName: null,
    })
  })

  it("setProjectName updates projectName", () => {
    useProjectStore.getState().setProjectName("mi-proyecto")
    expect(useProjectStore.getState().projectName).toBe("mi-proyecto")
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

describe("store chart operations", () => {
  beforeEach(() => {
    useProjectStore.setState({ state: null })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    useProjectStore.getState().addSeparator("Sec")
    useProjectStore.getState().addShell()
  })

  it("addChart appends one chart", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addChart(shellId, "q1", [], "PIE")
    const shell = useProjectStore.getState().state!.slides[1]
    expect(shell.charts.length).toBe(1)
    expect(shell.charts[0].chart_type).toBe("PIE")
  })

  it("addChart single-record stores breakdown_ids list", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addChart(shellId, "q1", ["sexo", "edad"], "TABLE_WITH_MINIBARS")
    const shell = useProjectStore.getState().state!.slides[1]
    expect(shell.charts.length).toBe(1)
    expect(shell.charts[0].breakdown_ids).toEqual(["sexo", "edad"])
    expect(shell.charts[0].chart_type).toBe("TABLE_WITH_MINIBARS")
  })

  it("updateChartType changes one chart", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addChart(shellId, "q1", ["sexo"], "PIE")
    const chart0 = useProjectStore.getState().state!.slides[1].charts[0]
    useProjectStore.getState().updateChartType(shellId, chart0.id, "BAR_HORIZONTAL")
    const updated = useProjectStore.getState().state!.slides[1].charts[0]
    expect(updated.chart_type).toBe("BAR_HORIZONTAL")
  })

  it("resetSlide clears charts and analyses", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addChart(shellId, "q1", [], "PIE")
    useProjectStore.getState().resetSlide(shellId)
    expect(useProjectStore.getState().state!.slides[1].charts).toEqual([])
  })

  it("resetAll empties slides", () => {
    useProjectStore.getState().resetAll()
    expect(useProjectStore.getState().state!.slides).toEqual([])
  })

  it("updateChartColors sets colors array on chart", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addChart(shellId, "q1", [], "PIE")
    const chartId = useProjectStore.getState().state!.slides[1].charts[0].id
    useProjectStore.getState().updateChartColors(shellId, chartId, ["#7F7F7F", "#BFBFBF"])
    const colors = useProjectStore.getState().state!.slides[1].charts[0].colors
    expect(colors).toEqual(["#7F7F7F", "#BFBFBF"])
  })
})

describe("store analysis operations", () => {
  beforeEach(() => {
    useProjectStore.setState({ state: null })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    useProjectStore.getState().addSeparator("Sec")
    useProjectStore.getState().addShell()
  })

  it("addAnalysis appends to slide.analyses", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addAnalysis(shellId, { scope: "slide", target_id: null, text: "Test", ai_generated: true, edited: false })
    expect(useProjectStore.getState().state!.slides[1].analyses.length).toBe(1)
  })

  it("removeAnalysis removes by id", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addAnalysis(shellId, { scope: "slide", target_id: null, text: "X", ai_generated: true, edited: false })
    const aid = useProjectStore.getState().state!.slides[1].analyses[0].id
    useProjectStore.getState().removeAnalysis(shellId, aid)
    expect(useProjectStore.getState().state!.slides[1].analyses.length).toBe(0)
  })

  it("updateAnalysisText changes text and marks edited", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addAnalysis(shellId, { scope: "slide", target_id: null, text: "X", ai_generated: true, edited: false })
    const aid = useProjectStore.getState().state!.slides[1].analyses[0].id
    useProjectStore.getState().updateAnalysisText(shellId, aid, "Nuevo")
    const a = useProjectStore.getState().state!.slides[1].analyses[0]
    expect(a.text).toBe("Nuevo")
    expect(a.edited).toBe(true)
  })
})

describe("M6 migration — .aurum.json backward compat", () => {
  beforeEach(() => {
    useProjectStore.setState({ state: null })
  })

  it("strips style_set field when loading old project", () => {
    const oldProject = {
      version: 1,
      app_name: "AurumEncuestas",
      project_name: "Old Project",
      created_at: null,
      updated_at: null,
      inputs: { db_path: "./x", template_path: "./y", font_override: null },
      parsed_db: null,
      slides: [],
      history: { past: [], future: [] },
      palette: null,
      style_set: "aurum_default",   // Legacy field — must be stripped
    }
    useProjectStore.getState().loadProjectState(oldProject as unknown as import("../src/types").ProjectState)
    const state = useProjectStore.getState().state
    expect(state).not.toBeNull()
    expect((state as unknown as Record<string, unknown>).style_set).toBeUndefined()
  })

  it("adds palette: null when loading project without palette field", () => {
    const oldProject = {
      version: 1,
      app_name: "AurumEncuestas",
      project_name: "Old Project",
      created_at: null,
      updated_at: null,
      inputs: { db_path: "./x", template_path: "./y", font_override: null },
      parsed_db: null,
      slides: [],
      history: { past: [], future: [] },
      // No palette field
    }
    useProjectStore.getState().loadProjectState(oldProject as unknown as import("../src/types").ProjectState)
    const state = useProjectStore.getState().state
    expect(state).not.toBeNull()
    expect(state!.palette).toBeNull()
  })

  it("preserves palette if present in loaded project", () => {
    const projectWithPalette = {
      version: 1,
      app_name: "AurumEncuestas",
      project_name: "New Project",
      created_at: null,
      updated_at: null,
      inputs: { db_path: "./x", template_path: "./y", font_override: null },
      parsed_db: null,
      slides: [],
      history: { past: [], future: [] },
      palette: { primary: "#7F7F7F", secondary: "#BFBFBF" },
    }
    useProjectStore.getState().loadProjectState(projectWithPalette as unknown as import("../src/types").ProjectState)
    const state = useProjectStore.getState().state
    expect(state!.palette).toEqual({ primary: "#7F7F7F", secondary: "#BFBFBF" })
  })

  it("defaults Chart.colors to [] when loading charts without colors field", () => {
    const projectWithOldChart = {
      version: 1,
      app_name: "AurumEncuestas",
      project_name: "Old Project",
      created_at: null,
      updated_at: null,
      inputs: { db_path: "./x", template_path: "./y", font_override: null },
      parsed_db: null,
      history: { past: [], future: [] },
      palette: null,
      slides: [
        {
          id: "sl1",
          type: "shell",
          title: "Sec",
          charts: [
            { id: "c1", question_id: "q1", breakdown_id: "general", chart_type: "PIE" },
            // no colors on chart
          ],
          analyses: [],
          auto_notes: null,
        },
      ],
    }
    useProjectStore.getState().loadProjectState(projectWithOldChart as unknown as import("../src/types").ProjectState)
    const chart = useProjectStore.getState().state!.slides[0].charts[0]
    expect(chart.colors).toEqual([])
  })
})

describe("subtitles", () => {
  it("add/update/remove subtitle on a slide", () => {
    useProjectStore.setState({ state: null, projectName: null })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    useProjectStore.getState().addSeparator("Sec")
    useProjectStore.getState().addShell()
    const slideId = useProjectStore.getState().state!.slides.find((s) => s.type === "shell")!.id

    useProjectStore.getState().addSubtitle(slideId, "P1. Pregunta")
    let sub = useProjectStore.getState().state!.slides.find((s) => s.id === slideId)!.subtitles[0]
    expect(sub.text).toBe("P1. Pregunta")

    useProjectStore.getState().updateSubtitle(slideId, sub.id, "Editado")
    sub = useProjectStore.getState().state!.slides.find((s) => s.id === slideId)!.subtitles[0]
    expect(sub.text).toBe("Editado")

    useProjectStore.getState().removeSubtitle(slideId, sub.id)
    expect(useProjectStore.getState().state!.slides.find((s) => s.id === slideId)!.subtitles).toEqual([])
  })
})

describe("T7 — addChart single-record action", () => {
  it("addChart creates ONE chart with breakdown_ids list", () => {
    const { setState, getState } = useProjectStore  // adapt to actual hook
    // Set up a minimal state with one slide
    setState({
      state: {
        version: 1, app_name: "AurumEncuestas", project_name: "t",
        inputs: { db_path: "", template_path: "" },
        parsed_db: null,
        slides: [{ id: "s1", type: "shell", title: "T", charts: [], analyses: [] }],
        history: { past: [], future: [] },
        palette: null,
      },
    } as any)
    getState().addChart("s1", "q1", ["edad", "sexo"], "TABLE_WITH_MINIBARS")
    const slide = getState().state!.slides.find((s) => s.id === "s1")!
    expect(slide.charts.length).toBe(1)
    expect(slide.charts[0].breakdown_ids).toEqual(["edad", "sexo"])
    expect(slide.charts[0].chart_type).toBe("TABLE_WITH_MINIBARS")
    expect(slide.charts[0].show_legend).toBe(false)
    expect(slide.charts[0].grid_cols).toBeNull()
    expect(slide.charts[0].title).toBeNull()
  })
})

// Helper shared by B8 store tests
function setStateMinimalSlide() {
  useProjectStore.setState({
    state: {
      version: 1, app_name: "AurumEncuestas", project_name: "t",
      inputs: { db_path: "", template_path: "" },
      parsed_db: null,
      slides: [{ id: "s1", type: "shell", title: "T", charts: [], analyses: [], auto_notes: null }],
      history: { past: [], future: [] },
      palette: null,
    },
  } as any)
}

describe("free layout types", () => {
  it("store round-trips a layout with free-mode overrides", () => {
    useProjectStore.setState({ state: null, projectName: null })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    useProjectStore.getState().addSeparator("Sec")
    useProjectStore.getState().addShell()
    const slideId = useProjectStore.getState().state!.slides.find((s) => s.type === "shell")!.id
    const loaded = {
      ...useProjectStore.getState().state!,
      slides: useProjectStore.getState().state!.slides.map((sl) =>
        sl.id !== slideId ? sl : {
          ...sl,
          layout: {
            positions: { a1: { x_emu: 0, y_emu: 0, cx_emu: 1, cy_emu: 1, color: "C00000", font_name: "Georgia", hidden: true } },
            extras: [{ kind: "textbox" as const, id: "free_1", x_emu: 1, y_emu: 1, cx_emu: 10, cy_emu: 2, text: "N", color: "404040" }],
            changes: [],
          },
        }),
    }
    useProjectStore.getState().loadProjectState(loaded)
    const sl = useProjectStore.getState().state!.slides.find((s) => s.id === slideId)!
    expect(sl.layout!.positions.a1.color).toBe("C00000")
    expect(sl.layout!.positions.a1.hidden).toBe(true)
    expect(sl.layout!.extras![0].kind).toBe("textbox")
  })
})

describe("B8 — addChart opts + updateChartField", () => {
  it("addChart with opts persists new fields", () => {
    setStateMinimalSlide()
    useProjectStore.getState().addChart("s1", "q1", ["edad"], "PIE_GROUPED", {
      show_legend: true, grid_cols: 2,
      title: "Plazo del crédito",
      cat_titles: { "18-39": "Jóvenes", "40-59": "Adultos" },
    })
    const c = useProjectStore.getState().state!.slides[0].charts[0]
    expect(c.chart_type).toBe("PIE_GROUPED")
    expect(c.show_legend).toBe(true)
    expect(c.grid_cols).toBe(2)
    expect(c.title).toBe("Plazo del crédito")
    expect(c.cat_titles).toEqual({ "18-39": "Jóvenes", "40-59": "Adultos" })
  })

  it("addChart without opts uses schema defaults", () => {
    setStateMinimalSlide()
    useProjectStore.getState().addChart("s1", "q1", [], "PIE")
    const c = useProjectStore.getState().state!.slides[0].charts[0]
    expect(c.show_legend).toBe(false)
    expect(c.grid_cols).toBeNull()
    expect(c.title).toBeNull()
    expect(c.cat_titles).toBeNull()
  })

  it("updateChartField patches only the targeted field", () => {
    setStateMinimalSlide()
    useProjectStore.getState().addChart("s1", "q1", ["edad"], "PIE_GROUPED", {
      show_legend: false, grid_cols: 3, title: null,
    })
    const cId = useProjectStore.getState().state!.slides[0].charts[0].id
    useProjectStore.getState().updateChartField("s1", cId, "show_legend", true)
    const c2 = useProjectStore.getState().state!.slides[0].charts[0]
    expect(c2.show_legend).toBe(true)
    expect(c2.grid_cols).toBe(3)
    expect(c2.title).toBeNull()
  })
})
