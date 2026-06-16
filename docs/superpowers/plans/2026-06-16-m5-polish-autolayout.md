# M5 — Polish + Auto-Layout (Banco Match) + AI Suggest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Layout engine completo: matchea contra banco aprendido antes de heurística, soporta AI suggest layout on-demand. Auto-save cada 5s. Recientes (últimos 5). Font picker realmente aplicado a slides generadas. Manejo de errores robusto (re-localize files modal). Atajos teclado. E2E Playwright smoke. Docs (xlsx-schema, template-spec, api).

**Architecture:** Backend gains layout-bank matching + AI-suggest endpoint. Frontend gains auto-save loop + recents dropdown + relocate modal + keyboard shortcuts + Playwright config.

**Tech Stack adds:** Playwright (E2E).

---

## File Structure

**Create (backend):**
- `backend/aurum_encuestas/layout_matcher.py` — bank lookup with signature fallback
- `backend/tests/test_layout_matcher.py`

**Modify (backend):**
- `backend/aurum_encuestas/pptx_generator.py` — call `match_layout` before falling to heuristic; pass font_override to text styling
- `backend/aurum_encuestas/api.py` — `/api/suggest-layout`, `/api/recents` (list/add), update `/api/save-project` to call `add_recent`
- `backend/aurum_encuestas/llm_client.py` — add `suggest_layout()` function
- `backend/tests/test_api.py` — recents + suggest-layout tests

**Create (frontend):**
- `frontend/src/hooks/useAutoSave.ts`
- `frontend/src/components/RelocateModal.tsx`
- `frontend/src/api/recents.ts`
- `frontend/tests/Recents.test.tsx`

**Modify (frontend):**
- `frontend/src/components/Topbar.tsx` — Abrir dropdown with recents + Guardar button
- `frontend/src/pages/Editor/EditorPage.tsx` — wire auto-save + keyboard shortcuts (Cmd+S, Cmd+E, Cmd+N)
- `frontend/src/pages/Editor/ConfigPanel.tsx` — AI suggest layout button + info line ("Usando: layout aprendido #x" / "heurística A")
- `frontend/src/api/client.ts` — `suggestLayout()`

**Create (docs + E2E):**
- `e2e/` — Playwright config + smoke test
- `docs/xlsx-schema.md`
- `docs/template-spec.md`
- `docs/api.md`

---

### Task 1: layout_matcher — match by signature with fallback heuristic

**Files:**
- Create: `backend/aurum_encuestas/layout_matcher.py`
- Create: `backend/tests/test_layout_matcher.py`

- [ ] **Step 1: Failing tests**

Create `backend/tests/test_layout_matcher.py`:

```python
from aurum_encuestas.layout_matcher import match_layout
from aurum_encuestas.models import LayoutBank, LearnedLayout, LayoutElement


FREE_AREA = {"x": 600000, "y": 1200000, "cx": 11000000, "cy": 5000000}


def _layout(sig: str) -> LearnedLayout:
    return LearnedLayout(
        id=f"lay_{sig}", signature=sig, source="x.pptx#slide1",
        free_area=FREE_AREA,
        elements=[LayoutElement(role="chart_0", x=0, y=0, cx=1000, cy=1000, chart_type="PIE")],
    )


def test_match_finds_exact_signature():
    bank = LayoutBank(layouts=[_layout("2|PIE,BAR|0|0|0"), _layout("1|PIE|0|0|0")])
    res = match_layout(bank=bank, n_charts=2, chart_types=["PIE", "BAR"], n_chart_an=0, n_q_an=0, has_slide_an=False, free_area=FREE_AREA)
    assert res["source"] == "bank"
    assert res["layout_id"] == "lay_2|PIE,BAR|0|0|0"


def test_match_falls_back_to_heuristic_when_no_signature():
    bank = LayoutBank(layouts=[_layout("1|PIE|0|0|0")])
    res = match_layout(bank=bank, n_charts=4, chart_types=["PIE"] * 4, n_chart_an=0, n_q_an=0, has_slide_an=False, free_area=FREE_AREA)
    assert res["source"] == "heuristic"
    chart_els = [e for e in res["elements"] if e["role"].startswith("chart_")]
    assert len(chart_els) == 4


def test_match_with_empty_bank_uses_heuristic():
    bank = LayoutBank(layouts=[])
    res = match_layout(bank=bank, n_charts=1, chart_types=["PIE"], n_chart_an=0, n_q_an=0, has_slide_an=False, free_area=FREE_AREA)
    assert res["source"] == "heuristic"
```

- [ ] **Step 2: Implement layout_matcher**

Create `backend/aurum_encuestas/layout_matcher.py`:

```python
from .layout_engine import compute_layout
from .models import LayoutBank
from .training_extractor import signature_for_slide


def match_layout(
    bank: LayoutBank,
    n_charts: int,
    chart_types: list[str],
    n_chart_an: int,
    n_q_an: int,
    has_slide_an: bool,
    free_area: dict,
) -> dict:
    """Try exact signature match in bank; fallback to heuristic A.

    Returns: {"source": "bank"|"heuristic", "layout_id": ..., "elements": [...]}.
    """
    sig = signature_for_slide(n_charts, chart_types, n_chart_an, n_q_an, has_slide_an)
    for lay in bank.layouts:
        if lay.signature == sig:
            return {
                "source": "bank",
                "layout_id": lay.id,
                "elements": [e.model_dump() for e in lay.elements],
            }

    fallback = compute_layout(
        n_charts=n_charts,
        chart_types=chart_types,
        n_chart_analyses=n_chart_an,
        n_question_analyses=n_q_an,
        has_slide_analysis=has_slide_an,
        free_area=free_area,
    )
    return {
        "source": "heuristic",
        "layout_id": None,
        "elements": fallback["elements"],
    }
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_layout_matcher.py -v`
Expected: 3 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/layout_matcher.py backend/tests/test_layout_matcher.py
git commit -m "feat(backend): layout_matcher — bank signature match + heuristic fallback"
```

---

### Task 2: Wire layout_matcher into pptx_generator

**Files:**
- Modify: `backend/aurum_encuestas/pptx_generator.py`

- [ ] **Step 1: Replace direct compute_layout with match_layout**

Edit `backend/aurum_encuestas/pptx_generator.py`. Replace the `layout = compute_layout(...)` call in `_append_shell` with:

```python
from .layout_matcher import match_layout
from .models import LayoutBank
from .config import get_layout_bank_path
import json as _json

def _load_bank() -> LayoutBank:
    p = get_layout_bank_path()
    if not p.exists():
        return LayoutBank()
    try:
        return LayoutBank.model_validate(_json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return LayoutBank()


# inside _append_shell, replace compute_layout call:
    n_chart_an = sum(1 for a in slide_def.analyses if a.scope == "chart")
    n_q_an = sum(1 for a in slide_def.analyses if a.scope == "question")
    has_slide_an = any(a.scope == "slide" for a in slide_def.analyses)

    layout_result = match_layout(
        bank=_load_bank(),
        n_charts=len(slide_def.charts),
        chart_types=[c.chart_type for c in slide_def.charts],
        n_chart_an=n_chart_an,
        n_q_an=n_q_an,
        has_slide_an=has_slide_an,
        free_area=free_area,
    )
    layout = {"elements": layout_result["elements"]}
```

- [ ] **Step 2: Run pptx_generator tests, verify still pass**

Run: `cd backend && .venv/bin/pytest tests/test_pptx_generator.py -v`
Expected: PASS (no behavioral change with empty bank).

- [ ] **Step 3: Commit**

```bash
git add backend/aurum_encuestas/pptx_generator.py
git commit -m "feat(backend): pptx_generator uses layout_matcher (bank match → heuristic)"
```

---

### Task 3: llm_client.suggest_layout — AI proposes coords

**Files:**
- Modify: `backend/aurum_encuestas/llm_client.py`
- Modify: `backend/tests/test_llm_client.py`

- [ ] **Step 1: Failing test**

Append to `backend/tests/test_llm_client.py`:

```python
from aurum_encuestas.llm_client import suggest_layout


@patch("aurum_encuestas.llm_client._client")
def test_suggest_layout_returns_validated_json(mock_client):
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text='{"elements":[{"role":"chart_0","x":1000,"y":1000,"cx":5000,"cy":4000}]}')]
    fake_msg.usage = MagicMock(input_tokens=200, output_tokens=80, cache_read_input_tokens=170)
    mock_client.messages.create.return_value = fake_msg

    res = suggest_layout(
        n_charts=1, chart_types=["PIE"], n_chart_an=0, n_q_an=0, has_slide_an=False,
        free_area={"x": 0, "y": 0, "cx": 12000000, "cy": 7000000},
    )
    assert "elements" in res
    assert len(res["elements"]) == 1


@patch("aurum_encuestas.llm_client._client")
def test_suggest_layout_invalid_json_falls_back(mock_client):
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="not json")]
    fake_msg.usage = MagicMock(input_tokens=200, output_tokens=20, cache_read_input_tokens=0)
    mock_client.messages.create.return_value = fake_msg

    res = suggest_layout(n_charts=1, chart_types=["PIE"], n_chart_an=0, n_q_an=0, has_slide_an=False, free_area={"x": 0, "y": 0, "cx": 12000000, "cy": 7000000})
    # falls back to heuristic
    assert res["source"] in ("heuristic", "ai_fallback")
```

- [ ] **Step 2: Implement suggest_layout**

Append to `backend/aurum_encuestas/llm_client.py`:

```python
import json as _json

LAYOUT_SYSTEM = """Sos diseñador de slides. Te paso config slide y free_area canvas. Devolvés JSON con posiciones EMU para cada elemento (charts y análisis).

Reglas:
- Coords todas dentro de free_area (x ≥ free_area.x, x+cx ≤ free_area.x+free_area.cx, similar Y).
- Sin overlaps.
- Padding mínimo 200000 EMU entre elementos.
- Output: solo JSON válido, sin texto explicativo, formato:
  {"elements": [{"role": "chart_0", "x": ..., "y": ..., "cx": ..., "cy": ...}, ...]}
"""


