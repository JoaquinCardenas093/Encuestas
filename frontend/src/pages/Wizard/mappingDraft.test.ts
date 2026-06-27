import { describe, it, expect } from "vitest"
import * as D from "./mappingDraft"
import type { ParsedDB } from "../../types"

const base: ParsedDB = {
  questions: [
    { id: "q1", code: "P1", text: "T1", options: ["Sí", "No"], confidence: 1 },
  ],
  breakdowns: [
    { id: "general", label: "General", categories: ["Total"] },
    { id: "sexo", label: "Sexo", categories: ["Hombre", "Mujer"] },
  ],
  sample_size: 500,
  data_blocks: { counts_cols: [3], pct_row_cols: [21], pct_col_cols: [40] },
}

it("setQuestionText is immutable", () => {
  const out = D.setQuestionText(base, "q1", "New")
  expect(out.questions[0].text).toBe("New")
  expect(base.questions[0].text).toBe("T1")
})

it("add/set/remove option", () => {
  let db = D.addQuestionOption(base, "q1")
  expect(db.questions[0].options).toHaveLength(3)
  db = D.setQuestionOption(db, "q1", 2, "Tal vez")
  expect(db.questions[0].options[2]).toBe("Tal vez")
  db = D.removeQuestionOption(db, "q1", 0)
  expect(db.questions[0].options).toEqual(["No", "Tal vez"])
})

it("deleteQuestion / deleteBreakdown", () => {
  expect(D.deleteQuestion(base, "q1").questions).toHaveLength(0)
  expect(D.deleteBreakdown(base, "sexo").breakdowns.map((b) => b.id)).toEqual(["general"])
})

it("breakdown label + categories", () => {
  let db = D.setBreakdownLabel(base, "sexo", "Género")
  expect(db.breakdowns[1].label).toBe("Género")
  db = D.addBreakdownCategory(db, "sexo")
  expect(db.breakdowns[1].categories).toHaveLength(3)
  db = D.removeBreakdownCategory(db, "sexo", 0)
  expect(db.breakdowns[1].categories[0]).toBe("Mujer")
})

it("sample size + data block + parseColList", () => {
  expect(D.setSampleSize(base, 600).sample_size).toBe(600)
  expect(D.parseColList("4, 5, x, 6")).toEqual([4, 5, 6])
  const db = D.setDataBlock(base, "counts_cols", [3, 4])
  expect(db.data_blocks.counts_cols).toEqual([3, 4])
})
