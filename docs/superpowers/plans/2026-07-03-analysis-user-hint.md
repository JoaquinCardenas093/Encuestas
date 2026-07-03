# Analysis User-Hint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user optionally type a context/guidance hint that steers AI analysis generation; blank hint = current behavior. Ephemeral (not stored on the `Analysis` model).

**Architecture:** A `user_hint` string flows modal → client → `/generate-analysis` endpoint → `generate_analysis(scope, ctx, user_hint)`. When non-blank (trimmed, capped 500 chars), a "Guía del usuario (prioridad alta): …" line is appended to the LLM user message in both prompt branches (multi-chart slide + single-chart). No model/schema change.

**Tech Stack:** Python (FastAPI, pytest), React + TypeScript (vitest, Zustand).

## Global Constraints

- Backend tests: `cd backend && arch -arm64 .venv/bin/python -m pytest <path> -v` (arm64 venv prefix).
- Frontend: `cd frontend && npx vitest run <path>`; typecheck `cd frontend && npx tsc --noEmit`.
- If a command hits ENOSPC / `/private/tmp ... full`, prefix: `export TMPDIR="$HOME/.cache/cc-tmp" && mkdir -p "$TMPDIR" &&`.
- Hint normalization VERBATIM: `hint = (user_hint or "").strip()[:500]`. Blank hint ⇒ prompt byte-identical to today.
- The hint line is appended to the SAME `user_msg` in BOTH branches of `generate_analysis` (the `charts` multi-chart branch and the flat single-chart branch).
- Ephemeral: do NOT touch the `Analysis` pydantic model or the `addAnalysis` store persistence.
- There is an UNRELATED uncommitted change in `backend/aurum_encuestas/llm_client.py` env var (`REACT_APP_ANTHROPIC_API_KEY`) and other uncommitted files — do NOT revert or touch them. `git add` only the files each task lists.
- Work on the branch the controller creates; do NOT switch branches inside a task.

---

### Task 1: Backend — `user_hint` in `generate_analysis` + endpoint

**Files:**
- Modify: `backend/aurum_encuestas/llm_client.py` (`generate_analysis`)
- Modify: `backend/aurum_encuestas/api.py` (`GenerateAnalysisRequest` + endpoint call)
- Test: `backend/tests/test_llm_client.py`

**Interfaces:**
- Produces: `generate_analysis(scope: str, context: dict, user_hint: str | None = None) -> str`; `GenerateAnalysisRequest.user_hint: str | None`.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_llm_client.py` (follow the existing `@patch("aurum_encuestas.llm_client._client")` style; the user message is `kwargs["messages"][0]["content"]`):

```python
def _fake_msg(text="ok"):
    m = MagicMock()
    m.content = [MagicMock(text=text)]
    m.usage = MagicMock(input_tokens=10, output_tokens=5, cache_read_input_tokens=0)
    return m


_BASE_CTX = {"section_title": "S", "question_text": "Q", "options": ["Sí", "No"],
             "breakdown_label": "General",
             "data": {"Total": {"Sí": {"count": 50, "pct": 0.5}, "No": {"count": 50, "pct": 0.5}}}}


@patch("aurum_encuestas.llm_client._client")
def test_generate_analysis_includes_user_hint(mock_client):
    mock_client.messages.create.return_value = _fake_msg()
    generate_analysis(scope="chart", context=dict(_BASE_CTX), user_hint="enfocate en jóvenes")
    _, kwargs = mock_client.messages.create.call_args
    user_msg = kwargs["messages"][0]["content"]
    assert "Guía del usuario" in user_msg
    assert "enfocate en jóvenes" in user_msg


@patch("aurum_encuestas.llm_client._client")
def test_generate_analysis_blank_hint_unchanged(mock_client):
    mock_client.messages.create.return_value = _fake_msg()
    generate_analysis(scope="chart", context=dict(_BASE_CTX), user_hint="   ")
    _, k1 = mock_client.messages.create.call_args
    msg_hinted = k1["messages"][0]["content"]
    mock_client.messages.create.reset_mock()
    mock_client.messages.create.return_value = _fake_msg()
    generate_analysis(scope="chart", context=dict(_BASE_CTX))  # no hint arg
    _, k2 = mock_client.messages.create.call_args
    msg_plain = k2["messages"][0]["content"]
    assert "Guía del usuario" not in msg_hinted
    assert msg_hinted == msg_plain


@patch("aurum_encuestas.llm_client._client")
def test_generate_analysis_hint_capped_500(mock_client):
    mock_client.messages.create.return_value = _fake_msg()
    generate_analysis(scope="chart", context=dict(_BASE_CTX), user_hint="Z" * 900)
    _, kwargs = mock_client.messages.create.call_args
    user_msg = kwargs["messages"][0]["content"]
    assert "Z" * 500 in user_msg
    assert "Z" * 501 not in user_msg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_llm_client.py::test_generate_analysis_includes_user_hint tests/test_llm_client.py::test_generate_analysis_blank_hint_unchanged tests/test_llm_client.py::test_generate_analysis_hint_capped_500 -v`
Expected: FAIL (`unexpected keyword argument 'user_hint'`).

- [ ] **Step 3: Add `user_hint` to `generate_analysis`**

In `backend/aurum_encuestas/llm_client.py`, change the signature:

```python
def generate_analysis(scope: str, context: dict, user_hint: str | None = None) -> str:
```

Right AFTER the `if _client is None:` guard and BEFORE `charts_block = context.get("charts")`, normalize the hint:

```python
    hint = (user_hint or "").strip()[:500]
