import { beforeEach, describe, expect, it } from "vitest"
import { getSessionId, sessionHeader } from "../src/api/session"

describe("session", () => {
  beforeEach(() => localStorage.clear())

  it("generates and persists a stable id", () => {
    const a = getSessionId()
    const b = getSessionId()
    expect(a).toBe(b)
    expect(localStorage.getItem("aurum_session_id")).toBe(a)
  })

  it("sessionHeader carries the id", () => {
    const id = getSessionId()
    expect(sessionHeader()).toEqual({ "X-Session-Id": id })
  })
})
