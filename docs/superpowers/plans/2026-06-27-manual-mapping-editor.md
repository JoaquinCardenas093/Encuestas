# Manual Mapping Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user correct the heuristic-detected XLSX mapping (questions, breakdowns, data blocks, sample size) in the verify wizard, and generalize the parser/extractor so any breakdown header works without code changes.

**Architecture:** Backend stops hardcoding the four known breakdowns: the parser auto-detects every row-1 header, and the extractor resolves a breakdown's columns by matching its slug/label to a header (canonical-id alias preserved). The wizard gains an edit mode whose edits mutate a draft `ParsedDB`; on save it calls the existing `setParsedDb`, and preview/export re-extract from the edited `parsed_db`. No new backend endpoint.

**Tech Stack:** Python (openpyxl, pytest), React + TypeScript (Zustand, vitest, testing-library).

## Global Constraints

- Backend tests run: `cd backend && arch -arm64 .venv/bin/python -m pytest <path> -v`
- Frontend tests run: `cd frontend && npx vitest run <path>`
- `_slug(text)` = `text.strip().lower()` — single definition in `xlsx_parser.py`, imported elsewhere; never re-implemented.
- `BREAKDOWN_ID_MAP = {"rango de edad":"edad","sexo":"sexo","nse":"nse","punto":"punto"}` stays as an **alias** map only; it must NOT filter which breakdowns are detected.
- The `general` breakdown (`id="general"`, `label="General"`, `categories=["Total"]`) is always present and never editable/deletable.
- All frontend draft helpers are **pure** (return a new `ParsedDB`, never mutate input).

---

### Task 1: Generalize breakdown detection (parser)

**Files:**
- Modify: `backend/aurum_encuestas/xlsx_parser.py` (`_detect_breakdowns`, ~lines 45-87)
- Test: `backend/tests/test_xlsx_parser.py`

**Interfaces:**
- Consumes: `_slug(text)`, `BREAKDOWN_ID_MAP` (existing module globals).
- Produces: `_detect_breakdowns(ws) -> list[Breakdown]` now returns one `Breakdown`
  per distinct row-1 header in block 1 (plus `general`). `id = BREAKDOWN_ID_MAP.get(_slug(label), _slug(label))`, `label = header text`, `categories = row2 sub-headers`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_xlsx_parser.py`:

```python
from openpyxl import Workbook
from aurum_encuestas.xlsx_parser import parse_xlsx, _detect_breakdowns


def _ws_with_custom_breakdown(tmp_path):
    wb = Workbook()
    ws = wb.active
    # Row 1 headers: a known one (Sexo) + an unknown one (Religión)
    ws.cell(1, 4, "Sexo")
    ws.cell(1, 6, "Religión")
    # Row 2 sub-categories; General anchors block 1 at col 3
    ws.cell(2, 3, "General")
    ws.cell(2, 4, "Hombre")
    ws.cell(2, 5, "Mujer")
    ws.cell(2, 6, "Católico")
    ws.cell(2, 7, "Evangélico")
    out = tmp_path / "custom_bd.xlsx"
    wb.save(out)
    from openpyxl import load_workbook
    return load_workbook(out, data_only=True).worksheets[0]


def test_detect_breakdowns_includes_unknown_header(tmp_path):
    ws = _ws_with_custom_breakdown(tmp_path)
    bds = _detect_breakdowns(ws)
    by_label = {b.label: b for b in bds}
    # Unknown header is no longer dropped
    assert "Religión" in by_label
    assert by_label["Religión"].id == "religión"
    assert by_label["Religión"].categories == ["Católico", "Evangélico"]
    # Known header keeps its canonical id via the alias map
    assert by_label["Sexo"].id == "sexo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_xlsx_parser.py::test_detect_breakdowns_includes_unknown_header -v`
Expected: FAIL (`"Religión" not in by_label` — currently dropped by the `BREAKDOWN_ID_MAP` filter).

- [ ] **Step 3: Implement the generalization**

In `xlsx_parser.py::_detect_breakdowns`, replace the group-collection loop (the block currently doing `slug_key = _slug(label); if slug_key in BREAKDOWN_ID_MAP: ...`) with:

