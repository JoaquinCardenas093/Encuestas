import { useEffect, useRef, useState } from "react"
import { Plus, Trash2, RefreshCw, Eye, Database } from "lucide-react"
import { useStyleGuideStore } from "../../store/styleGuide"
import StyleGuideViewer from "./StyleGuideViewer"
import AnalysisProgressModal from "./AnalysisProgressModal"

export default function TrainingPage() {
  const {
    styleGuide, isLoading, corpus, analysisJob,
    loadStyleGuide, loadCorpus, addPPT, deletePPT,
    analyzeWithAI, clearAnalysisJob,
  } = useStyleGuideStore((s) => s)

  const [showStyleGuide, setShowStyleGuide] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    loadStyleGuide()
    loadCorpus()
  }, [])

  const handleAddFile = async (file: File) => {
    await addPPT(file)
  }

  const handleDelete = async (filename: string) => {
    if (!window.confirm(`¿Eliminar ${filename} del corpus?`)) return
    await deletePPT(filename)
  }

  const hasManualEdits = styleGuide && Object.keys(styleGuide.manual_edits).length > 0

  return (
    <div className="p-6 max-w-5xl mx-auto text-neutral-100">
      {/* Header */}
      <header className="mb-6">
        <h2 className="text-lg font-semibold">Corpus de entrenamiento</h2>
        {styleGuide && (
          <p className="text-sm text-neutral-400 mt-1">
            Style guide {styleGuide.is_builtin ? (
              <span className="text-amber-400 font-semibold">built-in (fallback)</span>
            ) : (
              <span className="text-green-400 font-semibold">AI ✓</span>
            )}
            {" · "}
            {styleGuide.patterns.length} patterns
            {styleGuide.generated_at && (
              <> · actualizado {new Date(styleGuide.generated_at).toLocaleDateString()}</>
            )}
            {hasManualEdits && (
              <span className="ml-2 text-amber-400"
                title={`${Object.keys(styleGuide.manual_edits).length} patterns editados manualmente`}>
                ✎ edits manuales
              </span>
            )}
          </p>
        )}
      </header>

      {/* Corpus section */}
      <section className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Database size={16} />
            PPTs en corpus ({corpus.length})
          </h3>
          <button
            onClick={() => fileRef.current?.click()}
            disabled={isLoading}
            className="text-sm bg-accent text-neutral-900 font-semibold px-3 py-1.5 rounded flex items-center gap-1 disabled:opacity-40"
          >
            <Plus size={14} /> Agregar PPT al corpus
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".pptx"
            className="hidden"
            aria-label="Seleccionar PPT"
            onChange={(e) => e.target.files?.[0] && handleAddFile(e.target.files[0])}
          />
        </div>

        <div className="border border-neutral-700 rounded-lg overflow-hidden">
          {corpus.length === 0 && !isLoading && (
            <div className="text-center text-neutral-500 py-8 text-sm">
              Corpus vacío. Agregá PPTs de training para analizar el estilo.
            </div>
          )}
          {corpus.map((pptx) => (
            <div
              key={pptx.filename}
              className="flex items-center justify-between px-4 py-3 border-b border-neutral-800 last:border-b-0 hover:bg-neutral-800/50"
            >
              <div>
                <span className="text-sm font-medium">{pptx.filename}</span>
                <span className="text-xs text-neutral-500 ml-3">
                  {pptx.slides_with_charts} charts · agregado {new Date(pptx.added_at).toLocaleDateString()}
                </span>
              </div>
              <button
                onClick={() => handleDelete(pptx.filename)}
                aria-label="eliminar"
                className="text-neutral-500 hover:text-red-400 p-1"
              >
                <Trash2 size={15} />
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* Style Guide section */}
      <section className="mb-6">
        <div className="flex items-center gap-3 mb-3">
          <h3 className="text-sm font-semibold">Style guide</h3>
          <button
            onClick={() => setShowStyleGuide((v) => !v)}
            disabled={!styleGuide}
            className="text-xs text-neutral-400 hover:text-neutral-200 flex items-center gap-1 disabled:opacity-40"
          >
            <Eye size={12} />
            {showStyleGuide ? "Ocultar" : "Ver style guide"}
          </button>
          <button
            onClick={analyzeWithAI}
            disabled={isLoading || corpus.length === 0}
            className="ml-auto text-sm bg-purple-700 hover:bg-purple-600 text-white font-semibold px-3 py-1.5 rounded flex items-center gap-1 disabled:opacity-40"
          >
            <RefreshCw size={14} />
            Re-analizar con AI
          </button>
        </div>

        {styleGuide && (
          <div className="text-xs text-neutral-500 mb-3">
            <span className="font-medium text-neutral-300">Tipos disponibles:</span>{" "}
            {styleGuide.available_chart_types.join(", ") || "—"}
          </div>
        )}

        {showStyleGuide && styleGuide && (
          <StyleGuideViewer styleGuide={styleGuide} />
        )}
      </section>

      {/* Analysis Progress Modal */}
      {analysisJob && (
        <AnalysisProgressModal
          job={analysisJob}
          onClose={clearAnalysisJob}
        />
      )}
    </div>
  )
}
