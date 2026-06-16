import { Check, AlertTriangle } from "lucide-react"
import { useState } from "react"
import { useProjectStore } from "../../store/project"

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
  const setState = useProjectStore((s) => s.state)
  const updateState = (mut: (prev: NonNullable<typeof setState>) => NonNullable<typeof setState>) => {
    const cur = useProjectStore.getState().state
    if (cur) useProjectStore.setState({ state: mut(cur) })
  }
  const [font, setFont] = useState(FONTS[0])
  const [customFont, setCustomFont] = useState("")

  if (!parsedDb) return <div className="p-6">No hay datos detectados. Volvé a subir el xlsx.</div>

  const handleConfirm = () => {
    const finalFont = font === "Default del template" ? null : font === "Custom" ? customFont : font
    updateState((p) => ({ ...p, inputs: { ...p.inputs, font_override: finalFont } }))
    onConfirm()
  }

  return (
    <div className="h-full overflow-y-auto">
    <div className="max-w-2xl mx-auto p-6 text-neutral-100">
      <h2 className="text-lg font-semibold mb-1">Verificación de datos detectados</h2>
      <p className="text-sm text-neutral-400 mb-6">Revisá lo detectado por la heurística. 1 click para confirmar.</p>

      <section className="mb-6">
        <h3 className="text-sm font-semibold text-neutral-300 mb-2">Preguntas detectadas ({parsedDb.questions.length})</h3>
        <ul className="space-y-1 text-sm">
          {parsedDb.questions.map((q) => (
            <li key={q.id} className="flex items-center gap-2 bg-neutral-800 rounded px-3 py-2">
              {q.confidence >= 0.9 ? <Check size={14} className="text-green-400" /> : <AlertTriangle size={14} className="text-amber-400" />}
              <span className="font-semibold">{q.code}:</span> <span className="truncate">{q.text}</span>
              <span className="ml-auto text-xs text-neutral-500">({q.options.length} opciones)</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="mb-6">
        <h3 className="text-sm font-semibold text-neutral-300 mb-2">Breakdowns ({parsedDb.breakdowns.length})</h3>
        <ul className="space-y-1 text-sm">
          {parsedDb.breakdowns.map((b) => (
            <li key={b.id} className="bg-neutral-800 rounded px-3 py-2">
              <span className="font-semibold">{b.label}:</span>{" "}
              <span className="text-neutral-400">{b.categories.join(", ")}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="mb-6 text-sm">
        <div>Sample size: <strong>{parsedDb.sample_size}</strong></div>
        <div>Bloques cols — Counts: {parsedDb.data_blocks.counts_cols.join("–")} · %Row: {parsedDb.data_blocks.pct_row_cols.join("–")} · %Col: {parsedDb.data_blocks.pct_col_cols.join("–")}</div>
      </section>

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

      <div className="flex justify-end gap-2">
        <button
          disabled
          title="Próximamente — usá el xlsx con la convención esperada"
          className="px-4 py-2 text-sm rounded bg-neutral-800 text-neutral-500 cursor-not-allowed"
        >Editar mapping manual (próximamente)</button>
        <button onClick={handleConfirm} className="px-4 py-2 text-sm rounded bg-accent text-neutral-900 font-semibold">Confirmar</button>
      </div>
    </div>
    </div>
  )
}
