import { useState } from "react"
import { useSearchParams } from "react-router-dom"
import { useProjectStore } from "../../store/project"
import { useAutoSave } from "../../hooks/useAutoSave"
import { useKeyboardShortcuts } from "../../hooks/useKeyboardShortcuts"
import XlsxVerifyWizard from "../Wizard/XlsxVerifyWizard"
import SlideRail from "./SlideRail"
import Preview from "./Preview"
import ConfigPanel from "./ConfigPanel"
import EditorFooter from "./EditorFooter"

export function nextSelectionAfterDelete(
  slides: { id: string }[],
  deletedId: string,
  selectedId: string | null,
): string | null {
  if (deletedId !== selectedId) return selectedId
  const idx = slides.findIndex((s) => s.id === deletedId)
  const remaining = slides.filter((s) => s.id !== deletedId)
  const next = remaining[idx - 1] ?? remaining[0] ?? null
  return next ? next.id : null
}

export default function EditorPage() {
  const [params, setParams] = useSearchParams()
  const showWizard = params.get("wizard") === "1"
  const slides = useProjectStore((s) => s.state?.slides ?? [])
  const [selectedId, setSelectedId] = useState<string | null>(slides[0]?.id ?? null)

  const state = useProjectStore((s) => s.state)
  const addShell = useProjectStore((s) => s.addShell)
  const hasSeparator = state?.slides.some((sl) => sl.type === "separator")

  useAutoSave(5000)

  useKeyboardShortcuts({
    "Cmd+s": async () => {
      const cur = useProjectStore.getState().state
      const path = useProjectStore.getState().projectPath
      if (cur && path) {
        const api = await import("../../api/client")
        await api.saveProject(path, cur)
      }
    },
    "Cmd+n": () => { if (hasSeparator) addShell() },
  })

  // when slides list changes, pick first if none selected
  if (!selectedId && slides.length > 0) {
    setSelectedId(slides[0].id)
  }

  if (showWizard) {
    return <XlsxVerifyWizard onConfirm={() => setParams({})} />
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 grid grid-cols-[130px_1fr_320px] overflow-hidden">
        <SlideRail selectedId={selectedId} onSelect={setSelectedId} />
        <Preview slideId={selectedId} />
        <ConfigPanel slideId={selectedId} />
      </div>
      <EditorFooter />
    </div>
  )
}