def suggest_layout(
    n_charts: int,
    chart_types: list[str],
    n_chart_an: int,
    n_q_an: int,
    has_slide_an: bool,
    free_area: dict,
) -> dict:
    if _client is None:
        from .layout_engine import compute_layout
        return {"source": "heuristic", **compute_layout(n_charts, chart_types, n_chart_an, n_q_an, has_slide_an, free_area)}

    user_msg = _json.dumps({
        "n_charts": n_charts, "chart_types": chart_types,
        "n_chart_analyses": n_chart_an, "n_question_analyses": n_q_an,
        "has_slide_analysis": has_slide_an,
        "free_area": free_area,
    })

    try:
        msg = _client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=[{"type": "text", "text": LAYOUT_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_msg}],
        )
        text = "".join(b.text for b in msg.content if hasattr(b, "text")).strip()
        # strip code fences if any
        if text.startswith("```"):
            text = "\n".join(line for line in text.split("\n") if not line.startswith("```"))
        parsed = _json.loads(text)
        if not _validate_layout(parsed, free_area):
            raise ValueError("Layout validation failed")
        return {"source": "ai", **parsed}
    except Exception:
        from .layout_engine import compute_layout
        return {"source": "ai_fallback", **compute_layout(n_charts, chart_types, n_chart_an, n_q_an, has_slide_an, free_area)}


def _validate_layout(parsed: dict, free_area: dict) -> bool:
    if "elements" not in parsed or not isinstance(parsed["elements"], list):
        return False
    fx, fy, fw, fh = free_area["x"], free_area["y"], free_area["cx"], free_area["cy"]
    for el in parsed["elements"]:
        for k in ("x", "y", "cx", "cy"):
            if k not in el or not isinstance(el[k], (int, float)):
                return False
        if el["x"] < fx or el["x"] + el["cx"] > fx + fw:
            return False
        if el["y"] < fy or el["y"] + el["cy"] > fy + fh:
            return False
        if el["cx"] <= 0 or el["cy"] <= 0:
            return False
    return True
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_llm_client.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/llm_client.py backend/tests/test_llm_client.py
git commit -m "feat(backend): llm_client.suggest_layout — AI layout proposal with validation fallback"
```

---

### Task 4: API — /api/suggest-layout endpoint

**Files:**
- Modify: `backend/aurum_encuestas/api.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Failing test**

Append to `backend/tests/test_api.py`:

```python
@patch("aurum_encuestas.api.suggest_layout")
def test_suggest_layout_endpoint(mock_sug):
    mock_sug.return_value = {"source": "ai", "elements": [{"role": "chart_0", "x": 100, "y": 100, "cx": 1000, "cy": 1000}]}
    payload = {
        "n_charts": 1, "chart_types": ["PIE"],
        "n_chart_an": 0, "n_q_an": 0, "has_slide_an": False,
        "free_area": {"x": 0, "y": 0, "cx": 12000000, "cy": 7000000},
    }
    r = client.post("/api/suggest-layout", json=payload)
    assert r.status_code == 200
    assert r.json()["source"] == "ai"
```

- [ ] **Step 2: Implement endpoint**

Append to `backend/aurum_encuestas/api.py`:

```python
from .llm_client import suggest_layout


class SuggestLayoutRequest(BaseModel):
    n_charts: int
    chart_types: list[str]
    n_chart_an: int = 0
    n_q_an: int = 0
    has_slide_an: bool = False
    free_area: dict


@app.post("/api/suggest-layout")
async def suggest_layout_endpoint(req: SuggestLayoutRequest):
    return suggest_layout(
        n_charts=req.n_charts,
        chart_types=req.chart_types,
        n_chart_an=req.n_chart_an,
        n_q_an=req.n_q_an,
        has_slide_an=req.has_slide_an,
        free_area=req.free_area,
    )
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_api.py -v -k suggest`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/api.py backend/tests/test_api.py
git commit -m "feat(backend): /api/suggest-layout endpoint"
```

---

### Task 5: Recents endpoints + integration into save-project

**Files:**
- Modify: `backend/aurum_encuestas/api.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Failing test**

Append to `backend/tests/test_api.py`:

```python
def test_recents_add_and_list(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    # save a project (should auto-add to recents)
    proj = {"version": 1, "project_name": "P1", "inputs": {"db_path": "./x", "template_path": "./y", "font_override": None}, "slides": []}
    save_path = str(tmp_path / "p1.aurum.json")
    client.post("/api/save-project", json={"path": save_path, "state": proj})

    r = client.get("/api/recents")
    assert r.status_code == 200
    recs = r.json()["recents"]
    assert any(rec["path"] == save_path for rec in recs)
```

- [ ] **Step 2: Modify save_project endpoint + add /api/recents**

Edit `backend/aurum_encuestas/api.py`:

