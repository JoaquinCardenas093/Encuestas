import { useEffect, useRef } from "react"
import * as api from "../api/client"
import { useProjectStore } from "../store/project"

export function useAutoSave(intervalMs: number = 5000) {
  const state = useProjectStore((s) => s.state)
  const path = useProjectStore((s) => s.projectPath)
  const lastSavedRef = useRef<string>("")

  useEffect(() => {
    if (!state || !path) return
    const handle = setInterval(async () => {
      const cur = useProjectStore.getState().state
      const curPath = useProjectStore.getState().projectPath
      if (!cur || !curPath) return
      const snapshot = JSON.stringify(cur)
      if (snapshot === lastSavedRef.current) return
      try {
        await api.saveProject(curPath, cur)
        lastSavedRef.current = snapshot
        useProjectStore.setState({ state: { ...cur, updated_at: new Date().toISOString() } })
      } catch {
        // silently skip; toast handled elsewhere if persistent
      }
    }, intervalMs)
    return () => clearInterval(handle)
  }, [state, path, intervalMs])
}
