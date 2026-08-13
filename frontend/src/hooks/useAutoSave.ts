import { useEffect, useRef } from "react"
import * as api from "../api/client"
import { useProjectStore } from "../store/project"

export function useAutoSave(intervalMs: number = 5000) {
  const state = useProjectStore((s) => s.state)
  const name = useProjectStore((s) => s.projectName)
  const lastSavedRef = useRef<string>("")

  useEffect(() => {
    if (!state || !name) return
    const handle = setInterval(async () => {
      const cur = useProjectStore.getState().state
      const curName = useProjectStore.getState().projectName
      if (!cur || !curName) return
      const snapshot = JSON.stringify(cur)
      if (snapshot === lastSavedRef.current) return
      try {
        await api.saveProject(curName, cur)
        lastSavedRef.current = snapshot
        useProjectStore.setState({ state: { ...cur, updated_at: new Date().toISOString() } })
      } catch {
        // silently skip; toast handled elsewhere if persistent
      }
    }, intervalMs)
    return () => clearInterval(handle)
  }, [state, name, intervalMs])
}
