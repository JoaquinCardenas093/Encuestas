import { useState } from "react"
import Modal from "../../../components/Modal"
import * as api from "../../../api/client"
import { useProjectStore } from "../../../store/project"

interface Props {
  open: boolean
  onClose(): void
}

export default function ExportModal({ open, onClose }: Props) {
  const state = useProjectStore((s) => s.state)
  const [name, setName] = useState(`AurumEncuestas_${new Date().toISOString().replace(/[:.]/g, "").slice(0, 13)}.pptx`)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  if (!open || !state) return null

  const handleExport = async () => {
    setBusy(true); setError(null); setDone(false)
    try {
      await api.exportPptx(state, name)
      setDone(true)
    } catch (e) {
      setError((e as { message?: string }).message || "Error desconocido")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Exportar PPTX" footer={
      <>
        <button onClick={onClose} className="px-3 py-1.5 text-sm rounded bg-neutral-700">Cancelar</button>
        <button onClick={handleExport} disabled={busy} className="px-3 py-1.5 text-sm rounded bg-accent text-neutral-900 font-semibold disabled:opacity-40">
          {busy ? "Generando..." : "Descargar"}
        </button>
      </>
    }>
      <label className="block text-xs text-neutral-400 mb-1">Nombre archivo</label>
      <input value={name} onChange={(e) => setName(e.target.value)} className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm" />
      {done && <div className="mt-1 text-xs text-green-400">✓ Descarga iniciada</div>}
      {error && <div className="mt-1 text-xs text-red-400">{error}</div>}
    </Modal>
  )
}
