# Export descarga + Aislamiento por sesión

Fecha: 2026-08-13

## Objetivo

Hacer la app usable como servicio web multiusuario en el VPS:

- **Parte A:** el export de PPTX se descarga en el navegador del usuario, en vez de
  escribirse a una ruta del servidor (inservible en remoto).
- **Parte B:** cada navegador queda aislado por sesión (sin login): sus uploads,
  recents y proyectos guardados no chocan con los de otros usuarios. De paso cierra
  un path-traversal existente en save/load.

## Contexto existente

- Backend casi **sin estado**: el frontend guarda el `ProjectState` en localStorage
  (zustand persist) y lo manda en el body de cada request. Dos navegadores ya tienen
  estado independiente en memoria.
- Recursos **compartidos** en el server que hoy chocan entre usuarios:
  - `~/.aurum/uploads/<filename>` — keyed por nombre → dos users con `data.xlsx` se
    pisan (corrompe datos).
  - `~/.aurum/config.json` (recents) — global → se filtran nombres de proyectos.
  - `save-project`/`load-project` — reciben una **ruta arbitraria del server** desde
    el cliente (`window.prompt`). Path-traversal + escritura/lectura arbitraria.
- `get_aurum_dir()` (config.py) deriva todo de `$HOME`. En el contenedor `HOME=/data`
  (volumen). Todos los helpers de directorio cuelgan de ahí.
- Export actual (`ExportModal.tsx` + `/api/export-pptx`): escribe a `req.path` en el
  server y hace `window.open("file://"+path)` (apunta al FS del cliente, no existe).

## Parte A — Export descarga al navegador

### Backend `/api/export-pptx`

Reemplazar el request/response:

```python
class ExportPptxRequest(BaseModel):
    state: dict
    filename: str = "presentacion.pptx"

@app.post("/api/export-pptx")
async def export_pptx_endpoint(req: ExportPptxRequest):
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

- `FileResponse` (ya se importa de `fastapi.responses`? — importar si falta) con
  `filename` fija el `Content-Disposition: attachment`.
- `BackgroundTask` (de `starlette.background`) borra el temp tras enviarlo.
- Se elimina el manejo de `path`/`expanduser`/`mkdir`.

### Frontend `api/client.ts` — `exportPptx`

Cambiar de `request()` (que hace `.json()`) a un fetch que baja blob y dispara
descarga del navegador:

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

(`sessionHeader()` viene de Parte B; en Parte A sola sería `{}`.)

### Frontend `ExportModal.tsx`

- Quitar campo "Carpeta", checkbox "Abrir al terminar" y el `window.open("file://")`.
- Dejar solo input "Nombre archivo" + botón "Descargar".
- `handleExport`: `await api.exportPptx(state, name)`; en éxito, mensaje
  "✓ Descarga iniciada" y cerrar.

## Parte B — Aislamiento por sesión

### Identidad de sesión (frontend)

- Nuevo módulo `frontend/src/api/session.ts`:
  ```ts
  const KEY = "aurum_session_id"
  export function getSessionId(): string {
    let id = localStorage.getItem(KEY)
    if (!id) { id = crypto.randomUUID(); localStorage.setItem(KEY, id) }
    return id
  }
  export function sessionHeader(): Record<string, string> {
    return { "X-Session-Id": getSessionId() }
  }
  ```
- Inyectar `sessionHeader()` en **todas** las llamadas API:
  - `client.ts` `request()` — mergear en `init.headers`.
  - `client.ts` `exportPptx`, `fetchSheetGrid`, etc. que no usen `request()`.
  - `api/training.ts` (`_get`/`_post`/`_put` helpers).
  - `api/recents.ts` (`fetch("/api/recents")`).
  - `ColorPicker.tsx` (`fetch(RECENT_COLORS_ENDPOINT)`).

### Contexto de sesión (backend)

- Nuevo `session.py`:
  ```python
  import contextvars
  _current_session: contextvars.ContextVar[str | None] = contextvars.ContextVar("session", default=None)
  def set_session(sid: str | None) -> None: _current_session.set(sid)
  def get_session() -> str | None: return _current_session.get()
  ```
- Middleware en `api.py` (tras crear `app`):
  ```python
  @app.middleware("http")
  async def _session_ctx(request: Request, call_next):
      raw = request.headers.get("X-Session-Id")
      set_session(_safe_session_id(raw))
      return await call_next(request)
  ```
  `_safe_session_id`: acepta solo `[A-Za-z0-9-]{1,64}`; si no matchea → `None`.

### Directorios por sesión (config.py)

- Nuevo helper:
  ```python
  def get_session_dir() -> Path:
      from .session import get_session
      sid = get_session()
      base = get_aurum_dir()
      return base / "sessions" / sid if sid else base
  ```
- Repuntar a `get_session_dir()` (en vez de `get_aurum_dir()`):
  - **uploads** (`_persist_upload` en api.py): `get_session_dir() / "uploads"`.
  - **config/recents**: `get_config_path()` → `get_session_dir() / "config.json"`.
  - **proyectos guardados** (nuevo, ver abajo): `get_session_dir() / "projects"`.
- **Sin cambios (siguen globales):** `get_training_dir`, `get_corpus_dir`,
  `get_style_guide_path`, `get_render_cache_dir`, `get_ai_logs_dir`,
  `get_layout_bank_path`. Training/estilo/cache son house-style compartido.
- **Fallback:** sin header (tests, uso local single-user) → `get_session()` es `None`
  → `get_session_dir()` == `get_aurum_dir()`. Comportamiento actual intacto.

### Save/Load por nombre (cierra path-traversal)

Backend:
```python
def _project_path(name: str) -> Path:
    safe = Path(name).name  # strip separators
    if not safe.endswith(".aurum.json"): safe += ".aurum.json"
    d = get_session_dir() / "projects"
    d.mkdir(parents=True, exist_ok=True)
    return d / safe

