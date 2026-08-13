import { afterEach, describe, expect, it, vi } from "vitest"
import { getRecents } from "../src/api/recents"

describe("client session header", () => {
  afterEach(() => vi.restoreAllMocks())

  it("recents fetch carries X-Session-Id", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ recents: [] }), { status: 200 }),
    )
    await getRecents()
    const init = spy.mock.calls[0][1] as RequestInit
    const headers = new Headers(init.headers)
    expect(headers.get("X-Session-Id")).toBeTruthy()
  })
})
