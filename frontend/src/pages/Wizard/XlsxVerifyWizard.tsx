import { Check, AlertTriangle, Trash2, Plus } from "lucide-react"
import { useState } from "react"
import { useProjectStore } from "../../store/project"
import type { ParsedDB } from "../../types"
import * as D from "./mappingDraft"
import SheetGrid from "./SheetGrid"
import { paintToParsedDb, parsedDbToPaint, paintCountCells, type PaintMap } from "./sheetPaint"
import { fetchSheetGrid, fetchCountCells } from "../../api/client"
import CellValuesEditor from "./CellValuesEditor"

const FONTS = [
  "Default del template",
  "Arial",
  "Calibri",
  "Helvetica",
  "Times New Roman",
  "Roboto",
  "Open Sans",
  "Lato",
  "Montserrat",
  "Inter",
  "Custom",
]

interface Props {
  onConfirm(): void
}

export default function XlsxVerifyWizard({ onConfirm }: Props) {
  const parsedDb = useProjectStore((s) => s.parsedDb)
  const setParsedDb = useProjectStore((s) => s.setParsedDb)
  const storeState = useProjectStore((s) => s.state)
  const dbPath = storeState?.inputs.db_path ?? ""
  const updateState = (mut: (prev: NonNullable<typeof storeState>) => NonNullable<typeof storeState>) => {
    const cur = useProjectStore.getState().state
    if (cur) useProjectStore.setState({ state: mut(cur) })
  }
  const [font, setFont] = useState(FONTS[0])
  const [customFont, setCustomFont] = useState("")
  const [mode, setMode] = useState<"list" | "fields" | "excel">("list")
  const [draft, setDraft] = useState<ParsedDB | null>(null)
  const [gridCells, setGridCells] = useState<string[][] | null>(null)
  const [paint, setPaint] = useState<PaintMap>({})
  const [gridError, setGridError] = useState<string | null>(null)
  const [gridTruncated, setGridTruncated] = useState(false)

  if (!parsedDb) return <div className="p-6">No hay datos detectados. Volvé a subir el xlsx.</div>

  const view = mode === "fields" && draft ? draft : parsedDb

  const handleConfirm = () => {
    const finalFont = font === "Default del template" ? null : font === "Custom" ? customFont : font
    updateState((p) => ({ ...p, inputs: { ...p.inputs, font_override: finalFont } }))
    onConfirm()
  }

  const enterFields = () => {
    setDraft(parsedDb)
    setMode("fields")
  }

  const enterExcel = async () => {
    setGridError(null)
    setGridTruncated(false)
    const res = await fetchSheetGrid(dbPath)
    if (res.error || !res.cells?.length) {
      setGridError(res.error ?? "No se pudieron leer las celdas")
      setGridTruncated(false)
      return
    }
    const cells = res.cells
    setGridCells(cells)
    setGridTruncated(!!res.truncated)
    let nextPaint = parsedDbToPaint(cells, parsedDb!)
    // Auto-seleccionar las celdas de conteo detectadas al abrir el editor.
    try {
      const cc = await fetchCountCells(storeState)
      if (!cc.error) {
        const nRows = cells.length
        const nCols = cells.reduce((m, row) => Math.max(m, row.length), 0)
        const { paint: merged, dropped } = paintCountCells(nextPaint, cc.cells, nRows, nCols)
        nextPaint = merged
        if (dropped > 0) setGridError(`${dropped} celdas de conteo quedaron fuera de la vista (hoja truncada a 200×120).`)
      }
    } catch { /* si falla el auto-marcado, seguimos con el paint base */ }
    setPaint(nextPaint)
    setMode("excel")
  }

  return (
    <div className="h-full overflow-y-auto">
    <div className="max-w-2xl mx-auto p-6 text-neutral-100">
      <h2 className="text-lg font-semibold mb-1">Verificación de datos detectados</h2>
      <p className="text-sm text-neutral-400 mb-4">Revisá lo detectado por la heurística. 1 click para confirmar.</p>

      {/* 3-view mode switch */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setMode("list")}
          className={mode === "list" ? "font-semibold text-neutral-100" : "text-neutral-400 hover:text-neutral-200"}
        >Lista</button>
        <span className="text-neutral-600">|</span>
        <button
          onClick={enterFields}
          className={mode === "fields" ? "font-semibold text-neutral-100" : "text-neutral-400 hover:text-neutral-200"}
        >Editar campos</button>
        <span className="text-neutral-600">|</span>
        <button
          onClick={enterExcel}
          className={mode === "excel" ? "font-semibold text-neutral-100" : "text-neutral-400 hover:text-neutral-200"}
        >Editar en Excel</button>
      </div>

      {mode === "fields" && (
        <p className="text-xs text-neutral-500 mb-3">Si el texto editado no coincide con la hoja, ese ítem queda sin datos.</p>
      )}

      {/* Excel paint view */}
      {mode === "excel" && gridCells && (
        <div>
          {gridTruncated && (
            <p className="text-xs text-amber-400 mt-1">Hoja muy grande — se muestran las primeras 200 filas × 120 columnas.</p>
          )}
          <SheetGrid cells={gridCells} paint={paint} onChange={setPaint} />
          <div className="flex justify-end gap-2 mt-3">
            <button
              onClick={() => setMode("list")}
              className="px-4 py-2 text-sm rounded bg-neutral-700 text-neutral-200"
            >Cancelar</button>
            <button
              onClick={() => {
                const { db, warnings } = paintToParsedDb(gridCells, paint, parsedDb!)
                if (warnings.length && !confirm(`Avisos:\n${warnings.join("\n")}\n\n¿Guardar igual?`)) return
                setParsedDb(db)
                setMode("list")
              }}
              className="px-4 py-2 text-sm rounded bg-accent text-neutral-900 font-semibold"
            >Guardar</button>
          </div>
        </div>
      )}
      {mode === "excel" && gridError && <p className="text-xs text-red-400 mt-2">{gridError}</p>}

      {/* Lista + fields views: Questions */}
      {(mode === "list" || mode === "fields") && (
        <section className="mb-6">
          <h3 className="text-sm font-semibold text-neutral-300 mb-2">Preguntas detectadas ({view.questions.length})</h3>
          <ul className="space-y-2 text-sm">
            {view.questions.map((q) => (
              <li key={q.id} className="bg-neutral-800 rounded px-3 py-2">
                <div className="flex items-center gap-2 mb-1">
                  {q.confidence >= 0.9 ? <Check size={14} className="text-green-400" /> : <AlertTriangle size={14} className="text-amber-400" />}
                  <span className="font-semibold">{q.code}:</span>
                  {mode === "fields" ? (
                    <input
                      value={q.text}
                      onChange={(e) => setDraft(D.setQuestionText(draft!, q.id, e.target.value))}
                      className="flex-1 bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-sm"
                    />
                  ) : (
                    <span className="truncate">{q.text}</span>
                  )}
                  {mode === "fields" && (
                    <button
                      onClick={() => setDraft(D.deleteQuestion(draft!, q.id))}
                      className="ml-auto text-neutral-500 hover:text-red-400"
                      title="Eliminar pregunta"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                  {mode === "list" && (
                    <span className="ml-auto text-xs text-neutral-500">({q.options.length} opciones)</span>
                  )}
                </div>
                {mode === "fields" && (
                  <div className="mt-1 space-y-1 pl-5">
                    {q.options.map((opt, i) => (
                      <div key={i} className="flex items-center gap-1">
                        <input
                          value={opt}
                          onChange={(e) => setDraft(D.setQuestionOption(draft!, q.id, i, e.target.value))}
                          className="flex-1 bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-sm"
                        />
                        <button
                          onClick={() => setDraft(D.removeQuestionOption(draft!, q.id, i))}
                          className="text-neutral-500 hover:text-red-400"
                          title="Eliminar opción"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    ))}
                    <button
                      onClick={() => setDraft(D.addQuestionOption(draft!, q.id))}
                      className="flex items-center gap-1 text-xs text-neutral-400 hover:text-neutral-200 mt-1"
                    >
                      <Plus size={12} /> Agregar opción
                    </button>
                  </div>
                )}
                {mode === "list" && (
                  <div className="text-xs text-neutral-500 pl-5 mt-1">{q.options.join(", ")}</div>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Breakdowns */}
      {(mode === "list" || mode === "fields") && (
        <section className="mb-6">
          <h3 className="text-sm font-semibold text-neutral-300 mb-2">Breakdowns ({view.breakdowns.length})</h3>
          <ul className="space-y-2 text-sm">
            {view.breakdowns.map((b) => (
              <li key={b.id} className="bg-neutral-800 rounded px-3 py-2">
                <div className="flex items-center gap-2 mb-1">
                  {mode === "fields" && b.id !== "general" ? (
                    <input
                      value={b.label}
                      onChange={(e) => setDraft(D.setBreakdownLabel(draft!, b.id, e.target.value))}
                      className="flex-1 bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-sm font-semibold"
                    />
                  ) : (
                    <span className="font-semibold">{b.label}</span>
                  )}
                  {mode === "fields" && b.id !== "general" && (
                    <button
                      onClick={() => setDraft(D.deleteBreakdown(draft!, b.id))}
                      className="ml-auto text-neutral-500 hover:text-red-400"
                      title="Eliminar breakdown"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
                {mode === "fields" && b.id !== "general" ? (
                  <div className="space-y-1 pl-2">
                    {b.categories.map((cat, i) => (
                      <div key={i} className="flex items-center gap-1">
                        <input
                          value={cat}
                          onChange={(e) => setDraft(D.setBreakdownCategory(draft!, b.id, i, e.target.value))}
                          className="flex-1 bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-sm"
                        />
                        <button
                          onClick={() => setDraft(D.removeBreakdownCategory(draft!, b.id, i))}
                          className="text-neutral-500 hover:text-red-400"
                          title="Eliminar categoría"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    ))}
                    <button
                      onClick={() => setDraft(D.addBreakdownCategory(draft!, b.id))}
                      className="flex items-center gap-1 text-xs text-neutral-400 hover:text-neutral-200 mt-1"
                    >
                      <Plus size={12} /> Agregar categoría
                    </button>
                  </div>
                ) : (
                  <span className="text-neutral-400">{b.categories.join(", ")}</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Sample size + Data blocks */}
      {(mode === "list" || mode === "fields") && (
        <section className="mb-6 text-sm">
          <div className="mb-2 flex items-center gap-2">
            <span>Sample size:</span>
            {mode === "fields" ? (
              <input
                type="number"
                value={view.sample_size}
                onChange={(e) => setDraft(D.setSampleSize(draft!, parseInt(e.target.value, 10) || 0))}
                className="w-24 bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-sm"
              />
            ) : (
              <strong>{view.sample_size}</strong>
            )}
          </div>
          {mode === "fields" ? (
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="w-28 text-neutral-400">Counts cols:</span>
                <input
                  value={view.data_blocks.counts_cols.join(", ")}
                  onChange={(e) => setDraft(D.setDataBlock(draft!, "counts_cols", D.parseColList(e.target.value)))}
                  className="flex-1 bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-sm"
                  placeholder="ej: 1, 2, 3"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="w-28 text-neutral-400">%Row cols:</span>
                <input
                  value={view.data_blocks.pct_row_cols.join(", ")}
                  onChange={(e) => setDraft(D.setDataBlock(draft!, "pct_row_cols", D.parseColList(e.target.value)))}
                  className="flex-1 bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-sm"
                  placeholder="ej: 4, 5, 6"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="w-28 text-neutral-400">%Col cols:</span>
                <input
                  value={view.data_blocks.pct_col_cols.join(", ")}
                  onChange={(e) => setDraft(D.setDataBlock(draft!, "pct_col_cols", D.parseColList(e.target.value)))}
                  className="flex-1 bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-sm"
                  placeholder="ej: 7, 8, 9"
                />
              </div>
            </div>
          ) : (
            <div>Bloques cols — Counts: {view.data_blocks.counts_cols.join("–")} · %Row: {view.data_blocks.pct_row_cols.join("–")} · %Col: {view.data_blocks.pct_col_cols.join("–")}</div>
          )}
          {mode === "fields" ? (
            <>
              <label className="block text-xs text-neutral-400 mb-1 mt-3">Fila Total (denominadores)</label>
              <input
                type="number"
                value={view.total_row ?? ""}
                onChange={(e) => setDraft(D.setTotalRow(draft!, parseInt(e.target.value, 10) || 0))}
                className="w-32 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
              />
            </>
          ) : (
            <div>Fila Total: <strong>{view.total_row || "—"}</strong></div>
          )}
          {!view.total_row && (
            <p className="text-xs text-amber-400 mt-1">No se detectó la fila Total — los porcentajes quedarán vacíos. Editá "Fila Total".</p>
          )}
        </section>
      )}

      {/* Font selector (always visible in list mode) */}
      {mode === "list" && (
        <section className="mb-6">
          <label htmlFor="font-select" className="block text-xs font-medium text-neutral-400 mb-1">Fuente (opcional)</label>
          <select
            id="font-select"
            value={font}
            onChange={(e) => setFont(e.target.value)}
            className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
          >
            {FONTS.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
          {font === "Custom" && (
            <input
              value={customFont}
              onChange={(e) => setCustomFont(e.target.value)}
              placeholder="Nombre exacto de la fuente"
              className="w-full mt-2 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
            />
          )}
        </section>
      )}

      {/* Footer buttons */}
      {mode === "list" && (
        <div className="flex justify-end gap-2">
          <button
            onClick={handleConfirm}
            className="px-4 py-2 text-sm rounded bg-accent text-neutral-900 font-semibold"
          >Confirmar</button>
        </div>
      )}

      {mode === "fields" && draft && (
        <CellValuesEditor
          state={storeState}
          draft={draft}
          onChange={(db) => setDraft(db)}
        />
      )}

      {mode === "fields" && (
        <div className="flex justify-end gap-2">
          <button
            onClick={() => { setMode("list"); setDraft(null) }}
            className="px-4 py-2 text-sm rounded bg-neutral-700 text-neutral-200"
          >Cancelar</button>
          <button
            onClick={() => { if (draft) setParsedDb(draft); setMode("list"); setDraft(null) }}
            className="px-4 py-2 text-sm rounded bg-accent text-neutral-900 font-semibold"
          >Guardar</button>
        </div>
      )}
    </div>
    </div>
  )
}