```

Both branches build `user_msg`. After the `if charts_block: ... else: ...` block that assigns `user_msg`, and BEFORE the `try:` that calls `_client.messages.create`, append the hint once (covers both branches):

```python
    if hint:
        user_msg += (
            f"\nGuía del usuario (prioridad alta): {hint}\n"
            f"Enfocá y encuadrá el análisis según esta guía, sin inventar datos "
            f"ni contradecir las cifras.\n"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_llm_client.py -v`
Expected: PASS (new 3 + existing analysis tests unchanged, since default `user_hint=None` → no prompt change).

- [ ] **Step 5: Thread `user_hint` through the endpoint**

In `backend/aurum_encuestas/api.py`, add to `class GenerateAnalysisRequest` (after `target_id`):

```python
    user_hint: str | None = None
```

In `generate_analysis_endpoint`, change the call:

```python
        text = generate_analysis(req.scope, ctx, req.user_hint)
```

- [ ] **Step 6: Run the api test file to confirm no regression**

Run: `cd backend && arch -arm64 .venv/bin/python -m pytest tests/test_api.py -q`
Expected: PASS (pre-existing skips allowed; no new failures).

- [ ] **Step 7: Commit**

```bash
git add backend/aurum_encuestas/llm_client.py backend/aurum_encuestas/api.py backend/tests/test_llm_client.py
git commit -m "feat(analysis): optional user_hint steers AI analysis prompt"
```

---

### Task 2: Frontend — hint field in the analysis modal

**Files:**
- Modify: `frontend/src/api/client.ts` (`generateAnalysis` opts)
- Modify: `frontend/src/pages/Editor/modals/AddAnalysisModal.tsx` (textarea + wiring)

**Interfaces:**
- Consumes: `generate_analysis` accepts `user_hint` (Task 1).
- Produces: `generateAnalysis(scope, context, opts?)` where `opts` includes `user_hint?: string`; request body carries `user_hint`.

UI wiring; verify with `tsc --noEmit` (no pointer-test harness required for this field).

- [ ] **Step 1: Add `user_hint` to the API client**

In `frontend/src/api/client.ts`, in `generateAnalysis`, extend the `opts` type and the body:

```ts
export async function generateAnalysis(
  scope: "slide" | "chart",
  context: GenerateAnalysisContext,
  opts?: { state?: any; slide_id?: string; target_id?: string | null; user_hint?: string },
): Promise<{ text: string; fallback: boolean }> {
  return request("/generate-analysis", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scope,
      context,
      state: opts?.state ?? null,
      slide_id: opts?.slide_id ?? null,
      target_id: opts?.target_id ?? null,
      user_hint: opts?.user_hint ?? null,
    }),
  })
}
```

- [ ] **Step 2: Add the textarea + state in the modal**

In `frontend/src/pages/Editor/modals/AddAnalysisModal.tsx`:

Add state near the other `useState`s (e.g. after `targetId`):

```tsx
  const [userHint, setUserHint] = useState("")
```

Add a textarea in the modal body (visible for both scopes — place it after the scope/chart selector block, before the Generar button). Follow the existing textarea styling in the file:

```tsx
      <label className="block text-xs text-neutral-400 mb-1">Contexto / guía (opcional)</label>
      <textarea
        value={userHint}
        onChange={(e) => setUserHint(e.target.value)}
        placeholder="Ej: enfocate en las diferencias por edad; tono ejecutivo"
        rows={2}
        className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm resize-none"
      />
```

- [ ] **Step 3: Pass `user_hint` when generating**

In `handleGenerate`, add `user_hint: userHint` to the `api.generateAnalysis` opts:

```tsx
      const r = await api.generateAnalysis(scope, ctx, {
        state,
        slide_id: slide.id,
        target_id: scope === "slide" ? null : targetId,
        user_hint: userHint,
      })
```

- [ ] **Step 4: Reset the hint on accept/close**

In `handleAccept` (where `setText("")`, `setScope("slide")`, `setTargetId("")` run), add:

```tsx
    setUserHint("")
```

- [ ] **Step 5: Verify it type-checks**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit 0.

- [ ] **Step 6: Manual verification**

Run: `cd frontend && npm run dev` (backend already running + restarted so `_client` is live).
1. Open a slide with charts, add an analysis (scope slide), leave the hint blank → generates as today (all charts).
2. Add another, type a hint (e.g. "enfocate en jóvenes") → the generated text reflects the guidance.
3. Switch scope to chart → the hint field is still available and applies.

Expected: hint steers the output; blank behaves as before; no console errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/pages/Editor/modals/AddAnalysisModal.tsx
git commit -m "feat(analysis): optional context/guidance field in analysis modal"
```

---

## Self-Review

**Spec coverage:**
- §1 `generate_analysis(user_hint)` + prompt injection (both branches, strip, cap 500) → Task 1 Step 3. ✓
- §2 `GenerateAnalysisRequest.user_hint` + endpoint passes it → Task 1 Step 5. ✓
- §3 client `generateAnalysis` opts `user_hint` → Task 2 Step 1. ✓
- §4 modal textarea (both scopes) + wiring + reset → Task 2 Steps 2-4. ✓
- Ephemeral (no `Analysis` model change) → respected; no task touches the model/store. ✓
- Edge: blank hint unchanged (test), cap 500 (test), no-AI unchanged (default None) → Task 1 tests. ✓

**Placeholder scan:** none — all steps carry concrete code/commands.

**Type consistency:** `generate_analysis(scope, context, user_hint=None)` defined Task 1 Step 3, called by endpoint Task 1 Step 5 with `req.user_hint`. Frontend `generateAnalysis` opts `user_hint?: string` (Task 2 Step 1) sent as body `user_hint` → consumed by `GenerateAnalysisRequest.user_hint` (Task 1 Step 5). Consistent end-to-end.
