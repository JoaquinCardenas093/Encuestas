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
  const [folder, setFolder] = useState(`${(typeof globalThis !== "undefined" && (globalThis as any).os) ? "" : ""}/Users/${typeof globalThis !== "undefined" ? "" : ""}/Downloads`.replace("//", "/"))
  const [autoOpen, setAutoOpen] = useState(true)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  if (!open || !state) return null

  // default folder fallback if blank
  const effectiveFolder = folder || `~/Downloads`

  const handleExport = async () => {
    setBusy(true); setError(null); setResult(null)
    try {
      const fullPath = `${effectiveFolder.replace(/\/$/, "")}/${name}`
      const r = await api.exportPptx(state, fullPath)
      setResult(r.path)
      if (autoOpen) {
        window.open(`file://${r.path}`)
      }
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
          {busy ? "Exportando..." : "Exportar"}
        </button>
      </>
    }>
      <label className="block text-xs text-neutral-400 mb-1">Nombre archivo</label>
      <input value={name} onChange={(e) => setName(e.target.value)} className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm" />
      <label className="block text-xs text-neutral-400 mb-1">Carpeta</label>
      <input value={folder} onChange={(e) => setFolder(e.target.value)} placeholder="~/Downloads" className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm" />
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={autoOpen} onChange={(e) => setAutoOpen(e.target.checked)} />
        Abrir al terminar
      </label>
      {result && <div className="mt-3 text-xs text-green-400">✓ Exportado a {result}</div>}
      {error && <div className="mt-3 text-xs text-red-400">{error}</div>}
    </Modal>
  )
}
