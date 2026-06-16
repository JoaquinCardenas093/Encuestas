import { expect, afterEach, vi } from "vitest"
import { cleanup } from "@testing-library/react"

afterEach(() => {
  cleanup()
})

globalThis.fetch = vi.fn()
