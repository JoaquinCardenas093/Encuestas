# Delete Slide Button Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a UI to delete an entire slide (hover X on each thumbnail + a footer button for the selected slide), with native confirm and neighbour re-selection.

**Architecture:** The store already exposes a working, undoable `removeSlide(slideId)`. This plan only adds UI and selection handling. `EditorPage` owns `selectedId` (local `useState`) and gets a new `handleDeleteSlide` that calls `removeSlide` then repoints selection via a pure helper `nextSelectionAfterDelete`. `SlideRail` and `EditorFooter` receive callbacks; both confirm via `window.confirm`.

**Tech Stack:** React + TypeScript, Zustand (`useProjectStore`) with zundo temporal, lucide-react icons, Tailwind, Vitest + Testing Library (`frontend/tests`).

## Global Constraints

- Confirmation uses native `window.confirm` (matches existing "Reset todo"); no custom modal.
- Store (`removeSlide`) and backend are NOT modified.
- Deletion stays undoable via the existing footer Undo (temporal) — do not bypass the store.
- Spanish UI copy: confirm text `"¿Eliminar esta slide?"`, footer button label `"Eliminar slide"`.
- After deleting the selected slide, selection = previous neighbour; if the first was deleted, the first remaining; if none remain, `null`.
- Follow existing test patterns: reset store with `useProjectStore.setState({ state: null })` then `setNewProject(...)`; mock confirm with `vi.spyOn(window, "confirm").mockReturnValue(true|false)`.

---

### Task 1: `nextSelectionAfterDelete` selection helper

Pure function that computes the next `selectedId` after a delete. Extracted so the neighbour logic is unit-testable without rendering the full `EditorPage` (which pulls in react-router, autosave, shortcuts).

**Files:**
- Modify: `frontend/src/pages/Editor/EditorPage.tsx` (add + export helper near top, above the component)
- Test: `frontend/tests/nextSelectionAfterDelete.test.ts` (create)

**Interfaces:**
- Produces: `export function nextSelectionAfterDelete(slides: { id: string }[], deletedId: string, selectedId: string | null): string | null`
  - If `deletedId !== selectedId`: returns `selectedId` unchanged.
  - If `deletedId === selectedId`: let `idx = slides.findIndex(s => s.id === deletedId)`, `remaining = slides.filter(s => s.id !== deletedId)`, return `(remaining[idx - 1] ?? remaining[0] ?? null)?.id ?? null`.

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/nextSelectionAfterDelete.test.ts`:

```ts
import { describe, expect, it } from "vitest"
import { nextSelectionAfterDelete } from "../src/pages/Editor/EditorPage"

const slides = [{ id: "a" }, { id: "b" }, { id: "c" }]

