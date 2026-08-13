const KEY = "aurum_session_id"

// crypto.randomUUID only exists in a secure context (HTTPS or localhost).
// On plain http://<ip> it is undefined, so fall back to getRandomValues / Math.random.
function newSessionId(): string {
  const c = globalThis.crypto
  if (c?.randomUUID) {
    try {
      return c.randomUUID()
    } catch {
      /* insecure context — fall through */
    }
  }
  const bytes = new Uint8Array(16)
  if (c?.getRandomValues) c.getRandomValues(bytes)
  else for (let i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256)
  return Array.from(bytes, (x) => x.toString(16).padStart(2, "0")).join("")
}

export function getSessionId(): string {
  let id = localStorage.getItem(KEY)
  if (!id) {
    id = newSessionId()
    localStorage.setItem(KEY, id)
  }
  return id
}

export function sessionHeader(): Record<string, string> {
  return { "X-Session-Id": getSessionId() }
}
