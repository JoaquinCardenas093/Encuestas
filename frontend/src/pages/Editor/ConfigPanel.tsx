import { useState, useRef } from "react"
import { Plus, Trash2 } from "lucide-react"
import { useProjectStore } from "../../store/project"
import * as api from "../../api/client"
import AddChartModal from "./modals/AddChartModal"
import AddAnalysisModal from "./modals/AddAnalysisModal"
import { ColorPicker } from "../../components/ColorPicker"
import type { ChartType } from "../../types"
import { useStyleGuideStore } from "../../store/styleGuide"

const BUILTIN_CHART_TYPES: ChartType[] = [
  "PIE", "DONUT", "BAR_HORIZONTAL", "BAR_CLUSTERED", "COLUMN_CLUSTERED",
]

interface Props {
  slideId: string | null
}

interface ColorSlotProps {
  chartId: string
  optionIdx: number
  optionLabel: string
  color: string
  open: boolean
  onToggle: () => void
  onClose: () => void
  onColorChange: (color: string) => void
}

function ColorSlot({ optionIdx, optionLabel, color, open, onToggle, onClose, onColorChange, chartId }: ColorSlotProps) {
  const anchorRef = useRef<HTMLButtonElement>(null)
  return (
    <div className="flex flex-col items-center">
      <button
        ref={anchorRef}
        type="button"
        onClick={onToggle}
        aria-label={`color-${chartId}-${optionIdx}`}
        title={optionLabel}
        className="p-0.5 rounded hover:bg-neutral-700"
      >
        <div
          className="w-4 h-4 rounded border border-neutral-600"
          style={{ backgroundColor: color || "#7F7F7F" }}
        />
      </button>
      <span className="text-[9px] text-neutral-400 max-w-[60px] truncate">{optionLabel}</span>
      <ColorPicker
        open={open}
        value={color}
        onChange={onColorChange}
        onClose={onClose}
        anchorRef={anchorRef}
      />
    </div>
  )
}

export default function ConfigPanel({ slideId }: Props) {
  const state = useProjectStore((s) => s.state)
  const parsedDb = useProjectStore((s) => s.parsedDb)
  const addCharts = useProjectStore((s) => s.addCharts)
  const removeChart = useProjectStore((s) => s.removeChart)
  const updateChartType = useProjectStore((s) => s.updateChartType)
  const styleGuide = useStyleGuideStore((s) => s.styleGuide)
  const CHART_TYPES = (styleGuide?.available_chart_types?.length
    ? styleGuide.available_chart_types
    : BUILTIN_CHART_TYPES) as ChartType[]
  const updateSeparatorTitle = useProjectStore((s) => s.updateSeparatorTitle)
  const addAnalysis = useProjectStore((s) => s.addAnalysis)
  const removeAnalysis = useProjectStore((s) => s.removeAnalysis)
  const updateChartColors = useProjectStore((s) => s.updateChartColors)
  const [chartModalOpen, setChartModalOpen] = useState(false)
  const [analysisModalOpen, setAnalysisModalOpen] = useState(false)
  const [chartColorOpen, setChartColorOpen] = useState<string | null>(null) // key: `${chartId}:${optionIdx}`

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
            const options = q?.options ?? []
            return (
              <div key={c.id} className="bg-neutral-800 border border-neutral-700 rounded p-2 mb-2 flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <span className="bg-blue-700 text-white text-xs px-1.5 rounded">{q?.code || c.question_id}</span>
                  <span className="text-xs flex-1 truncate">{b?.label || c.breakdown_id}</span>
                  <select
                    value={c.chart_type}
                    onChange={(e) => updateChartType(slide.id, c.id, e.target.value as ChartType)}
                    className="text-xs bg-neutral-900 border border-neutral-700 rounded px-1 py-0.5"
                  >
                    {(c.breakdown_id && c.breakdown_id !== 'general'
                      ? CHART_TYPES
                      : CHART_TYPES.filter((t) => t !== 'TABLE_WITH_MINIBARS')
                    ).map((t) => (
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
                {options.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5 pl-1">
                    <span className="text-[10px] text-neutral-500 uppercase tracking-wide mr-1">Colores</span>
                    {options.map((opt, i) => (
                      <ColorSlot
                        key={`${c.id}:${i}`}
                        chartId={c.id}
                        optionIdx={i}
                        optionLabel={opt}
                        color={c.colors?.[i] || ""}
                        open={chartColorOpen === `${c.id}:${i}`}
                        onToggle={() => setChartColorOpen(chartColorOpen === `${c.id}:${i}` ? null : `${c.id}:${i}`)}
                        onClose={() => setChartColorOpen(null)}
                        onColorChange={(color) => {
                          const newColors = [...(c.colors ?? [])]
                          while (newColors.length < options.length) newColors.push("")
                          newColors[i] = color
                          updateChartColors(slide.id, c.id, newColors)
                          setChartColorOpen(null)
                        }}
                      />
                    ))}
                  </div>
                )}
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
              addCharts(slide.id, r.questionId, r.breakdownIds, r.chartType)
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
          {/* Pattern matched indicator */}
          {slide.matched_pattern ? (
            <div className="flex items-center gap-2 text-xs text-green-400 mt-3 mb-1 bg-green-900/20 border border-green-800/40 rounded px-3 py-2">
              <span className="font-mono">{slide.matched_pattern}</span>
              <span className="text-green-300">✓ matched</span>
            </div>
          ) : (
            <div className="text-xs text-neutral-500 italic mt-3 mb-1">
              Layout: fallback heurístico
            </div>
          )}

          <button
            onClick={async () => {
              const free_area = { x: 600000, y: 1200000, cx: 11000000, cy: 5000000 }
              const r = await api.suggestLayout({
                n_charts: slide.charts.length,
                chart_types: slide.charts.map((c) => c.chart_type),
                n_chart_an: slide.analyses.filter((a) => a.scope === "chart").length,
                n_q_an: slide.analyses.filter((a) => a.scope === "question").length,
                has_slide_an: slide.analyses.some((a) => a.scope === "slide"),
                free_area,
              })
              alert(`AI suggest source: ${r.source}. (Vista previa requiere agregar este layout al state — feature v2.)`)
            }}
            className="w-full mt-3 text-xs bg-gradient-to-r from-purple-700 to-violet-700 text-white py-2 rounded font-semibold"
          >
            ✨ AI sugiere layout
          </button>
        </>
      )}
    </aside>
  )
}
