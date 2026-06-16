import { useSearchParams } from "react-router-dom"
import XlsxVerifyWizard from "../Wizard/XlsxVerifyWizard"

export default function EditorPage() {
  const [params, setParams] = useSearchParams()
  const showWizard = params.get("wizard") === "1"

  if (showWizard) {
    return <XlsxVerifyWizard onConfirm={() => setParams({})} />
  }

  return (
    <div className="grid grid-cols-[130px_1fr_320px] h-full">
      <aside className="bg-neutral-900 border-r border-neutral-700 p-2 text-xs">Slides (vacío — M3)</aside>
      <section className="bg-neutral-800 flex items-center justify-center text-neutral-500">Preview (M3)</section>
      <aside className="bg-neutral-900 border-l border-neutral-700 p-3 text-sm">Config (M3)</aside>
    </div>
  )
}
