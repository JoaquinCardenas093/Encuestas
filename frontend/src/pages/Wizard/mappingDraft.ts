import type { ParsedDB, Question, Breakdown } from "../../types"

type DataBlockKey = "counts_cols" | "pct_row_cols" | "pct_col_cols"

function mapQ(db: ParsedDB, qid: string, fn: (q: Question) => Question): ParsedDB {
  return { ...db, questions: db.questions.map((q) => (q.id === qid ? fn(q) : q)) }
}
function mapB(db: ParsedDB, bid: string, fn: (b: Breakdown) => Breakdown): ParsedDB {
  return { ...db, breakdowns: db.breakdowns.map((b) => (b.id === bid ? fn(b) : b)) }
}

export const setQuestionText = (db: ParsedDB, qid: string, text: string) =>
  mapQ(db, qid, (q) => ({ ...q, text }))
export const addQuestionOption = (db: ParsedDB, qid: string) =>
  mapQ(db, qid, (q) => ({ ...q, options: [...q.options, ""] }))
export const setQuestionOption = (db: ParsedDB, qid: string, idx: number, value: string) =>
  mapQ(db, qid, (q) => ({ ...q, options: q.options.map((o, i) => (i === idx ? value : o)) }))
export const removeQuestionOption = (db: ParsedDB, qid: string, idx: number) =>
  mapQ(db, qid, (q) => ({ ...q, options: q.options.filter((_, i) => i !== idx) }))
export const deleteQuestion = (db: ParsedDB, qid: string) =>
  ({ ...db, questions: db.questions.filter((q) => q.id !== qid) })

export const setBreakdownLabel = (db: ParsedDB, bid: string, label: string) =>
  mapB(db, bid, (b) => ({ ...b, label }))
export const addBreakdownCategory = (db: ParsedDB, bid: string) =>
  mapB(db, bid, (b) => ({ ...b, categories: [...b.categories, ""] }))
export const setBreakdownCategory = (db: ParsedDB, bid: string, idx: number, value: string) =>
  mapB(db, bid, (b) => ({ ...b, categories: b.categories.map((c, i) => (i === idx ? value : c)) }))
export const removeBreakdownCategory = (db: ParsedDB, bid: string, idx: number) =>
  mapB(db, bid, (b) => ({ ...b, categories: b.categories.filter((_, i) => i !== idx) }))
export const deleteBreakdown = (db: ParsedDB, bid: string) =>
  ({ ...db, breakdowns: db.breakdowns.filter((b) => b.id !== bid) })

export const setSampleSize = (db: ParsedDB, n: number) => ({ ...db, sample_size: n })
export const setDataBlock = (db: ParsedDB, key: DataBlockKey, cols: number[]): ParsedDB =>
  ({ ...db, data_blocks: { ...db.data_blocks, [key]: cols } })
export const setTotalRow = (db: ParsedDB, n: number): ParsedDB => ({ ...db, total_row: n })

export function parseColList(s: string): number[] {
  return s
    .split(",")
    .map((p) => parseInt(p.trim(), 10))
    .filter((n) => Number.isFinite(n))
}

export function setValueOverride(
  db: ParsedDB,
  key: string,
  patch: { count?: number | null; pct?: number | null },
): ParsedDB {
  const all = { ...(db.value_overrides ?? {}) }
  const merged: { count?: number; pct?: number } = { ...(all[key] ?? {}) } as { count?: number; pct?: number }
  for (const f of ["count", "pct"] as const) {
    if (f in patch) {
      const v = patch[f]
      if (v == null) delete merged[f]
      else merged[f] = v
    }
  }
  if (Object.keys(merged).length === 0) delete all[key]
  else all[key] = merged
  return { ...db, value_overrides: all }
}
