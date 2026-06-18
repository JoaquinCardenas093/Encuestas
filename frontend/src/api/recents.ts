export interface RecentItem {
  path: string
  name: string
  opened_at: string
}

export async function getRecents(): Promise<RecentItem[]> {
  const r = await fetch("/api/recents")
  if (!r.ok) throw await r.json()
  return (await r.json()).recents
}
