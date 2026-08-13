# Export Download + Session Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the hosted app multiuser-safe: PPTX export downloads in the browser, and each browser session is isolated (uploads, recents, saved projects) with save/load rewritten to be name-based.

**Architecture:** Part A swaps `/api/export-pptx` to return a `FileResponse` download. Part B adds an `X-Session-Id` header (frontend-generated uuid in localStorage), read by a FastAPI middleware into a contextvar; `get_session_dir()` namespaces per-user dirs under `~/.aurum/sessions/<id>`. Save/load become name-based, closing an arbitrary server-path traversal.

**Tech Stack:** FastAPI + Starlette (middleware, FileResponse, BackgroundTask), Python contextvars, pytest + TestClient; React + TypeScript, Zustand, Vitest + Testing Library.

## Global Constraints

- No login/accounts. Isolation is per-browser via `X-Session-Id` header only.
- Session id format: `^[A-Za-z0-9-]{1,64}$`; anything else → treated as no session.
- No session header → `get_session_dir()` falls back to `get_aurum_dir()` (keeps local/single-user and all existing tests green).
- Stay per-session: uploads, config/recents, saved projects. Stay global: training corpus, style_guide, render_cache, logs, layout_bank.
- Filenames/project names are sanitized server-side with `Path(x).name` (defense in depth).
- Backend tests use `TestClient(app)` and `monkeypatch.setenv("HOME", str(tmp_path))`. Always reset session state with `set_session(None)` at test end.
- Spanish UI copy: export button `"Descargar"`, prompt `"Nombre del proyecto"`.

---

### Task 1: Backend — export returns a browser download

**Files:**
- Modify: `backend/aurum_encuestas/api.py` (imports; `ExportPptxRequest`; `export_pptx_endpoint` ~264-277)
- Test: `backend/tests/test_api.py` (add)

**Interfaces:**
- Produces: `POST /api/export-pptx` with body `{state: dict, filename: str}` returns a PPTX file download (`Content-Disposition: attachment; filename="<name>.pptx"`).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_api.py`:

```python
def test_export_pptx_is_download():
    state = {"project_name": "T", "inputs": {"db_path": "x", "template_path": "y"}}

    def fake_build(_state, path):
        from pathlib import Path
        Path(path).write_bytes(b"PPTXDATA")

    with patch("aurum_encuestas.api.build_pptx", side_effect=fake_build):
        r = client.post("/api/export-pptx", json={"state": state, "filename": "reporte"})
    assert r.status_code == 200
    cd = r.headers["content-disposition"]
    assert cd.startswith("attachment")
    assert "reporte.pptx" in cd
    assert r.content == b"PPTXDATA"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_api.py::test_export_pptx_is_download -v`
Expected: FAIL (endpoint still expects `path`, returns JSON, no attachment header).

- [ ] **Step 3: Write minimal implementation**

In `backend/aurum_encuestas/api.py`, extend the responses import and add BackgroundTask import:

```python
from fastapi.responses import JSONResponse, FileResponse
from starlette.background import BackgroundTask
```

Replace `ExportPptxRequest` and `export_pptx_endpoint`:

```python
class ExportPptxRequest(BaseModel):
    state: dict
    filename: str = "presentacion.pptx"


