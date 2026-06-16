import { useState } from "react"
import Modal from "../../../components/Modal"

interface Props {
  open: boolean
  onClose(): void
  onCreate(title: string): void
}

export default function AddSeparatorModal({ open, onClose, onCreate }: Props) {
  const [title, setTitle] = useState("")
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return
    onCreate(title.trim())
    setTitle("")
    onClose()
  }
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Nuevo separador"
      footer={
        <>
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm rounded bg-neutral-700"
          >
            Cancelar
          </button>
          <button
            onClick={handleSubmit}
            className="px-3 py-1.5 text-sm rounded bg-accent text-neutral-900 font-semibold"
          >
            Crear
          </button>
        </>
      }
    >
      <form onSubmit={handleSubmit}>
        <label htmlFor="sep-title" className="block text-xs text-neutral-400 mb-1">
          Título sección
        </label>
        <input
          id="sep-title"
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
        />
      </form>
    </Modal>
  )
}
