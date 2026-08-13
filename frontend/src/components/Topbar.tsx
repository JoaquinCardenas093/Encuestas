import { useState, useEffect } from "react"
import { Link, NavLink } from "react-router-dom"
import { useProjectStore } from "../store/project"
import * as recentsApi from "../api/recents"
import * as api from "../api/client"
import { Pill } from "./Pills"
import ExportModal from "../pages/Editor/modals/ExportModal"
import RelocateModal from "./RelocateModal"

export default function Topbar() {
  const state = useProjectStore((s) => s.state)
  const projectName = useProjectStore((s) => s.projectName)
  const setProjectName = useProjectStore((s) => s.setProjectName)
  const loadProjectState = useProjectStore((s) => s.loadProjectState)
  const dbName = state ? state.inputs.db_path.split("/").pop() : null
  const tplName = state ? state.inputs.template_path.split("/").pop() : null
  const font = state?.inputs.font_override
  const [exportOpen, setExportOpen] = useState(false)
  const [recents, setRecents] = useState<recentsApi.RecentItem[]>([])
  const [showRecents, setShowRecents] = useState(false)

  useEffect(() => {
    if (showRecents) recentsApi.getRecents().then(setRecents).catch(() => setRecents([]))
  }, [showRecents])

  const handleSave = async () => {
    if (!state) return
    let name = projectName
    if (!name) {
      name = window.prompt("Nombre del proyecto") || ""
      if (!name) return
    }
    await api.saveProject(name, state)
    setProjectName(name)
  }

  const handleOpenRecent = async (name: string) => {
    const loadedState = await api.loadProject(name)
    loadProjectState(loadedState)
    setProjectName(name)
    setShowRecents(false)
  }

  const tabClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-1 rounded text-sm ${isActive ? "bg-neutral-700 text-white" : "text-neutral-300 hover:bg-neutral-800"}`

  return (
    <header className="h-12 bg-neutral-800 border-b border-neutral-700 flex items-center px-4 gap-4">
      <Link to="/" className="font-semibold text-accent">AurumEncuestas</Link>
      <nav className="flex gap-1">
        <NavLink to="/editor" className={tabClass}>Editor</NavLink>
        <NavLink to="/training" className={tabClass}>Entrenamiento</NavLink>
      </nav>
      <div className="flex-1" />
      <div className="flex items-center gap-2">
        {dbName && <Pill label="DB" value={dbName} ok />}
        {tplName && <Pill label="Template" value={tplName} ok />}
        {font && <Pill label="Font" value={font} />}
      </div>
      <div className="relative">
        <button onClick={() => setShowRecents(!showRecents)} className="px-3 py-1 rounded text-sm bg-neutral-700 hover:bg-neutral-600">Abrir ▾</button>
        {showRecents && (
          <ul className="absolute top-full mt-1 left-0 bg-neutral-800 border border-neutral-700 rounded shadow z-20 w-72">
            {recents.length === 0 && <li className="px-3 py-2 text-xs text-neutral-500">Sin recientes</li>}
            {recents.map((r) => (
              <li key={r.path}>
                <button onClick={() => handleOpenRecent(r.path)} className="block w-full text-left px-3 py-2 text-sm hover:bg-neutral-700">
                  <div>{r.name}</div>
                  <div className="text-[10px] text-neutral-500 truncate">{r.path}</div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <button onClick={handleSave} disabled={!state} className="px-3 py-1 rounded text-sm bg-neutral-700 disabled:opacity-40">Guardar</button>
      <button
        onClick={() => setExportOpen(true)}
        disabled={!state}
        className="ml-2 px-3 py-1 text-sm rounded bg-accent text-neutral-900 font-semibold disabled:opacity-40"
      >Exportar PPTX</button>
      <ExportModal open={exportOpen} onClose={() => setExportOpen(false)} />
      <RelocateModal open={false} missingFiles={[]} onClose={() => {}} onRelocate={() => {}} />
    </header>
  )
}
