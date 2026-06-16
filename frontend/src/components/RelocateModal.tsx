import { useState } from "react"
import Modal from "./Modal"

interface Props {
  open: boolean
  missingFiles: { kind: "db" | "template"; original: string }[]
  onClose(): void
  onRelocate(map: { db?: string; template?: string }): void
}

export default function RelocateModal({ open, missingFiles, onClose, onRelocate }: Props) {
  const [dbPath, setDbPath] = useState("")
  const [tplPath, setTplPath] = useState("")
  if (!open) return null
  return (
    <Modal open={open} onClose={onClose} title="Re-localizar archivos" footer={
      <button onClick={() => onRelocate({ db: dbPath || undefined, template: tplPath || undefined })} className="px-3 py-1.5 text-sm rounded bg-accent text-neutral-900 font-semibold">Aplicar</button>
    }>
      <p className="text-sm text-neutral-300 mb-3">No se encontraron estos archivos. Indicá la nueva ruta:</p>
      {missingFiles.map((m) => (
        <div key={m.kind} className="mb-3">
          <label className="block text-xs text-neutral-400 mb-1">{m.kind === "db" ? "DB" : "Template"} (era: {m.original})</label>
          <input
            value={m.kind === "db" ? dbPath : tplPath}
            onChange={(e) => m.kind === "db" ? setDbPath(e.target.value) : setTplPath(e.target.value)}
            placeholder="/ruta/absoluta/al/archivo"
            className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
          />
        </div>
      ))}
    </Modal>
  )
}
