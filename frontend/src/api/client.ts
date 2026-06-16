import type { ParsedDB, ProjectState, TemplateInfo } from "../types"

const BASE = "http://localhost:8000/api"

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, init || { method: "GET" })
  if (!r.ok) {
    let payload: any
    try {
      payload = await r.json()
    } catch {
      payload = { code: "unknown", message: r.statusText }
    }
    throw payload
  }
  return r.json() as Promise<T>
}

async function uploadFile<T>(path: string, file: File): Promise<T> {
  const fd = new FormData()
  fd.append("file", file)
  return request<T>(path, { method: "POST", body: fd })
}

export async function health(): Promise<{ status: string }> {
  return request("/health")
}

export async function parseXlsx(file: File): Promise<ParsedDB> {
  return uploadFile("/parse-xlsx", file)
}

export async function parseTemplate(file: File): Promise<TemplateInfo> {
  return uploadFile("/parse-template", file)
}

export async function saveProject(path: string, state: ProjectState): Promise<{ saved: boolean; path: string }> {
  return request("/save-project", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, state }),
  })
}

export async function loadProject(path: string): Promise<ProjectState> {
  return request("/load-project", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  })
}
