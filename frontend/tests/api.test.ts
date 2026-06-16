import { describe, expect, it, beforeEach, vi } from "vitest"
import * as api from "../src/api/client"
import type { ParsedDB, TemplateInfo } from "../src/types"

const mockFetch = globalThis.fetch as ReturnType<typeof vi.fn>

describe("API client", () => {
  beforeEach(() => {
    mockFetch.mockClear()
  })

  it("health() calls GET /health", async () => {
    mockFetch.mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), { status: 200 }))
    const r = await api.health()
    expect(r.status).toBe("ok")
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/health"),
      expect.objectContaining({ method: "GET" }),
    )
  })

  it("parseXlsx uploads file to /parse-xlsx", async () => {
    const db: ParsedDB = {
      questions: [{ id: "q1", code: "A", text: "Q?", options: ["1", "2"], confidence: 0.9 }],
      breakdowns: [],
      sample_size: 1000,
      data_blocks: { counts_cols: [], pct_row_cols: [], pct_col_cols: [] },
    }
    mockFetch.mockResolvedValueOnce(new Response(JSON.stringify(db), { status: 200 }))
    const f = new File(["x"], "db.xlsx")
    const r = await api.parseXlsx(f)
    expect(r.questions.length).toBe(1)
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/parse-xlsx"),
      expect.objectContaining({ method: "POST" }),
    )
  })

  it("parseTemplate uploads file to /parse-template", async () => {
    const tpl: TemplateInfo = {
      shell_slide_index: 1,
      separator_slide_index: 0,
      free_area: { x: 0, y: 0, cx: 100, cy: 100 },
      placeholders: ["title"],
      default_font: "Roboto",
    }
    mockFetch.mockResolvedValueOnce(new Response(JSON.stringify(tpl), { status: 200 }))
    const f = new File(["x"], "tpl.pptx")
    const r = await api.parseTemplate(f)
    expect(r.shell_slide_index).toBe(1)
  })

  it("request throws ApiError on error", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ code: "invalid_file", message: "Bad xlsx" }), { status: 400 }),
    )
    const f = new File(["x"], "bad.xlsx")
    try {
      await api.parseXlsx(f)
      expect.fail("should have thrown")
    } catch (e) {
      expect((e as any).code).toBe("invalid_file")
    }
  })
})
