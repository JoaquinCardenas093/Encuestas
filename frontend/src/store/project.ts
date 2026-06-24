import { create } from "zustand"
import { temporal } from "zundo"
import type { ParsedDB, ProjectState, Slide, TemplateInfo } from "../types"

function uid(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`
}

function _migrateProjectState(raw: unknown): ProjectState {
  const obj = raw as Record<string, unknown>

  // Strip legacy style_set field
  const { style_set: _dropped, ...rest } = obj

  // Ensure palette defaults to null
  if (!("palette" in rest)) {
    rest.palette = null
  }

  // Ensure each chart has colors: []
  if (Array.isArray(rest.slides)) {
    rest.slides = (rest.slides as unknown[]).map((sl) => {
      const slide = sl as Record<string, unknown>
      if (!Array.isArray(slide.charts)) return slide
      return {
        ...slide,
        charts: (slide.charts as unknown[]).map((ch) => {
          const chart = ch as Record<string, unknown>
          return {
            ...chart,
            show_legend: chart.show_legend ?? false,
            grid_cols: chart.grid_cols ?? null,
            title: chart.title ?? null,
            cat_titles: chart.cat_titles ?? null,
            colors: chart.colors ?? [],
          }
        }),
      }
    })
  }

  return rest as unknown as ProjectState
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

  addChart(
    slideId: string,
    questionId: string,
    breakdownIds: string[],
    chartType: import("../types").ChartType,
    opts?: {
      show_legend?: boolean
      grid_cols?: number | null
      title?: string | null
      cat_titles?: Record<string, string> | null
      colors?: string[]
    },
  ): void
  removeChart(slideId: string, chartId: string): void
  updateChartType(slideId: string, chartId: string, chartType: import("../types").ChartType): void
  updateChartColors(slideId: string, chartId: string, colors: string[]): void
  updateChartField<K extends keyof import("../types").Chart>(
    slideId: string,
    chartId: string,
    field: K,
    value: import("../types").Chart[K],
  ): void
  resetSlide(slideId: string): void
  resetAll(): void

  addAnalysis(slideId: string, analysis: Omit<import("../types").Analysis, "id">): void
  removeAnalysis(slideId: string, analysisId: string): void
  updateAnalysisText(slideId: string, analysisId: string, text: string): void
  setSlideLayout(slideId: string, layout: import("../types").SlideLayout | null): void
}

function applyTitleInheritance(slides: Slide[]): Slide[] {
  // Shell slides inherit the most recent separator's title ONLY if their own
  // title is null/empty (never edited). User-set shell titles preserved.
  let currentTitle: string | null = null
  return slides.map((s) => {
    if (s.type === "separator") {
      currentTitle = s.title
      return s
    }
    if (s.title == null || s.title === "") {
      return { ...s, title: currentTitle }
    }
    return s
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
            palette: null,
          },
        })
      },

      setProjectPath(path) { set({ projectPath: path }) },
      setParsedDb(db) { set({ parsedDb: db }); const s = get().state; if (s) set({ state: { ...s, parsed_db: db } }) },
      setTemplateInfo(info) { set({ templateInfo: info }) },
      loadProjectState(raw) { set({ state: _migrateProjectState(raw) }) },

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
              s.slides.map((sl) => (sl.id === slideId ? { ...sl, title } : sl)),
            ),
          },
        })
      },

      addChart(slideId, questionId, breakdownIds, chartType, opts) {
        const s = get().state
        if (!s) return
        const slides = s.slides.map((sl) => {
          if (sl.id !== slideId) return sl
          const newChart = {
            id: uid("ch"),
            question_id: questionId,
            breakdown_ids: breakdownIds,
            chart_type: chartType,
            show_legend: opts?.show_legend ?? false,
            grid_cols: opts?.grid_cols ?? null,
            title: opts?.title ?? null,
            cat_titles: opts?.cat_titles ?? null,
            colors: opts?.colors ?? [] as string[],
          }
          return { ...sl, charts: [...sl.charts, newChart] }
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

      updateChartColors(slideId, chartId, colors) {
        const s = get().state
        if (!s) return
        const slides = s.slides.map((sl) =>
          sl.id !== slideId ? sl : {
            ...sl,
            charts: sl.charts.map((c) =>
              c.id !== chartId ? c : { ...c, colors }
            ),
          }
        )
        set({ state: { ...s, slides } })
      },

      updateChartField(slideId, chartId, field, value) {
        const s = get().state
        if (!s) return
        const slides = s.slides.map((sl) => {
          if (sl.id !== slideId) return sl
          return {
            ...sl,
            charts: sl.charts.map((c) =>
              c.id !== chartId ? c : { ...c, [field]: value }
            ),
          }
        })
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

      addAnalysis(slideId, analysis) {
        const s = get().state
        if (!s) return
        const newAnalysis = { ...analysis, id: uid("an") }
        const slides = s.slides.map((sl) =>
          sl.id !== slideId ? sl : { ...sl, analyses: [...sl.analyses, newAnalysis] },
        )
        set({ state: { ...s, slides } })
      },

      removeAnalysis(slideId, analysisId) {
        const s = get().state
        if (!s) return
        const slides = s.slides.map((sl) =>
          sl.id !== slideId ? sl : { ...sl, analyses: sl.analyses.filter((a) => a.id !== analysisId) },
        )
        set({ state: { ...s, slides } })
      },

      updateAnalysisText(slideId, analysisId, text) {
        const s = get().state
        if (!s) return
        const slides = s.slides.map((sl) =>
          sl.id !== slideId ? sl : {
            ...sl,
            analyses: sl.analyses.map((a) => (a.id === analysisId ? { ...a, text, edited: true } : a)),
          },
        )
        set({ state: { ...s, slides } })
      },

      setSlideLayout(slideId, layout) {
        const s = get().state
        if (!s) return
        const slides = s.slides.map((sl) => (sl.id === slideId ? { ...sl, layout } : sl))
        set({ state: { ...s, slides } })
      },
    }),
    {
      limit: 100,
      partialize: (state) => ({ state: state.state }) as any,
    },
  ),
)