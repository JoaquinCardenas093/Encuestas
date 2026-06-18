# M6.11 — Welcome + AddChartModal + ConfigPanel Updates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update `WelcomePage` (remove any training set selector, add corpus-empty banner). Update `AddChartModal` (chart type dropdown sourced dynamically from `styleGuide.available_chart_types`). Update `ConfigPanel` (pattern matched indicator per chart). Handle `.aurum.json` migration: strip `style_set` field on load, add `palette: null` default.

**Architecture:** WelcomePage reads `useStyleGuideStore` to detect `is_builtin` or empty corpus and conditionally renders a banner. AddChartModal now sources chart types from the style guide store (with built-in 5-type fallback). ConfigPanel shows a "Layout: pattern X ✓" or "fallback heurístico" indicator driven by the project state's `matched_pattern` field (set by backend via preview-slide response). Migration logic lives in `project_store.ts` load path.

**Spec refs:** Section 10 (WelcomePage, AddChartModal, ConfigPanel UI changes). Section 16 (Migration/cleanup, strip `style_set`, `Chart.colors = []` default). Section 20 (Acceptance criteria — pattern indicator visible, WelcomePage banner).

**Predecessor:** M6.10 (ColorPicker + types updated; M6.9 styleGuide store available).

---

## File Structure

**Modify (frontend):**
- `frontend/src/pages/Welcome.tsx` — remove training set selector; add corpus-empty/builtin banner
- `frontend/src/pages/Editor/modals/AddChartModal.tsx` — chart type dropdown from styleGuide + fallback
- `frontend/src/pages/Editor/ConfigPanel.tsx` — pattern matched indicator per slide
- `frontend/src/store/project.ts` — `loadProject` migration (strip `style_set`, add `palette: null`)
- `frontend/src/types/index.ts` — add optional `matched_pattern` field to `Slide`

**Create (frontend):**
- `frontend/tests/Welcome.test.tsx` — update/extend
- `frontend/tests/AddChartModal.m6.test.tsx` — new tests for dynamic chart types
- `frontend/tests/ConfigPanel.pattern.test.tsx` — new tests for pattern indicator

---

### Task 1: Update WelcomePage — remove set selector + add corpus-empty banner

**Files:**
- Modify: `frontend/src/pages/Welcome.tsx`
- Modify (or create): `frontend/tests/Welcome.test.tsx`

- [ ] **Step 1: Failing tests**

Create (or extend) `frontend/tests/Welcome.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import Welcome from "../src/pages/Welcome"

// Mock styleGuide store
const mockStyleGuide = {
  styleGuide: null as null | { is_builtin: boolean },
  corpus: [] as unknown[],
  isLoading: false,
  loadStyleGuide: vi.fn(),
  loadCorpus: vi.fn(),
}

vi.mock("../src/store/styleGuide", () => ({
  useStyleGuideStore: (sel: (s: typeof mockStyleGuide) => unknown) => sel(mockStyleGuide),
}))

// Mock project store (basic)
vi.mock("../src/store/project", () => ({
  useProjectStore: (sel: (s: unknown) => unknown) => sel({
    state: null,
    setNewProject: vi.fn(),
    loadProjectState: vi.fn(),
  }),
}))

beforeEach(() => {
  vi.clearAllMocks()
  mockStyleGuide.styleGuide = null
  mockStyleGuide.corpus = []
})

describe("WelcomePage", () => {
  it("renders without training set selector", () => {
    render(<Welcome />)
    // Should NOT have any "Seleccionar set" or "training set" selector
    expect(screen.queryByText(/training set/i)).toBeNull()
    expect(screen.queryByText(/Seleccionar set/i)).toBeNull()
  })

  it("shows empty-corpus banner when corpus is empty and no style guide", () => {
    mockStyleGuide.styleGuide = null
    mockStyleGuide.corpus = []
    render(<Welcome />)
    expect(screen.getByText(/Cargá training PPTs/i)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Configurar/i })).toBeInTheDocument()
  })

  it("shows builtin banner when style guide is_builtin = true", () => {
    mockStyleGuide.styleGuide = { is_builtin: true }
    mockStyleGuide.corpus = [{ filename: "a.pptx" }]
    render(<Welcome />)
    expect(screen.getByText(/Cargá training PPTs/i)).toBeInTheDocument()
  })

  it("does NOT show banner when style guide is AI-generated and corpus has PPTs", () => {
    mockStyleGuide.styleGuide = { is_builtin: false }
    mockStyleGuide.corpus = [{ filename: "a.pptx" }]
    render(<Welcome />)
    expect(screen.queryByText(/Cargá training PPTs/i)).toBeNull()
  })

  it("calls loadStyleGuide and loadCorpus on mount", () => {
    render(<Welcome />)
    expect(mockStyleGuide.loadStyleGuide).toHaveBeenCalled()
    expect(mockStyleGuide.loadCorpus).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run failing**

```bash
cd frontend && npm test -- Welcome.test
```

Expected: some tests fail (banner not implemented; set selector may exist).

- [ ] **Step 3: Modify WelcomePage**

Edit `frontend/src/pages/Welcome.tsx`:

Add imports:

```tsx
import { useEffect } from "react"
import { useStyleGuideStore } from "../store/styleGuide"
import { useNavigate } from "react-router-dom"
```

Inside the component, add:

```tsx
const navigate = useNavigate()
const { styleGuide, corpus, loadStyleGuide, loadCorpus } = useStyleGuideStore((s) => s)

