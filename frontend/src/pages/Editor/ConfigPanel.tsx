import { useState } from "react"
import { Plus, Trash2 } from "lucide-react"
import { useProjectStore } from "../../store/project"
import AddChartModal from "./modals/AddChartModal"
import AddAnalysisModal from "./modals/AddAnalysisModal"
import type { ChartType } from "../../types"

const CHART_TYPES: ChartType[] = [
  "PIE",
  "DONUT",
  "BAR",
  "COLUMN",
  "BAR_STACKED",
  "COLUMN_STACKED",
  "LINE",
  "AREA",
  "RADAR",
]

interface Props {
  slideId: string | null
}

export default function ConfigPanel({ slideId }: Props) {
  const state = useProjectStore((s) => s.state)
  const parsedDb = useProjectStore((s) => s.parsedDb)
  const addCharts = useProjectStore((s) => s.addCharts)
  const removeChart = useProjectStore((s) => s.removeChart)
  const updateChartType = useProjectStore((s) => s.updateChartType)
  const updateSeparatorTitle = useProjectStore((s) => s.updateSeparatorTitle)
  const addAnalysis = useProjectStore((s) => s.addAnalysis)
  const removeAnalysis = useProjectStore((s) => s.removeAnalysis)
  const [chartModalOpen, setChartModalOpen] = useState(false)
  const [analysisModalOpen, setAnalysisModalOpen] = useState(false)

  const slide = state?.slides.find((s) => s.id === slideId)
  if (!slide) {
    return (
      <aside className="bg-neutral-900 border-l border-neutral-700 p-3 text-sm text-neutral-500">
        Seleccioná una slide
      </aside>
    )
  }

  const isSep = slide.type === "separator"

  return (
    <aside className="bg-neutral-900 border-l border-neutral-700 p-3 text-sm overflow-y-auto">
      <h3 className="text-xs uppercase text-neutral-500 mb-2">{isSep ? "Separador" : "Shell"}</h3>
      <label className="block text-xs text-neutral-400 mb-1">Título</label>
      <input
        value={slide.title || ""}
        disabled={!isSep}
        onChange={(e) => isSep && updateSeparatorTitle(slide.id, e.target.value)}
        className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-sm mb-4 disabled:opacity-60"
      />

      {!isSep && (
        <>
          <h4 className="text-xs uppercase text-neutral-500 mb-2">Charts ({slide.charts.length})</h4>
          {slide.charts.map((c) => {
            const q = parsedDb?.questions.find((q) => q.id === c.question_id)
            const b = parsedDb?.breakdowns.find((b) => b.id === c.breakdown_id)
            return (
              <div key={c.id} className="bg-neutral-800 border border-neutral-700 rounded p-2 mb-2 flex items-center gap-2">
                <span className="bg-blue-700 text-white text-xs px-1.5 rounded">{q?.code || c.question_id}</span>
                <span className="text-xs flex-1 truncate">{b?.label || c.breakdown_id}</span>
                <select
                  value={c.chart_type}
                  onChange={(e) => updateChartType(slide.id, c.id, e.target.value as ChartType)}
                  className="text-xs bg-neutral-900 border border-neutral-700 rounded px-1 py-0.5"
                >
                  {CHART_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => removeChart(slide.id, c.id)}
                  className="text-neutral-500 hover:text-red-400"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            )
          })}
          <button
            onClick={() => setChartModalOpen(true)}
            className="w-full text-xs bg-transparent border border-dashed border-neutral-600 rounded py-1.5 flex items-center justify-center gap-1 text-neutral-400 hover:text-neutral-200"
          >
            <Plus size={12} /> Chart
          </button>

          <AddChartModal
            open={chartModalOpen}
            onClose={() => setChartModalOpen(false)}
            onApply={(r) =>
              addCharts(slide.id, r.questionId, r.breakdownIds, r.chartType, r.multiSeries)
            }
            db={parsedDb}
          />

          <h4 className="text-xs uppercase text-neutral-500 mt-4 mb-2">Análisis ({slide.analyses.length})</h4>
          {slide.analyses.map((a) => (
            <div key={a.id} className="bg-neutral-800 border border-neutral-700 rounded p-2 mb-2 flex items-start gap-2">
              <span className={`text-xs px-1.5 rounded font-semibold ${
                a.scope === "slide" ? "bg-accent text-neutral-900" :
                a.scope === "question" ? "bg-green-500 text-neutral-900" :
                "bg-blue-400 text-neutral-900"
              }`}>{a.scope.slice(0, 4).toUpperCase()}</span>
              <span className="text-xs flex-1 line-clamp-2">{a.text}</span>
              <button onClick={() => removeAnalysis(slide.id, a.id)} className="text-neutral-500 hover:text-red-400">
                <Trash2 size={12} />
              </button>
            </div>
          ))}
          <button
            onClick={() => setAnalysisModalOpen(true)}
            className="w-full text-xs bg-transparent border border-dashed border-neutral-600 rounded py-1.5 flex items-center justify-center gap-1 text-neutral-400 hover:text-neutral-200"
          >
            <Plus size={12} /> Análisis
          </button>

          <AddAnalysisModal
            open={analysisModalOpen}
            slide={slide}
            db={parsedDb}
            onClose={() => setAnalysisModalOpen(false)}
            onAdd={(a) => addAnalysis(slide.id, a)}
          />
        </>
      )}
    </aside>
  )
}
