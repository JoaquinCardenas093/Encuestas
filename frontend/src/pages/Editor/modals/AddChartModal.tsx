import { useState, useEffect } from "react"
import Modal from "../../../components/Modal"
import type { ChartType, ParsedDB } from "../../../types"
import { ColorPicker } from "../../../components/ColorPicker"
import { autoDeriveColors } from "../../../utils/colorUtils"
import { useStyleGuideStore } from "../../../store/styleGuide"

const BUILTIN_CHART_TYPES = ["PIE", "DONUT", "BAR_HORIZONTAL", "BAR_CLUSTERED", "COLUMN_CLUSTERED"]

interface ApplyResult {
  questionId: string
  breakdownIds: string[]
  chartType: ChartType
  colors: string[]
}

interface Props {
  open: boolean
  onClose(): void
  onApply(r: ApplyResult): void
  db: ParsedDB | null
}

export default function AddChartModal({ open, onClose, onApply, db }: Props) {
  const styleGuide = useStyleGuideStore((s) => s.styleGuide)
  const allChartTypes = styleGuide?.available_chart_types?.length
    ? styleGuide.available_chart_types
    : BUILTIN_CHART_TYPES

  const [questionId, setQuestionId] = useState<string>("")
  const [breakdownIds, setBreakdownIds] = useState<Set<string>>(new Set())
  const hasRealBreakdown = Array.from(breakdownIds).some((bid) => bid !== 'general')
  const chartTypes = hasRealBreakdown
    ? allChartTypes
    : allChartTypes.filter((t) => t !== 'TABLE_WITH_MINIBARS')
  const [chartType, setChartType] = useState<ChartType>((chartTypes[0] ?? "PIE") as ChartType)
  const [colorPickerOpen, setColorPickerOpen] = useState(false)
  const [primaryColor, setPrimaryColor] = useState("")
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [advancedColors, setAdvancedColors] = useState<string[]>([])
  const [openAdvancedPicker, setOpenAdvancedPicker] = useState<number | null>(null)

  // Sync chartType when available chart types change (style guide loads after mount)
  useEffect(() => {
    setChartType((chartTypes[0] ?? "PIE") as ChartType)
  }, [chartTypes.join(",")])

  useEffect(() => {
    if (open && db && db.questions.length > 0) {
      setQuestionId(db.questions[0].id)
      setBreakdownIds(new Set())
      setPrimaryColor("")
      setShowAdvanced(false)
      setAdvancedColors([])
    }
  }, [open, db])

  // Reset advanced colors count when breakdowns change
  useEffect(() => {
    setAdvancedColors(Array.from(breakdownIds).map(() => ""))
  }, [breakdownIds])

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
    const nOptions = breakdownIds.size
    const finalColors = showAdvanced && advancedColors.some(Boolean)
      ? advancedColors
      : primaryColor
        ? autoDeriveColors(primaryColor, nOptions)
        : []

    onApply({
      questionId,
      breakdownIds: Array.from(breakdownIds),
      chartType,
      colors: finalColors,
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
        aria-label="Tipo de chart"
        value={chartType}
        onChange={(e) => setChartType(e.target.value as ChartType)}
        className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
      >
        {chartTypes.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>

      {/* Color section */}
      <div className="mt-2">
        <label className="block text-xs text-neutral-400 mb-2">Color principal</label>
        <div className="relative">
          <button
            type="button"
            aria-label="Abrir selector de color principal"
            onClick={() => setColorPickerOpen((v) => !v)}
            className="flex items-center gap-2 px-3 py-2 bg-neutral-800 border border-neutral-700 rounded text-sm hover:bg-neutral-700"
          >
            {primaryColor ? (
              <div className="w-4 h-4 rounded border border-neutral-600" style={{ backgroundColor: primaryColor }} />
            ) : (
              <span className="text-neutral-500 text-xs">Auto</span>
            )}
            <span className="text-xs text-neutral-300">{primaryColor || "Auto"} ▾</span>
          </button>
          <ColorPicker
            open={colorPickerOpen}
            value={primaryColor}
            onChange={(c) => { setPrimaryColor(c); setColorPickerOpen(false) }}
            onClose={() => setColorPickerOpen(false)}
          />
        </div>

        {/* Avanzados expand */}
        <button
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          className="mt-2 text-xs text-neutral-500 hover:text-neutral-300"
        >
          {showAdvanced ? "▴" : "▾"} Avanzados (N colores individuales)
        </button>

        {showAdvanced && (
          <div className="mt-2 space-y-2">
            {advancedColors.map((color, i) => (
              <div key={i} className="flex items-center gap-2">
                <span className="text-xs text-neutral-400 w-16">Color {i + 1}</span>
                <div className="relative">
                  <button
                    type="button"
                    aria-label={`Color avanzado ${i + 1}`}
                    onClick={() => setOpenAdvancedPicker(openAdvancedPicker === i ? null : i)}
                    className="flex items-center gap-2 px-2 py-1 bg-neutral-800 border border-neutral-700 rounded text-xs"
                  >
                    <div className="w-4 h-4 rounded border border-neutral-600" style={{ backgroundColor: color || "#7F7F7F" }} />
                    <span>{color || "Auto"}</span>
                  </button>
                  <ColorPicker
                    open={openAdvancedPicker === i}
                    value={color}
                    onChange={(c) => {
                      const next = [...advancedColors]
                      next[i] = c
                      setAdvancedColors(next)
                      setOpenAdvancedPicker(null)
                    }}
                    onClose={() => setOpenAdvancedPicker(null)}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Modal>
  )
}
