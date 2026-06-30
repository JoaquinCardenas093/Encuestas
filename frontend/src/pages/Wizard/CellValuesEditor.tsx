import { useEffect, useState } from "react"
import type { ParsedDB } from "../../types"
import { fetchCellValues, type CellValuesResponse } from "../../api/client"
import { setValueOverride } from "./mappingDraft"

interface Props {
  state: any                 // saved ProjectState (for fetch)
  draft: ParsedDB            // current draft (holds overrides)
  onChange(db: ParsedDB): void
}

const keyFor = (q: string, b: string, cat: string, opt: string) => `${q}|${b}|${cat}|${opt}`

export default function CellValuesEditor({ state, draft, onChange }: Props) {
  const [qid, setQid] = useState(draft.questions[0]?.id ?? "")
  const [bid, setBid] = useState(draft.breakdowns[0]?.id ?? "general")
  const [data, setData] = useState<CellValuesResponse | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (!qid || !bid) return
    let active = true
    fetchCellValues(state, qid, bid).then((r) => {
      if (!active) return
      if (r.error) { setErr(r.error); setData(null) } else { setErr(null); setData(r) }
    }).catch((e) => { if (active) { setErr(String(e)); setData(null) } })
    return () => { active = false }
  }, [state, qid, bid])

  const ov = draft.value_overrides ?? {}
  const cellCount = (cat: string, opt: string) => {
    const o = ov[keyFor(qid, bid, cat, opt)]
    return o?.count != null ? o.count : (data?.cells[opt]?.[cat]?.count ?? 0)
  }
  const cellPct = (cat: string, opt: string) => {
    const o = ov[keyFor(qid, bid, cat, opt)]
    const p = o?.pct != null ? o.pct : data?.cells[opt]?.[cat]?.pct
    return p == null ? "" : (p * 100).toFixed(1)
  }
  const set = (cat: string, opt: string, patch: { count?: number | null; pct?: number | null }) =>
    onChange(setValueOverride(draft, keyFor(qid, bid, cat, opt), patch))

  return (
    <div className="mt-4">
      <div className="text-sm font-semibold text-neutral-300 mb-2">Valores (conteo / %)</div>
      <div className="flex gap-2 mb-2">
        <select value={qid} onChange={(e) => setQid(e.target.value)} className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-sm">
          {draft.questions.map((q) => <option key={q.id} value={q.id}>{q.code}: {q.text.slice(0, 40)}</option>)}
        </select>
        <select value={bid} onChange={(e) => setBid(e.target.value)} className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-sm">
          {draft.breakdowns.map((b) => <option key={b.id} value={b.id}>{b.label}</option>)}
        </select>
      </div>
      {err && <p className="text-xs text-red-400">{err}</p>}
      {data && (
        <div className="overflow-auto">
          <table className="text-xs border-collapse">
            <thead>
              <tr><th className="border border-neutral-700 px-2 py-1 bg-neutral-800" />
                {data.categories.map((c) => <th key={c} className="border border-neutral-700 px-2 py-1 bg-neutral-800 text-neutral-300">{c}</th>)}
              </tr>
            </thead>
            <tbody>
              {data.options.map((opt) => (
                <tr key={opt}>
                  <th className="border border-neutral-700 px-2 py-1 bg-neutral-800 text-neutral-300 text-left">{opt}</th>
                  {data.categories.map((cat) => (
                    <td key={cat} className="border border-neutral-700 px-1 py-1">
                      <div className="flex flex-col gap-0.5">
                        <input type="number" title="conteo" value={cellCount(cat, opt)}
                          onChange={(e) => { const n = parseInt(e.target.value, 10); set(cat, opt, { count: Number.isNaN(n) ? null : n }) }}
                          className="w-16 bg-neutral-900 border border-neutral-700 rounded px-1 text-[11px]" />
                        <input type="number" step="0.1" title="%" value={cellPct(cat, opt)}
                          onChange={(e) => { const n = parseFloat(e.target.value); set(cat, opt, { pct: Number.isNaN(n) ? null : n / 100 }) }}
                          className="w-16 bg-neutral-900 border border-neutral-700 rounded px-1 text-[11px]" />
                      </div>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