describe("nextSelectionAfterDelete", () => {
  it("keeps selection when a different slide is deleted", () => {
    expect(nextSelectionAfterDelete(slides, "c", "a")).toBe("a")
  })

  it("selects previous neighbour when deleting the selected middle slide", () => {
    expect(nextSelectionAfterDelete(slides, "b", "b")).toBe("a")
  })

  it("selects first remaining when deleting the selected first slide", () => {
    expect(nextSelectionAfterDelete(slides, "a", "a")).toBe("b")
  })

  it("selects previous neighbour when deleting the selected last slide", () => {
    expect(nextSelectionAfterDelete(slides, "c", "c")).toBe("b")
  })

  it("returns null when deleting the only slide", () => {
    expect(nextSelectionAfterDelete([{ id: "a" }], "a", "a")).toBe(null)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/nextSelectionAfterDelete.test.ts`
Expected: FAIL — `nextSelectionAfterDelete` is not exported / not a function.

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/pages/Editor/EditorPage.tsx`, above `export default function EditorPage()`:

```tsx
export function nextSelectionAfterDelete(
  slides: { id: string }[],
  deletedId: string,
  selectedId: string | null,
): string | null {
  if (deletedId !== selectedId) return selectedId
  const idx = slides.findIndex((s) => s.id === deletedId)
  const remaining = slides.filter((s) => s.id !== deletedId)
  const next = remaining[idx - 1] ?? remaining[0] ?? null
  return next ? next.id : null
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/nextSelectionAfterDelete.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Editor/EditorPage.tsx frontend/tests/nextSelectionAfterDelete.test.ts
git commit -m "feat(delete-slide): pure nextSelectionAfterDelete selection helper"
```

---

### Task 2: EditorFooter "Eliminar slide" button

Add a footer button that deletes the currently selected slide. Props are optional so the existing `<EditorFooter />` usage/test keeps compiling.

**Files:**
- Modify: `frontend/src/pages/Editor/EditorFooter.tsx`
- Test: `frontend/tests/EditorFooter.test.tsx` (add cases; keep existing ones)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `EditorFooter` now accepts optional props
  `{ selectedId?: string | null; onDeleteSlide?: (id: string) => void }`.
  Button is disabled when `!selectedId`. On click, if `selectedId` and `window.confirm("¿Eliminar esta slide?")` → `onDeleteSlide?.(selectedId)`. `aria-label="eliminar slide"`.

- [ ] **Step 1: Write the failing test**

Add to `frontend/tests/EditorFooter.test.tsx` (inside the `describe`):

```tsx
it("Eliminar slide is disabled when nothing selected", () => {
  useProjectStore.setState({ state: null })
  useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
  render(<EditorFooter selectedId={null} onDeleteSlide={() => {}} />)
  expect(screen.getByRole("button", { name: /eliminar slide/i })).toBeDisabled()
})

it("Eliminar slide calls onDeleteSlide with selected id after confirm", async () => {
  useProjectStore.setState({ state: null })
  useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
  vi.spyOn(window, "confirm").mockReturnValue(true)
  const onDelete = vi.fn()
  render(<EditorFooter selectedId={"sl-1"} onDeleteSlide={onDelete} />)
  await userEvent.click(screen.getByRole("button", { name: /eliminar slide/i }))
  expect(onDelete).toHaveBeenCalledWith("sl-1")
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/EditorFooter.test.tsx`
Expected: FAIL — no button matching `/eliminar slide/i`.

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/pages/Editor/EditorFooter.tsx`:

Update the icon import:
```tsx
import { Undo2, Redo2, RotateCcw, Trash2 } from "lucide-react"
```

Add props to the component signature:
```tsx
interface Props {
  selectedId?: string | null
  onDeleteSlide?: (id: string) => void
}

export default function EditorFooter({ selectedId, onDeleteSlide }: Props = {}) {
```

Add the button immediately after the "Reset todo" button (before the trailing `<span>`):
```tsx
<button
  disabled={!selectedId}
  onClick={() => {
    if (selectedId && window.confirm("¿Eliminar esta slide?")) onDeleteSlide?.(selectedId)
  }}
  aria-label="eliminar slide"
  className="flex items-center gap-1 bg-red-900/40 hover:bg-red-900/60 border border-red-900 text-red-300 px-2 py-1 rounded disabled:opacity-40 disabled:cursor-not-allowed"
>
  <Trash2 size={12} /> Eliminar slide
</button>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/EditorFooter.test.tsx`
Expected: PASS (existing 2 + new 2). The existing `renders undo/redo/reset buttons` test still passes because props are optional.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Editor/EditorFooter.tsx frontend/tests/EditorFooter.test.tsx
git commit -m "feat(delete-slide): footer Eliminar slide button for selected slide"
```

---

### Task 3: SlideRail hover X on each thumbnail

Add a delete X to each thumbnail, visible on hover, that confirms and calls `onDelete(id)` without selecting the thumbnail or starting a drag.

**Files:**
- Modify: `frontend/src/pages/Editor/SlideRail.tsx`
- Test: `frontend/tests/SlideRail.test.tsx` (add cases; keep existing ones)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `SlideRail` accepts a new prop `onDelete: (id: string) => void` (add to its `Props`); each `SortableThumb` renders a button with `data-testid={`delete-slide-${slide.id}`}` and `aria-label="eliminar slide"`.

- [ ] **Step 1: Write the failing test**

Add to `frontend/tests/SlideRail.test.tsx` (inside the `describe`):

```tsx
it("clicking thumbnail X calls onDelete with slide id after confirm", async () => {
  useProjectStore.getState().addSeparator("S")
  const id = useProjectStore.getState().state!.slides[0].id
  vi.spyOn(window, "confirm").mockReturnValue(true)
  const onDelete = vi.fn()
  render(<SlideRail selectedId={id} onSelect={() => {}} onDelete={onDelete} />)
  await userEvent.click(screen.getByTestId(`delete-slide-${id}`))
  expect(onDelete).toHaveBeenCalledWith(id)
})

it("cancelling confirm does not call onDelete", async () => {
  useProjectStore.getState().addSeparator("S")
  const id = useProjectStore.getState().state!.slides[0].id
  vi.spyOn(window, "confirm").mockReturnValue(false)
  const onDelete = vi.fn()
  render(<SlideRail selectedId={id} onSelect={() => {}} onDelete={onDelete} />)
  await userEvent.click(screen.getByTestId(`delete-slide-${id}`))
  expect(onDelete).not.toHaveBeenCalled()
})
```

Also add `vi` to the import line at the top of the file:
```tsx
import { describe, expect, it, beforeEach, vi } from "vitest"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/SlideRail.test.tsx`
Expected: FAIL — no element with testid `delete-slide-<id>` (and TS error on unknown `onDelete` prop).

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/pages/Editor/SlideRail.tsx`:

Update the icon import:
```tsx
import { Plus, X } from "lucide-react"
```

Add `onDelete` to `Props` and thread it through:
```tsx
interface Props {
  selectedId: string | null
  onSelect(id: string): void
  onDelete(id: string): void
}
```
```tsx
export default function SlideRail({ selectedId, onSelect, onDelete }: Props) {
```

Pass it to each thumb in the `.map`:
```tsx
<SortableThumb
  key={slide.id}
  slide={slide}
  index={idx}
  selected={selectedId === slide.id}
  onClick={() => onSelect(slide.id)}
  onDelete={() => onDelete(slide.id)}
/>
```

Extend `SortableThumb` signature and add `group` + the X button. Change the props block and the root div:
```tsx
function SortableThumb({
  slide,
  index,
  selected,
  onClick,
  onDelete,
}: {
  slide: any
  index: number
  selected: boolean
  onClick(): void
  onDelete(): void
}) {
```

On the root `<div>`, add `group` to its className (append to the existing class string, e.g. `` `group relative aspect-[16/9] ...` ``), then add the button as the first child inside the div:
```tsx
<button
  data-testid={`delete-slide-${slide.id}`}
  aria-label="eliminar slide"
  onPointerDown={(e) => e.stopPropagation()}
  onClick={(e) => {
    e.stopPropagation()
    if (window.confirm("¿Eliminar esta slide?")) onDelete()
  }}
  className="absolute -top-2 -right-2 z-10 bg-neutral-800 hover:bg-red-700 text-neutral-300 hover:text-white rounded-full w-4 h-4 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
>
  <X size={10} />
</button>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/SlideRail.test.tsx`
Expected: PASS (existing 5 + new 2).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Editor/SlideRail.tsx frontend/tests/SlideRail.test.tsx
git commit -m "feat(delete-slide): hover X delete button on slide thumbnails"
```

---

### Task 4: Wire EditorPage — handler + pass callbacks

Connect the pieces: `EditorPage` builds `handleDeleteSlide`, passes it to `SlideRail` (`onDelete`) and `EditorFooter` (`onDeleteSlide` + `selectedId`).

**Files:**
- Modify: `frontend/src/pages/Editor/EditorPage.tsx`
- Test: `frontend/tests/EditorPage.delete.test.tsx` (create)

**Interfaces:**
- Consumes: `nextSelectionAfterDelete` (Task 1); `SlideRail` `onDelete` prop (Task 3); `EditorFooter` `selectedId`/`onDeleteSlide` props (Task 2); store `removeSlide` (existing).
- Produces: end-to-end delete flow. `handleDeleteSlide(id)` reads current `slides`, calls `removeSlide(id)`, then `setSelectedId(nextSelectionAfterDelete(slides, id, selectedId))`.

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/EditorPage.delete.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import EditorPage from "../src/pages/Editor/EditorPage"
import { useProjectStore } from "../src/store/project"

function setup() {
  useProjectStore.setState({ state: null })
  useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
  useProjectStore.getState().addSeparator("Sec")
  useProjectStore.getState().addShell()
}

describe("EditorPage delete slide", () => {
  it("deleting a thumbnail removes it from the store", async () => {
    setup()
    const firstId = useProjectStore.getState().state!.slides[0].id
    vi.spyOn(window, "confirm").mockReturnValue(true)
    render(
      <MemoryRouter>
        <EditorPage />
      </MemoryRouter>,
    )
    expect(useProjectStore.getState().state!.slides.length).toBe(2)
    await userEvent.click(screen.getByTestId(`delete-slide-${firstId}`))
    const ids = useProjectStore.getState().state!.slides.map((s) => s.id)
    expect(ids).not.toContain(firstId)
    expect(ids.length).toBe(1)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/EditorPage.delete.test.tsx`
Expected: FAIL — `EditorPage` does not pass `onDelete` to `SlideRail`, so `SlideRail`'s required `onDelete` prop is missing (TS error) and/or the store still contains the slide.

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/pages/Editor/EditorPage.tsx`:

Add the store selector alongside the existing ones (near `addShell`):
```tsx
const removeSlide = useProjectStore((s) => s.removeSlide)
```

Add the handler inside the component (after the `selectedId` state, before the render):
```tsx
function handleDeleteSlide(id: string) {
  const next = nextSelectionAfterDelete(slides, id, selectedId)
  removeSlide(id)
  setSelectedId(next)
}
```

Pass the callbacks in the JSX:
```tsx
<SlideRail selectedId={selectedId} onSelect={setSelectedId} onDelete={handleDeleteSlide} />
```
```tsx
<EditorFooter selectedId={selectedId} onDeleteSlide={handleDeleteSlide} />
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/EditorPage.delete.test.tsx`
Expected: PASS.

- [ ] **Step 5: Run the full frontend suite + typecheck**

Run: `cd frontend && npx vitest run && npx tsc --noEmit`
Expected: all tests PASS, no type errors. (Confirms Task 2/3 optional-vs-required props line up with the new `EditorPage` usage.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Editor/EditorPage.tsx frontend/tests/EditorPage.delete.test.tsx
git commit -m "feat(delete-slide): wire EditorPage delete handler + selection repoint"
```

---

## Self-Review

**Spec coverage:**
- Hover X on thumbnail → Task 3. ✓
- Footer button on selected slide → Task 2. ✓
- `window.confirm` native → Tasks 2 & 3. ✓
- Selection = previous neighbour / first / null → Task 1 helper, wired in Task 4. ✓
- Store/backend untouched, undo preserved → no store edits; `removeSlide` reused. ✓
- Preview/ConfigPanel tolerate `selectedId=null` → existing behaviour (EditorPage:37 repopulates); no change needed. ✓
- Tests for all three surfaces → Tasks 1–4 each ship tests. ✓

**Placeholder scan:** No TBD/TODO; all steps contain concrete code and exact run commands. ✓

**Type consistency:**
- `nextSelectionAfterDelete(slides, deletedId, selectedId)` signature identical in Task 1 definition and Task 4 call. ✓
- `SlideRail` `onDelete: (id) => void` (required) defined Task 3, provided by Task 4. ✓
- `EditorFooter` `selectedId?`/`onDeleteSlide?` (optional) defined Task 2, provided Task 4; optional keeps existing propless test valid. ✓
- `handleDeleteSlide(id: string)` matches both `onDelete` and `onDeleteSlide` expected `(id: string) => void`. ✓
