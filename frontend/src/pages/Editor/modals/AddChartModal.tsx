import { useState, useEffect, useMemo } from "react"
import Modal from "../../../components/Modal"
import type { ChartType, ParsedDB } from "../../../types"
import { ColorPicker } from "../../../components/ColorPicker"
import { autoDeriveColors } from "../../../utils/colorUtils"
import { useStyleGuideStore } from "../../../store/styleGuide"

const BUILTIN_CHART_TYPES = [
  "PIE", "PIE_GROUPED",
  "BAR_HORIZONTAL", "BAR_HORIZONTAL_GROUPED",
  "TABLE_WITH_MINIBARS",
]

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
  const styleGuide = useStyleGuideStore((s) => s.styleGuide)
  const allChartTypes = styleGuide?.available_chart_types?.length
    ? styleGuide.available_chart_types
    : BUILTIN_CHART_TYPES

  const [questionId, setQuestionId] = useState<string>("")
  const [breakdownIds, setBreakdownIds] = useState<Set<string>>(new Set())
  const realBreakdownIds = useMemo(
    () => Array.from(breakdownIds).filter((b) => b !== "general"),
    [breakdownIds],
  )
  const nReal = realBreakdownIds.length
  const chartTypes = useMemo(() => {
    if (nReal === 0) {
      return allChartTypes.filter((t) =>
        t !== "TABLE_WITH_MINIBARS" &&
        t !== "PIE_GROUPED" &&
        t !== "BAR_HORIZONTAL_GROUPED"
      )
    }
    if (nReal >= 2) return ["TABLE_WITH_MINIBARS"]
    return allChartTypes
  }, [allChartTypes.join(","), nReal])
  const [chartType, setChartType] = useState<ChartType>((chartTypes[0] ?? "PIE") as ChartType)
  const [colorPickerOpen, setColorPickerOpen] = useState(false)
  const [primaryColor, setPrimaryColor] = useState("")
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [advancedColors, setAdvancedColors] = useState<string[]>([])
  const [openAdvancedPicker, setOpenAdvancedPicker] = useState<number | null>(null)
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
      setPrimaryColor("")
      setShowAdvanced(false)
      setAdvancedColors([])
      setTitle("")
      setShowLegend(false)
      setGridCols(null)
      setCatTitles({})
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
    if (!questionId) return
    const nOptions = realBreakdownIds.length || breakdownIds.size
    const finalColors = showAdvanced && advancedColors.some(Boolean)
      ? advancedColors
      : primaryColor
        ? autoDeriveColors(primaryColor, nOptions)
        : []

    const catTitlesPayload = Object.keys(catTitles).length ? catTitles : null
    onApply({
      questionId,
      breakdownIds: realBreakdownIds,
      chartType,
      show_legend: showLegend,
      grid_cols: gridCols,
      title: title.trim() || null,
      cat_titles: catTitlesPayload,
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
        disabled={nReal >= 2}
        onChange={(e) => setChartType(e.target.value as ChartType)}
        className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm disabled:opacity-60"
      >
        {chartTypes.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>
      {nReal >= 2 && (
        <p className="text-xs text-neutral-500 mt-1">Con 2+ breakdowns solo se permite TABLE_WITH_MINIBARS.</p>
      )}

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
