import { useState } from "react"
import { useSearchParams } from "react-router-dom"
import { useProjectStore } from "../../store/project"
import XlsxVerifyWizard from "../Wizard/XlsxVerifyWizard"
import SlideRail from "./SlideRail"
import Preview from "./Preview"
import ConfigPanel from "./ConfigPanel"
import EditorFooter from "./EditorFooter"

export default function EditorPage() {
  const [params, setParams] = useSearchParams()
  const showWizard = params.get("wizard") === "1"
  const slides = useProjectStore((s) => s.state?.slides ?? [])
  const [selectedId, setSelectedId] = useState<string | null>(slides[0]?.id ?? null)

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
