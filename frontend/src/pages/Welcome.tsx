import { useNavigate } from "react-router-dom"
import { useState, useEffect } from "react"
import { Upload, FileSpreadsheet, Presentation } from "lucide-react"
import * as api from "../api/client"
import { useFileUpload } from "../hooks/useUpload"
import { useProjectStore } from "../store/project"
import { useStyleGuideStore } from "../store/styleGuide"

export default function Welcome() {
  const navigate = useNavigate()
  const [dbFile, setDbFile] = useState<File | null>(null)
  const [tplFile, setTplFile] = useState<File | null>(null)
  const [projectName, setProjectName] = useState("Nuevo proyecto")

  const xlsxUpload = useFileUpload(api.parseXlsx)
  const tplUpload = useFileUpload(api.parseTemplate)

  const setParsedDb = useProjectStore((s) => s.setParsedDb)
  const setTemplateInfo = useProjectStore((s) => s.setTemplateInfo)
  const setNewProject = useProjectStore((s) => s.setNewProject)

  const { loadStyleGuide, loadCorpus } = useStyleGuideStore((s) => s)

  useEffect(() => {
    loadStyleGuide()
    loadCorpus()
  }, [])


  async function handleContinue() {
    if (!dbFile || !tplFile) return
    const [db, tpl] = await Promise.all([
      xlsxUpload.upload(dbFile),
      tplUpload.upload(tplFile),
    ])
    const dbPersisted = (db as { persisted_path?: string }).persisted_path || `./${dbFile.name}`
    const tplPersisted = (tpl as { persisted_path?: string }).persisted_path || `./${tplFile.name}`
    setNewProject({
      name: projectName,
      db_path: dbPersisted,
      template_path: tplPersisted,
    })
    setParsedDb(db)
    setTemplateInfo(tpl)
    navigate("/editor?wizard=1")
  }

  return (
    <div className="flex flex-col items-center justify-center h-full bg-neutral-900 text-neutral-100">
      <div className="w-full max-w-xl bg-neutral-800 rounded-lg p-8 shadow border border-neutral-700">
        <h1 className="text-xl font-semibold mb-1">Nuevo proyecto</h1>
        <p className="text-sm text-neutral-400 mb-6">Subí los 3 archivos para empezar.</p>

        <label className="block text-xs font-medium text-neutral-400 mb-1">Nombre del proyecto</label>
        <input
          value={projectName}
          onChange={(e) => setProjectName(e.target.value)}
          className="w-full mb-4 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
        />

        <FileSlot icon={<FileSpreadsheet size={20} />} label="DB (xlsx)" file={dbFile} onPick={setDbFile} accept=".xlsx" />
        {xlsxUpload.error && <p className="text-xs text-red-400 mb-2">{xlsxUpload.error}</p>}

        <FileSlot icon={<Presentation size={20} />} label="Template (pptx)" file={tplFile} onPick={setTplFile} accept=".pptx" />
        {tplUpload.error && <p className="text-xs text-red-400 mb-2">{tplUpload.error}</p>}

        <button
          disabled={!dbFile || !tplFile || xlsxUpload.loading || tplUpload.loading}
          onClick={handleContinue}
          className="w-full mt-2 bg-accent text-neutral-900 font-semibold py-2 rounded disabled:opacity-40"
        >
          {xlsxUpload.loading || tplUpload.loading ? "Procesando..." : "Continuar"}
        </button>
      </div>
    </div>
  )
}

interface FileSlotProps {
  icon: React.ReactNode
  label: string
  file: File | null
  onPick(f: File): void
  accept: string
}

function FileSlot({ icon, label, file, onPick, accept }: FileSlotProps) {
  return (
    <label className="flex items-center gap-3 bg-neutral-900 border border-neutral-700 hover:border-accent rounded p-3 cursor-pointer mb-3">
      <span className="text-neutral-400">{icon}</span>
      <div className="flex-1">
        <div className="text-sm">{label}</div>
        <div className="text-xs text-neutral-500">{file ? file.name : "Click para elegir archivo"}</div>
      </div>
      <Upload size={14} className="text-neutral-500" />
      <input type="file" accept={accept} className="hidden" onChange={(e) => e.target.files?.[0] && onPick(e.target.files[0])} />
    </label>
  )
}
