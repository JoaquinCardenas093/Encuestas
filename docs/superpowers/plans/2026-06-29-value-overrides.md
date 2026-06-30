# Per-Cell Value Overrides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users see and override the per-cell count and computed percentage (per option×category) in the field editor, persisted as `ParsedDB.value_overrides` and applied on top of computed values everywhere data is read.

**Architecture:** `ParsedDB.value_overrides` (a `key → {count?, pct?}` map) is applied in both extractors after computing values. A `/api/cell-values` endpoint returns the crosstab for a (question, breakdown) so the field editor can display current values; a crosstab editor writes overrides into the draft via a pure `setValueOverride` helper.

**Tech Stack:** Python (FastAPI, openpyxl, pytest/TestClient), React + TypeScript (vitest, Zustand).

## Global Constraints

- Backend tests run: `cd backend && arch -arm64 .venv/bin/python -m pytest <path> -v` (arm64 venv prefix required).
- Frontend tests run: `cd frontend && npx vitest run <path>`; typecheck `cd frontend && npx tsc --noEmit`.
- If a command hits ENOSPC / `/private/tmp ... full`, prefix with `export TMPDIR="$HOME/.cache/cc-tmp" && mkdir -p "$TMPDIR" &&`.
- Override key format (verbatim): `f"{question_id}|{breakdown_id}|{category}|{option}"`.
- `pct` is stored as a **fraction** (e.g. `0.916`); the UI shows/edits it as percent (`×100`).
- Count and pct overrides are **independent** — applying one never alters the other. An override field present with a non-null value wins; absent/null → computed value.
- The `general` breakdown's category key is `"Total"`.
- Work on a feature branch (controller creates it); do NOT switch branches inside a task.

---

### Task 1: `value_overrides` model + apply in extraction

**Files:**
- Modify: `backend/aurum_encuestas/models.py` (`ParsedDB`)
- Modify: `backend/aurum_encuestas/data_extractor.py` (`_override_key`, `overrides` on both extractors)
- Modify: `backend/aurum_encuestas/pattern_classifier.py`, `pptx_generator.py`, `api.py` (pass `overrides`)
- Test: `backend/tests/test_data_extractor.py`

