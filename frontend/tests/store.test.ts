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

describe("store chart operations", () => {
  beforeEach(() => {
    useProjectStore.setState({ state: null })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    useProjectStore.getState().addSeparator("Sec")
    useProjectStore.getState().addShell()
  })

  it("addChart appends one chart", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addCharts(shellId, "q1", ["general"], "PIE", false)
    const shell = useProjectStore.getState().state!.slides[1]
    expect(shell.charts.length).toBe(1)
    expect(shell.charts[0].chart_type).toBe("PIE")
  })

  it("addCharts multi-select breakdowns creates N charts", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addCharts(shellId, "q1", ["general", "sexo", "edad"], "BAR", false)
    const shell = useProjectStore.getState().state!.slides[1]
    expect(shell.charts.length).toBe(3)
    expect(shell.charts.every((c) => c.chart_type === "BAR")).toBe(true)
  })

  it("updateChartType changes one chart", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addCharts(shellId, "q1", ["general", "sexo"], "PIE", false)
    const chart0 = useProjectStore.getState().state!.slides[1].charts[0]
    useProjectStore.getState().updateChartType(shellId, chart0.id, "BAR")
    const updated = useProjectStore.getState().state!.slides[1].charts[0]
    expect(updated.chart_type).toBe("BAR")
  })

  it("resetSlide clears charts and analyses", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addCharts(shellId, "q1", ["general"], "PIE", false)
    useProjectStore.getState().resetSlide(shellId)
    expect(useProjectStore.getState().state!.slides[1].charts).toEqual([])
  })

  it("resetAll empties slides", () => {
    useProjectStore.getState().resetAll()
    expect(useProjectStore.getState().state!.slides).toEqual([])
  })

  it("updateChartColors sets colors array on chart", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addCharts(shellId, "q1", ["general"], "PIE", false)
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
            { id: "c1", question_id: "q1", breakdown_id: "general", chart_type: "PIE", multi_series: false },
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
