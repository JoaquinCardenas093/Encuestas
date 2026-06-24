import { useState } from "react"
import Modal from "../../../components/Modal"
import * as api from "../../../api/client"
import { useProjectStore } from "../../../store/project"
import type { Analysis, AnalysisScope, ParsedDB, Slide } from "../../../types"

interface Props {
  open: boolean
  slide: Slide | null
  db: ParsedDB | null
  onClose(): void
  onAdd(a: Omit<Analysis, "id">): void
}

export default function AddAnalysisModal({ open, slide, db, onClose, onAdd }: Props) {
  const [scope, setScope] = useState<AnalysisScope>("slide")
  const [targetId, setTargetId] = useState<string>("")
  const [text, setText] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!open || !slide || !db) return null

  const state = useProjectStore((s) => s.state)
  const handleGenerate = async () => {
    setBusy(true); setError(null)
    try {
      const ctx = _buildContext(scope, targetId, slide, db)
      const r = await api.generateAnalysis(scope, ctx, {
        state,
        slide_id: slide.id,
        target_id: scope === "slide" ? null : targetId,
      })
      setText(r.text)
    } catch (e) {
      setError((e as { message?: string }).message || "Error")
      setText("[Análisis no disponible — editar manualmente]")
    } finally {
      setBusy(false)
    }
  }

  const handleAccept = () => {
    if (!text.trim()) return
    onAdd({
      scope, target_id: scope === "slide" ? null : targetId,
      text, ai_generated: true, edited: false,
    })
    setText(""); setScope("slide"); setTargetId("")
    onClose()
  }

  return (
    <Modal open={open} onClose={onClose} title="Agregar análisis" footer={
      <>
        <button onClick={onClose} className="px-3 py-1.5 text-sm rounded bg-neutral-700">Cancelar</button>
        <button onClick={handleAccept} disabled={!text.trim()} className="px-3 py-1.5 text-sm rounded bg-accent text-neutral-900 font-semibold disabled:opacity-40">Aceptar</button>
      </>
    }>
      <div className="text-xs text-neutral-400 mb-1">Scope</div>
      <div className="flex gap-3 mb-3">
        {(["slide", "question", "chart"] as AnalysisScope[]).map((s) => (
          <label key={s} className="flex items-center gap-1 text-sm">
            <input type="radio" name="scope" checked={scope === s} onChange={() => { setScope(s); setTargetId("") }} aria-label={s} />
            {s}
          </label>
        ))}
      </div>

      {scope === "question" && (
        <>
          <label className="block text-xs text-neutral-400 mb-1">Pregunta</label>
          <select value={targetId} onChange={(e) => setTargetId(e.target.value)} className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm">
            <option value="">— Seleccionar —</option>
            {Array.from(new Set(slide.charts.map((c) => c.question_id))).map((qid) => {
              const q = db.questions.find((q) => q.id === qid)
              return <option key={qid} value={qid}>{q?.code}: {q?.text}</option>
            })}
          </select>
        </>
      )}

      {scope === "chart" && (
        <>
          <label className="block text-xs text-neutral-400 mb-1">Chart</label>
          <select value={targetId} onChange={(e) => setTargetId(e.target.value)} className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm">
            <option value="">— Seleccionar —</option>
            {slide.charts.map((c) => {
              const q = db.questions.find((q) => q.id === c.question_id)
              const b = db.breakdowns.find((b) => b.id === (c.breakdown_ids[0] ?? "general"))
              return <option key={c.id} value={c.id}>{q?.code} · {b?.label} · {c.chart_type}</option>
            })}
          </select>
        </>
      )}

      <button
        onClick={handleGenerate}
        disabled={busy || (scope !== "slide" && !targetId)}
        className="w-full mb-3 bg-purple-700 hover:bg-purple-600 text-white text-sm py-1.5 rounded disabled:opacity-40"
      >
        {busy ? "Generando..." : "✨ Generar con AI"}
      </button>

      <label className="block text-xs text-neutral-400 mb-1">Texto análisis (editable)</label>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={5}
        className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
        placeholder="Generá o escribí manualmente..."
      />
      {error && <p className="text-xs text-red-400 mt-2">{error}</p>}
    </Modal>
  )
}


function _buildContext(scope: AnalysisScope, targetId: string, slide: Slide, db: ParsedDB) {
  const charts = scope === "chart"
    ? slide.charts.filter((c) => c.id === targetId)
    : scope === "question"
      ? slide.charts.filter((c) => c.question_id === targetId)
      : slide.charts

  const firstChart = charts[0]
  const q = firstChart ? db.questions.find((q) => q.id === firstChart.question_id) : null
  const b = firstChart ? db.breakdowns.find((b) => b.id === (firstChart.breakdown_ids[0] ?? "general")) : null

  return {
    section_title: slide.title || "",
    question_text: q?.text || "",
    options: q?.options || [],
    breakdown_label: b?.label || "",
    data: {},  // backend fills if needed; for MVP we send empty since extractor lives backend-side
  }
}
