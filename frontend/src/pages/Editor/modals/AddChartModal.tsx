import { useState, useEffect } from "react"
import Modal from "../../../components/Modal"
import type { ChartType, ParsedDB } from "../../../types"

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

interface ApplyResult {
  questionId: string
  breakdownIds: string[]
  chartType: ChartType
  multiSeries: boolean
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
  const [chartType, setChartType] = useState<ChartType>("PIE")
  const [multiSeries, setMultiSeries] = useState(false)

  useEffect(() => {
    if (open && db && db.questions.length > 0) {
      setQuestionId(db.questions[0].id)
      setBreakdownIds(new Set())
    }
  }, [open, db])

  if (!db) return null

  const toggleBreakdown = (bid: string) => {
    const next = new Set(breakdownIds)
    if (next.has(bid)) {
      next.delete(bid)
    } else {
      next.add(bid)
    }
    setBreakdownIds(next)
  }

  const handleApply = () => {
    if (!questionId || breakdownIds.size === 0) return
    onApply({
      questionId,
      breakdownIds: Array.from(breakdownIds),
      chartType,
      multiSeries,
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
            disabled={!questionId || breakdownIds.size === 0}
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
        {db.breakdowns.map((b) => (
          <label key={b.id} className="flex items-center gap-2 text-sm bg-neutral-900 px-2 py-1.5 rounded cursor-pointer">
            <input
              type="checkbox"
              checked={breakdownIds.has(b.id)}
              onChange={() => toggleBreakdown(b.id)}
              aria-label={b.label}
            />
            {b.label}
          </label>
        ))}
      </div>

      <label htmlFor="ct-select" className="block text-xs text-neutral-400 mb-1">
        Tipo de chart
      </label>
      <select
        id="ct-select"
        value={chartType}
        onChange={(e) => setChartType(e.target.value as ChartType)}
        className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
      >
        {CHART_TYPES.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={multiSeries}
          onChange={(e) => setMultiSeries(e.target.checked)}
        />
        Multi-serie (desglose por sub-categoría)
      </label>
    </Modal>
  )
}
