import { Undo2, Redo2, RotateCcw } from "lucide-react"
import { useProjectStore } from "../../store/project"
import { useKeyboardShortcuts } from "../../hooks/useKeyboardShortcuts"

export default function EditorFooter() {
  const undo = useProjectStore.temporal.getState().undo
  const redo = useProjectStore.temporal.getState().redo
  const resetAll = useProjectStore((s) => s.resetAll)
  const updatedAt = useProjectStore((s) => s.state?.updated_at)

  useKeyboardShortcuts({
    "Cmd+z": undo,
    "Cmd+Shift+z": redo,
  })

  return (
    <footer className="h-10 bg-neutral-800 border-t border-neutral-700 flex items-center px-4 gap-2 text-xs">
      <button onClick={() => undo()} aria-label="undo" className="flex items-center gap-1 bg-neutral-700 hover:bg-neutral-600 px-2 py-1 rounded">
        <Undo2 size={12} /> Undo
      </button>
      <button onClick={() => redo()} aria-label="redo" className="flex items-center gap-1 bg-neutral-700 hover:bg-neutral-600 px-2 py-1 rounded">
        <Redo2 size={12} /> Redo
      </button>
      <button
        onClick={() => {
          if (window.confirm("Borrar todas las slides? No se puede deshacer fácilmente.")) resetAll()
        }}
        aria-label="reset todo"
        className="flex items-center gap-1 bg-red-900/40 hover:bg-red-900/60 border border-red-900 text-red-300 px-2 py-1 rounded"
      >
        <RotateCcw size={12} /> Reset todo
      </button>
      <span className="ml-auto text-neutral-500">{updatedAt && `Actualizado: ${new Date(updatedAt).toLocaleTimeString()}`}</span>
    </footer>
  )
}
