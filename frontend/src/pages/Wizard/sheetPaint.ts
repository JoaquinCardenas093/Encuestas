import type { ParsedDB, Question, Breakdown } from "../../types"

export type Role =
  | "question" | "option" | "breakdown" | "category"
  | "counts" | "total"
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

const BREAKDOWN_ALIAS: Record<string, string> = {
  "rango de edad": "edad", "sexo": "sexo", "nse": "nse", "punto": "punto",
}

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
    breakdowns.push({ id: prevBd?.id ?? (BREAKDOWN_ALIAS[slug(label)] ?? slug(label)), label, categories: cats })
  })
  catCells.forEach((cat) => {
    if (!ownerOf(cat)) warnings.push(`Categoría "${text(cat.r, cat.c)}" sin breakdown a la izquierda — descartada`)
  })

  // --- Data blocks (counts only; pct_* carried from prev, no longer read) ---
  const countsCols = entries.filter((e) => e.role === "counts").map((e) => e.c)
  // Only counts_cols[0] drives extraction; counts_cols[1] widening after "Seleccionar conteos" is benign.
  const counts_cols = countsCols.length
    ? [Math.min(...countsCols) + 1, Math.max(...countsCols) + 1]
    : prev.data_blocks.counts_cols
  const data_blocks = {
    counts_cols,
    pct_row_cols: prev.data_blocks.pct_row_cols,
    pct_col_cols: prev.data_blocks.pct_col_cols,
  }

  // --- Total row (1-based) ---
  const totalRows = entries.filter((e) => e.role === "total").map((e) => e.r)
  const total_row = totalRows.length ? Math.min(...totalRows) + 1 : (prev.total_row ?? null)

  return { db: { ...prev, questions, breakdowns, data_blocks, sample_size: prev.sample_size, total_row }, warnings }
}

export function paintCountCells(
  paint: PaintMap,
  coords: { row: number; col: number }[],
  nRows: number,
  nCols: number,
): { paint: PaintMap; dropped: number } {
  const next = { ...paint }
  let dropped = 0
  for (const { row, col } of coords) {
    const r = row - 1
    const c = col - 1
    if (r < 0 || c < 0 || r >= nRows || c >= nCols) { dropped++; continue }
    next[cellKey(r, c)] = "counts"
  }
  return { paint: next, dropped }
}

export function parsedDbToPaint(cells: string[][], db: ParsedDB): PaintMap {
  const paint: PaintMap = {}
  const norm = (s: string | undefined) => (s ?? "").trim()
  const COL_A = 0, COL_B = 1, HEADER_ROW = 0, CAT_ROW = 1

  db.questions.forEach((q) => {
    let anchorRow = -1
    for (let r = 0; r < cells.length; r++) {
      const a = norm(cells[r]?.[COL_A])
      if (a && (a === q.text || a.startsWith(q.text + ".") || q.text.startsWith(a + "."))) {
        anchorRow = r; break
      }
    }
    if (anchorRow < 0) return
    paint[cellKey(anchorRow, COL_A)] = "question"
    q.options.forEach((opt) => {
      for (let r = anchorRow; r < cells.length; r++) {
        if (norm(cells[r]?.[COL_B]) === opt) { paint[cellKey(r, COL_B)] = "option"; break }
      }
    })
  })

  db.breakdowns.filter((b) => b.id !== "general").forEach((b) => {
    const hrow = cells[HEADER_ROW] ?? []
    for (let c = 0; c < hrow.length; c++) {
      if (norm(hrow[c]) === b.label) { paint[cellKey(HEADER_ROW, c)] = "breakdown"; break }
    }
    const crow = cells[CAT_ROW] ?? []
    b.categories.forEach((cat) => {
      for (let c = 0; c < crow.length; c++) {
        if (norm(crow[c]) === cat) { paint[cellKey(CAT_ROW, c)] = "category"; break }
      }
    })
  })

  // Counts block: paint an indicator row across the counts columns.
  const baseRow = Math.min(2, Math.max(0, cells.length - 1))
  const cc = db.data_blocks.counts_cols
  if (cc && cc.length >= 2) {
    for (let c = cc[0] - 1; c <= cc[1] - 1; c++) paint[cellKey(baseRow, c)] = "counts"
  }
  // Total row across the counts columns.
  if (db.total_row && db.total_row >= 1) {
    const r = db.total_row - 1
    if (cc && cc.length >= 2) for (let c = cc[0] - 1; c <= cc[1] - 1; c++) paint[cellKey(r, c)] = "total"
  }

  return paint
}
