import { create } from "zustand"
import { temporal } from "zundo"
import type { ParsedDB, ProjectState, Slide, TemplateInfo } from "../types"

function uid(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`
}

interface NewProjectArgs {
  name: string
  db_path: string
  template_path: string
}

interface Store {
  state: ProjectState | null
  projectPath: string | null
  parsedDb: ParsedDB | null
  templateInfo: TemplateInfo | null

  setNewProject(args: NewProjectArgs): void
  setProjectPath(path: string | null): void
  setParsedDb(db: ParsedDB | null): void
  setTemplateInfo(info: TemplateInfo | null): void
  loadProjectState(state: ProjectState): void

  addSeparator(title: string): void
  addShell(): void
  reorderSlide(fromIdx: number, toIdx: number): void
  removeSlide(slideId: string): void
  updateSeparatorTitle(slideId: string, title: string): void

  addCharts(slideId: string, questionId: string, breakdownIds: string[], chartType: import("../types").ChartType, multiSeries: boolean): void
  removeChart(slideId: string, chartId: string): void
  updateChartType(slideId: string, chartId: string, chartType: import("../types").ChartType): void
  resetSlide(slideId: string): void
  resetAll(): void
}

function applyTitleInheritance(slides: Slide[]): Slide[] {
  // every shell slide inherits the most recent separator's title
  let currentTitle: string | null = null
  return slides.map((s) => {
    if (s.type === "separator") {
      currentTitle = s.title
      return s
    }
    return { ...s, title: currentTitle }
  })
}

export const useProjectStore = create<Store>()(
  temporal(
    (set, get) => ({
      state: null,
      projectPath: null,
      parsedDb: null,
      templateInfo: null,

      setNewProject({ name, db_path, template_path }) {
        set({
          state: {
            version: 1,
            app_name: "AurumEncuestas",
            project_name: name,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            inputs: { db_path, template_path, font_override: null },
            parsed_db: null,
            slides: [],
            history: { past: [], future: [] },
          },
        })
      },

      setProjectPath(path) { set({ projectPath: path }) },
      setParsedDb(db) { set({ parsedDb: db }); const s = get().state; if (s) set({ state: { ...s, parsed_db: db } }) },
      setTemplateInfo(info) { set({ templateInfo: info }) },
      loadProjectState(state) { set({ state }) },

      addSeparator(title: string) {
        const s = get().state
        if (!s) return
        const sep: Slide = { id: uid("sl"), type: "separator", title, charts: [], analyses: [], auto_notes: null }
        set({ state: { ...s, slides: applyTitleInheritance([...s.slides, sep]) } })
      },

      addShell() {
        const s = get().state
        if (!s) return
        const hasSeparator = s.slides.some((sl) => sl.type === "separator")
        if (!hasSeparator) throw new Error("Necesitás crear un separador antes de agregar una shell.")
        const shell: Slide = { id: uid("sl"), type: "shell", title: null, charts: [], analyses: [], auto_notes: null }
        set({ state: { ...s, slides: applyTitleInheritance([...s.slides, shell]) } })
      },

      reorderSlide(fromIdx, toIdx) {
        const s = get().state
        if (!s) return
        const copy = [...s.slides]
        const [moved] = copy.splice(fromIdx, 1)
        copy.splice(toIdx, 0, moved)
        set({ state: { ...s, slides: applyTitleInheritance(copy) } })
      },

      removeSlide(slideId) {
        const s = get().state
        if (!s) return
        set({ state: { ...s, slides: applyTitleInheritance(s.slides.filter((sl) => sl.id !== slideId)) } })
      },

      updateSeparatorTitle(slideId, title) {
        const s = get().state
        if (!s) return
        set({
          state: {
            ...s,
            slides: applyTitleInheritance(
              s.slides.map((sl) => (sl.id === slideId && sl.type === "separator" ? { ...sl, title } : sl)),
            ),
          },
        })
      },

      addCharts(slideId, questionId, breakdownIds, chartType, multiSeries) {
        const s = get().state
        if (!s) return
        const slides = s.slides.map((sl) => {
          if (sl.id !== slideId) return sl
          const newCharts = breakdownIds.map((bid) => ({
            id: uid("ch"),
            question_id: questionId,
            breakdown_id: bid,
            chart_type: chartType,
            multi_series: multiSeries,
          }))
          return { ...sl, charts: [...sl.charts, ...newCharts] }
        })
        set({ state: { ...s, slides } })
      },

      removeChart(slideId, chartId) {
        const s = get().state
        if (!s) return
        const slides = s.slides.map((sl) =>
          sl.id !== slideId ? sl : { ...sl, charts: sl.charts.filter((c) => c.id !== chartId) },
        )
        set({ state: { ...s, slides } })
      },

      updateChartType(slideId, chartId, chartType) {
        const s = get().state
        if (!s) return
        const slides = s.slides.map((sl) =>
          sl.id !== slideId
            ? sl
            : {
                ...sl,
                charts: sl.charts.map((c) => (c.id === chartId ? { ...c, chart_type: chartType } : c)),
              },
        )
        set({ state: { ...s, slides } })
      },

      resetSlide(slideId) {
        const s = get().state
        if (!s) return
        const slides = s.slides.map((sl) =>
          sl.id !== slideId ? sl : { ...sl, charts: [], analyses: [] },
        )
        set({ state: { ...s, slides } })
      },

      resetAll() {
        const s = get().state
        if (!s) return
        set({ state: { ...s, slides: [] } })
      },
    }),
    {
      limit: 100,
      partialize: (state) => ({ state: state.state }) as any,
    },
  ),
)
