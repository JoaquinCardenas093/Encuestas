import { useEffect, useRef, useState } from "react"
import { Plus, Trash2, RefreshCw } from "lucide-react"
import * as tapi from "../../api/training"

export default function TrainingPage() {
  const [pptxs, setPptxs] = useState<tapi.TrainingPPT[]>([])
  const [bankSize, setBankSize] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const refresh = async () => {
    setLoading(true); setError(null)
    try {
      const r = await tapi.listTraining()
      setPptxs(r.pptxs)
      setBankSize(r.bank_size)
    } catch (e) {
      setError((e as { message?: string }).message || "Error")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  const handleAdd = async (f: File) => {
    setLoading(true)
    try {
      await tapi.addTraining(f)
      await refresh()
    } catch (e) {
      setError((e as { message?: string }).message || "Error")
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (filename: string) => {
    if (!window.confirm(`Eliminar ${filename}?`)) return
    await tapi.deleteTraining(filename)
    await refresh()
  }

  const handleReprocess = async () => {
    setLoading(true)
    try {
      await tapi.reprocessTraining()
      await refresh()
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto text-neutral-100">
      <header className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold">Entrenamiento</h2>
          <p className="text-sm text-neutral-400">Banco: {bankSize} layouts de {pptxs.length} PPTs</p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleReprocess} disabled={loading} className="text-sm bg-neutral-700 hover:bg-neutral-600 px-3 py-1.5 rounded flex items-center gap-1 disabled:opacity-40">
            <RefreshCw size={14} /> Re-procesar
          </button>
          <button onClick={() => fileRef.current?.click()} disabled={loading} className="text-sm bg-accent text-neutral-900 font-semibold px-3 py-1.5 rounded flex items-center gap-1">
            <Plus size={14} /> Agregar PPT
          </button>
          <input ref={fileRef} type="file" accept=".pptx" className="hidden" onChange={(e) => e.target.files?.[0] && handleAdd(e.target.files[0])} />
        </div>
      </header>

      {error && <div className="bg-red-900/40 border border-red-900 text-red-300 px-3 py-2 rounded mb-4 text-sm">{error}</div>}

      <table className="w-full text-sm">
        <thead className="text-xs text-neutral-400 border-b border-neutral-700">
          <tr>
            <th className="text-left py-2 px-2">Archivo</th>
            <th className="text-left py-2 px-2">Agregado</th>
            <th className="text-left py-2 px-2">Layouts</th>
            <th className="text-left py-2 px-2">Status</th>
            <th className="py-2 px-2 w-12"></th>
          </tr>
        </thead>
        <tbody>
          {pptxs.length === 0 && !loading && (
            <tr><td colSpan={5} className="text-center text-neutral-500 py-6">Sin training PPTs aún. Agregá uno.</td></tr>
          )}
          {pptxs.map((p) => (
            <tr key={p.filename} className="border-b border-neutral-800">
              <td className="py-2 px-2">{p.filename}</td>
              <td className="py-2 px-2 text-neutral-400">{new Date(p.added_at).toLocaleString()}</td>
              <td className="py-2 px-2">{p.layouts_extracted}</td>
              <td className="py-2 px-2">{p.status === "ok" ? "✓" : "⚠"}</td>
              <td className="py-2 px-2">
                <button onClick={() => handleDelete(p.filename)} className="text-neutral-500 hover:text-red-400">
                  <Trash2 size={14} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