useEffect(() => {
  loadStyleGuide()
  loadCorpus()
}, [])

const showCorpusBanner = !styleGuide || styleGuide.is_builtin || corpus.length === 0
```

Remove any `<select>` or form control that references "training set", "Seleccionar set de training", or similar. Search for strings like `style_set`, `training_set`, `setSelector`, `trainingSet` in the file and remove those sections.

Add banner JSX (add at the top of the page content, above the main wizard/upload form):

```tsx
{showCorpusBanner && (
  <div className="mb-4 flex items-center gap-2 bg-amber-900/20 border border-amber-700/40 rounded-lg px-4 py-3 text-sm">
    <span>⚡ Cargá training PPTs para que las generaciones reflejen tu estilo casa</span>
    <a
      href="#"
      role="link"
      aria-label="Configurar"
      onClick={(e) => { e.preventDefault(); navigate("/training") }}
      className="ml-auto text-amber-400 hover:text-amber-200 font-semibold whitespace-nowrap"
    >
      → Configurar
    </a>
  </div>
)}
```

- [ ] **Step 4: Run, verify pass**

```bash
cd frontend && npm test -- Welcome.test
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Welcome.tsx frontend/tests/Welcome.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): WelcomePage — remove set selector, add corpus-empty/builtin banner

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Update AddChartModal — dynamic chart types from styleGuide

**Files:**
- Modify: `frontend/src/pages/Editor/modals/AddChartModal.tsx`
- Create: `frontend/tests/AddChartModal.m6.test.tsx`

- [ ] **Step 1: Failing tests**

Create `frontend/tests/AddChartModal.m6.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import AddChartModal from "../src/pages/Editor/modals/AddChartModal"

// Mock styleGuide store — with AI-generated style guide
const mockStyleGuideWithTypes = {
  styleGuide: {
    available_chart_types: ["PIE", "DONUT", "TABLE_WITH_MINIBARS"],
    global: { suggested_palette: [] },
  },
  corpus: [{ filename: "a.pptx" }],
}

const mockStyleGuideBuiltin = {
  styleGuide: null,
  corpus: [],
}

let currentMock = mockStyleGuideWithTypes

vi.mock("../src/store/styleGuide", () => ({
  useStyleGuideStore: (sel: (s: typeof mockStyleGuideWithTypes) => unknown) => sel(currentMock as typeof mockStyleGuideWithTypes),
}))

// Mock project store
vi.mock("../src/store/project", () => ({
  useProjectStore: (sel: (s: unknown) => unknown) => sel({
    state: { slides: [], inputs: {} },
  }),
}))

const DB = {
  questions: [{ id: "q1", code: "P1", text: "¿Usa el producto?", options: ["Sí", "No"], confidence: 1.0 }],
  breakdowns: [{ id: "general", label: "General", categories: ["Total"] }],
  sample_size: 500,
  data_blocks: { counts_cols: [], pct_row_cols: [], pct_col_cols: [] },
}

beforeEach(() => { currentMock = mockStyleGuideWithTypes })

describe("AddChartModal — M6 chart types", () => {
  it("shows chart type options sourced from styleGuide.available_chart_types", () => {
    render(<AddChartModal open db={DB} slideId="sl1" onClose={vi.fn()} onAdd={vi.fn()} />)
    const select = screen.getByRole("combobox", { name: /tipo de gráfico/i })
    expect(select).toBeInTheDocument()
    expect(screen.getByRole("option", { name: /PIE/i })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: /DONUT/i })).toBeInTheDocument()
    expect(screen.getByRole("option", { name: /TABLE_WITH_MINIBARS/i })).toBeInTheDocument()
    // BAR_HORIZONTAL not in styleGuide — should NOT appear
    expect(screen.queryByRole("option", { name: /BAR_HORIZONTAL/i })).toBeNull()
  })

  it("falls back to 5 built-in chart types when styleGuide not loaded", () => {
    currentMock = mockStyleGuideBuiltin as typeof mockStyleGuideWithTypes
    render(<AddChartModal open db={DB} slideId="sl1" onClose={vi.fn()} onAdd={vi.fn()} />)
    // Should have PIE as at minimum (fallback)
    expect(screen.getByRole("option", { name: /PIE/i })).toBeInTheDocument()
  })

  it("includes ColorPicker trigger button", () => {
    render(<AddChartModal open db={DB} slideId="sl1" onClose={vi.fn()} onAdd={vi.fn()} />)
    // Should have the primary color button (Auto or swatch)
    const colorTriggers = screen.getAllByRole("button", { name: /auto|color/i })
    expect(colorTriggers.length).toBeGreaterThan(0)
  })
})
```

