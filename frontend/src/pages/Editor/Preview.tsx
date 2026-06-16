import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"
import { useProjectStore } from "../../store/project"
import { useDebounce } from "../../hooks/useDebounce"
import * as api from "../../api/client"

interface Props {
  slideId: string | null
}

export default function Preview({ slideId }: Props) {
  const state = useProjectStore((s) => s.state)
  const [pngUrl, setPngUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const slideIdx = state?.slides.findIndex((s) => s.id === slideId) ?? -1
  const debouncedState = useDebounce(state, 500)

  useEffect(() => {
    if (!debouncedState || slideIdx < 0) return
    let cancelled = false
    setLoading(true); setError(null)
    api.previewSlide(debouncedState, slideIdx)
      .then((r) => {
        if (cancelled) return
        const blob = new Blob([Uint8Array.from(atob(r.png_base64), (c) => c.charCodeAt(0))], { type: "image/png" })
        setPngUrl(URL.createObjectURL(blob))
      })
      .catch((e: { message?: string }) => !cancelled && setError(e.message || "Error renderizando"))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [debouncedState, slideIdx])

  return (
    <section className="bg-neutral-800 flex items-center justify-center relative overflow-hidden">
      {loading && <div className="absolute top-3 right-3 text-neutral-400"><Loader2 size={16} className="animate-spin" /></div>}
      {error && <div className="text-red-400 text-sm">[Render error: {error}] <button onClick={() => setError(null)} className="underline">retry</button></div>}
      {!error && pngUrl && (
        <img src={pngUrl} alt={`Slide ${slideIdx + 1}`} className="max-w-full max-h-full shadow-xl" />
      )}
      {!pngUrl && !loading && !error && (
        <div className="text-neutral-500 text-sm">Seleccioná una slide para previsualizar</div>
      )}
    </section>
  )
}
