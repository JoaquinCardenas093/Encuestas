import type { ParsedDB, Question, Breakdown } from "../../types"

export type Role =
  | "question" | "option" | "breakdown" | "category"
  | "counts" | "pctRow" | "pctCol"
export type PaintMap = Record<string, Role>   // key "r,c" (0-based) -> Role

export const cellKey = (r: number, c: number) => `${r},${c}`

export function colLetter(c: number): string {
  let s = ""
  let n = c
  do { s = String.fromCharCode(65 + (n % 26)) + s; n = Math.floor(n / 26) - 1 } while (n >= 0)
  return s
}

export function paintRect(
  map: PaintMap, r0: number, c0: number, r1: number, c1: number, role: Role | null,
): PaintMap {
  const next = { ...map }
  const [ra, rb] = r0 <= r1 ? [r0, r1] : [r1, r0]
  const [ca, cb] = c0 <= c1 ? [c0, c1] : [c1, c0]
  for (let r = ra; r <= rb; r++) {
    for (let c = ca; c <= cb; c++) {
      const k = cellKey(r, c)
      if (role === null) delete next[k]
      else next[k] = role
    }
  }
  return next
}

const slug = (s: string) => s.trim().toLowerCase()

type Cell = { r: number; c: number; role: Role }

export function paintToParsedDb(
  cells: string[][], paint: PaintMap, prev: ParsedDB,
): { db: ParsedDB; warnings: string[] } {
  const warnings: string[] = []
  const text = (r: number, c: number) => (cells[r]?.[c] ?? "").trim()
  const entries: Cell[] = Object.entries(paint).map(([k, role]) => {
    const [r, c] = k.split(",").map(Number)
    return { r, c, role }
  })

  // --- Questions ---
  const anchors = entries.filter((e) => e.role === "question").sort((a, b) => a.r - b.r || a.c - b.c)
  const options = entries.filter((e) => e.role === "option")
  const prevQByText = new Map(prev.questions.map((q) => [q.text, q]))
  const questions: Question[] = []
  anchors.forEach((anchor, i) => {
    const nextRow = i + 1 < anchors.length ? anchors[i + 1].r : Infinity
    const opts = options
      .filter((o) => o.r >= anchor.r && o.r < nextRow)
      .sort((a, b) => a.r - b.r || a.c - b.c)
      .map((o) => text(o.r, o.c))
      .filter((t) => t.length > 0)
    const qtext = text(anchor.r, anchor.c)
    if (opts.length === 0) { warnings.push(`Pregunta "${qtext}" sin opciones — descartada`); return }
    const prevQ = prevQByText.get(qtext)
    questions.push({
      id: prevQ?.id ?? `q${i + 1}`,
      code: prevQ?.code ?? `P${i + 1}`,
      text: qtext, options: opts, confidence: 1,
    })
  })

  // --- Breakdowns (carry prev general first) ---
  const headers = entries.filter((e) => e.role === "breakdown").sort((a, b) => a.c - b.c)
  const catCells = entries.filter((e) => e.role === "category")
  const ownerOf = (cat: Cell): Cell | undefined =>
    headers.filter((h) => h.c <= cat.c).sort((a, b) => b.c - a.c)[0]
  const prevBdByLabel = new Map(prev.breakdowns.map((b) => [b.label, b]))
  const general = prev.breakdowns.find((b) => b.id === "general")
  const breakdowns: Breakdown[] = general ? [general] : []
  // dedupe header instances by label (a header label can span >1 painted cell)
  const seenLabels = new Set<string>()
  headers.forEach((h) => {
    const label = text(h.r, h.c)
    if (!label || seenLabels.has(label)) return
    seenLabels.add(label)
    const cats = catCells
      .filter((cat) => { const o = ownerOf(cat); return o && text(o.r, o.c) === label })
      .sort((a, b) => a.c - b.c)
      .map((cat) => text(cat.r, cat.c))
      .filter((t) => t.length > 0)
    const prevBd = prevBdByLabel.get(label)
    breakdowns.push({ id: prevBd?.id ?? slug(label), label, categories: cats })
  })
  catCells.forEach((cat) => {
    if (!ownerOf(cat)) warnings.push(`Categoría "${text(cat.r, cat.c)}" sin breakdown a la izquierda — descartada`)
  })

  // --- Data blocks ---
  const colRange = (role: Role, fallback: number[]): number[] => {
    const cols = entries.filter((e) => e.role === role).map((e) => e.c)
    return cols.length === 0 ? fallback : [Math.min(...cols) + 1, Math.max(...cols) + 1]
  }
  const data_blocks = {
    counts_cols: colRange("counts", prev.data_blocks.counts_cols),
    pct_row_cols: colRange("pctRow", prev.data_blocks.pct_row_cols),
    pct_col_cols: colRange("pctCol", prev.data_blocks.pct_col_cols),
  }

  return { db: { ...prev, questions, breakdowns, data_blocks, sample_size: prev.sample_size }, warnings }
}
