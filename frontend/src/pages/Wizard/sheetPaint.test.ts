import { it, expect, describe } from "vitest"
import { cellKey, colLetter, paintRect, paintToParsedDb, parsedDbToPaint, paintCountCells, type PaintMap } from "./sheetPaint"
import type { ParsedDB } from "../../types"

const prev: ParsedDB = {
  questions: [{ id: "q1", code: "P1", text: "$p1.rec", options: ["Sí", "No"], confidence: 1 }],
  breakdowns: [
    { id: "general", label: "General", categories: ["Total"] },
    { id: "sexo", label: "Sexo", categories: ["Hombre", "Mujer"] },
  ],
  sample_size: 500,
  data_blocks: { counts_cols: [3, 5], pct_row_cols: [7, 9], pct_col_cols: [11, 13] },
  total_row: 3,
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
  p = paintRect(p, 1, 2, 1, 4, "total")         // total row = sheet row 2 (overwrites category cells)
  const { db, warnings } = paintToParsedDb(cells, p, prev)
  expect(warnings).toEqual([])
  expect(db.questions).toHaveLength(1)
  expect(db.questions[0].options).toEqual(["Sí", "No"])
  // general carried through + the painted Sexo breakdown
  expect(db.breakdowns.map((b) => b.id)).toEqual(["general", "sexo"])
  expect(db.breakdowns[1].categories).toEqual([])  // total paint overwrote category cells
  expect(db.data_blocks.counts_cols).toEqual([3, 5])
  // pct cols carried from prev (no longer painted)
  expect(db.data_blocks.pct_row_cols).toEqual([7, 9])
  expect(db.total_row).toBe(2)
})

it("category with no breakdown to its left is dropped with a warning", () => {
  let p: PaintMap = {}
  p = paintRect(p, 1, 0, 1, 0, "category")  // col 0, no header to the left
  const { warnings } = paintToParsedDb(cells, p, prev)
  expect(warnings.some((w) => w.includes("sin breakdown"))).toBe(true)
})

it("parsedDbToPaint round-trips through paintToParsedDb", () => {
  const paint = parsedDbToPaint(cells, prev)
  const { db, warnings } = paintToParsedDb(cells, paint, prev)
  expect(warnings).toEqual([])
  expect(db.questions[0].options).toEqual(["Sí", "No"])
  expect(db.breakdowns.map((b) => b.id)).toEqual(["general", "sexo"])
  expect(db.breakdowns[1].categories).toEqual(["Hombre", "Mujer"])
  expect(db.data_blocks.counts_cols).toEqual([3, 5])
  expect(db.data_blocks.pct_row_cols).toEqual([7, 9])
  expect(db.data_blocks.pct_col_cols).toEqual([11, 13])
  expect(db.total_row).toBe(prev.total_row)
})

it("parsedDbToPaint distinct marker rows — adjacent blocks do not bleed (I1)", () => {
  const adjPrev: ParsedDB = {
    questions: [],
    breakdowns: [{ id: "general", label: "General", categories: ["Total"] }],
    sample_size: 100,
    data_blocks: { counts_cols: [3, 4], pct_row_cols: [5, 6], pct_col_cols: [7, 8] },
  }
  // 6 rows × 8 cols so baseRow=2 and offsets 0/1/2 all land on distinct rows
  const adjCells: string[][] = Array.from({ length: 6 }, () => Array(8).fill("x"))
  const paint = parsedDbToPaint(adjCells, adjPrev)
  const { db } = paintToParsedDb(adjCells, paint, adjPrev)
  expect(db.data_blocks.counts_cols).toEqual([3, 4])
  expect(db.data_blocks.pct_row_cols).toEqual([5, 6])
  expect(db.data_blocks.pct_col_cols).toEqual([7, 8])
})

describe("paintCountCells", () => {
  it("paints counts role at 0-based coords and counts out-of-window drops", () => {
    const { paint, dropped } = paintCountCells({}, [
      { row: 5, col: 3 },     // → "4,2"
      { row: 1, col: 200 },   // col 200 > nCols 120 → dropped
      { row: 250, col: 2 },   // row 250 > nRows 200 → dropped
    ], 200, 120)
    expect(paint["4,2"]).toBe("counts")
    expect(dropped).toBe(2)
  })

  it("merges over existing paint without mutating the input", () => {
    const base = { "0,0": "question" } as Record<string, string>
    const { paint } = paintCountCells(base as any, [{ row: 2, col: 2 }], 200, 120)
    expect(paint["0,0"]).toBe("question")   // preserved
    expect(paint["1,1"]).toBe("counts")     // added
    expect(base["1,1"]).toBeUndefined()     // pure
  })
})

it("breakdown alias map resolves 'Rango de edad' to id 'edad' (I2)", () => {
  // prev does NOT include a 'Rango de edad' breakdown → alias map must fire
  const aliasPrev: ParsedDB = {
    questions: [],
    breakdowns: [{ id: "general", label: "General", categories: ["Total"] }],
    sample_size: 100,
    data_blocks: { counts_cols: [3, 4], pct_row_cols: [5, 6], pct_col_cols: [7, 8] },
  }
  const aliasCells: string[][] = [
    ["", "Rango de edad", "", ""],
    ["", "18-24", "", ""],
    ["q1", "resp", "", ""],
  ]
  let p: PaintMap = {}
  p = paintRect(p, 0, 1, 0, 1, "breakdown")
  p = paintRect(p, 1, 1, 1, 1, "category")
  const { db } = paintToParsedDb(aliasCells, p, aliasPrev)
  const bd = db.breakdowns.find((b) => b.label === "Rango de edad")
  expect(bd?.id).toBe("edad")
})

it("paintToParsedDb emits count_cells (1-based) for painted counts cells", () => {
  const cells = [["P1", "", ""], ["", "Sí", ""], ["", "No", ""]]
  const p: PaintMap = {
    "0,0": "question", "1,1": "option", "2,1": "option",
    "1,2": "counts", "2,2": "counts",
  }
  const prev = { questions: [], breakdowns: [], data_blocks: { counts_cols: [3, 3], pct_row_cols: [], pct_col_cols: [] }, sample_size: 0, total_row: null } as any
  const { db } = paintToParsedDb(cells, p, prev)
  expect(db.count_cells).toEqual([[2, 3], [3, 3]])   // (r+1,c+1), sorted
})

it("paintToParsedDb keeps prev.count_cells when truncated", () => {
  const cells = [["P1"]]
  const p: PaintMap = { "0,0": "counts" }
  const prev = { questions: [], breakdowns: [], data_blocks: { counts_cols: [1, 1], pct_row_cols: [], pct_col_cols: [] }, sample_size: 0, total_row: null, count_cells: [[9, 9]] } as any
  const { db } = paintToParsedDb(cells, p, prev, true)
  expect(db.count_cells).toEqual([[9, 9]])           // not re-derived
})