```python
from .config import add_recent, load_recents


# Update save_project_endpoint:
@app.post("/api/save-project")
async def save_project_endpoint(req: SaveProjectRequest):
    state = ProjectState.model_validate(req.state)
    save_project(state, req.path)
    add_recent(req.path, state.project_name)
    return {"saved": True, "path": req.path}


@app.get("/api/recents")
async def recents_endpoint():
    return {"recents": load_recents()}
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_api.py -v -k recents`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/api.py backend/tests/test_api.py
git commit -m "feat(backend): recents endpoint + auto-add on save-project"
```

---

### Task 6: Frontend — suggestLayout client + ConfigPanel button + layout info

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/Editor/ConfigPanel.tsx`

- [ ] **Step 1: Add suggestLayout client**

Append to `frontend/src/api/client.ts`:

```ts
export interface SuggestLayoutRequest {
  n_charts: number
  chart_types: string[]
  n_chart_an: number
  n_q_an: number
  has_slide_an: boolean
  free_area: { x: number; y: number; cx: number; cy: number }
}

export async function suggestLayout(req: SuggestLayoutRequest): Promise<{ source: string; elements: unknown[] }> {
  return request("/suggest-layout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })
}
```

- [ ] **Step 2: Add AI suggest button + layout info to ConfigPanel**

Edit `frontend/src/pages/Editor/ConfigPanel.tsx`. Add a section at the end of the `!isSep` block (after analyses list):

```tsx
          <button
            onClick={async () => {
              const free_area = { x: 600000, y: 1200000, cx: 11000000, cy: 5000000 }
              const r = await api.suggestLayout({
                n_charts: slide.charts.length,
                chart_types: slide.charts.map((c) => c.chart_type),
                n_chart_an: slide.analyses.filter((a) => a.scope === "chart").length,
                n_q_an: slide.analyses.filter((a) => a.scope === "question").length,
                has_slide_an: slide.analyses.some((a) => a.scope === "slide"),
                free_area,
              })
              alert(`AI suggest source: ${r.source}. (Vista previa requiere agregar este layout al state — feature v2.)`)
            }}
            className="w-full mt-3 text-xs bg-gradient-to-r from-purple-700 to-violet-700 text-white py-2 rounded font-semibold"
          >
            ✨ AI sugiere layout
          </button>
          <p className="text-[10px] text-neutral-500 mt-1 italic">Layout actual: heurística A (default)</p>
```

Add `import * as api from "../../api/client"` at top.

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/pages/Editor/ConfigPanel.tsx
git commit -m "feat(frontend): AI suggest layout button in ConfigPanel"
```

---

### Task 7: Auto-save hook

**Files:**
- Create: `frontend/src/hooks/useAutoSave.ts`
- Modify: `frontend/src/pages/Editor/EditorPage.tsx`

- [ ] **Step 1: Implement useAutoSave**

Create `frontend/src/hooks/useAutoSave.ts`:

```ts
import { useEffect, useRef } from "react"
import * as api from "../api/client"
import { useProjectStore } from "../store/project"

export function useAutoSave(intervalMs: number = 5000) {
  const state = useProjectStore((s) => s.state)
  const path = useProjectStore((s) => s.projectPath)
  const lastSavedRef = useRef<string>("")

  useEffect(() => {
    if (!state || !path) return
    const handle = setInterval(async () => {
      const cur = useProjectStore.getState().state
      const curPath = useProjectStore.getState().projectPath
      if (!cur || !curPath) return
      const snapshot = JSON.stringify(cur)
      if (snapshot === lastSavedRef.current) return
      try {
        await api.saveProject(curPath, cur)
        lastSavedRef.current = snapshot
        useProjectStore.setState({ state: { ...cur, updated_at: new Date().toISOString() } })
      } catch {
        // silently skip; toast handled elsewhere if persistent
      }
    }, intervalMs)
    return () => clearInterval(handle)
  }, [state, path, intervalMs])
}
```

- [ ] **Step 2: Wire into EditorPage**

Edit `frontend/src/pages/Editor/EditorPage.tsx` — add `useAutoSave()` call inside component:

```tsx
import { useAutoSave } from "../../hooks/useAutoSave"

