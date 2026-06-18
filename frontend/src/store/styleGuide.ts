import { create } from "zustand"
import * as tapi from "../api/training"
import type { StyleGuide, CorpusPPT, AnalysisStatusResponse } from "../api/training"

interface AnalysisJobState {
  jobId: string
  progress: number
  status: tapi.AnalysisStatusValue
  message: string
  resultSummary?: AnalysisStatusResponse["result_summary"]
  error?: string
}

interface StyleGuideStore {
  styleGuide: StyleGuide | null
  isLoading: boolean
  corpus: CorpusPPT[]
  analysisJob: AnalysisJobState | null

  loadStyleGuide(): Promise<void>
  loadCorpus(): Promise<void>
  addPPT(file: File): Promise<void>
  deletePPT(filename: string): Promise<void>
  analyzeWithAI(): Promise<void>
  clearAnalysisJob(): void
}

const POLL_INTERVAL_MS = 2000

export const useStyleGuideStore = create<StyleGuideStore>((set, get) => ({
  styleGuide: null,
  isLoading: false,
  corpus: [],
  analysisJob: null,

  async loadStyleGuide() {
    set({ isLoading: true })
    try {
      const sg = await tapi.getStyleGuide()
      set({ styleGuide: sg })
    } catch {
      // Style guide unavailable — leave null (will show built-in indicator in UI)
    } finally {
      set({ isLoading: false })
    }
  },

  async loadCorpus() {
    set({ isLoading: true })
    try {
      const res = await tapi.listCorpus()
      set({ corpus: res.pptxs })
    } catch {
      // Silently fail; UI shows empty corpus
    } finally {
      set({ isLoading: false })
    }
  },

  async addPPT(file: File) {
    set({ isLoading: true })
    try {
      await tapi.addCorpusPPT(file)
      await get().loadCorpus()
    } finally {
      set({ isLoading: false })
    }
  },

  async deletePPT(filename: string) {
    set({ isLoading: true })
    try {
      await tapi.deleteCorpusPPT(filename)
      await get().loadCorpus()
    } finally {
      set({ isLoading: false })
    }
  },

  async analyzeWithAI() {
    set({ isLoading: true })
    let jobId: string
    try {
      const res = await tapi.triggerAnalyzeWithAI()
      jobId = res.job_id
      set({ analysisJob: { jobId, progress: 0, status: "running", message: "Iniciando análisis..." } })
    } catch (e) {
      set({
        isLoading: false,
        analysisJob: { jobId: "", progress: 0, status: "error", message: "Error al iniciar análisis" },
      })
      return
    } finally {
      set({ isLoading: false })
    }

    // Poll until done or error
    await new Promise<void>((resolve) => {
      const poll = async () => {
        try {
          const status = await tapi.getAnalysisStatus(jobId)
          set({
            analysisJob: {
              jobId,
              progress: status.progress,
              status: status.status,
              message: status.message,
              resultSummary: status.result_summary,
            },
          })
          if (status.status === "done") {
            // Reload style guide with fresh AI result
            await get().loadStyleGuide()
            resolve()
            return
          }
          if (status.status === "error") {
            resolve()
            return
          }
        } catch {
          set((s) => ({
            analysisJob: s.analysisJob
              ? { ...s.analysisJob, status: "error", message: "Error al consultar estado" }
              : null,
          }))
          resolve()
          return
        }
        setTimeout(poll, POLL_INTERVAL_MS)
      }
      setTimeout(poll, POLL_INTERVAL_MS)
    })
  },

  clearAnalysisJob() {
    set({ analysisJob: null })
  },
}))