- [ ] **Step 2: Run failing**

```bash
cd frontend && npm test -- AddChartModal.m6
```

Expected: test failures — chart types not dynamic yet.

- [ ] **Step 3: Modify AddChartModal — dynamic chart types**

Edit `frontend/src/pages/Editor/modals/AddChartModal.tsx`:

Add import:

```tsx
import { useStyleGuideStore } from "../../../store/styleGuide"
```

Add built-in fallback constant near top of file:

```tsx
const BUILTIN_CHART_TYPES = ["PIE", "DONUT", "BAR_HORIZONTAL", "BAR_CLUSTERED", "COLUMN_CLUSTERED"]
```

Inside the component function, add:

```tsx
const styleGuide = useStyleGuideStore((s) => s.styleGuide)
const chartTypes = styleGuide?.available_chart_types?.length
  ? styleGuide.available_chart_types
  : BUILTIN_CHART_TYPES
```

Replace the existing hardcoded chart type `<select>` options with dynamic ones:

```tsx
<select
  id="chart-type-select"
  aria-label="Tipo de gráfico"
  value={selectedChartType}
  onChange={(e) => setSelectedChartType(e.target.value)}
  className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
>
  {chartTypes.map((ct) => (
    <option key={ct} value={ct}>{ct}</option>
  ))}
</select>
```

Ensure the state is initialized from the first available type:

```tsx
const [selectedChartType, setSelectedChartType] = useState(chartTypes[0] ?? "PIE")
```

If `chartTypes` changes (style guide loads after mount), sync:

```tsx
useEffect(() => {
  setSelectedChartType(chartTypes[0] ?? "PIE")
}, [chartTypes.join(",")])
```

- [ ] **Step 4: Run, verify pass**

```bash
cd frontend && npm test -- AddChartModal.m6
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add \
  frontend/src/pages/Editor/modals/AddChartModal.tsx \
  frontend/tests/AddChartModal.m6.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): AddChartModal — chart type dropdown from styleGuide.available_chart_types

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Update ConfigPanel — pattern matched indicator

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/pages/Editor/ConfigPanel.tsx`
- Create: `frontend/tests/ConfigPanel.pattern.test.tsx`

- [ ] **Step 1: Add matched_pattern field to types**

Edit `frontend/src/types/index.ts`. In the `Slide` interface (or wherever slide state is defined), add optional field:

```ts
// In Slide interface:
matched_pattern?: string | null   // set by backend on preview; null = fallback heurístico
```

This field is populated by the backend `preview-slide` response and stored transiently in the project state. It is read-only from the frontend perspective.

Also add it to the store's slide update path so it persists in the local state:

In `project.ts`, when processing `preview-slide` response, add:

```ts
// When backend returns preview for a slide, also update matched_pattern if present
// (existing preview logic already handles png_base64; extend it to also set matched_pattern)
```

- [ ] **Step 2: Failing tests**

