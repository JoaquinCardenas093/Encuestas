import { Link, NavLink } from "react-router-dom"
import { useProjectStore } from "../store/project"
import { Pill } from "./Pills"

export default function Topbar() {
  const state = useProjectStore((s) => s.state)
  const dbName = state ? state.inputs.db_path.split("/").pop() : null
  const tplName = state ? state.inputs.template_path.split("/").pop() : null
  const font = state?.inputs.font_override

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
    </header>
  )
}
