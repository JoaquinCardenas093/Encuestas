import { describe, it, expect, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import ConfigPanel from "../src/pages/Editor/ConfigPanel"
import { useProjectStore } from "../src/store/project"
import type { Slide } from "../src/types"


const makeSlide = (matched_pattern: string | null | undefined): Slide => ({
  id: "sl1",
  type: "shell",
  title: "Recordación",
  charts: [],
  analyses: [],
  subtitles: [],
  auto_notes: null,
  matched_pattern,
})

describe("ConfigPanel — pattern matched indicator", () => {
  beforeEach(() => {
    useProjectStore.setState({ state: null })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
  })

  it("shows matched pattern id when slide has matched_pattern", () => {
    const s = useProjectStore.getState().state!
    const slide = makeSlide("binary_general_demographics")
    useProjectStore.setState({ state: { ...s, slides: [slide] } })
    render(<ConfigPanel slideId="sl1" />)
    expect(screen.getByText(/binary_general_demographics/i)).toBeInTheDocument()
    expect(screen.getByText(/matched/i)).toBeInTheDocument()
  })

  it("shows fallback heurístico when matched_pattern is null", () => {
    const s = useProjectStore.getState().state!
    const slide = makeSlide(null)
    useProjectStore.setState({ state: { ...s, slides: [slide] } })
    render(<ConfigPanel slideId="sl1" />)
    expect(screen.getByText(/fallback heurístico/i)).toBeInTheDocument()
  })

  it("shows fallback heurístico when matched_pattern is undefined", () => {
    const s = useProjectStore.getState().state!
    const slide = makeSlide(undefined)
    useProjectStore.setState({ state: { ...s, slides: [slide] } })
    render(<ConfigPanel slideId="sl1" />)
    expect(screen.getByText(/fallback heurístico/i)).toBeInTheDocument()
  })
})