Create `frontend/tests/ConfigPanel.pattern.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import ConfigPanel from "../src/pages/Editor/ConfigPanel"
import type { Slide } from "../src/types"

// Mock store with a slide that has matched_pattern set
const makeSlide = (matched_pattern: string | null | undefined): Slide => ({
  id: "sl1",
  type: "shell",
  title: "Recordación",
  charts: [],
  analyses: [],
  auto_notes: null,
  matched_pattern,
})

const mockStore = {
  state: {
    slides: [makeSlide("binary_general_demographics")],
    inputs: { db_path: "./x", template_path: "./y", font_override: null },
  },
  parsedDb: null,
  selectedSlideId: "sl1",
  removeChart: vi.fn(),
  removeAnalysis: vi.fn(),
  updateChartColors: vi.fn(),
}

vi.mock("../src/store/project", () => ({
  useProjectStore: (sel: (s: typeof mockStore) => unknown) => sel(mockStore),
}))

vi.mock("../src/store/styleGuide", () => ({
  useStyleGuideStore: (sel: (s: unknown) => unknown) => sel({ styleGuide: null }),
}))

describe("ConfigPanel — pattern matched indicator", () => {
  it("shows matched pattern id when slide has matched_pattern", () => {
    render(<ConfigPanel />)
    expect(screen.getByText(/binary_general_demographics/i)).toBeInTheDocument()
    expect(screen.getByText(/matched/i)).toBeInTheDocument()
  })

  it("shows fallback heurístico when matched_pattern is null", () => {
    mockStore.state.slides[0] = makeSlide(null)
    render(<ConfigPanel />)
    expect(screen.getByText(/fallback heurístico/i)).toBeInTheDocument()
  })

  it("shows fallback heurístico when matched_pattern is undefined", () => {
    mockStore.state.slides[0] = makeSlide(undefined)
    render(<ConfigPanel />)
    expect(screen.getByText(/fallback heurístico/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 3: Run failing**

```bash
cd frontend && npm test -- ConfigPanel.pattern
```

Expected: fails — indicator not yet implemented.

- [ ] **Step 4: Modify ConfigPanel — add pattern indicator**

Edit `frontend/src/pages/Editor/ConfigPanel.tsx`:

Find the section inside the `!isSep` block where chart info is displayed. After the chart list and before the AI suggest layout button (or at the top of the config section for the selected slide), add a layout indicator:

```tsx
{/* Pattern matched indicator */}
{slide.matched_pattern ? (
  <div className="flex items-center gap-2 text-xs text-green-400 mb-3 bg-green-900/20 border border-green-800/40 rounded px-3 py-2">
    <span className="font-mono">{slide.matched_pattern}</span>
    <span className="text-green-300">✓ matched</span>
  </div>
) : (
  <div className="text-xs text-neutral-500 italic mb-3">
    Layout: fallback heurístico
  </div>
)}
```

This indicator reads `slide.matched_pattern` from the slide in the project state. The backend will populate this field when it returns a preview response — the store's `previewSlide` action should be updated to store the `matched_pattern` from the backend response alongside the PNG. Add to the store's `previewSlide` handling:

```ts
// In the store, when preview response is received (existing logic):
// Existing: set png base64 on the slide state
// Add: also set matched_pattern if backend returns it
if (response.matched_pattern !== undefined) {
  // update slide.matched_pattern in state
  const slides = s.slides.map((sl) =>
    sl.id !== slideId ? sl : { ...sl, matched_pattern: response.matched_pattern ?? null }
  )
  set({ state: { ...s, slides } })
}
```

- [ ] **Step 5: Run, verify pass**

```bash
cd frontend && npm test -- ConfigPanel.pattern
```

Expected: 3 tests PASS.

- [ ] **Step 6: Run full test suite**

```bash
cd frontend && npm test
```

Expected: all passing.

- [ ] **Step 7: Commit**

```bash
git add \
  frontend/src/types/index.ts \
  frontend/src/pages/Editor/ConfigPanel.tsx \
  frontend/tests/ConfigPanel.pattern.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): ConfigPanel — pattern matched indicator (binary_general_demographics ✓ / fallback)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Migration — strip style_set, add palette default, round-trip load/save

**Files:**
- Modify: `frontend/src/store/project.ts`
- Modify (tests): `frontend/tests/store.test.ts`

- [ ] **Step 1: Failing migration tests**

Append to `frontend/tests/store.test.ts`:

