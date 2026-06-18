import { useState } from "react"
import { JsonView, allExpanded, defaultStyles } from "react-json-view-lite"
import "react-json-view-lite/dist/index.css"
import { Edit2, X } from "lucide-react"
import type { StyleGuide, Pattern } from "../../api/training"
import { putPattern } from "../../api/training"

interface Props {
  styleGuide: StyleGuide
}

interface EditState {
  pattern: Pattern
  jsonText: string
  error: string | null
  saving: boolean
}

export default function StyleGuideViewer({ styleGuide }: Props) {
  const [editState, setEditState] = useState<EditState | null>(null)

  const openEdit = (pattern: Pattern) => {
    setEditState({
      pattern,
      jsonText: JSON.stringify(pattern, null, 2),
      error: null,
      saving: false,
    })
  }

  const closeEdit = () => setEditState(null)

  const handleSave = async () => {
    if (!editState) return
    let parsed: Pattern
    try {
      parsed = JSON.parse(editState.jsonText)
    } catch {
      setEditState((s) => s ? { ...s, error: "JSON inválido. Corregí la sintaxis e intentá de nuevo." } : s)
      return
    }
    setEditState((s) => s ? { ...s, saving: true, error: null } : s)
    try {
      await putPattern(editState.pattern.id, parsed)
      closeEdit()
    } catch (e) {
      setEditState((s) => s ? { ...s, saving: false, error: `Error al guardar: ${(e as { message?: string }).message ?? "desconocido"}` } : s)
    }
  }

  return (
    <div className="space-y-4">
      {/* Global info */}
      <div className="border border-neutral-700 rounded-lg p-4">
        <h4 className="text-xs font-semibold uppercase text-neutral-400 mb-3">Global</h4>
        <div className="grid grid-cols-2 gap-4 text-sm mb-3">
          <div>
            <span className="text-neutral-400 text-xs">Fuente:</span>
            <span className="ml-2">{styleGuide.global.typography.font_family}</span>
          </div>
          <div>
            <span className="text-neutral-400 text-xs">Vibe:</span>
            <span className="ml-2 text-xs">{styleGuide.global.vibe}</span>
          </div>
        </div>
        <div>
          <span className="text-neutral-400 text-xs block mb-2">Paleta sugerida:</span>
          <div className="flex gap-2 flex-wrap">
            {styleGuide.global.suggested_palette.map((color) => (
              <div key={color} className="flex items-center gap-1">
                <div
                  className="w-5 h-5 rounded border border-neutral-600"
                  style={{ backgroundColor: color }}
                />
                <span className="text-xs text-neutral-400">{color}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Patterns */}
      <div className="border border-neutral-700 rounded-lg overflow-hidden">
        <div className="bg-neutral-800/50 px-4 py-2 border-b border-neutral-700">
          <span className="text-xs font-semibold uppercase text-neutral-400">
            Patterns ({styleGuide.patterns.length})
          </span>
        </div>
        {styleGuide.patterns.map((pattern) => {
          const isManuallyEdited = pattern.id in styleGuide.manual_edits
          return (
            <div key={pattern.id} className="border-b border-neutral-800 last:border-b-0">
              <div className="flex items-center justify-between px-4 py-3">
                <div>
                  <span className="text-sm font-mono">{pattern.id}</span>
                  <span className="text-xs text-neutral-500 ml-3">priority {pattern.priority}</span>
                  {pattern.extends && (
                    <span className="text-xs text-neutral-500 ml-2">extends {pattern.extends}</span>
                  )}
                  {isManuallyEdited && (
                    <span className="ml-2 text-xs text-amber-400">✎ editado</span>
                  )}
                </div>
                <button
                  onClick={() => openEdit(pattern)}
                  aria-label="editar"
                  className="text-neutral-500 hover:text-neutral-200 flex items-center gap-1 text-xs px-2 py-1 rounded hover:bg-neutral-700"
                >
                  <Edit2 size={12} /> editar
                </button>
              </div>
              <div className="px-4 pb-3">
                <JsonView
                  data={pattern.implementation}
                  shouldExpandNode={allExpanded}
                  style={defaultStyles}
                />
              </div>
            </div>
          )
        })}
      </div>

      {/* Edit Modal */}
      {editState && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
        >
          <div className="bg-neutral-900 border border-neutral-700 rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between px-5 py-4 border-b border-neutral-700">
              <h3 className="text-sm font-semibold">Editar pattern: {editState.pattern.id}</h3>
              <button onClick={closeEdit} className="text-neutral-400 hover:text-neutral-200">
                <X size={18} />
              </button>
            </div>
            <div className="flex-1 p-4 overflow-auto">
              <textarea
                value={editState.jsonText}
                onChange={(e) => setEditState((s) => s ? { ...s, jsonText: e.target.value, error: null } : s)}
                className="w-full h-64 bg-neutral-950 border border-neutral-700 rounded px-3 py-2 text-xs font-mono resize-none focus:outline-none focus:border-neutral-500"
                spellCheck={false}
              />
              {editState.error && (
                <p className="text-red-400 text-xs mt-2">{editState.error}</p>
              )}
            </div>
            <div className="flex justify-end gap-2 px-5 py-3 border-t border-neutral-700">
              <button onClick={closeEdit} className="px-3 py-1.5 text-sm rounded bg-neutral-700 hover:bg-neutral-600">
                Cancelar
              </button>
              <button
                onClick={handleSave}
                disabled={editState.saving}
                className="px-3 py-1.5 text-sm rounded bg-accent text-neutral-900 font-semibold disabled:opacity-40"
              >
                {editState.saving ? "Guardando..." : "Guardar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