**Interfaces:**
- Produces: `ParsedDB.value_overrides: dict`; `_override_key(question_id, breakdown_id, category, option) -> str`; `extract_chart_data(..., overrides=None)` and `extract_all_breakdowns_data(..., overrides=None)` apply overrides.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_data_extractor.py`:

```python
def test_extract_chart_data_override_count(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    q1 = db.questions[0]
    key = f"{q1.id}|general|Total|Sí"
    data = extract_chart_data(str(valid_xlsx_path), q1, "general", db.data_blocks,
                              total_row=db.total_row, overrides={key: {"count": 999}})
    assert data["Total"]["Sí"]["count"] == 999
    assert abs(data["Total"]["Sí"]["pct"] - 458 / 500) < 1e-9  # pct untouched


def test_extract_chart_data_override_pct(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    q1 = db.questions[0]
    key = f"{q1.id}|general|Total|Sí"
    data = extract_chart_data(str(valid_xlsx_path), q1, "general", db.data_blocks,
                              total_row=db.total_row, overrides={key: {"pct": 0.5}})
    assert data["Total"]["Sí"]["pct"] == 0.5
    assert data["Total"]["Sí"]["count"] == 458  # count untouched
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_data_extractor.py::test_extract_chart_data_override_count tests/test_data_extractor.py::test_extract_chart_data_override_pct -v`
Expected: FAIL (`unexpected keyword argument 'overrides'`).

- [ ] **Step 3: Add the model field**

In `backend/aurum_encuestas/models.py`, `class ParsedDB` — add after `total_row`:

```python
    value_overrides: dict = {}
```

- [ ] **Step 4: Add `_override_key` + apply in `extract_chart_data`**

In `backend/aurum_encuestas/data_extractor.py`, add the helper near the top (after imports):

```python
def _override_key(question_id: str, breakdown_id: str, category: str, option: str) -> str:
    return f"{question_id}|{breakdown_id}|{category}|{option}"
```

Change `extract_chart_data`'s signature to add `overrides: dict | None = None` (last param) and, inside the option loop right before `result[cat][opt] = {...}`, apply the override:

```python
            if overrides:
                ov = overrides.get(_override_key(getattr(question, "id", ""), breakdown_id, cat, opt))
                if ov:
                    if ov.get("count") is not None:
                        count_v = ov["count"]
                    if ov.get("pct") is not None:
                        pct_v = ov["pct"]
            result[cat][opt] = {"count": count_v, "pct": pct_v}
```

- [ ] **Step 5: Apply in `extract_all_breakdowns_data`**

Add `overrides: dict | None = None` to its signature and, in its inner option loop right before `cell_map[opt] = {...}`, apply the same override (using `bd.id` as the breakdown id):

```python
                if overrides:
                    ov = overrides.get(_override_key(getattr(question, "id", ""), bd.id, cat, opt))
                    if ov:
                        if ov.get("count") is not None:
                            count_v = ov["count"]
                        if ov.get("pct") is not None:
                            pct_v = ov["pct"]
                cell_map[opt] = {"count": count_v, "pct": pct_v}
```

- [ ] **Step 6: Pass `overrides` from all callers**

Read each call site and add `overrides=...`:
- `pattern_classifier.py` (`extract_chart_data(...)` ~line 494 and `extract_all_breakdowns_data(...)` ~line 500): pass `overrides=getattr(parsed_db, "value_overrides", None)`.
- `api.py` (`extract_chart_data(...)` ~line 266 and `extract_all_breakdowns_data(...)` ~line 561): pass `overrides=state.parsed_db.value_overrides`.
- `pptx_generator.py` (`extract_chart_data(...)` ~line 419): pass `overrides=state.parsed_db.value_overrides if state.parsed_db else None`.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_data_extractor.py tests/test_pattern_classifier.py -v`
Expected: PASS (new tests + existing — existing tests pass `overrides=None` by default).

- [ ] **Step 8: Commit**

```bash
git add backend/aurum_encuestas/models.py backend/aurum_encuestas/data_extractor.py backend/aurum_encuestas/pattern_classifier.py backend/aurum_encuestas/pptx_generator.py backend/aurum_encuestas/api.py backend/tests/test_data_extractor.py
git commit -m "feat(extractor): apply per-cell value_overrides (count/pct) on top of computed values"
```

---

### Task 2: `/api/cell-values` endpoint

**Files:**
- Modify: `backend/aurum_encuestas/api.py` (request model + route)
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `ParsedDB.value_overrides` + `extract_chart_data(..., overrides=...)` (Task 1).
- Produces: `POST /api/cell-values` body `{state, question_id, breakdown_id}` → `{options: string[], categories: string[], cells: {option: {category: {count, pct}}}}` (or `{error, options:[], categories:[], cells:{}}`).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_api.py`. Build a minimal valid `ProjectState` dict — read `backend/aurum_encuestas/models.py` for the exact `ProjectState`/`ProjectInputs` fields and construct it (e.g. via `ProjectState(...).model_dump()` or a literal). The assertions:

```python
def test_cell_values_endpoint(valid_xlsx_path):
    from aurum_encuestas.xlsx_parser import parse_xlsx
    db = parse_xlsx(str(valid_xlsx_path))
    # Construct a valid ProjectState dict with parsed_db + inputs.db_path set to the fixture.
    state = _minimal_state(db, str(valid_xlsx_path))   # build per the ProjectState model
    r = client.post("/api/cell-values", json={
        "state": state, "question_id": db.questions[0].id, "breakdown_id": "general",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["options"] == db.questions[0].options
    assert body["categories"] == ["Total"]
    assert body["cells"]["Sí"]["Total"]["count"] == 458
```

Provide a `_minimal_state(db, path)` helper in the test file that returns a dict matching the `ProjectState` model (use `db.model_dump()` for `parsed_db`).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_api.py::test_cell_values_endpoint -v`
Expected: FAIL (404 — route missing).

- [ ] **Step 3: Add the request model + route**

In `backend/aurum_encuestas/api.py` add the model near the other request classes:

```python
class CellValuesRequest(BaseModel):
    state: dict
    question_id: str
    breakdown_id: str
```

And the endpoint:

```python
@app.post("/api/cell-values")
async def cell_values_endpoint(req: CellValuesRequest):
    """Crosstab of {count, pct} for a (question, breakdown), overrides applied,
    so the field editor can display + override current values."""
    from .data_extractor import extract_chart_data
    try:
        state = ProjectState.model_validate(req.state)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e), "options": [], "categories": [], "cells": {}}
    if not state.parsed_db or not state.inputs:
        return {"error": "Sin datos", "options": [], "categories": [], "cells": {}}
    q = next((qq for qq in state.parsed_db.questions if qq.id == req.question_id), None)
    if q is None:
        return {"error": "pregunta no encontrada", "options": [], "categories": [], "cells": {}}
    try:
        data = extract_chart_data(
            state.inputs.db_path, q, req.breakdown_id, state.parsed_db.data_blocks or {},
            total_row=state.parsed_db.total_row, overrides=state.parsed_db.value_overrides,
        )
    except Exception as e:  # noqa: BLE001
        return {"error": str(e), "options": [], "categories": [], "cells": {}}
    categories = list(data.keys())
    options = list(q.options)
    cells = {opt: {cat: data[cat].get(opt, {"count": 0, "pct": None}) for cat in categories} for opt in options}
    return {"options": options, "categories": categories, "cells": cells}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_api.py::test_cell_values_endpoint -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/api.py backend/tests/test_api.py
git commit -m "feat(api): /api/cell-values returns crosstab with overrides applied"
```

---

### Task 3: Frontend `value_overrides` type + `setValueOverride`

**Files:**
- Modify: `frontend/src/types/index.ts` (`ParsedDB`)
- Modify: `frontend/src/pages/Wizard/mappingDraft.ts`
- Modify: `frontend/src/pages/Wizard/mappingDraft.test.ts`

**Interfaces:**
- Produces: `setValueOverride(db, key, patch) -> ParsedDB` (pure, merge + clear-empty).

- [ ] **Step 1: Add the type field**

In `frontend/src/types/index.ts`, `interface ParsedDB` — add after `total_row`:

```ts
  value_overrides?: Record<string, { count?: number | null; pct?: number | null }>
```

- [ ] **Step 2: Write the failing test**

Append to `frontend/src/pages/Wizard/mappingDraft.test.ts`:

```ts
it("setValueOverride sets, merges, and clears purely", () => {
  const k = "q1|sexo|Hombre|Sí"
  let db = D.setValueOverride(base, k, { count: 5 })
  expect(db.value_overrides![k]).toEqual({ count: 5 })
  expect(base.value_overrides).toBeUndefined()              // pure
  db = D.setValueOverride(db, k, { pct: 0.5 })              // merge
  expect(db.value_overrides![k]).toEqual({ count: 5, pct: 0.5 })
  db = D.setValueOverride(db, k, { count: null })           // clear one field
  expect(db.value_overrides![k]).toEqual({ pct: 0.5 })
  db = D.setValueOverride(db, k, { pct: null })             // clear last → key removed
  expect(db.value_overrides![k]).toBeUndefined()
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/Wizard/mappingDraft.test.ts`
Expected: FAIL (`D.setValueOverride` is not a function).

- [ ] **Step 4: Implement the helper**

Append to `frontend/src/pages/Wizard/mappingDraft.ts`:

```ts
export function setValueOverride(
  db: ParsedDB,
  key: string,
  patch: { count?: number | null; pct?: number | null },
): ParsedDB {
  const all = { ...(db.value_overrides ?? {}) }
  const merged: Record<string, number> = { ...(all[key] ?? {}) }
  for (const f of ["count", "pct"] as const) {
    if (f in patch) {
      const v = patch[f]
      if (v == null) delete merged[f]
      else merged[f] = v
    }
  }
  if (Object.keys(merged).length === 0) delete all[key]
  else all[key] = merged
  return { ...db, value_overrides: all }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/Wizard/mappingDraft.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/pages/Wizard/mappingDraft.ts frontend/src/pages/Wizard/mappingDraft.test.ts
git commit -m "feat(wizard): value_overrides type + setValueOverride helper"
```

---

### Task 4: `fetchCellValues` client + crosstab editor

**Files:**
- Modify: `frontend/src/api/client.ts` (`fetchCellValues`)
- Create: `frontend/src/pages/Wizard/CellValuesEditor.tsx`
- Modify: `frontend/src/pages/Wizard/XlsxVerifyWizard.tsx` (render the editor under `mode === "fields"`)

**Interfaces:**
- Consumes: `setValueOverride` (Task 3), `fetchCellValues`, `ParsedDB`.

UI wiring; verify with `tsc --noEmit` + manual browser check (no pointer-test harness).

- [ ] **Step 1: Add the API client function**

In `frontend/src/api/client.ts`:

```ts
export interface CellValuesResponse {
  options: string[]
  categories: string[]
  cells: Record<string, Record<string, { count: number; pct: number | null }>>
  error?: string
}

export async function fetchCellValues(state: any, question_id: string, breakdown_id: string): Promise<CellValuesResponse> {
  return request("/cell-values", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state, question_id, breakdown_id }),
  })
}
```

- [ ] **Step 2: Create the `CellValuesEditor` component**

Create `frontend/src/pages/Wizard/CellValuesEditor.tsx`:

```tsx
import { useEffect, useState } from "react"
import type { ParsedDB } from "../../types"
import { fetchCellValues, type CellValuesResponse } from "../../api/client"
import { setValueOverride } from "./mappingDraft"

interface Props {
  state: any                 // saved ProjectState (for fetch)
  draft: ParsedDB            // current draft (holds overrides)
  onChange(db: ParsedDB): void
}

const keyFor = (q: string, b: string, cat: string, opt: string) => `${q}|${b}|${cat}|${opt}`

export default function CellValuesEditor({ state, draft, onChange }: Props) {
  const [qid, setQid] = useState(draft.questions[0]?.id ?? "")
  const [bid, setBid] = useState(draft.breakdowns[0]?.id ?? "general")
  const [data, setData] = useState<CellValuesResponse | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (!qid || !bid) return
    let active = true
    fetchCellValues(state, qid, bid).then((r) => {
      if (!active) return
      if (r.error) { setErr(r.error); setData(null) } else { setErr(null); setData(r) }
    })
    return () => { active = false }
  }, [state, qid, bid])

  const ov = draft.value_overrides ?? {}
  const cellCount = (cat: string, opt: string) => {
    const o = ov[keyFor(qid, bid, cat, opt)]
    return o?.count != null ? o.count : (data?.cells[opt]?.[cat]?.count ?? 0)
  }
  const cellPct = (cat: string, opt: string) => {
    const o = ov[keyFor(qid, bid, cat, opt)]
    const p = o?.pct != null ? o.pct : data?.cells[opt]?.[cat]?.pct
    return p == null ? "" : (p * 100).toFixed(1)
  }
  const set = (cat: string, opt: string, patch: { count?: number | null; pct?: number | null }) =>
    onChange(setValueOverride(draft, keyFor(qid, bid, cat, opt), patch))

  return (
    <div className="mt-4">
      <div className="text-sm font-semibold text-neutral-300 mb-2">Valores (conteo / %)</div>
      <div className="flex gap-2 mb-2">
        <select value={qid} onChange={(e) => setQid(e.target.value)} className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-sm">
          {draft.questions.map((q) => <option key={q.id} value={q.id}>{q.code}: {q.text.slice(0, 40)}</option>)}
        </select>
        <select value={bid} onChange={(e) => setBid(e.target.value)} className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-sm">
          {draft.breakdowns.map((b) => <option key={b.id} value={b.id}>{b.label}</option>)}
        </select>
      </div>
      {err && <p className="text-xs text-red-400">{err}</p>}
      {data && (
        <div className="overflow-auto">
          <table className="text-xs border-collapse">
            <thead>
              <tr><th className="border border-neutral-700 px-2 py-1 bg-neutral-800" />
                {data.categories.map((c) => <th key={c} className="border border-neutral-700 px-2 py-1 bg-neutral-800 text-neutral-300">{c}</th>)}
              </tr>
            </thead>
            <tbody>
              {data.options.map((opt) => (
                <tr key={opt}>
                  <th className="border border-neutral-700 px-2 py-1 bg-neutral-800 text-neutral-300 text-left">{opt}</th>
                  {data.categories.map((cat) => (
                    <td key={cat} className="border border-neutral-700 px-1 py-1">
                      <div className="flex flex-col gap-0.5">
                        <input type="number" title="conteo" value={cellCount(cat, opt)}
                          onChange={(e) => set(cat, opt, { count: e.target.value === "" ? null : parseInt(e.target.value, 10) })}
                          className="w-16 bg-neutral-900 border border-neutral-700 rounded px-1 text-[11px]" />
                        <input type="number" step="0.1" title="%" value={cellPct(cat, opt)}
                          onChange={(e) => set(cat, opt, { pct: e.target.value === "" ? null : parseFloat(e.target.value) / 100 })}
                          className="w-16 bg-neutral-900 border border-neutral-700 rounded px-1 text-[11px]" />
                      </div>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Render the editor in the wizard**

In `frontend/src/pages/Wizard/XlsxVerifyWizard.tsx`, under the `mode === "fields"` block (after the existing field editor sections, before the footer), add:

```tsx
{mode === "fields" && draft && (
  <CellValuesEditor
    state={useProjectStore.getState().state}
    draft={draft}
    onChange={(db) => setDraft(db)}
  />
)}
```

Add `import CellValuesEditor from "./CellValuesEditor"` at the top. (`draft`/`setDraft`/`useProjectStore` already exist in the component.)

- [ ] **Step 4: Verify it type-checks**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit 0.

- [ ] **Step 5: Manual verification**

Run: `cd frontend && npm run dev` (backend already running).
1. Upload `BD Aurora ejemplo.xlsx`, reach the wizard, click **Editar campos**.
2. The "Valores" section shows question + breakdown selectors and a table (rows=options, cols=categories) with conteo + % per cell, pre-filled from the sheet (e.g. P1 "Sí" General count 458, % 91.6).
3. Change a count and a % in a cell; **Guardar**; generate a preview → the chart/table reflects the overridden value.
4. Clear an input (empty) → reverts to the computed value on next render.

Expected: all behave; no console errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/pages/Wizard/CellValuesEditor.tsx frontend/src/pages/Wizard/XlsxVerifyWizard.tsx
git commit -m "feat(wizard): crosstab value editor (count/pct overrides) in field editor"
```

---

## Self-Review

**Spec coverage:**
- §1 model `value_overrides` (backend + frontend type) → Task 1 (backend), Task 3 (frontend type). ✓
- §2 extraction applies overrides + callers + `_override_key` → Task 1. ✓
- §3 `/api/cell-values` endpoint → Task 2. ✓
- §4 crosstab editor (selectors, table, percent display, draft override overlay) → Task 4. ✓
- §5 `setValueOverride` (merge/clear) + persistence via existing Guardar + edges → Task 3 (helper) + Task 4 (UI overlay/clear). ✓
- Testing (override count/pct independent; endpoint crosstab; setValueOverride pure) → Tasks 1-3 automated, Task 4 manual. ✓

**Type consistency:** override key format `${q}|${b}|${cat}|${opt}` identical in backend (`_override_key`) and frontend (`keyFor`); `value_overrides` shape `{count?, pct?}` matches backend dict; `setValueOverride(db, key, patch)` defined Task 3, used Task 4; `fetchCellValues(state, qid, bid)` + `CellValuesResponse` defined Task 4 client, used by the component in the same task; pct fraction↔percent conversion (`*100` display, `/100` store) consistent.

**Placeholder scan:** no TBD/TODO; Task 2's `_minimal_state` helper is described with the exact construction approach (`db.model_dump()` for parsed_db, fields per the ProjectState model) and concrete assertions — the implementer reads the model to fill exact field names, which is judgment, not a placeholder.
