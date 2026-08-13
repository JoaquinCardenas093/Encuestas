import { describe, expect, it } from "vitest"
import { nextSelectionAfterDelete } from "../src/pages/Editor/EditorPage"

const slides = [{ id: "a" }, { id: "b" }, { id: "c" }]

describe("nextSelectionAfterDelete", () => {
  it("keeps selection when a different slide is deleted", () => {
    expect(nextSelectionAfterDelete(slides, "c", "a")).toBe("a")
  })

  it("selects previous neighbour when deleting the selected middle slide", () => {
    expect(nextSelectionAfterDelete(slides, "b", "b")).toBe("a")
  })

  it("selects first remaining when deleting the selected first slide", () => {
    expect(nextSelectionAfterDelete(slides, "a", "a")).toBe("b")
  })

  it("selects previous neighbour when deleting the selected last slide", () => {
    expect(nextSelectionAfterDelete(slides, "c", "c")).toBe("b")
  })

  it("returns null when deleting the only slide", () => {
    expect(nextSelectionAfterDelete([{ id: "a" }], "a", "a")).toBe(null)
  })
})
