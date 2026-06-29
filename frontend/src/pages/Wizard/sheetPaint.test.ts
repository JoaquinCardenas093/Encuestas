import { it, expect } from "vitest"
import { cellKey, colLetter, paintRect, paintToParsedDb, type PaintMap } from "./sheetPaint"
import type { ParsedDB } from "../../types"

const prev: ParsedDB = {
  questions: [{ id: "q1", code: "P1", text: "$p1.rec", options: ["Sí", "No"], confidence: 1 }],
  breakdowns: [
    { id: "general", label: "General", categories: ["Total"] },
    { id: "sexo", label: "Sexo", categories: ["Hombre", "Mujer"] },
  ],
  sample_size: 500,
  data_blocks: { counts_cols: [3, 5], pct_row_cols: [7, 9], pct_col_cols: [11, 13] },
}

// cells grid (row-major, 0-based). Row0=sheet row1.
const cells: string[][] = [
  ["", "", "Sexo", "Sexo", "", "", "", "", ""],          // row0: breakdown header at cols 2,3
  ["General", "", "Hombre", "Mujer", "", "", "", "", ""], // row1: categories at cols 2,3
  ["$p1.rec", "Sí", "458", "230", "228", "x", "x", "x", "x"], // row2: question + option Sí
  ["", "No", "42", "20", "22", "x", "x", "x", "x"],       // row3: option No
]

it("colLetter + cellKey", () => {
  expect(colLetter(0)).toBe("A")
  expect(colLetter(26)).toBe("AA")
  expect(cellKey(2, 1)).toBe("2,1")
})

it("paintRect fills and clears a rectangle", () => {
  let m: PaintMap = {}
  m = paintRect(m, 2, 1, 3, 1, "option")
  expect(m["2,1"]).toBe("option")
  expect(m["3,1"]).toBe("option")
  m = paintRect(m, 2, 1, 2, 1, null)
  expect(m["2,1"]).toBeUndefined()
})

it("paintToParsedDb rebuilds questions, breakdowns, data blocks", () => {
  let p: PaintMap = {}
  p = paintRect(p, 2, 0, 2, 0, "question")     // $p1.rec
  p = paintRect(p, 2, 1, 3, 1, "option")        // Sí, No
  p = paintRect(p, 0, 2, 0, 3, "breakdown")     // Sexo header (cols 2,3 same label)
  p = paintRect(p, 1, 2, 1, 3, "category")      // Hombre, Mujer
  p = paintRect(p, 2, 2, 2, 4, "counts")        // counts cols 2..4 -> [3,5]
  const { db, warnings } = paintToParsedDb(cells, p, prev)
  expect(warnings).toEqual([])
  expect(db.questions).toHaveLength(1)
  expect(db.questions[0].options).toEqual(["Sí", "No"])
  // general carried through + the painted Sexo breakdown
  expect(db.breakdowns.map((b) => b.id)).toEqual(["general", "sexo"])
  expect(db.breakdowns[1].categories).toEqual(["Hombre", "Mujer"])
  expect(db.data_blocks.counts_cols).toEqual([3, 5])
  // untouched blocks keep prev
  expect(db.data_blocks.pct_row_cols).toEqual([7, 9])
})

it("category with no breakdown to its left is dropped with a warning", () => {
  let p: PaintMap = {}
  p = paintRect(p, 1, 0, 1, 0, "category")  // col 0, no header to the left
  const { warnings } = paintToParsedDb(cells, p, prev)
  expect(warnings.some((w) => w.includes("sin breakdown"))).toBe(true)
})