```ts
describe("M6 migration — .aurum.json backward compat", () => {
  it("strips style_set field when loading old project", () => {
    // Simulate loading an old project with style_set field
    const oldProject = {
      version: 1,
      project_name: "Old Project",
      inputs: { db_path: "./x", template_path: "./y", font_override: null },
      slides: [],
      style_set: "aurum_default",   // Legacy field — must be stripped
    }
    useProjectStore.getState().loadProjectState(oldProject as unknown as import("../src/types").ProjectState)
    const state = useProjectStore.getState().state
    expect(state).not.toBeNull()
    expect((state as unknown as Record<string, unknown>).style_set).toBeUndefined()
  })

  it("adds palette: null when loading project without palette field", () => {
    const oldProject = {
      version: 1,
      project_name: "Old Project",
      inputs: { db_path: "./x", template_path: "./y", font_override: null },
      slides: [],
      // No palette field
    }
    useProjectStore.getState().loadProjectState(oldProject as unknown as import("../src/types").ProjectState)
    const state = useProjectStore.getState().state
    expect(state).not.toBeNull()
    expect(state!.palette).toBeNull()
  })

  it("preserves palette if present in loaded project", () => {
    const projectWithPalette = {
      version: 1,
      project_name: "New Project",
      inputs: { db_path: "./x", template_path: "./y", font_override: null },
      slides: [],
      palette: { primary: "#7F7F7F", secondary: "#BFBFBF" },
    }
    useProjectStore.getState().loadProjectState(projectWithPalette as unknown as import("../src/types").ProjectState)
    const state = useProjectStore.getState().state
    expect(state!.palette).toEqual({ primary: "#7F7F7F", secondary: "#BFBFBF" })
  })

  it("defaults Chart.colors to [] when loading charts without colors field", () => {
    const projectWithOldChart = {
      version: 1,
      project_name: "Old Project",
      inputs: { db_path: "./x", template_path: "./y", font_override: null },
      slides: [{
        id: "sl1", type: "shell", title: "Sec",
        charts: [{ id: "c1", question_id: "q1", breakdown_id: "general", chart_type: "PIE", multi_series: false }],
        // no colors on chart
        analyses: [], auto_notes: null,
      }],
    }
    useProjectStore.getState().loadProjectState(projectWithOldChart as unknown as import("../src/types").ProjectState)
    const chart = useProjectStore.getState().state!.slides[0].charts[0]
    expect(chart.colors).toEqual([])
  })
})
```

- [ ] **Step 2: Run failing**

```bash
cd frontend && npm test -- store.test
```

Expected: migration tests fail.

- [ ] **Step 3: Implement migration in store**

Edit `frontend/src/store/project.ts`. Modify `loadProjectState` action (or create a `_migrateProject` helper called inside it):

```ts
function _migrateProjectState(raw: unknown): ProjectState {
  const obj = raw as Record<string, unknown>

  // Strip legacy style_set field
  const { style_set: _dropped, ...rest } = obj

  // Ensure palette defaults to null
  if (!("palette" in rest)) {
    rest.palette = null
  }

  // Ensure each chart has colors: []
  if (Array.isArray(rest.slides)) {
    rest.slides = (rest.slides as unknown[]).map((sl) => {
      const slide = sl as Record<string, unknown>
      if (!Array.isArray(slide.charts)) return slide
      return {
        ...slide,
        charts: (slide.charts as unknown[]).map((ch) => {
          const chart = ch as Record<string, unknown>
          if (!("colors" in chart)) {
            return { ...chart, colors: [] }
          }
          return chart
        }),
      }
    })
  }

  return rest as unknown as ProjectState
}

// In loadProjectState action:
loadProjectState(raw: unknown) {
  const migrated = _migrateProjectState(raw)
  set({ state: migrated })
},
```

- [ ] **Step 4: Run, verify pass**

```bash
cd frontend && npm test -- store.test
```

Expected: all store tests PASS including 4 new migration tests.

- [ ] **Step 5: Verify full test suite + build**

```bash
cd frontend && npm test
cd frontend && npm run build
```

Expected: all PASS, build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/store/project.ts frontend/tests/store.test.ts
git commit -m "$(cat <<'EOF'
feat(frontend): M6 migration in loadProjectState — strip style_set, add palette:null, Chart.colors:[]

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Tag milestone:

```bash
git tag m6.11
```

---

## M6.11 Done When

- `WelcomePage` has no training set selector UI element
- `WelcomePage` shows banner "⚡ Cargá training PPTs para que las generaciones reflejen tu estilo casa → Configurar" when corpus is empty or `styleGuide.is_builtin === true`; banner is absent when style guide is AI-generated and corpus is non-empty
- `WelcomePage` calls `loadStyleGuide()` and `loadCorpus()` on mount to determine banner visibility
- `AddChartModal` chart type `<select>` is populated from `styleGuide.available_chart_types` when the style guide is loaded; falls back to 5 built-in types (`PIE`, `DONUT`, `BAR_HORIZONTAL`, `BAR_CLUSTERED`, `COLUMN_CLUSTERED`) when style guide is null
- `ConfigPanel` renders pattern matched indicator: green badge with pattern id + "✓ matched" when `slide.matched_pattern` is set; grey italic "Layout: fallback heurístico" when null/undefined
- `loadProjectState` migration: `style_set` field stripped from loaded projects; `palette` defaults to `null` if absent; `Chart.colors` defaults to `[]` if field absent on loaded charts
- All frontend tests pass; build succeeds
- Git tag `m6.11` created
