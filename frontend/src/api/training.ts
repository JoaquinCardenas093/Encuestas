const BASE = "/api/training"

export interface TrainingPPT {
  filename: string
  added_at: string
  layouts_extracted: number
  status: string
}

export interface TrainingListResponse {
  pptxs: TrainingPPT[]
  bank_size: number
}

export async function addTraining(file: File): Promise<{ filename: string; layouts_extracted: number; added_at: string }> {
  const fd = new FormData()
  fd.append("file", file)
  const r = await fetch(`${BASE}/add`, { method: "POST", body: fd })
  if (!r.ok) throw await r.json()
  return r.json()
}

export async function listTraining(): Promise<TrainingListResponse> {
  const r = await fetch(`${BASE}/list`)
  if (!r.ok) throw await r.json()
  return r.json()
}

export async function deleteTraining(filename: string): Promise<void> {
  const r = await fetch(`${BASE}/delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename }),
  })
  if (!r.ok) throw await r.json()
}

export async function reprocessTraining(): Promise<void> {
  const r = await fetch(`${BASE}/reprocess`, { method: "POST" })
  if (!r.ok) throw await r.json()
}

export async function getBank(): Promise<{ layouts: unknown[]; source_pptxs: string[] }> {
  const r = await fetch(`${BASE}/bank`)
  if (!r.ok) throw await r.json()
  return r.json()
}
