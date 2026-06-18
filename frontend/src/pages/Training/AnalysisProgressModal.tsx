import { CheckCircle, AlertCircle } from "lucide-react"

interface ResultSummary {
  patterns_valid: number
  patterns_dropped: number
  patterns_repaired: number
  estimated_cost_usd?: number
}

interface AnalysisJobState {
  jobId: string
  progress: number
  status: "running" | "done" | "error"
  message: string
  resultSummary?: ResultSummary
  error?: string
}

interface Props {
  job: AnalysisJobState
  onClose(): void
}

export default function AnalysisProgressModal({ job, onClose }: Props) {
  const isDone = job.status === "done"
  const isError = job.status === "error"
  const isRunning = job.status === "running"

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-neutral-900 border border-neutral-700 rounded-xl shadow-2xl w-full max-w-md p-6">
        {/* Title */}
        <div className="flex items-center gap-3 mb-4">
          {isRunning && (
            <div
              role="status"
              aria-label="Analizando"
              className="w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full animate-spin"
            />
          )}
          {isDone && <CheckCircle size={20} className="text-green-400" />}
          {isError && <AlertCircle size={20} className="text-red-400" />}
          <h3 className="text-sm font-semibold">
            {isRunning && "Analizando corpus con AI..."}
            {isDone && "Análisis completado"}
            {isError && "Error en el análisis"}
          </h3>
        </div>

        {/* Progress bar (running only) */}
        {isRunning && (
          <div className="mb-4">
            <div className="w-full bg-neutral-800 rounded-full h-2 mb-2">
              <div
                className="bg-purple-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${job.progress}%` }}
              />
            </div>
            <p className="text-xs text-neutral-400">{job.progress}% — {job.message}</p>
          </div>
        )}

        {/* Status message (done/error) */}
        {!isRunning && (
          <p className={`text-sm mb-4 ${isError ? "text-red-300" : "text-neutral-300"}`}>
            {job.message}
          </p>
        )}

        {/* Result summary (done only) */}
        {isDone && job.resultSummary && (
          <div className="bg-neutral-800 rounded-lg p-4 mb-4 text-sm space-y-1">
            <div className="flex justify-between">
              <span className="text-neutral-400">Patterns válidos</span>
              <span className="font-semibold text-green-400">{job.resultSummary.patterns_valid} patterns válidos</span>
            </div>
            {job.resultSummary.patterns_dropped > 0 && (
              <div className="flex justify-between">
                <span className="text-neutral-400">Eliminados (inválidos)</span>
                <span className="text-amber-400">{job.resultSummary.patterns_dropped}</span>
              </div>
            )}
            {job.resultSummary.patterns_repaired > 0 && (
              <div className="flex justify-between">
                <span className="text-neutral-400">Reparados</span>
                <span className="text-amber-400">{job.resultSummary.patterns_repaired}</span>
              </div>
            )}
            {job.resultSummary.estimated_cost_usd !== undefined && (
              <div className="flex justify-between pt-1 border-t border-neutral-700 mt-2">
                <span className="text-neutral-400">Costo estimado</span>
                <span className="font-mono">${job.resultSummary.estimated_cost_usd.toFixed(2)}</span>
              </div>
            )}
          </div>
        )}

        {/* Close button (done/error) */}
        {(isDone || isError) && (
          <div className="flex justify-end">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm rounded bg-neutral-700 hover:bg-neutral-600 font-medium"
            >
              Cerrar
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
