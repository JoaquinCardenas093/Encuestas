import { useState, useEffect, useMemo } from "react"
import Modal from "../../../components/Modal"
import type { ChartType, ParsedDB } from "../../../types"

// General (no real breakdowns) → only PIE / BAR_HORIZONTAL.
// 1+ real breakdowns → only grouped/table types. Colors are edited after the
// chart is placed, so no color picker here.
const GENERAL_CHART_TYPES = ["PIE", "BAR_HORIZONTAL"]
const SEGMENTED_CHART_TYPES = ["PIE_GROUPED", "BAR_HORIZONTAL_GROUPED", "TABLE_WITH_MINIBARS"]

interface ApplyResult {
  questionId: string
  breakdownIds: string[]
  chartType: ChartType
  show_legend: boolean
  grid_cols: number | null
  title: string | null
  cat_titles: Record<string, string> | null
  colors: string[]
}

interface Props {
  open: boolean
  onClose(): void
  onApply(r: ApplyResult): void
  db: ParsedDB | null
}

export default function AddChartModal({ open, onClose, onApply, db }: Props) {
  const [questionId, setQuestionId] = useState<string>("")
  const [breakdownIds, setBreakdownIds] = useState<Set<string>>(new Set())
  const generalSelected = breakdownIds.has("general")
  const realBreakdownIds = useMemo(
    () => Array.from(breakdownIds).filter((b) => b !== "general"),
    [breakdownIds],
  )
  const nReal = realBreakdownIds.length
  const chartTypes = useMemo(
    () => (nReal >= 1 ? SEGMENTED_CHART_TYPES : GENERAL_CHART_TYPES),
    [nReal],
  )
  const [chartType, setChartType] = useState<ChartType>((chartTypes[0] ?? "PIE") as ChartType)
  const [title, setTitle] = useState("")
  const [showLegend, setShowLegend] = useState(false)
  const [gridCols, setGridCols] = useState<number | null>(null)
  const [catTitles, setCatTitles] = useState<Record<string, string>>({})

  const breakdownCats = useMemo(() => {
    if (nReal !== 1) return [] as string[]
    const bdId = realBreakdownIds[0]
    return db?.breakdowns.find((b) => b.id === bdId)?.categories ?? []
  }, [db, realBreakdownIds, nReal])

  // Sync chartType when available chart types change or filter changes
  useEffect(() => {
    if (!chartTypes.includes(chartType)) {
      setChartType(chartTypes[0] as ChartType)
    }
  }, [chartTypes.join(","), chartType])

  useEffect(() => {
    if (open && db && db.questions.length > 0) {
      setQuestionId(db.questions[0].id)
      setBreakdownIds(new Set())
      setTitle("")
      setShowLegend(false)
      setGridCols(null)
      setCatTitles({})
    }
  }, [open, db])

  if (!db) return null

  // Mutual exclusivity: "general" and real breakdowns can't coexist.
  const toggleBreakdown = (bid: string) => {
    const next = new Set(breakdownIds)
    if (next.has(bid)) {
      next.delete(bid)
    } else if (bid === "general") {
      next.clear()
      next.add("general")
    } else {
      next.delete("general")
      next.add(bid)
    }
    setBreakdownIds(next)
  }

  const handleApply = () => {
    if (!questionId) return
    const catTitlesPayload = Object.keys(catTitles).length ? catTitles : null
    onApply({
      questionId,
      breakdownIds: realBreakdownIds,
      chartType,
      show_legend: showLegend,
      grid_cols: gridCols,
      title: title.trim() || null,
      cat_titles: catTitlesPayload,
      colors: [],
    })
    onClose()
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Agregar chart"
      footer={
        <>
          <button onClick={onClose} className="px-3 py-1.5 text-sm rounded bg-neutral-700">
            Cancelar
          </button>
          <button
            disabled={!questionId}
            onClick={handleApply}
            className="px-3 py-1.5 text-sm rounded bg-accent text-neutral-900 font-semibold disabled:opacity-40"
          >
            Aplicar
          </button>
        </>
      }
    >
      <label htmlFor="q-select" className="block text-xs text-neutral-400 mb-1">
        Pregunta
      </label>
      <select
        id="q-select"
        value={questionId}
        onChange={(e) => setQuestionId(e.target.value)}
        className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
      >
        {db.questions.map((q) => (
          <option key={q.id} value={q.id}>
            {q.code}: {q.text}
          </option>
        ))}
      </select>

      <div className="text-xs text-neutral-400 mb-1">Breakdowns (multi-select)</div>
      <div className="grid grid-cols-2 gap-1 mb-3">
        {db.breakdowns.map((b) => {
          const isGeneral = b.id === "general"
          // General disabled when any real bd picked; real bds disabled when general picked.
          const disabled = isGeneral ? nReal >= 1 : generalSelected
          return (
            <label
              key={b.id}
              className={`flex items-center gap-2 text-sm bg-neutral-900 px-2 py-1.5 rounded ${disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
            >
              <input
                type="checkbox"
                checked={breakdownIds.has(b.id)}
                disabled={disabled}
                onChange={() => toggleBreakdown(b.id)}
                aria-label={b.label}
              />
              {b.label}
            </label>
          )
        })}
      </div>

      <label htmlFor="ct-select" className="block text-xs text-neutral-400 mb-1">
        Tipo de chart
      </label>
      <select
        id="ct-select"
        aria-label="Tipo de chart"
        value={chartType}
        onChange={(e) => {
          const newType = e.target.value as ChartType
          setChartType(newType)
          if (newType !== "BAR_HORIZONTAL_GROUPED" && newType !== "TABLE_WITH_MINIBARS") {
            setShowLegend(false)
          }
          if (newType !== "PIE_GROUPED") {
            setGridCols(null)
            setCatTitles({})
          }
        }}
        className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm disabled:opacity-60"
      >
        {chartTypes.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>

      <label className="block text-xs text-neutral-400 mb-1">Título (opcional)</label>
      <input
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
        placeholder="Ej: Plazo del crédito"
      />

      {(chartType === "BAR_HORIZONTAL_GROUPED" || chartType === "TABLE_WITH_MINIBARS") && (
        <label className="flex items-center gap-2 text-sm mb-3">
          <input
            type="checkbox"
            checked={showLegend}
            onChange={(e) => setShowLegend(e.target.checked)}
          />
          Mostrar leyenda
        </label>
      )}

      {chartType === "PIE_GROUPED" && (
        <>
          <label htmlFor="grid-cols-input" className="block text-xs text-neutral-400 mb-1">
            Columnas por fila (vacío = auto)
          </label>
          <input
            id="grid-cols-input"
            type="number"
            min={1}
            value={gridCols ?? ""}
            onChange={(e) =>
              setGridCols(e.target.value === "" ? null : Math.max(1, parseInt(e.target.value, 10)))
            }
            className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
          />
        </>
      )}

      {chartType === "PIE_GROUPED" && nReal === 1 && breakdownCats.length > 0 && (
        <div className="mb-3">
          <label className="block text-xs text-neutral-400 mb-2">
            Títulos por categoría (opcional)
          </label>
          {breakdownCats.map((cat) => (
            <div key={cat} className="flex items-center gap-2 mb-1">
              <span className="text-xs text-neutral-500 w-32 truncate">{cat}</span>
              <input
                type="text"
                value={catTitles[cat] ?? ""}
                onChange={(e) => setCatTitles({ ...catTitles, [cat]: e.target.value })}
                className="flex-1 bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs"
                placeholder={cat}
              />
            </div>
          ))}
        </div>
      )}

      <p className="mt-2 text-xs text-neutral-500">
        Los colores se editan una vez agregado el gráfico.
      </p>
    </Modal>
  )
}