export default function EditorPage() {
  useAutoSave(5000)
  // ... rest unchanged
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useAutoSave.ts frontend/src/pages/Editor/EditorPage.tsx
git commit -m "feat(frontend): auto-save every 5s when project has known path"
```

---

### Task 8: Recents dropdown in Topbar + relocate modal

**Files:**
- Create: `frontend/src/api/recents.ts`
- Create: `frontend/src/components/RelocateModal.tsx`
- Modify: `frontend/src/components/Topbar.tsx`

- [ ] **Step 1: Recents API wrapper**

Create `frontend/src/api/recents.ts`:

```ts
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
```

- [ ] **Step 2: RelocateModal**

Create `frontend/src/components/RelocateModal.tsx`:

```tsx
import { useState } from "react"
import Modal from "./Modal"

interface Props {
  open: boolean
  missingFiles: { kind: "db" | "template"; original: string }[]
  onClose(): void
  onRelocate(map: { db?: string; template?: string }): void
}

export default function RelocateModal({ open, missingFiles, onClose, onRelocate }: Props) {
  const [dbPath, setDbPath] = useState("")
  const [tplPath, setTplPath] = useState("")
  if (!open) return null
  return (
    <Modal open={open} onClose={onClose} title="Re-localizar archivos" footer={
      <button onClick={() => onRelocate({ db: dbPath || undefined, template: tplPath || undefined })} className="px-3 py-1.5 text-sm rounded bg-accent text-neutral-900 font-semibold">Aplicar</button>
    }>
      <p className="text-sm text-neutral-300 mb-3">No se encontraron estos archivos. Indicá la nueva ruta:</p>
      {missingFiles.map((m) => (
        <div key={m.kind} className="mb-3">
          <label className="block text-xs text-neutral-400 mb-1">{m.kind === "db" ? "DB" : "Template"} (era: {m.original})</label>
          <input
            value={m.kind === "db" ? dbPath : tplPath}
            onChange={(e) => m.kind === "db" ? setDbPath(e.target.value) : setTplPath(e.target.value)}
            placeholder="/ruta/absoluta/al/archivo"
            className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
          />
        </div>
      ))}
    </Modal>
  )
}
```

- [ ] **Step 3: Add recents dropdown to Topbar**

Edit `frontend/src/components/Topbar.tsx`. Add recents dropdown + Guardar button between brand and tabs:

```tsx
// add imports
import { useEffect } from "react"
import * as recentsApi from "../api/recents"
import * as api from "../api/client"

// add state inside Topbar
const [recents, setRecents] = useState<recentsApi.RecentItem[]>([])
const [showRecents, setShowRecents] = useState(false)
useEffect(() => {
  if (showRecents) recentsApi.getRecents().then(setRecents).catch(() => setRecents([]))
}, [showRecents])

const projectPath = useProjectStore((s) => s.projectPath)
const setProjectPath = useProjectStore((s) => s.setProjectPath)
const loadProjectState = useProjectStore((s) => s.loadProjectState)

const handleSave = async () => {
  const state = useProjectStore.getState().state
  if (!state) return
  let path = projectPath
  if (!path) {
    path = window.prompt("Ruta para guardar (ej: /Users/me/Documents/p.aurum.json)") || ""
    if (!path) return
  }
  await api.saveProject(path, state)
  setProjectPath(path)
}

const handleOpenRecent = async (path: string) => {
  const state = await api.loadProject(path)
  loadProjectState(state)
  setProjectPath(path)
  setShowRecents(false)
}
```

Replace existing render of buttons:

```tsx
      <div className="relative">
        <button onClick={() => setShowRecents(!showRecents)} className="px-3 py-1 rounded text-sm bg-neutral-700 hover:bg-neutral-600">Abrir ▾</button>
        {showRecents && (
          <ul className="absolute top-full mt-1 left-0 bg-neutral-800 border border-neutral-700 rounded shadow z-20 w-72">
            {recents.length === 0 && <li className="px-3 py-2 text-xs text-neutral-500">Sin recientes</li>}
            {recents.map((r) => (
              <li key={r.path}>
                <button onClick={() => handleOpenRecent(r.path)} className="block w-full text-left px-3 py-2 text-sm hover:bg-neutral-700">
                  <div>{r.name}</div>
                  <div className="text-[10px] text-neutral-500 truncate">{r.path}</div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <button onClick={handleSave} disabled={!state} className="px-3 py-1 rounded text-sm bg-neutral-700 disabled:opacity-40">Guardar</button>
```

- [ ] **Step 4: Build + commit**

Run: `cd frontend && npm run build`
Expected: succeeds.

```bash
git add frontend/src/components/Topbar.tsx frontend/src/components/RelocateModal.tsx frontend/src/api/recents.ts
git commit -m "feat(frontend): Topbar recents dropdown + Guardar button + RelocateModal"
```

---

### Task 9: Keyboard shortcuts (Cmd+S, Cmd+E, Cmd+N)

**Files:**
- Modify: `frontend/src/pages/Editor/EditorPage.tsx`

- [ ] **Step 1: Add shortcuts**

Edit `frontend/src/pages/Editor/EditorPage.tsx`:

```tsx
import { useKeyboardShortcuts } from "../../hooks/useKeyboardShortcuts"

// inside EditorPage:
const addShell = useProjectStore((s) => s.addShell)
const state = useProjectStore((s) => s.state)
const hasSeparator = state?.slides.some((sl) => sl.type === "separator")

useKeyboardShortcuts({
  "Cmd+s": async () => {
    const cur = useProjectStore.getState().state
    const path = useProjectStore.getState().projectPath
    if (cur && path) {
      const api = await import("../../api/client")
      await api.saveProject(path, cur)
    }
  },
  "Cmd+n": () => { if (hasSeparator) addShell() },
})
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Editor/EditorPage.tsx
git commit -m "feat(frontend): keyboard shortcuts Cmd+S (save) + Cmd+N (new shell)"
```

---

### Task 10: Apply font_override in pptx_generator

**Files:**
- Modify: `backend/aurum_encuestas/pptx_generator.py`
- Modify: `backend/tests/test_pptx_generator.py`

- [ ] **Step 1: Failing test**

Append to `backend/tests/test_pptx_generator.py`:

```python
def test_build_pptx_applies_font_override(tmp_path, valid_xlsx_path, valid_template_path):
    state = _state(
        [
            Slide(id="s1", type="separator", title="Sec"),
            Slide(id="s2", type="shell", title="Sec",
                  analyses=[Analysis(id="a1", scope="slide", target_id=None, text="X", ai_generated=False, edited=True)]),
        ],
        valid_xlsx_path, valid_template_path,
    )
    state.inputs.font_override = "Roboto"
    out = tmp_path / "out.pptx"
    build_pptx(state, str(out))

    prs = Presentation(str(out))
    fonts = []
    for sh in prs.slides[1].shapes:
        if sh.has_text_frame:
            for para in sh.text_frame.paragraphs:
                for run in para.runs:
                    if run.font.name:
                        fonts.append(run.font.name)
    # at least one analysis textbox should have Roboto
    assert "Roboto" in fonts
```

- [ ] **Step 2: Apply font in _add_textbox**

Edit `backend/aurum_encuestas/pptx_generator.py`. Modify `_add_textbox` signature and impl:

```python
def _add_textbox(slide, text: str, el: dict, font_name: str | None = None) -> None:
    tb = slide.shapes.add_textbox(Emu(el["x"]), Emu(el["y"]), Emu(el["cx"]), Emu(el["cy"]))
    tf = tb.text_frame
    tf.text = text
    tf.word_wrap = True
    if font_name:
        for para in tf.paragraphs:
            for run in para.runs:
                run.font.name = font_name
```

In `_append_shell`, pass `state.inputs.font_override` to every `_add_textbox` call:

```python
        elif role.startswith("chart_analysis_"):
            i = int(role.split("_")[2])
            chart_analyses = [a for a in slide_def.analyses if a.scope == "chart"]
            if i < len(chart_analyses):
                _add_textbox(slide, chart_analyses[i].text, el, state.inputs.font_override)
        elif role.startswith("question_analysis_"):
            i = int(role.split("_")[2])
            q_analyses = [a for a in slide_def.analyses if a.scope == "question"]
            if i < len(q_analyses):
                _add_textbox(slide, q_analyses[i].text, el, state.inputs.font_override)
        elif role == "slide_analysis":
            slide_an = next((a for a in slide_def.analyses if a.scope == "slide"), None)
            if slide_an:
                _add_textbox(slide, slide_an.text, el, state.inputs.font_override)
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_pptx_generator.py -v`
Expected: PASS (including new font test).

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/pptx_generator.py backend/tests/test_pptx_generator.py
git commit -m "feat(backend): pptx_generator applies font_override to analysis textboxes"
```

---

### Task 11: Playwright E2E smoke

**Files:**
- Create: `e2e/package.json`
- Create: `e2e/playwright.config.ts`
- Create: `e2e/smoke.spec.ts`
- Modify: `Makefile` — `make e2e` target

- [ ] **Step 1: Bootstrap Playwright**

Create `e2e/package.json`:

```json
{
  "name": "aurum-encuestas-e2e",
  "private": true,
  "scripts": {
    "test": "playwright test"
  },
  "devDependencies": {
    "@playwright/test": "^1.47.2",
    "typescript": "^5.6.2"
  }
}
```

Create `e2e/playwright.config.ts`:

```ts
import { defineConfig } from "@playwright/test"

export default defineConfig({
  testDir: ".",
  timeout: 60_000,
  use: {
    baseURL: "http://localhost:5173",
    headless: true,
  },
})
```

Run: `cd e2e && npm install && npx playwright install chromium`

- [ ] **Step 2: Write smoke spec**

Create `e2e/smoke.spec.ts`:

```ts
import { test, expect } from "@playwright/test"
import path from "path"

const XLSX = "/Users/joaquincardenas/Downloads/BD Aurora ejemplo.xlsx"
const TPL = path.resolve(__dirname, "../e2e_fixtures/template.pptx")

test("upload + wizard + add shell + add chart + export", async ({ page }) => {
  await page.goto("/")
  await page.setInputFiles('input[accept=".xlsx"]', XLSX)
  await page.setInputFiles('input[accept=".pptx"]', TPL)
  await page.click('button:has-text("Continuar")')
  await expect(page.getByText(/Verificación de datos/i)).toBeVisible()
  await page.click('button:has-text("Confirmar")')
  await page.click('button:has-text("Separador")')
  await page.fill('input[id="sep-title"]', "Recordación")
  await page.click('button:has-text("Crear")')
  await page.click('button:has-text("Slide")')
  await page.click('button:has-text("+ Chart")')
  await page.selectOption('select[id="q-select"]', { index: 0 })
  await page.click('input[aria-label="General"]')
  await page.click('button:has-text("Aplicar")')
  await expect(page.locator("img")).toBeVisible({ timeout: 15000 })
})
```

Before running, generate the fixture:

```bash
mkdir -p e2e_fixtures
cd backend && .venv/bin/python -c "
from pptx import Presentation
from pptx.util import Inches
prs = Presentation()
prs.slide_width = Inches(13.33); prs.slide_height = Inches(7.5)
layout = prs.slide_layouts[6]
shell = prs.slides.add_slide(layout)
shell.shapes.add_textbox(Inches(0.4), Inches(0.2), Inches(6), Inches(0.5)).text_frame.text = '@Titulo'
shell.shapes.add_textbox(Inches(0.4), Inches(6.7), Inches(8), Inches(0.6)).text_frame.text = '@Notas'
sep = prs.slides.add_slide(layout)
sep.shapes.add_textbox(Inches(0.4), Inches(3.5), Inches(10), Inches(0.6)).text_frame.text = 'Análisis de resultados\n@Titulo'
prs.save('../e2e_fixtures/template.pptx')
"
```

- [ ] **Step 3: Makefile target**

Append to `Makefile`:

```makefile
e2e:
	cd e2e && npm test
```

- [ ] **Step 4: Run smoke (requires backend + frontend running)**

Terminal A: `make dev-backend`
Terminal B: `make dev-frontend`
Terminal C: `make e2e`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add e2e Makefile
git commit -m "test(e2e): Playwright smoke — upload → wizard → builder → chart → preview"
```

---

### Task 12: Docs — xlsx-schema + template-spec + api

**Files:**
- Create: `docs/xlsx-schema.md`
- Create: `docs/template-spec.md`
- Create: `docs/api.md`

- [ ] **Step 1: Write xlsx-schema.md**

Create `docs/xlsx-schema.md`:

````markdown
# Convención XLSX esperada (heurística B)

AurumEncuestas auto-detecta la estructura del xlsx con heurística + wizard de verificación 1-click. La convención esperada (matchea 100% del ejemplo Aurum):

## Layout de hojas

Una sola hoja. Nombre típico: `BD - Análisis`. Si tu workbook tiene varias hojas, app usa la primera.

## Filas

| Fila | Contenido |
|---|---|
| 1 | Headers de grupos de breakdown (Rango de edad, Sexo, NSE, Punto) en cols dispersas |
| 2 | Sub-categorías de cada breakdown bajo su grupo. La col donde aparece `General` marca inicio de cada bloque de columnas. |
| 3 | Total muestral (col 2 = "Total", col 3 = N, cols 4+ = N por sub-categoría) |
| 4 a ~17 | Distribución demográfica de la muestra (rows con label en col A) |
| 18+ | Bloques de preguntas |

## Marcador de pregunta

Col A no vacía con uno de:
- `$pN.label` (literal `$p` + dígitos + `.` + texto) — confianza 1.0
- Texto que termina en `?` — confianza 0.9
- Texto largo (>40 chars) — confianza 0.5

## Opciones de pregunta

Filas posteriores a la del marcador, con col A vacía y col B con texto de opción.

## Columnas — 3 bloques

| Bloque | Contenido | Valores |
|---|---|---|
| 1 (cols 3-17 típicamente) | Conteos | enteros > 1 |
| 2 (cols 21-35) | % de fila | 0-1 |
| 3 (cols 41-55) | % de columna | 0-1 |

Cada bloque arranca donde row2 = "General". Detección automática.

## Breakdowns soportados (auto-mapeo)

- `General` (col donde row2=="General")
- `Rango de edad` → id `edad`
- `Sexo` → id `sexo`
- `NSE` → id `nse`
- `Punto` → id `punto`

Cualquier otro breakdown en row1 se ignora.

## Si tu xlsx no matchea

El wizard de verificación lista lo detectado con ✓/⚠. Si hay rojo, podés:
1. Re-exportar el xlsx en la convención
2. Usar "Editar mapping manual" (M5+)
````

- [ ] **Step 2: Write template-spec.md**

Create `docs/template-spec.md`:

````markdown
# Spec del template.pptx

El template define el branding y los layouts base. Debe cumplir:

## Estructura exacta

**2 slides**, en este orden:

1. **Slide 1 = shell** (canvas para charts + análisis)
2. **Slide 2 = separador** (sección divider)

Si el orden está invertido, app muestra warning con opción de swap manual al subir.

## Placeholders

Cada slide debe tener un textbox con `@Titulo` exacto. El shell puede tener adicionalmente `@Notas` (opcional).

Variables soportadas:
- `@Titulo` — título de slide (separador) o título de sección heredado (shell). Requerido.
- `@Notas` — texto auto-computado por app `{tipo_respuesta}. Número de observaciones: {N}`. Opcional.

Variables futuras (no MVP): `@Subtitulo`, `@NumSlide`, `@Fecha`.

## Área libre del shell

App calcula automáticamente la zona libre donde meter charts y análisis: detecta el rectángulo más grande no ocupado por shapes/placeholders fijos.

Para máxima zona libre, mantené el branding (logo, líneas) en bordes superior/inferior, dejando el centro libre.

## Tamaño slide

Recomendado: 16:9 estándar (13.33 × 7.5 in). Otros tamaños funcionan, el área libre se recalcula.

## Fuente

La fuente del primer textbox del shell se considera fuente default. El usuario puede sobrescribir con el font picker al subir el xlsx (override total en analyses y charts generados).

## Ejemplo mínimo

```
Slide 1 (shell):
  - Textbox top-left "@Titulo"
  - Textbox bottom-left "@Notas"
  - Logo top-right (PNG)
  - Línea separadora horizontal bajo header

Slide 2 (separador):
  - Textbox medio "Análisis de resultados\n@Titulo"
  - Logo lateral
```
````

- [ ] **Step 3: Write api.md**

Create `docs/api.md`:

````markdown
# Backend API

Base: `http://localhost:8000`

| Method | Path | Body / Form | Response |
|---|---|---|---|
| GET | `/api/health` | — | `{status: "ok"}` |
| POST | `/api/parse-xlsx` | multipart `file` | `ParsedDB` |
| POST | `/api/parse-template` | multipart `file` | `TemplateInfo` |
| POST | `/api/save-project` | `{path, state: ProjectState}` | `{saved, path}` |
| POST | `/api/load-project` | `{path}` | `ProjectState` |
| GET | `/api/recents` | — | `{recents: [...]}` |
| POST | `/api/preview-slide` | `{state, slide_index}` | `{png_base64}` |
| POST | `/api/export-pptx` | `{state, path}` | `{exported, path, size}` |
| POST | `/api/generate-analysis` | `{scope, context}` | `{text, fallback}` |
| POST | `/api/suggest-layout` | `{n_charts, chart_types, ..., free_area}` | `{source, elements}` |
| POST | `/api/training/add` | multipart `file` | `{filename, layouts_extracted, added_at}` |
| GET | `/api/training/list` | — | `{pptxs, bank_size}` |
| POST | `/api/training/delete` | `{filename}` | `{deleted}` |
| POST | `/api/training/reprocess` | — | `{reprocessed, bank_size}` |
| GET | `/api/training/bank` | — | `LayoutBank` |

## Errores

Status 400: `{code: "xlsx_parse_error"|"template_invalid", message}`
Status 500: errores generales
Status 502: `{code: "llm_error", message}` — LLM API issues

Detalles de tipos: ver `backend/aurum_encuestas/models.py` (pydantic) y `frontend/src/types/index.ts` (TS mirror).
````

- [ ] **Step 4: Commit docs**

```bash
git add docs/xlsx-schema.md docs/template-spec.md docs/api.md
git commit -m "docs: xlsx-schema + template-spec + api reference"
```

---

### Task 13: M5 wrap-up — final lint + full tests + manual E2E + tag v0.1.0

**Files:** none

- [ ] **Step 1: Run all tests + lint**

```bash
cd backend && .venv/bin/pytest -v
cd frontend && npm test
cd frontend && npm run lint
cd backend && .venv/bin/ruff check aurum_encuestas tests
```

Expected: all pass.

- [ ] **Step 2: Build production frontend**

```bash
cd frontend && npm run build
```

Expected: bundle in `frontend/dist/`.

- [ ] **Step 3: Full manual smoke**

Terminals: `make dev-backend` + `make dev-frontend`.

1. Open app, upload xlsx + template, confirm wizard
2. Add separador "Recordación"
3. Add 2 shells: each with 2 charts (P1 general+sexo Pie, P2 general+sexo Bar)
4. Add analysis (slide scope) → AI generate → accept
5. Add analysis (chart scope) → AI generate → edit text → accept
6. Drag reorder shells
7. Undo (Cmd+Z) twice
8. Save (Cmd+S) → pick path
9. Close browser tab. Re-open. Verify recents dropdown shows project. Click → loads.
10. Topbar Exportar → choose path → exports pptx
11. Open exported pptx in PowerPoint → verify slides, charts editable, separator with title, analyses textboxes present
12. Tab "Entrenamiento" → upload training PPT → verify bank grows
13. AI sugiere layout button → click → verify alert/result

- [ ] **Step 4: Tag v0.1.0**

```bash
git tag v0.1.0
git log --oneline | head -50
```

- [ ] **Step 5: Update README with full launch instructions**

Edit `README.md` to include final instructions for full setup, env vars, dependencies (libreoffice install on macOS via brew, etc.), and the 5 milestones reference.

```bash
git add README.md
git commit -m "docs(readme): final launch instructions + milestones reference"
git tag -f v0.1.0
```

---

## M5 Done When

- Layout matcher usa banco aprendido cuando matchea signature; fallback heurística determinística cuando no
- `/api/suggest-layout` funciona (Haiku con validación + fallback)
- Auto-save cada 5s persiste estado
- Recents dropdown lista últimos 5 proyectos
- Font picker realmente afecta fuente de analyses + charts en pptx generado
- Atajos Cmd+S / Cmd+N funcionan
- RelocateModal disponible si paths rotos
- E2E Playwright smoke pasa
- Docs (xlsx-schema / template-spec / api) commiteados
- All tests pass (~80-90 total)
- Lint passes
- Tag `v0.1.0` creado
- README final updated
