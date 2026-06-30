import { useState } from "react"
import { paintRect, cellKey, colLetter, type PaintMap, type Role } from "./sheetPaint"

const ROLES: { role: Role; label: string; color: string }[] = [
  { role: "question", label: "Pregunta", color: "#2e7d32" },
  { role: "option", label: "Opciones", color: "#1565c0" },
  { role: "breakdown", label: "Breakdown", color: "#e07b00" },
  { role: "category", label: "Categoría", color: "#7b3fb5" },
  { role: "counts", label: "Counts", color: "#616161" },
  { role: "total", label: "Total", color: "#00838f" },
]
const COLOR: Record<Role, string> = Object.fromEntries(ROLES.map((r) => [r.role, r.color])) as Record<Role, string>

interface Props {
  cells: string[][]
  paint: PaintMap
  onChange(p: PaintMap): void
}

export default function SheetGrid({ cells, paint, onChange }: Props) {
  const [active, setActive] = useState<Role | null>("question")
  const [erase, setErase] = useState(false)
  const [anchor, setAnchor] = useState<{ r: number; c: number } | null>(null)
  const nCols = cells.reduce((m, row) => Math.max(m, row.length), 0)

  const apply = (r0: number, c0: number, r1: number, c1: number) => {
    const role = erase ? null : active
    if (role === undefined) return
    onChange(paintRect(paint, r0, c0, r1, c1, role))
  }

  return (
    <div className="text-xs">
      <div className="flex flex-wrap gap-1.5 mb-2">
        {ROLES.map((r) => (
          <button
            key={r.role}
            onClick={() => { setActive(r.role); setErase(false) }}
            className="px-2 py-1 rounded border"
            style={{
              background: active === r.role && !erase ? r.color : "transparent",
              color: active === r.role && !erase ? "#fff" : r.color,
              borderColor: r.color,
            }}
          >
            {r.label}
          </button>
        ))}
        <button
          onClick={() => setErase((v) => !v)}
          className="px-2 py-1 rounded border"
          style={{ background: erase ? "#b00020" : "transparent", color: erase ? "#fff" : "#b00020", borderColor: "#b00020" }}
        >
          Borrar
        </button>
      </div>

      <div className="overflow-auto max-h-[60vh] border border-neutral-700 rounded" onMouseLeave={() => setAnchor(null)}>
        <table className="border-collapse select-none" style={{ fontFamily: "ui-monospace, monospace" }}>
          <thead>
            <tr>
              <th className="bg-neutral-800 text-neutral-500 px-1 sticky left-0" />
              {Array.from({ length: nCols }, (_, c) => (
                <th key={c} className="bg-neutral-800 text-neutral-400 px-2 py-0.5 border border-neutral-700">{colLetter(c)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cells.map((row, r) => (
              <tr key={r}>
                <th className="bg-neutral-800 text-neutral-500 px-1 border border-neutral-700 sticky left-0">{r + 1}</th>
                {Array.from({ length: nCols }, (_, c) => {
                  const role = paint[cellKey(r, c)]
                  return (
                    <td
                      key={c}
                      onMouseDown={() => setAnchor({ r, c })}
                      onMouseEnter={() => { if (anchor) { /* live preview not required */ } }}
                      onMouseUp={() => { if (anchor) { apply(anchor.r, anchor.c, r, c); setAnchor(null) } }}
                      className="px-2 py-0.5 border border-neutral-700 whitespace-nowrap cursor-cell"
                      style={{ background: role ? COLOR[role] : undefined, color: role ? "#fff" : "#d4d4d4", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis" }}
                      title={row[c] ?? ""}
                    >
                      {row[c] ?? ""}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-neutral-500 mt-1">Elegí un rol y arrastrá sobre las celdas para asignarlo. "Borrar" limpia el rol.</p>
    </div>
  )
}