```python
    for col in sorted(row1.keys()):
        if general_col and (col <= general_col or col > block1_max):
            continue
        label = str(row1[col]).strip()
        if not label or label in seen_labels:
            continue
        seen_labels.add(label)
        slug_key = _slug(label)
        gid = BREAKDOWN_ID_MAP.get(slug_key, slug_key)  # alias known ids, else slug
        group_starts.append((col, label, gid))
```

(The rest of the function — building categories from row2 between group starts and appending `Breakdown(id=gid, label=label, categories=...)` — is unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_xlsx_parser.py -v`
Expected: PASS (new test + all existing parser tests).

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/xlsx_parser.py backend/tests/test_xlsx_parser.py
git commit -m "feat(parser): auto-detect all breakdown headers (drop hardcoded filter)"
```

---

### Task 2: Generalize breakdown→column resolution (extractor)

**Files:**
- Modify: `backend/aurum_encuestas/data_extractor.py` (`_resolve_breakdown_cols`, ~lines 125-164)
- Test: `backend/tests/test_data_extractor.py`

**Interfaces:**
- Consumes: `_slug`, `BREAKDOWN_ID_MAP` imported from `xlsx_parser`.
- Produces: `_resolve_breakdown_cols(ws, breakdown_id, block_start_col) -> dict[str, int]`
  resolves ANY breakdown by matching `breakdown_id` to a row-1 header via slug or alias.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_data_extractor.py`:

```python
from openpyxl import Workbook, load_workbook
from aurum_encuestas.data_extractor import _resolve_breakdown_cols


def _ws_custom(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.cell(1, 6, "Religión")        # unknown header at col 6
    ws.cell(2, 3, "General")
    ws.cell(2, 6, "Católico")
    ws.cell(2, 7, "Evangélico")
    out = tmp_path / "res.xlsx"
    wb.save(out)
    return load_workbook(out, data_only=True).worksheets[0]


def test_resolve_breakdown_cols_generic(tmp_path):
    ws = _ws_custom(tmp_path)
    cols = _resolve_breakdown_cols(ws, "religión", block_start_col=3)
    assert cols == {"Católico": 6, "Evangélico": 7}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_data_extractor.py::test_resolve_breakdown_cols_generic -v`
Expected: FAIL (returns `{}` — `"religión"` not in `target_label_map`).

- [ ] **Step 3: Implement generic resolution**

At the top of `data_extractor.py`, import the shared helpers:

```python
from .xlsx_parser import _slug, BREAKDOWN_ID_MAP
```

Replace `_resolve_breakdown_cols` body (keep the `general` short-circuit) with:

```python
def _resolve_breakdown_cols(ws, breakdown_id: str, block_start_col: int) -> dict[str, int]:
    """Map category label → column for the given breakdown within the column block.

    Generic: find the row-1 header at/after block_start_col whose slug equals
    breakdown_id, or whose alias (BREAKDOWN_ID_MAP) equals breakdown_id.
    """
    row2 = {c.column: (c.value or "") for c in ws[2]}

    if breakdown_id == "general":
        return {"Total": block_start_col}

    row1 = {c.column: (c.value or "") for c in ws[1]}
    sorted_cols = sorted(c for c in row1.keys() if c >= block_start_col)
    group_starts = [(c, str(row1[c]).strip()) for c in sorted_cols if str(row1[c]).strip()]

    found = None
    for i, (c, label) in enumerate(group_starts):
        slug = _slug(label)
        if slug == breakdown_id or BREAKDOWN_ID_MAP.get(slug) == breakdown_id:
            end_col = group_starts[i + 1][0] if i + 1 < len(group_starts) else c + 7
            found = (c, end_col)
            break

    if not found:
        return {}

    start, end = found
    out: dict[str, int] = {}
    for c in range(start, end):
        cat = str(row2.get(c) or "").strip()
        if cat:
            out[cat] = c
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_data_extractor.py -v`
Expected: PASS (new test + existing `test_extract_chart_data_general` / `_sexo`).

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/data_extractor.py backend/tests/test_data_extractor.py
git commit -m "feat(extractor): resolve breakdown columns generically (no hardcoded labels)"
```

---

### Task 3: Honor declared categories in chart extraction

**Files:**
- Modify: `backend/aurum_encuestas/data_extractor.py` (`extract_chart_data`, ~lines 6-36)
- Modify: `backend/aurum_encuestas/pattern_classifier.py` (call ~line 490)
- Modify: `backend/aurum_encuestas/pptx_generator.py` (call ~line 416)
- Test: `backend/tests/test_data_extractor.py`

**Interfaces:**
- Produces: `extract_chart_data(xlsx_path, question, breakdown_id, data_blocks, allowed_categories=None) -> dict`.
  When `allowed_categories` is a list, the returned top-level keys are filtered to
  that list (by exact text) and ordered to match it. `None` → unchanged behavior.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_data_extractor.py`:

```python
from aurum_encuestas.data_extractor import extract_chart_data
from aurum_encuestas.xlsx_parser import parse_xlsx


def test_extract_chart_data_allowed_categories(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    q1 = db.questions[0]
    data = extract_chart_data(
        str(valid_xlsx_path), q1, "sexo", db.data_blocks,
        allowed_categories=["Mujer"],
    )
    assert list(data.keys()) == ["Mujer"]  # Hombre filtered out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_data_extractor.py::test_extract_chart_data_allowed_categories -v`
Expected: FAIL (`TypeError: unexpected keyword argument 'allowed_categories'`).

- [ ] **Step 3: Add the parameter + filter**

Change the `extract_chart_data` signature to:

```python
def extract_chart_data(xlsx_path: str, question: Question, breakdown_id: str,
                       data_blocks: dict, allowed_categories: list[str] | None = None) -> dict:
```

After `breakdown_cols = _resolve_breakdown_cols(ws, breakdown_id, counts_start)` and before the result loop, add:

```python
    if allowed_categories is not None:
        allowed = list(allowed_categories)
        breakdown_cols = {c: breakdown_cols[c] for c in allowed if c in breakdown_cols}
```

(The result loop already iterates `breakdown_cols.items()`, so filtering+ordering the
dict is sufficient — Python dicts preserve insertion order.)

- [ ] **Step 4: Pass declared categories from callers**

In `pattern_classifier.py` (the `extract_chart_data(db_path, question, primary_bd, data_blocks)` call near line 490), resolve the breakdown object and pass its categories:

```python
                bd_obj_primary = next(
                    (b for b in (getattr(parsed_db, "breakdowns", []) or []) if b.id == primary_bd),
                    None,
                )
                chart_data = extract_chart_data(
                    db_path, question, primary_bd, data_blocks,
                    allowed_categories=(bd_obj_primary.categories if bd_obj_primary else None),
                )
```

In `pptx_generator.py` (the `extract_chart_data(...)` call near line 416), do the same — find the `Breakdown` for the chart's primary breakdown in `state.parsed_db.breakdowns` and pass `allowed_categories=its categories` (or `None` for `general`). Read the surrounding lines first to match the local variable names; pass `None` when the breakdown id is `general` or not found.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_data_extractor.py tests/test_pattern_classifier.py -v`
Expected: PASS (new test + existing suites — category order/filtering must not break canonical breakdowns).

- [ ] **Step 6: Commit**

```bash
git add backend/aurum_encuestas/data_extractor.py backend/aurum_encuestas/pattern_classifier.py backend/aurum_encuestas/pptx_generator.py backend/tests/test_data_extractor.py
git commit -m "feat(extractor): chart extraction honors declared breakdown categories"
```

---

### Task 4: Draft-mutation helpers (frontend pure logic)

**Files:**
- Create: `frontend/src/pages/Wizard/mappingDraft.ts`
- Test: `frontend/src/pages/Wizard/mappingDraft.test.ts`

**Interfaces:**
- Consumes: `ParsedDB`, `Question`, `Breakdown` from `../../types`.
- Produces (all pure, return a new `ParsedDB`):
  `setQuestionText(db, qid, text)`, `addQuestionOption(db, qid)`,
  `setQuestionOption(db, qid, idx, value)`, `removeQuestionOption(db, qid, idx)`,
  `deleteQuestion(db, qid)`, `setBreakdownLabel(db, bid, label)`,
  `addBreakdownCategory(db, bid)`, `setBreakdownCategory(db, bid, idx, value)`,
  `removeBreakdownCategory(db, bid, idx)`, `deleteBreakdown(db, bid)`,
  `setSampleSize(db, n)`, `setDataBlock(db, key, cols)`, `parseColList(s) -> number[]`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/pages/Wizard/mappingDraft.test.ts`:

```ts
import { describe, it, expect } from "vitest"
import * as D from "./mappingDraft"
import type { ParsedDB } from "../../types"

const base: ParsedDB = {
  questions: [
    { id: "q1", code: "P1", text: "T1", options: ["Sí", "No"], confidence: 1 },
  ],
  breakdowns: [
    { id: "general", label: "General", categories: ["Total"] },
    { id: "sexo", label: "Sexo", categories: ["Hombre", "Mujer"] },
  ],
  sample_size: 500,
  data_blocks: { counts_cols: [3], pct_row_cols: [21], pct_col_cols: [40] },
}

it("setQuestionText is immutable", () => {
  const out = D.setQuestionText(base, "q1", "New")
  expect(out.questions[0].text).toBe("New")
  expect(base.questions[0].text).toBe("T1")
})

it("add/set/remove option", () => {
  let db = D.addQuestionOption(base, "q1")
  expect(db.questions[0].options).toHaveLength(3)
  db = D.setQuestionOption(db, "q1", 2, "Tal vez")
  expect(db.questions[0].options[2]).toBe("Tal vez")
  db = D.removeQuestionOption(db, "q1", 0)
  expect(db.questions[0].options).toEqual(["No", "Tal vez"])
})

it("deleteQuestion / deleteBreakdown", () => {
  expect(D.deleteQuestion(base, "q1").questions).toHaveLength(0)
  expect(D.deleteBreakdown(base, "sexo").breakdowns.map((b) => b.id)).toEqual(["general"])
})

it("breakdown label + categories", () => {
  let db = D.setBreakdownLabel(base, "sexo", "Género")
  expect(db.breakdowns[1].label).toBe("Género")
  db = D.addBreakdownCategory(db, "sexo")
  expect(db.breakdowns[1].categories).toHaveLength(3)
  db = D.removeBreakdownCategory(db, "sexo", 0)
  expect(db.breakdowns[1].categories[0]).toBe("Mujer")
})

it("sample size + data block + parseColList", () => {
  expect(D.setSampleSize(base, 600).sample_size).toBe(600)
  expect(D.parseColList("4, 5, x, 6")).toEqual([4, 5, 6])
  const db = D.setDataBlock(base, "counts_cols", [3, 4])
  expect(db.data_blocks.counts_cols).toEqual([3, 4])
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/pages/Wizard/mappingDraft.test.ts`
Expected: FAIL (module `./mappingDraft` not found).

- [ ] **Step 3: Implement the helpers**

Create `frontend/src/pages/Wizard/mappingDraft.ts`:

```ts
import type { ParsedDB, Question, Breakdown } from "../../types"

type DataBlockKey = "counts_cols" | "pct_row_cols" | "pct_col_cols"

function mapQ(db: ParsedDB, qid: string, fn: (q: Question) => Question): ParsedDB {
  return { ...db, questions: db.questions.map((q) => (q.id === qid ? fn(q) : q)) }
}
function mapB(db: ParsedDB, bid: string, fn: (b: Breakdown) => Breakdown): ParsedDB {
  return { ...db, breakdowns: db.breakdowns.map((b) => (b.id === bid ? fn(b) : b)) }
}

export const setQuestionText = (db: ParsedDB, qid: string, text: string) =>
  mapQ(db, qid, (q) => ({ ...q, text }))
export const addQuestionOption = (db: ParsedDB, qid: string) =>
  mapQ(db, qid, (q) => ({ ...q, options: [...q.options, ""] }))
export const setQuestionOption = (db: ParsedDB, qid: string, idx: number, value: string) =>
  mapQ(db, qid, (q) => ({ ...q, options: q.options.map((o, i) => (i === idx ? value : o)) }))
export const removeQuestionOption = (db: ParsedDB, qid: string, idx: number) =>
  mapQ(db, qid, (q) => ({ ...q, options: q.options.filter((_, i) => i !== idx) }))
export const deleteQuestion = (db: ParsedDB, qid: string) =>
  ({ ...db, questions: db.questions.filter((q) => q.id !== qid) })

export const setBreakdownLabel = (db: ParsedDB, bid: string, label: string) =>
  mapB(db, bid, (b) => ({ ...b, label }))
export const addBreakdownCategory = (db: ParsedDB, bid: string) =>
  mapB(db, bid, (b) => ({ ...b, categories: [...b.categories, ""] }))
export const setBreakdownCategory = (db: ParsedDB, bid: string, idx: number, value: string) =>
  mapB(db, bid, (b) => ({ ...b, categories: b.categories.map((c, i) => (i === idx ? value : c)) }))
export const removeBreakdownCategory = (db: ParsedDB, bid: string, idx: number) =>
  mapB(db, bid, (b) => ({ ...b, categories: b.categories.filter((_, i) => i !== idx) }))
export const deleteBreakdown = (db: ParsedDB, bid: string) =>
  ({ ...db, breakdowns: db.breakdowns.filter((b) => b.id !== bid) })

export const setSampleSize = (db: ParsedDB, n: number) => ({ ...db, sample_size: n })
export const setDataBlock = (db: ParsedDB, key: DataBlockKey, cols: number[]): ParsedDB =>
  ({ ...db, data_blocks: { ...db.data_blocks, [key]: cols } })

export function parseColList(s: string): number[] {
  return s
    .split(",")
    .map((p) => parseInt(p.trim(), 10))
    .filter((n) => Number.isFinite(n))
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/pages/Wizard/mappingDraft.test.ts`
Expected: PASS (all assertions).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Wizard/mappingDraft.ts frontend/src/pages/Wizard/mappingDraft.test.ts
git commit -m "feat(wizard): pure draft-mutation helpers for manual mapping"
```

---

### Task 5: Wire the edit mode into the wizard

**Files:**
- Modify: `frontend/src/pages/Wizard/XlsxVerifyWizard.tsx`

**Interfaces:**
- Consumes: all helpers from `./mappingDraft`; `useProjectStore().setParsedDb(db)`
  (existing — updates both `parsedDb` and `state.parsed_db`).
- Produces: no exports change; `XlsxVerifyWizard({ onConfirm })` unchanged.

This task is UI wiring with no automated test (no component-test harness for the
store-connected wizard). Verify manually with the dev server.

- [ ] **Step 1: Add edit state + draft**

In the component body add:

```tsx
const setParsedDb = useProjectStore((s) => s.setParsedDb)
const [editing, setEditing] = useState(false)
const [draft, setDraft] = useState<ParsedDB | null>(null)
const view = editing && draft ? draft : parsedDb
```

Add `import { useState } from "react"` is already present; add
`import type { ParsedDB } from "../../types"` and `import * as D from "./mappingDraft"`.

- [ ] **Step 2: Enter/exit edit mode + footer buttons**

Replace the disabled "Editar mapping manual (próximamente)" button and footer with:

```tsx
{editing ? (
  <>
    <button onClick={() => { setEditing(false); setDraft(null) }}
      className="px-4 py-2 text-sm rounded bg-neutral-700">Cancelar</button>
    <button onClick={() => { if (draft) setParsedDb(draft); setEditing(false); setDraft(null) }}
      className="px-4 py-2 text-sm rounded bg-accent text-neutral-900 font-semibold">Guardar</button>
  </>
) : (
  <>
    <button onClick={() => { setDraft(parsedDb); setEditing(true) }}
      className="px-4 py-2 text-sm rounded bg-neutral-700 text-neutral-200">Editar mapping manual</button>
    <button onClick={handleConfirm}
      className="px-4 py-2 text-sm rounded bg-accent text-neutral-900 font-semibold">Confirmar</button>
  </>
)}
```

Render all three list sections (questions/breakdowns/data blocks/sample size) from
`view` instead of `parsedDb`. A small inline note in edit mode:
`<p className="text-xs text-neutral-500 mb-3">Si el texto editado no coincide con la hoja, ese ítem queda sin datos.</p>`

- [ ] **Step 3: Make the sections editable in edit mode**

For each section, when `editing`, render inputs wired to the `D.*` helpers via
`setDraft(D.fn(draft!, ...))`. Example for a question option:

```tsx
<input value={opt}
  onChange={(e) => setDraft(D.setQuestionOption(draft!, q.id, i, e.target.value))}
  className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-sm" />
<button onClick={() => setDraft(D.removeQuestionOption(draft!, q.id, i))}>
  <Trash2 size={12} /></button>
```

Apply the same pattern for: question text (`D.setQuestionText`), add option
(`D.addQuestionOption`), delete question (`D.deleteQuestion`); breakdown label
(`D.setBreakdownLabel`), category add/set/remove (`D.addBreakdownCategory` /
`D.setBreakdownCategory` / `D.removeBreakdownCategory`), delete breakdown
(`D.deleteBreakdown`) — skip the delete/label controls for `b.id === "general"`;
data blocks (three inputs: `D.setDataBlock(draft!, "counts_cols", D.parseColList(value))`
etc., display `view.data_blocks.<key>.join(", ")`); sample size
(`D.setSampleSize(draft!, parseInt(value,10) || 0)`).
Import `Trash2` is already imported via lucide-react? (it imports `Check, AlertTriangle`
— add `Trash2` and a `Plus` to that import.)

- [ ] **Step 4: Manual verification**

Run: `cd frontend && npm run dev` (backend already running).
Steps:
1. Upload `BD Aurora ejemplo.xlsx`, reach the verify wizard.
2. Click **Editar mapping manual** → inputs appear; **Confirmar** is replaced by **Guardar/Cancelar**.
3. Rename a breakdown label, remove a category, edit an option, change sample size.
4. Click **Cancelar** → edits discarded (values revert).
5. Re-enter, make an edit, click **Guardar** → wizard returns to read-only showing the edited values.
6. Confirm and generate a preview → the edited mapping is reflected (e.g. removed category absent from charts/tables).

Expected: all six behave as described; no console errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Wizard/XlsxVerifyWizard.tsx
git commit -m "feat(wizard): manual mapping edit mode (questions/breakdowns/blocks/sample)"
```

---

## Self-Review

**Spec coverage:**
- Parser generalization → Task 1. ✓
- Resolver generalization (label/slug, alias) → Task 2. ✓
- Category consistency for charts (`allowed_categories`) → Task 3. ✓
- Editor UI (questions/breakdowns/data-blocks/sample, Guardar/Cancelar, draft) → Tasks 4-5. ✓
- Persistence via existing `setParsedDb` (updates both `parsedDb` + `state.parsed_db`) → Task 5 Step 2. ✓
- Edge cases (label/option not in sheet → empty; inline note; `general` not editable) → Task 3 filter + Task 5 Steps 2-3. ✓

**Type consistency:** helper names in Task 4 (`setQuestionText`, `addQuestionOption`,
`setQuestionOption`, `removeQuestionOption`, `deleteQuestion`, `setBreakdownLabel`,
`addBreakdownCategory`, `setBreakdownCategory`, `removeBreakdownCategory`,
`deleteBreakdown`, `setSampleSize`, `setDataBlock`, `parseColList`) match their uses in
Task 5. `extract_chart_data(..., allowed_categories=...)` signature in Task 3 matches both
caller updates.

**Placeholder scan:** no TBD/TODO; all code blocks concrete. Task 5 is explicitly a
UI-wiring task with manual verification (no component-test harness exists), which is
called out rather than left vague.
