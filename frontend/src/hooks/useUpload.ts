import { useState } from "react"

export function useFileUpload<T>(uploader: (f: File) => Promise<T>) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<T | null>(null)

  async function upload(f: File) {
    setLoading(true); setError(null)
    try {
      const r = await uploader(f)
      setData(r); return r
    } catch (e) {
      const msg = (e as { message?: string })?.message ?? "Error desconocido"
      setError(msg)
      throw e
    } finally {
      setLoading(false)
    }
  }

  return { upload, loading, error, data, reset: () => { setError(null); setData(null) } }
}