@app.post("/api/export-pptx")
async def export_pptx_endpoint(req: ExportPptxRequest):
    """Build a PPTX from ProjectState and return it as a browser download."""
    state = ProjectState.model_validate(req.state)
    safe_name = Path(req.filename).name or "presentacion.pptx"
    if not safe_name.endswith(".pptx"):
        safe_name += ".pptx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx")
    tmp.close()
    build_pptx(state, tmp.name)
    return FileResponse(
        tmp.name,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=safe_name,
        background=BackgroundTask(lambda: Path(tmp.name).unlink(missing_ok=True)),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_api.py::test_export_pptx_is_download -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/api.py backend/tests/test_api.py
git commit -m "feat(export): return PPTX as browser download instead of server path"
```

---

### Task 2: Backend — session contextvar + safe id + middleware

**Files:**
- Create: `backend/aurum_encuestas/session.py`
- Modify: `backend/aurum_encuestas/api.py` (add middleware after `app = FastAPI(...)`)
- Test: `backend/tests/test_session.py` (create)

**Interfaces:**
- Produces:
  - `session.set_session(sid: str | None) -> None`
  - `session.get_session() -> str | None`
  - `session.safe_session_id(raw: str | None) -> str | None` (returns raw if it matches `^[A-Za-z0-9-]{1,64}$`, else None)
  - HTTP middleware that sets the contextvar from the `X-Session-Id` header on every request.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_session.py`:

```python
from aurum_encuestas.session import get_session, safe_session_id, set_session


def test_safe_session_id_accepts_valid():
    assert safe_session_id("a-b-1") == "a-b-1"
    assert safe_session_id("ABCdef0123") == "ABCdef0123"


def test_safe_session_id_rejects_bad():
    assert safe_session_id(None) is None
    assert safe_session_id("") is None
    assert safe_session_id("../../etc") is None
    assert safe_session_id("has space") is None
    assert safe_session_id("x" * 65) is None


def test_set_get_session():
    set_session("abc")
    assert get_session() == "abc"
    set_session(None)
    assert get_session() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_session.py -v`
Expected: FAIL (module `session` does not exist).

- [ ] **Step 3: Write minimal implementation**

Create `backend/aurum_encuestas/session.py`:

```python
"""Per-request session identity (no auth). Set from the X-Session-Id header."""
import contextvars
import re

_current_session: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "aurum_session", default=None
)
_VALID = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def set_session(sid: str | None) -> None:
    _current_session.set(sid)


def get_session() -> str | None:
    return _current_session.get()


def safe_session_id(raw: str | None) -> str | None:
    if raw and _VALID.match(raw):
        return raw
    return None
```

In `backend/aurum_encuestas/api.py`, add the import and the middleware right after `app = FastAPI(...)` (before or after the CORS block is fine):

```python
from .session import safe_session_id, set_session


@app.middleware("http")
async def _session_ctx(request: Request, call_next):
    set_session(safe_session_id(request.headers.get("X-Session-Id")))
    return await call_next(request)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_session.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/session.py backend/aurum_encuestas/api.py backend/tests/test_session.py
git commit -m "feat(session): X-Session-Id contextvar + middleware"
```

---

### Task 3: Backend — namespace uploads + config/recents per session

**Files:**
- Modify: `backend/aurum_encuestas/config.py` (add `get_session_dir`, repoint `get_config_path`)
- Modify: `backend/aurum_encuestas/api.py` (`_persist_upload` uploads dir)
- Test: `backend/tests/test_config.py` (add), `backend/tests/test_api.py` (add)

**Interfaces:**
- Consumes: `session.get_session` (Task 2).
- Produces: `config.get_session_dir() -> Path` = `get_aurum_dir()/"sessions"/<sid>` when a session is set, else `get_aurum_dir()`. `get_config_path()` and `_persist_upload` now resolve under `get_session_dir()`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_config.py` (top imports already include `get_aurum_dir`; add `get_session_dir` to the import list):

```python
def test_session_dir_falls_back_without_session(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from aurum_encuestas.config import get_session_dir
    from aurum_encuestas.session import set_session
    set_session(None)
    assert get_session_dir() == get_aurum_dir()


def test_session_dir_namespaced(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from aurum_encuestas.config import get_session_dir
    from aurum_encuestas.session import set_session
    set_session("s1")
    try:
        assert get_session_dir() == tmp_path / ".aurum" / "sessions" / "s1"
    finally:
        set_session(None)
```

Add to `backend/tests/test_api.py`:

```python
def test_uploads_are_session_isolated(valid_xlsx_path, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    with open(valid_xlsx_path, "rb") as f:
        data = f.read()
    files = {"file": ("data.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r1 = client.post("/api/parse-xlsx", files=files, headers={"X-Session-Id": "s1"})
    r2 = client.post("/api/parse-xlsx", files=files, headers={"X-Session-Id": "s2"})
    assert r1.status_code == 200 and r2.status_code == 200
    assert (tmp_path / ".aurum" / "sessions" / "s1" / "uploads" / "data.xlsx").exists()
    assert (tmp_path / ".aurum" / "sessions" / "s2" / "uploads" / "data.xlsx").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_config.py::test_session_dir_namespaced tests/test_api.py::test_uploads_are_session_isolated -v`
Expected: FAIL (`get_session_dir` missing; uploads land under `~/.aurum/uploads`, not `sessions/...`).

- [ ] **Step 3: Write minimal implementation**

In `backend/aurum_encuestas/config.py`, add after `get_aurum_dir`:

```python
def get_session_dir() -> Path:
    """Per-session dir (uploads/config/projects). Falls back to the global aurum dir."""
    from .session import get_session
    sid = get_session()
    base = get_aurum_dir()
    return base / "sessions" / sid if sid else base
```

Repoint `get_config_path`:

```python
def get_config_path() -> Path:
    return get_session_dir() / "config.json"
```

In `backend/aurum_encuestas/api.py`, `_persist_upload`: change the import and dir:

```python
def _persist_upload(file_bytes: bytes, original_name: str) -> str:
    """Save uploaded file to <session>/uploads/ keyed by filename. Returns absolute path."""
    from .config import get_session_dir
    uploads_dir = get_session_dir() / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(original_name).name
    dest = uploads_dir / safe_name
    dest.write_bytes(file_bytes)
    return str(dest.resolve())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_config.py tests/test_api.py -v`
Expected: PASS (new tests pass; existing config/recents tests still pass via fallback).

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/config.py backend/aurum_encuestas/api.py backend/tests/test_config.py backend/tests/test_api.py
git commit -m "feat(session): namespace uploads and config/recents per session"
```

---

### Task 4: Backend — save/load projects by name

**Files:**
- Modify: `backend/aurum_encuestas/api.py` (`_project_path` helper; `SaveProjectRequest`, `LoadProjectRequest`, both endpoints ~121-142)
- Test: `backend/tests/test_api.py` (add)

**Interfaces:**
- Consumes: `config.get_session_dir` (Task 3); existing `save_project`, `load_project`, `add_recent`.
- Produces: `POST /api/save-project` body `{name: str, state: dict}` → `{saved: true, name}`; `POST /api/load-project` body `{name: str}` → ProjectState dict. Files stored at `get_session_dir()/projects/<safe>.aurum.json`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_api.py`:

```python
def test_save_load_project_by_name_isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    state = {"project_name": "P1", "inputs": {"db_path": "x", "template_path": "y"}}
    s = client.post("/api/save-project", json={"name": "p1", "state": state}, headers={"X-Session-Id": "s1"})
    assert s.status_code == 200 and s.json()["name"] == "p1"
    # same session loads it
    l1 = client.post("/api/load-project", json={"name": "p1"}, headers={"X-Session-Id": "s1"})
    assert l1.status_code == 200 and l1.json()["project_name"] == "P1"
    # other session cannot
    l2 = client.post("/api/load-project", json={"name": "p1"}, headers={"X-Session-Id": "s2"})
    assert l2.status_code >= 400


def test_save_project_name_traversal_is_contained(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    state = {"project_name": "Evil", "inputs": {"db_path": "x", "template_path": "y"}}
    client.post("/api/save-project", json={"name": "../../evil", "state": state}, headers={"X-Session-Id": "s3"})
    projects_dir = tmp_path / ".aurum" / "sessions" / "s3" / "projects"
    written = list(projects_dir.glob("*.aurum.json"))
    assert len(written) == 1
    assert written[0].name == "evil.aurum.json"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_api.py::test_save_load_project_by_name_isolated tests/test_api.py::test_save_project_name_traversal_is_contained -v`
Expected: FAIL (endpoints still expect `path`).

- [ ] **Step 3: Write minimal implementation**

In `backend/aurum_encuestas/api.py`, add the helper (near `_persist_upload`):

```python
def _project_path(name: str) -> Path:
    from .config import get_session_dir
    safe = Path(name).name
    if not safe.endswith(".aurum.json"):
        safe += ".aurum.json"
    d = get_session_dir() / "projects"
    d.mkdir(parents=True, exist_ok=True)
    return d / safe
```

Replace the save/load models and endpoints:

```python
class SaveProjectRequest(BaseModel):
    name: str
    state: dict


@app.post("/api/save-project")
async def save_project_endpoint(req: SaveProjectRequest):
    state = ProjectState.model_validate(req.state)
    p = _project_path(req.name)
    save_project(state, str(p))
    add_recent(req.name, state.project_name)
    return {"saved": True, "name": req.name}


class LoadProjectRequest(BaseModel):
    name: str


@app.post("/api/load-project")
async def load_project_endpoint(req: LoadProjectRequest):
    p = _project_path(req.name)
    return load_project(str(p)).model_dump()
```

Note: `load_project` raises `ProjectIOError` (an `AurumError`) for a missing file; the existing `AurumError` handler turns that into a 4xx, satisfying the `>= 400` assertion.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_api.py -v`
Expected: PASS. Note: any pre-existing `test_api.py` test that posted `save-project`/`load-project` with a `path` key must be updated to the new `{name}` shape — update those in this step if present.

- [ ] **Step 5: Run full backend suite**

Run: `cd backend && .venv/bin/pytest -q`
Expected: green (aside from any failures that pre-date this branch).

- [ ] **Step 6: Commit**

```bash
git add backend/aurum_encuestas/api.py backend/tests/test_api.py
git commit -m "feat(session): save/load projects by name under session dir (closes path traversal)"
```

---

### Task 5: Frontend — session id module

**Files:**
- Create: `frontend/src/api/session.ts`
- Test: `frontend/tests/session.test.ts` (create)

**Interfaces:**
- Produces: `getSessionId(): string` (persists a uuid in `localStorage["aurum_session_id"]`); `sessionHeader(): Record<string, string>` → `{ "X-Session-Id": <id> }`.

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/session.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest"
import { getSessionId, sessionHeader } from "../src/api/session"

describe("session", () => {
  beforeEach(() => localStorage.clear())

  it("generates and persists a stable id", () => {
    const a = getSessionId()
    const b = getSessionId()
    expect(a).toBe(b)
    expect(localStorage.getItem("aurum_session_id")).toBe(a)
  })

  it("sessionHeader carries the id", () => {
    const id = getSessionId()
    expect(sessionHeader()).toEqual({ "X-Session-Id": id })
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/session.test.ts`
Expected: FAIL (module missing).

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/api/session.ts`:

```ts
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/session.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/session.ts frontend/tests/session.test.ts
git commit -m "feat(session): frontend session id in localStorage"
```

---

### Task 6: Frontend — attach X-Session-Id to all API calls

**Files:**
- Modify: `frontend/src/api/client.ts` (`request`, and the non-`request` fetches)
- Modify: `frontend/src/api/training.ts` (`_get`, `_post`, `_put`)
- Modify: `frontend/src/api/recents.ts`
- Modify: `frontend/src/components/ColorPicker/ColorPicker.tsx`
- Test: `frontend/tests/client-session.test.ts` (create)

**Interfaces:**
- Consumes: `sessionHeader` (Task 5).
- Produces: every API fetch includes the `X-Session-Id` header.

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/client-session.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest"
import { fetchRecents } from "../src/api/recents"

describe("client session header", () => {
  afterEach(() => vi.restoreAllMocks())

  it("recents fetch carries X-Session-Id", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ recents: [] }), { status: 200 }),
    )
    await fetchRecents()
    const init = spy.mock.calls[0][1] as RequestInit
    const headers = new Headers(init.headers)
    expect(headers.get("X-Session-Id")).toBeTruthy()
  })
})
```

Check the real export name in `recents.ts` first; if it differs from `fetchRecents`, use the actual exported function in the test.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/client-session.test.ts`
Expected: FAIL (no session header sent).

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/api/client.ts`, import and merge the header in `request`:

```ts
import { sessionHeader } from "./session"
```
```ts
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: init?.method ?? "GET",
    ...init,
    headers: { ...(init?.headers || {}), ...sessionHeader() },
  })
```

In `frontend/src/api/training.ts`, add `import { sessionHeader } from "./session"` and merge into each helper's fetch, e.g.:
```ts
const r = await fetch(path, { headers: { ...sessionHeader() } })                       // _get
```
```ts
opts.headers = { ...(opts.headers || {}), ...sessionHeader() }   // _post/_put, after setting Content-Type
```
(For `_post` FormData branch, still add `sessionHeader()` — do not set Content-Type there.)

In `frontend/src/api/recents.ts`:
```ts
import { sessionHeader } from "./session"
// ...
const r = await fetch("/api/recents", { headers: { ...sessionHeader() } })
```

In `frontend/src/components/ColorPicker/ColorPicker.tsx`:
```ts
import { sessionHeader } from "../../api/session"
// ...
fetch(RECENT_COLORS_ENDPOINT, { headers: { ...sessionHeader() } })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/client-session.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/api/training.ts frontend/src/api/recents.ts frontend/src/components/ColorPicker/ColorPicker.tsx frontend/tests/client-session.test.ts
git commit -m "feat(session): attach X-Session-Id to all frontend API calls"
```

---

### Task 7: Frontend — export blob download + ExportModal

**Files:**
- Modify: `frontend/src/api/client.ts` (`exportPptx`)
- Modify: `frontend/src/pages/Editor/modals/ExportModal.tsx`
- Test: `frontend/tests/ExportModal.test.tsx` (create)

**Interfaces:**
- Consumes: `sessionHeader` (Task 5); backend `/api/export-pptx` download (Task 1).
- Produces: `exportPptx(state: ProjectState, filename: string): Promise<void>` (triggers a browser download). `ExportModal` has only a filename field and a "Descargar" button.

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/ExportModal.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import ExportModal from "../src/pages/Editor/modals/ExportModal"
import * as api from "../src/api/client"
import { useProjectStore } from "../src/store/project"

describe("ExportModal", () => {
  it("has no folder field and downloads via exportPptx", async () => {
    useProjectStore.setState({ state: null })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    const spy = vi.spyOn(api, "exportPptx").mockResolvedValue(undefined)
    render(<ExportModal open={true} onClose={() => {}} />)
    expect(screen.queryByText(/Carpeta/i)).toBeNull()
    await userEvent.click(screen.getByRole("button", { name: /Descargar/i }))
    expect(spy).toHaveBeenCalled()
    expect(typeof spy.mock.calls[0][1]).toBe("string")
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/ExportModal.test.tsx`
Expected: FAIL (folder label present / button labeled "Exportar" / `exportPptx` signature mismatch).

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/api/client.ts`, replace `exportPptx`:

```ts
export async function exportPptx(state: ProjectState, filename: string): Promise<void> {
  const r = await fetch(`${BASE}/export-pptx`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...sessionHeader() },
    body: JSON.stringify({ state, filename }),
  })
  if (!r.ok) throw await r.json().catch(() => ({ message: "Error al exportar" }))
  const blob = await r.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename.endsWith(".pptx") ? filename : `${filename}.pptx`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
```

Rewrite `frontend/src/pages/Editor/modals/ExportModal.tsx` to drop the folder input, the `autoOpen` checkbox, and the `window.open("file://")`:

```tsx
import { useState } from "react"
import Modal from "../../../components/Modal"
import * as api from "../../../api/client"
import { useProjectStore } from "../../../store/project"

interface Props {
  open: boolean
  onClose(): void
}

export default function ExportModal({ open, onClose }: Props) {
  const state = useProjectStore((s) => s.state)
  const [name, setName] = useState(
    `AurumEncuestas_${new Date().toISOString().replace(/[:.]/g, "").slice(0, 13)}.pptx`,
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  if (!open || !state) return null

  const handleExport = async () => {
    setBusy(true); setError(null); setDone(false)
    try {
      await api.exportPptx(state, name)
      setDone(true)
    } catch (e) {
      setError((e as { message?: string }).message || "Error desconocido")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Exportar PPTX" footer={
      <>
        <button onClick={onClose} className="px-3 py-1.5 text-sm rounded bg-neutral-700">Cancelar</button>
        <button onClick={handleExport} disabled={busy} className="px-3 py-1.5 text-sm rounded bg-accent text-neutral-900 font-semibold disabled:opacity-40">
          {busy ? "Generando..." : "Descargar"}
        </button>
      </>
    }>
      <label className="block text-xs text-neutral-400 mb-1">Nombre archivo</label>
      <input value={name} onChange={(e) => setName(e.target.value)} className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm" />
      {done && <div className="mt-1 text-xs text-green-400">✓ Descarga iniciada</div>}
      {error && <div className="mt-1 text-xs text-red-400">{error}</div>}
    </Modal>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/ExportModal.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/pages/Editor/modals/ExportModal.tsx frontend/tests/ExportModal.test.tsx
git commit -m "feat(export): browser download in ExportModal, drop server-path fields"
```

---

### Task 8: Frontend — save/load projects by name

**Files:**
- Modify: `frontend/src/api/client.ts` (`saveProject`, `loadProject`)
- Modify: `frontend/src/store/project.ts` (`projectPath`→`projectName`, `setProjectPath`→`setProjectName`)
- Modify: `frontend/src/components/Topbar.tsx` (`handleSave`, `handleOpenRecent`)
- Modify: `frontend/src/hooks/useAutoSave.ts`
- Modify: `frontend/src/pages/Editor/EditorPage.tsx` (Cmd+s handler)
- Modify: `frontend/src/api/recents.ts` (open by name — if it exposes a click handler; otherwise only display uses `name`)
- Test: `frontend/tests/store.test.ts` (add) — check the existing file name; if project store tests live elsewhere, add there.

**Interfaces:**
- Consumes: backend `save-project {name,state}` / `load-project {name}` (Task 4).
- Produces: `saveProject(name: string, state: ProjectState)`, `loadProject(name: string)`; store field `projectName: string | null` with `setProjectName(name: string | null)`.

- [ ] **Step 1: Write the failing test**

Add to `frontend/tests/store.test.ts` (adjust import if the store test file differs):

```ts
import { describe, expect, it } from "vitest"
import { useProjectStore } from "../src/store/project"

describe("project name state", () => {
  it("setProjectName updates projectName", () => {
    useProjectStore.getState().setProjectName("mi-proyecto")
    expect(useProjectStore.getState().projectName).toBe("mi-proyecto")
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/store.test.ts`
Expected: FAIL (`setProjectName`/`projectName` don't exist yet — TS/runtime error).

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/store/project.ts`: rename the field and setter.
- Interface `Store`: `projectPath: string | null` → `projectName: string | null`; `setProjectPath(path: string | null): void` → `setProjectName(name: string | null): void`.
- Initial value: `projectName: null`.
- Implementation: `setProjectName(name) { set({ projectName: name }) }`.
- If `projectPath` is in the zustand `partialize`/persist allowlist, rename it there too.

In `frontend/src/api/client.ts`:
```ts
export async function saveProject(name: string, state: ProjectState): Promise<{ saved: boolean; name: string }> {
  return request("/save-project", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, state }) })
}

export async function loadProject(name: string): Promise<ProjectState> {
  return request("/load-project", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) })
}
```
(Keep the existing body-construction style of the file if it differs; only the payload keys `path`→`name` and the param name change.)

In `frontend/src/components/Topbar.tsx`:
```ts
const projectName = useProjectStore((s) => s.projectName)
const setProjectName = useProjectStore((s) => s.setProjectName)
// ...
const handleSave = async () => {
  if (!state) return
  let name = projectName
  if (!name) {
    name = window.prompt("Nombre del proyecto") || ""
    if (!name) return
  }
  await api.saveProject(name, state)
  setProjectName(name)
}
const handleOpenRecent = async (name: string) => {
  const loadedState = await api.loadProject(name)
  loadProjectState(loadedState)
  setProjectName(name)
  setShowRecents(false)
}
```

In `frontend/src/hooks/useAutoSave.ts`: replace `projectPath` reads with `projectName`; if `null`, skip autosave (same guard as today), else `api.saveProject(name, cur)`.

In `frontend/src/pages/Editor/EditorPage.tsx` (Cmd+s): read `projectName`; if present, `api.saveProject(projectName, cur)`.

In `frontend/src/api/recents.ts`: recents already display the `name` field returned by the backend; ensure the "open" path passes `name` to `handleOpenRecent`. No fetch-shape change beyond the header added in Task 6.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/store.test.ts`
Expected: PASS.

- [ ] **Step 5: Run full frontend suite + typecheck**

Run: `cd frontend && npx vitest run && npx tsc --noEmit`
Expected: all tests pass (aside from failures pre-dating this branch), no type errors. `tsc` catches any leftover `projectPath` reference.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/store/project.ts frontend/src/components/Topbar.tsx frontend/src/hooks/useAutoSave.ts frontend/src/pages/Editor/EditorPage.tsx frontend/src/api/recents.ts frontend/tests/store.test.ts
git commit -m "feat(session): save/load projects by name in frontend"
```

---

## Self-Review

**Spec coverage:**
- Part A backend FileResponse download → Task 1. ✓
- Part A frontend exportPptx blob + ExportModal → Task 7. ✓
- Session id frontend module → Task 5. ✓
- X-Session-Id on all calls (client/training/recents/ColorPicker) → Task 6. ✓
- Backend contextvar + middleware + safe id → Task 2. ✓
- `get_session_dir` + repoint uploads + config/recents → Task 3. ✓
- Global dirs unchanged (training/style/cache/logs/layout_bank) → not touched in any task. ✓
- Save/load by name + `_project_path` + traversal containment → Task 4 (backend), Task 8 (frontend). ✓
- Error handling: missing project → AurumError→4xx (Task 4 note); export no state → ExportModal returns early (Task 7). ✓
- Fallback without header → `get_session_dir` returns base (Task 3 test). ✓

**Placeholder scan:** No TBD/TODO; every code step has concrete code and exact run commands. Two "verify the real export name / store test file" notes are self-check instructions, not placeholders — the code to write is fully specified.

**Type consistency:**
- `get_session_dir` defined Task 3, used Tasks 3 & 4. ✓
- `set_session`/`get_session`/`safe_session_id` defined Task 2, used Tasks 3. ✓
- `sessionHeader` defined Task 5, used Tasks 6 & 7. ✓
- `saveProject(name, state)` / `loadProject(name)` — backend `{name,state}`/`{name}` (Task 4) matches frontend payloads (Task 8). ✓
- `projectName`/`setProjectName` defined Task 8, used across Topbar/useAutoSave/EditorPage in the same task. ✓
- `exportPptx(state, filename)` — frontend (Task 7) matches backend `{state, filename}` (Task 1). ✓
