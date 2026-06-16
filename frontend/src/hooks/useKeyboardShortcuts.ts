import { useEffect } from "react"

interface ShortcutMap {
  [key: string]: () => void
}

export function useKeyboardShortcuts(map: ShortcutMap) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const key = [
        e.metaKey || e.ctrlKey ? "Cmd+" : "",
        e.shiftKey ? "Shift+" : "",
        e.altKey ? "Alt+" : "",
        e.key.toLowerCase(),
      ].join("")
      const action = map[key]
      if (action) {
        e.preventDefault()
        action()
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [map])
}