class SaveProjectRequest(BaseModel):
    name: str
    state: dict

@app.post("/api/save-project")
async def save_project_endpoint(req: SaveProjectRequest):
    state = ProjectState.model_validate(req.state)
    p = _project_path(req.name)
    save_project(state, str(p))
    add_recent(req.name, state.project_name)   # recent keyed by name now
    return {"saved": True, "name": req.name}

class LoadProjectRequest(BaseModel):
    name: str

@app.post("/api/load-project")
async def load_project_endpoint(req: LoadProjectRequest):
    p = _project_path(req.name)
    return load_project(str(p)).model_dump()
```

- `add_recent(path,name)` sigue igual de firma; ahora se le pasa `name` como clave.
  Recents por sesión (config namespaced). El campo `path` del recent guarda el
  `name`.

Frontend:
- `store/project.ts`: renombrar `projectPath`→`projectName`, `setProjectPath`→
  `setProjectName`. Persisten igual.
- `client.ts`: `saveProject(name, state)`, `loadProject(name)`.
- `Topbar.tsx` `handleSave`: si no hay `projectName`, `window.prompt("Nombre del
  proyecto")` (nombre, no ruta). `handleOpenRecent(name)`.
- `useAutoSave.ts` y `EditorPage.tsx` (Cmd+s): usar `projectName`; si es `null`, no
  autosalvar (igual que hoy cuando no hay path).
- `recents.ts`: cada recent muestra `name`; abrir → `loadProject(name)`.

## Manejo de errores / borde

- Export sin `state` → `ExportModal` ya retorna si `!state`.
- `filename`/`name` con separadores → `Path(x).name` los tira (backend). Doble
  defensa: front no valida, back sí.
- Header `X-Session-Id` inválido/ausente → `None` → dir global (no rompe, solo no
  aísla). En prod el front siempre lo manda.
- Proyecto inexistente en load → `ProjectIOError` → el manejo de errores actual del
  endpoint lo propaga (mismo que hoy).
- Concurrencia de escritura al mismo `config.json`/proyecto dentro de **una** sesión:
  fuera de alcance (un usuario, una pestaña activa). Distintas sesiones ya no
  comparten archivo.

## Testing

Backend (`backend/tests`, pytest + httpx TestClient):

1. **export-pptx**: POST `{state, filename:"x"}` → 200, `Content-Disposition` con
   `attachment; filename="x.pptx"`, `content-type` pptx, body no vacío.
2. **session dir**: con `set_session("abc")`, `get_session_dir()` termina en
   `sessions/abc`; sin sesión, == `get_aurum_dir()`.
3. **_safe_session_id**: `"../../etc"` → `None`; `"a-b-1"` → `"a-b-1"`.
4. **upload aislado**: POST parse-xlsx con header `X-Session-Id: s1` guarda bajo
   `sessions/s1/uploads/`; con `s2`, distinto dir; mismo filename no se pisa.
5. **save/load por nombre**: save `{name:"p1", state}` con sesión s1 → load
   `{name:"p1"}` en s1 devuelve el state; load `{name:"p1"}` en s2 → error (aislado).
6. **path-traversal**: save `{name:"../../evil"}` escribe dentro de
   `sessions/<sid>/projects/` (nombre saneado), no fuera.

Frontend (`frontend/tests`, vitest):

7. **session.ts**: `getSessionId()` persiste el mismo id entre llamadas; setea
   localStorage.
8. **exportPptx**: mock `fetch` → blob; espía creación de `<a download>` con el
   nombre correcto (o al menos que llama fetch a `/export-pptx` con `filename`).
9. **ExportModal**: no hay input "Carpeta"; botón dice "Descargar"; click llama
   `api.exportPptx(state, name)`.
10. **client headers**: `request()` incluye `X-Session-Id` (mock localStorage +
    espiar fetch headers).

## Fuera de alcance

- Login / cuentas / passwords.
- Expiración/limpieza de sesiones viejas (se puede sumar un cron después).
- Concurrencia multi-pestaña dentro de una misma sesión.
- HTTPS/TLS (tema aparte de deploy).
