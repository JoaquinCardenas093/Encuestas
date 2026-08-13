const KEY = "aurum_session_id"

export function getSessionId(): string {
  let id = localStorage.getItem(KEY)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(KEY, id)
  }
  return id
}

export function sessionHeader(): Record<string, string> {
  return { "X-Session-Id": getSessionId() }
}
