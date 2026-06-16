# M2 — Frontend Skeleton + Integración Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** React + Vite frontend wired to the M1 backend. User can upload xlsx + template, see the wizard verification screen with detected questions/breakdowns, navigate between Editor and Entrenamiento tabs, save/load `.aurum.json` projects.

**Architecture:** SPA with React 18 + TypeScript + Vite. State via zustand. Typed API client wrapping fetch. Tailwind for styles. Tabs routing via React Router. Vite dev server proxies `/api/*` → `http://localhost:8000`.

**Tech Stack:** Vite, React 18, TypeScript, zustand, zundo, React Router 6, Tailwind CSS, Lucide icons, vitest + @testing-library/react.

---

## File Structure

**Create:**
- `frontend/package.json`
- `frontend/tsconfig.json`, `tsconfig.node.json`
- `frontend/vite.config.ts`
- `frontend/tailwind.config.ts`, `postcss.config.js`
- `frontend/index.html`
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/index.css`
- `frontend/src/types/index.ts` (TS mirror of backend models)
- `frontend/src/api/client.ts` (fetch wrappers)
- `frontend/src/store/project.ts` (zustand + zundo)
- `frontend/src/components/Topbar.tsx`
- `frontend/src/components/Pills.tsx`
- `frontend/src/components/Modal.tsx`
- `frontend/src/pages/Welcome.tsx` (empty state when no project)
- `frontend/src/pages/Wizard/XlsxVerifyWizard.tsx`
- `frontend/src/pages/Editor/EditorPage.tsx` (skeleton — 3 columns empty)
- `frontend/src/pages/Training/TrainingPage.tsx` (skeleton)
- `frontend/src/hooks/useUpload.ts`
- `frontend/tests/setup.ts`
- `frontend/tests/api.test.ts`
- `frontend/tests/store.test.ts`
- `frontend/tests/Topbar.test.tsx`
- `frontend/tests/Wizard.test.tsx`

**Modify:**
- `Makefile` — add frontend targets
- `README.md` — add frontend instructions

---

### Task 1: Frontend bootstrap (Vite + TypeScript + deps)

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/.gitignore`

- [ ] **Step 1: Write package.json**

Create `frontend/package.json`:

```json
{
  "name": "aurum-encuestas-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "eslint src --ext ts,tsx"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.2",
    "zustand": "^4.5.5",
    "zundo": "^2.2.0",
    "@dnd-kit/core": "^6.1.0",
    "@dnd-kit/sortable": "^8.0.0",
    "@dnd-kit/utilities": "^3.2.2",
    "lucide-react": "^0.452.0",
    "immer": "^10.1.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.10",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.2",
    "typescript": "^5.6.2",
    "vite": "^5.4.8",
    "vitest": "^2.1.2",
    "@testing-library/react": "^16.0.1",
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/user-event": "^14.5.2",
    "jsdom": "^25.0.1",
    "tailwindcss": "^3.4.13",
    "postcss": "^8.4.47",
    "autoprefixer": "^10.4.20",
    "eslint": "^9.11.1",
    "@typescript-eslint/parser": "^8.7.0",
    "@typescript-eslint/eslint-plugin": "^8.7.0"
  }
}
```

- [ ] **Step 2: Write tsconfig + vite config**

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "tests"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Create `frontend/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

Create `frontend/vite.config.ts`:

```ts
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
  },
})
```

- [ ] **Step 3: Write index.html + main.tsx + App.tsx + index.css**

Create `frontend/index.html`:

```html
<!doctype html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AurumEncuestas</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `frontend/src/main.tsx`:

```tsx
import React from "react"
import ReactDOM from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import App from "./App"
import "./index.css"

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
```

Create `frontend/src/App.tsx` (skeleton):

```tsx
import { Route, Routes } from "react-router-dom"
import Topbar from "./components/Topbar"
import EditorPage from "./pages/Editor/EditorPage"
import TrainingPage from "./pages/Training/TrainingPage"
import Welcome from "./pages/Welcome"

export default function App() {
  return (
    <div className="h-screen flex flex-col bg-neutral-900 text-neutral-100">
      <Topbar />
      <main className="flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<Welcome />} />
          <Route path="/editor" element={<EditorPage />} />
          <Route path="/training" element={<TrainingPage />} />
        </Routes>
      </main>
    </div>
  )
}
```

Create `frontend/src/index.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

html, body, #root {
  height: 100%;
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
```

- [ ] **Step 4: Tailwind config + postcss**

Create `frontend/tailwind.config.ts`:

```ts
import type { Config } from "tailwindcss"

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        accent: "#FFC940",
      },
    },
  },
  plugins: [],
} satisfies Config
```

Create `frontend/postcss.config.js`:

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **Step 5: Frontend .gitignore**

Create `frontend/.gitignore`:

```
node_modules/
dist/
.vite/
*.log
.vitest-cache/
```

- [ ] **Step 6: Install + build smoke**

Run: `cd frontend && npm install`
Expected: completes without error.

Run: `cd frontend && npm run build`
Expected: build succeeds — produces `dist/` folder. (Will fail if `Topbar.tsx`, `EditorPage.tsx`, `TrainingPage.tsx`, `Welcome.tsx` not yet created — create empty placeholders.)

Create placeholder component files so build passes:

`frontend/src/components/Topbar.tsx`:
```tsx
export default function Topbar() { return <header className="h-12 bg-neutral-800 border-b border-neutral-700 flex items-center px-4">AurumEncuestas</header> }
```

`frontend/src/pages/Welcome.tsx`:
```tsx
export default function Welcome() { return <div className="p-8">Bienvenido</div> }
```

`frontend/src/pages/Editor/EditorPage.tsx`:
```tsx
export default function EditorPage() { return <div className="p-8">Editor</div> }
```

`frontend/src/pages/Training/TrainingPage.tsx`:
```tsx
export default function TrainingPage() { return <div className="p-8">Training</div> }
```

Re-run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/tsconfig.node.json frontend/vite.config.ts frontend/index.html frontend/src frontend/tailwind.config.ts frontend/postcss.config.js frontend/.gitignore
git commit -m "chore(frontend): bootstrap Vite + React + Tailwind + Router"
```

---

### Task 2: Update Makefile + README with frontend targets

**Files:**
- Modify: `Makefile`
- Modify: `README.md`

- [ ] **Step 1: Add frontend targets to Makefile**

Edit `Makefile` — add:

```makefile
frontend-install:
	cd frontend && npm install

dev-frontend:
	cd frontend && npm run dev

test-frontend:
	cd frontend && npm test

build-frontend:
	cd frontend && npm run build

# update install to include both
install: backend-install frontend-install

# parallel dev (foreground both): use 'make dev-all' in two terminals or use concurrently if installed
dev-all:
	@echo "Run 'make dev-backend' and 'make dev-frontend' in separate terminals"

test: test-backend test-frontend
```

- [ ] **Step 2: Update README**

Append to `README.md`:

````markdown
## Frontend

```bash
make frontend-install
make dev-frontend
```

App en http://localhost:5173. Proxy `/api/*` → http://localhost:8000.

Para correr todo: en una terminal `make dev-backend`, en otra `make dev-frontend`.
````

- [ ] **Step 3: Commit**

```bash
git add Makefile README.md
git commit -m "chore: Makefile frontend targets + README updates"
```

---

### Task 3: TypeScript types mirror backend models

**Files:**
- Create: `frontend/src/types/index.ts`

- [ ] **Step 1: Define types**

Create `frontend/src/types/index.ts`:

```ts
export type ChartType =
  | "PIE" | "DONUT" | "BAR" | "COLUMN"
  | "BAR_STACKED" | "COLUMN_STACKED"
  | "LINE" | "AREA" | "RADAR"

export type AnalysisScope = "slide" | "question" | "chart"
export type SlideType = "separator" | "shell"

export interface Question {
  id: string
  code: string
  text: string
  options: string[]
  confidence: number
}

export interface Breakdown {
  id: string
  label: string
  categories: string[]
}

export interface ParsedDB {
  questions: Question[]
  breakdowns: Breakdown[]
  sample_size: number
  data_blocks: { counts_cols: number[]; pct_row_cols: number[]; pct_col_cols: number[] }
}

export interface Chart {
  id: string
  question_id: string
  breakdown_id: string
  chart_type: ChartType
  multi_series: boolean
}

export interface Analysis {
  id: string
  scope: AnalysisScope
  target_id: string | null
  text: string
  ai_generated: boolean
  edited: boolean
}

export interface Slide {
  id: string
  type: SlideType
  title: string | null
  charts: Chart[]
  analyses: Analysis[]
  auto_notes: string | null
}

export interface ProjectInputs {
  db_path: string
  template_path: string
  font_override: string | null
}

export interface ProjectState {
  version: number
  app_name: string
  project_name: string
  created_at: string | null
  updated_at: string | null
  inputs: ProjectInputs
  parsed_db: ParsedDB | null
  slides: Slide[]
  history: { past: unknown[]; future: unknown[] }
}

export interface TemplateInfo {
  shell_slide_index: number
  separator_slide_index: number
  free_area: { x: number; y: number; cx: number; cy: number }
  placeholders: string[]
  default_font: string | null
}

export interface ApiError {
  code: string
  message: string
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(frontend): TS types mirroring backend models"
```

---

### Task 4: API client (fetch wrappers, typed)

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/tests/setup.ts`
- Create: `frontend/tests/api.test.ts`

- [ ] **Step 1: Tests setup**

Create `frontend/tests/setup.ts`:

```ts
import "@testing-library/jest-dom"
```

- [ ] **Step 2: Write failing tests for api client**

Create `frontend/tests/api.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import * as api from "../src/api/client"

describe("api client", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString()
      if (url.endsWith("/api/health")) {
        return new Response(JSON.stringify({ status: "ok" }), { status: 200, headers: { "Content-Type": "application/json" } })
      }
      if (url.endsWith("/api/parse-xlsx")) {
        return new Response(
          JSON.stringify({ sample_size: 500, questions: [], breakdowns: [], data_blocks: {} }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        )
      }
      if (url.endsWith("/api/parse-template")) {
        return new Response(
          JSON.stringify({ shell_slide_index: 0, separator_slide_index: 1, free_area: { x: 0, y: 0, cx: 100, cy: 100 }, placeholders: ["@Titulo"], default_font: null }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        )
      }
      if (url.endsWith("/api/save-project") || url.endsWith("/api/load-project")) {
        return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json" } })
      }
      return new Response(JSON.stringify({ code: "not_found", message: "?" }), { status: 404 })
    })
  })

  afterEach(() => vi.restoreAllMocks())

  it("health", async () => {
    const r = await api.health()
    expect(r.status).toBe("ok")
  })

  it("parseXlsx returns ParsedDB", async () => {
    const f = new File([new Blob([])], "x.xlsx")
    const r = await api.parseXlsx(f)
    expect(r.sample_size).toBe(500)
  })

  it("parseTemplate returns TemplateInfo", async () => {
    const f = new File([new Blob([])], "t.pptx")
    const r = await api.parseTemplate(f)
    expect(r.shell_slide_index).toBe(0)
    expect(r.placeholders).toContain("@Titulo")
  })

  it("error throws ApiError", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ code: "xlsx_parse_error", message: "bad" }), { status: 400 }),
    )
    const f = new File([new Blob([])], "x.xlsx")
    await expect(api.parseXlsx(f)).rejects.toMatchObject({ code: "xlsx_parse_error" })
  })
})
```

- [ ] **Step 3: Run failing**

Run: `cd frontend && npm test`
Expected: ImportError on `../src/api/client`.

- [ ] **Step 4: Implement client.ts**

Create `frontend/src/api/client.ts`:

```ts
import type { ApiError, ParsedDB, ProjectState, TemplateInfo } from "../types"

const BASE = "/api"

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, init)
  if (!r.ok) {
    let payload: ApiError
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
```

- [ ] **Step 5: Run, verify pass**

Run: `cd frontend && npm test`
Expected: 4 PASS in api.test.ts.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.ts frontend/tests/api.test.ts frontend/tests/setup.ts
git commit -m "feat(frontend): typed API client with fetch wrappers + error mapping"
```

---

### Task 5: Zustand store (project state) + zundo undo/redo

**Files:**
- Create: `frontend/src/store/project.ts`
- Create: `frontend/tests/store.test.ts`

- [ ] **Step 1: Failing tests**

Create `frontend/tests/store.test.ts`:

```ts
import { describe, expect, it, beforeEach } from "vitest"
import { useProjectStore } from "../src/store/project"

describe("project store", () => {
  beforeEach(() => {
    useProjectStore.setState({
      state: null,
      projectPath: null,
    })
  })

  it("initial state is null", () => {
    expect(useProjectStore.getState().state).toBeNull()
  })

  it("setNewProject creates blank state", () => {
    useProjectStore.getState().setNewProject({
      name: "Test",
      db_path: "./x.xlsx",
      template_path: "./t.pptx",
    })
    const s = useProjectStore.getState().state
    expect(s).not.toBeNull()
    expect(s!.project_name).toBe("Test")
    expect(s!.slides).toEqual([])
  })

  it("addSeparator appends a separator slide", () => {
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    useProjectStore.getState().addSeparator("Sección 1")
    const slides = useProjectStore.getState().state!.slides
    expect(slides.length).toBe(1)
    expect(slides[0].type).toBe("separator")
    expect(slides[0].title).toBe("Sección 1")
  })

  it("addShell requires a previous separator", () => {
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    expect(() => useProjectStore.getState().addShell()).toThrow(/separador/)
  })

  it("addShell inherits last separator title", () => {
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    useProjectStore.getState().addSeparator("Sección A")
    useProjectStore.getState().addShell()
    const slides = useProjectStore.getState().state!.slides
    expect(slides[1].type).toBe("shell")
    expect(slides[1].title).toBe("Sección A")
  })
})
```

- [ ] **Step 2: Run failing**

Run: `cd frontend && npm test`
Expected: import error.

- [ ] **Step 3: Implement store**

Create `frontend/src/store/project.ts`:

```ts
import { create } from "zustand"
import { temporal } from "zundo"
import type { ParsedDB, ProjectState, Slide, TemplateInfo } from "../types"

function uid(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`
}

interface NewProjectArgs {
  name: string
  db_path: string
  template_path: string
}

interface Store {
  state: ProjectState | null
  projectPath: string | null
  parsedDb: ParsedDB | null
  templateInfo: TemplateInfo | null

  setNewProject(args: NewProjectArgs): void
  setProjectPath(path: string | null): void
  setParsedDb(db: ParsedDB | null): void
  setTemplateInfo(info: TemplateInfo | null): void
  loadProjectState(state: ProjectState): void

  addSeparator(title: string): void
  addShell(): void
  reorderSlide(fromIdx: number, toIdx: number): void
  removeSlide(slideId: string): void
  updateSeparatorTitle(slideId: string, title: string): void
}

function applyTitleInheritance(slides: Slide[]): Slide[] {
  // every shell slide inherits the most recent separator's title
  let currentTitle: string | null = null
  return slides.map((s) => {
    if (s.type === "separator") {
      currentTitle = s.title
      return s
    }
    return { ...s, title: currentTitle }
  })
}

export const useProjectStore = create<Store>()(
  temporal(
    (set, get) => ({
      state: null,
      projectPath: null,
      parsedDb: null,
      templateInfo: null,

      setNewProject({ name, db_path, template_path }) {
        set({
          state: {
            version: 1,
            app_name: "AurumEncuestas",
            project_name: name,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            inputs: { db_path, template_path, font_override: null },
            parsed_db: null,
            slides: [],
            history: { past: [], future: [] },
          },
        })
      },

      setProjectPath(path) { set({ projectPath: path }) },
      setParsedDb(db) { set({ parsedDb: db }); const s = get().state; if (s) set({ state: { ...s, parsed_db: db } }) },
      setTemplateInfo(info) { set({ templateInfo: info }) },
      loadProjectState(state) { set({ state }) },

      addSeparator(title: string) {
        const s = get().state
        if (!s) return
        const sep: Slide = { id: uid("sl"), type: "separator", title, charts: [], analyses: [], auto_notes: null }
        set({ state: { ...s, slides: applyTitleInheritance([...s.slides, sep]) } })
      },

      addShell() {
        const s = get().state
        if (!s) return
        const hasSeparator = s.slides.some((sl) => sl.type === "separator")
        if (!hasSeparator) throw new Error("Necesitás crear un separador antes de agregar una shell.")
        const shell: Slide = { id: uid("sl"), type: "shell", title: null, charts: [], analyses: [], auto_notes: null }
        set({ state: { ...s, slides: applyTitleInheritance([...s.slides, shell]) } })
      },

      reorderSlide(fromIdx, toIdx) {
        const s = get().state
        if (!s) return
        const copy = [...s.slides]
        const [moved] = copy.splice(fromIdx, 1)
        copy.splice(toIdx, 0, moved)
        set({ state: { ...s, slides: applyTitleInheritance(copy) } })
      },

      removeSlide(slideId) {
        const s = get().state
        if (!s) return
        set({ state: { ...s, slides: applyTitleInheritance(s.slides.filter((sl) => sl.id !== slideId)) } })
      },

      updateSeparatorTitle(slideId, title) {
        const s = get().state
        if (!s) return
        set({
          state: {
            ...s,
            slides: applyTitleInheritance(
              s.slides.map((sl) => (sl.id === slideId && sl.type === "separator" ? { ...sl, title } : sl)),
            ),
          },
        })
      },
    }),
    {
      limit: 100,
      partialize: (state) => ({ state: state.state }) as any,
    },
  ),
)
```

- [ ] **Step 4: Run, verify pass**

Run: `cd frontend && npm test`
Expected: 5 store tests + 4 api tests = 9 PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/store/project.ts frontend/tests/store.test.ts
git commit -m "feat(frontend): zustand store with zundo undo/redo + separator title inheritance"
```

---

### Task 6: Topbar component with tabs + pills

**Files:**
- Modify: `frontend/src/components/Topbar.tsx`
- Create: `frontend/src/components/Pills.tsx`
- Create: `frontend/tests/Topbar.test.tsx`

- [ ] **Step 1: Failing test**

Create `frontend/tests/Topbar.test.tsx`:

```tsx
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import Topbar from "../src/components/Topbar"
import { useProjectStore } from "../src/store/project"

describe("Topbar", () => {
  it("renders app name + tabs", () => {
    render(
      <MemoryRouter>
        <Topbar />
      </MemoryRouter>,
    )
    expect(screen.getByText(/AurumEncuestas/i)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Editor/i })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Entrenamiento/i })).toBeInTheDocument()
  })

  it("shows pill with DB filename when project loaded", () => {
    useProjectStore.getState().setNewProject({
      name: "X",
      db_path: "/path/to/BD.xlsx",
      template_path: "/path/to/tpl.pptx",
    })
    render(
      <MemoryRouter>
        <Topbar />
      </MemoryRouter>,
    )
    expect(screen.getByText(/BD\.xlsx/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run failing**

Run: `cd frontend && npm test -- Topbar`
Expected: fails (Topbar is placeholder, no tabs).

- [ ] **Step 3: Implement Pills**

Create `frontend/src/components/Pills.tsx`:

```tsx
interface PillProps {
  label: string
  value: string
  ok?: boolean
}

export function Pill({ label, value, ok }: PillProps) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-neutral-900 border border-neutral-700 text-neutral-400">
      {label}: <span className={ok ? "text-green-400" : "text-neutral-300"}>{value}</span>
    </span>
  )
}
```

- [ ] **Step 4: Implement Topbar**

Overwrite `frontend/src/components/Topbar.tsx`:

```tsx
import { Link, NavLink } from "react-router-dom"
import { useProjectStore } from "../store/project"
import { Pill } from "./Pills"

export default function Topbar() {
  const state = useProjectStore((s) => s.state)
  const dbName = state ? state.inputs.db_path.split("/").pop() : null
  const tplName = state ? state.inputs.template_path.split("/").pop() : null
  const font = state?.inputs.font_override

  const tabClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-1 rounded text-sm ${isActive ? "bg-neutral-700 text-white" : "text-neutral-300 hover:bg-neutral-800"}`

  return (
    <header className="h-12 bg-neutral-800 border-b border-neutral-700 flex items-center px-4 gap-4">
      <Link to="/" className="font-semibold text-accent">AurumEncuestas</Link>
      <nav className="flex gap-1">
        <NavLink to="/editor" className={tabClass}>Editor</NavLink>
        <NavLink to="/training" className={tabClass}>Entrenamiento</NavLink>
      </nav>
      <div className="flex-1" />
      <div className="flex items-center gap-2">
        {dbName && <Pill label="DB" value={dbName} ok />}
        {tplName && <Pill label="Template" value={tplName} ok />}
        {font && <Pill label="Font" value={font} />}
      </div>
    </header>
  )
}
```

- [ ] **Step 5: Run, verify pass**

Run: `cd frontend && npm test`
Expected: all tests PASS including Topbar (2 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/Topbar.tsx frontend/src/components/Pills.tsx frontend/tests/Topbar.test.tsx
git commit -m "feat(frontend): Topbar with tabs + DB/template/font pills"
```

---

### Task 7: Modal component (reusable)

**Files:**
- Create: `frontend/src/components/Modal.tsx`

- [ ] **Step 1: Implement Modal**

Create `frontend/src/components/Modal.tsx`:

```tsx
import { ReactNode, useEffect } from "react"
import { X } from "lucide-react"

interface ModalProps {
  open: boolean
  onClose(): void
  title: string
  children: ReactNode
  footer?: ReactNode
  maxWidth?: string
}

export default function Modal({ open, onClose, title, children, footer, maxWidth = "max-w-lg" }: ModalProps) {
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className={`bg-neutral-800 rounded-lg shadow-xl border border-neutral-700 w-full ${maxWidth} mx-4`}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between px-5 py-3 border-b border-neutral-700">
          <h3 className="text-sm font-semibold text-neutral-100">{title}</h3>
          <button onClick={onClose} className="text-neutral-400 hover:text-white">
            <X size={16} />
          </button>
        </header>
        <div className="p-5">{children}</div>
        {footer && <footer className="px-5 py-3 border-t border-neutral-700 flex justify-end gap-2">{footer}</footer>}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/Modal.tsx
git commit -m "feat(frontend): reusable Modal component with esc-to-close"
```

---

### Task 8: Welcome page — upload DB + template flow

**Files:**
- Modify: `frontend/src/pages/Welcome.tsx`
- Create: `frontend/src/hooks/useUpload.ts`

- [ ] **Step 1: Implement useUpload hook**

Create `frontend/src/hooks/useUpload.ts`:

```ts
import { useState } from "react"

export function useFileUpload<T>(uploader: (f: File) => Promise<T>) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<T | null>(null)

  async function upload(f: File) {
    setLoading(true); setError(null)
    try {
      const r = await uploader(f)
      setData(r); return r
    } catch (e) {
      const msg = (e as { message?: string })?.message ?? "Error desconocido"
      setError(msg)
      throw e
    } finally {
      setLoading(false)
    }
  }

  return { upload, loading, error, data, reset: () => { setError(null); setData(null) } }
}
```

- [ ] **Step 2: Implement Welcome page**

Overwrite `frontend/src/pages/Welcome.tsx`:

```tsx
import { useNavigate } from "react-router-dom"
import { useState } from "react"
import { Upload, FileSpreadsheet, Presentation } from "lucide-react"
import * as api from "../api/client"
import { useFileUpload } from "../hooks/useUpload"
import { useProjectStore } from "../store/project"

export default function Welcome() {
  const navigate = useNavigate()
  const [dbFile, setDbFile] = useState<File | null>(null)
  const [tplFile, setTplFile] = useState<File | null>(null)
  const [projectName, setProjectName] = useState("Nuevo proyecto")

  const xlsxUpload = useFileUpload(api.parseXlsx)
  const tplUpload = useFileUpload(api.parseTemplate)

  const setParsedDb = useProjectStore((s) => s.setParsedDb)
  const setTemplateInfo = useProjectStore((s) => s.setTemplateInfo)
  const setNewProject = useProjectStore((s) => s.setNewProject)

  async function handleContinue() {
    if (!dbFile || !tplFile) return
    const [db, tpl] = await Promise.all([
      xlsxUpload.upload(dbFile),
      tplUpload.upload(tplFile),
    ])
    setNewProject({
      name: projectName,
      db_path: `./${dbFile.name}`,
      template_path: `./${tplFile.name}`,
    })
    setParsedDb(db)
    setTemplateInfo(tpl)
    navigate("/editor?wizard=1")
  }

  return (
    <div className="flex flex-col items-center justify-center h-full bg-neutral-900 text-neutral-100">
      <div className="w-full max-w-xl bg-neutral-800 rounded-lg p-8 shadow border border-neutral-700">
        <h1 className="text-xl font-semibold mb-1">Nuevo proyecto</h1>
        <p className="text-sm text-neutral-400 mb-6">Subí los 3 archivos para empezar.</p>

        <label className="block text-xs font-medium text-neutral-400 mb-1">Nombre del proyecto</label>
        <input
          value={projectName}
          onChange={(e) => setProjectName(e.target.value)}
          className="w-full mb-4 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
        />

        <FileSlot icon={<FileSpreadsheet size={20} />} label="DB (xlsx)" file={dbFile} onPick={setDbFile} accept=".xlsx" />
        {xlsxUpload.error && <p className="text-xs text-red-400 mb-2">{xlsxUpload.error}</p>}

        <FileSlot icon={<Presentation size={20} />} label="Template (pptx)" file={tplFile} onPick={setTplFile} accept=".pptx" />
        {tplUpload.error && <p className="text-xs text-red-400 mb-2">{tplUpload.error}</p>}

        <button
          disabled={!dbFile || !tplFile || xlsxUpload.loading || tplUpload.loading}
          onClick={handleContinue}
          className="w-full mt-2 bg-accent text-neutral-900 font-semibold py-2 rounded disabled:opacity-40"
        >
          {xlsxUpload.loading || tplUpload.loading ? "Procesando..." : "Continuar"}
        </button>
      </div>
    </div>
  )
}

interface FileSlotProps {
  icon: React.ReactNode
  label: string
  file: File | null
  onPick(f: File): void
  accept: string
}

function FileSlot({ icon, label, file, onPick, accept }: FileSlotProps) {
  return (
    <label className="flex items-center gap-3 bg-neutral-900 border border-neutral-700 hover:border-accent rounded p-3 cursor-pointer mb-3">
      <span className="text-neutral-400">{icon}</span>
      <div className="flex-1">
        <div className="text-sm">{label}</div>
        <div className="text-xs text-neutral-500">{file ? file.name : "Click para elegir archivo"}</div>
      </div>
      <Upload size={14} className="text-neutral-500" />
      <input type="file" accept={accept} className="hidden" onChange={(e) => e.target.files?.[0] && onPick(e.target.files[0])} />
    </label>
  )
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Welcome.tsx frontend/src/hooks/useUpload.ts
git commit -m "feat(frontend): Welcome page with xlsx + template upload flow"
```

---

### Task 9: Wizard de verificación xlsx

**Files:**
- Create: `frontend/src/pages/Wizard/XlsxVerifyWizard.tsx`
- Create: `frontend/tests/Wizard.test.tsx`
- Modify: `frontend/src/pages/Editor/EditorPage.tsx` (render wizard if `?wizard=1`)

- [ ] **Step 1: Failing test**

Create `frontend/tests/Wizard.test.tsx`:

```tsx
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import XlsxVerifyWizard from "../src/pages/Wizard/XlsxVerifyWizard"
import { useProjectStore } from "../src/store/project"
import type { ParsedDB } from "../src/types"

const FAKE_DB: ParsedDB = {
  questions: [
    { id: "q1", code: "P1", text: "¿Recuerda?", options: ["Sí", "No"], confidence: 1.0 },
    { id: "q2", code: "P2", text: "$p2.label", options: ["a", "b", "c"], confidence: 1.0 },
  ],
  breakdowns: [
    { id: "general", label: "General", categories: ["Total"] },
    { id: "sexo", label: "Sexo", categories: ["Hombre", "Mujer"] },
  ],
  sample_size: 500,
  data_blocks: { counts_cols: [3, 17], pct_row_cols: [21, 35], pct_col_cols: [41, 55] },
}

describe("XlsxVerifyWizard", () => {
  it("lists questions and breakdowns from store.parsedDb", () => {
    useProjectStore.setState({ parsedDb: FAKE_DB })
    render(
      <MemoryRouter>
        <XlsxVerifyWizard onConfirm={() => {}} />
      </MemoryRouter>,
    )
    expect(screen.getByText(/P1/)).toBeInTheDocument()
    expect(screen.getByText(/¿Recuerda\?/)).toBeInTheDocument()
    expect(screen.getByText(/Sexo/)).toBeInTheDocument()
    expect(screen.getByText(/Sample size:.*500/)).toBeInTheDocument()
  })

  it("Confirm button calls onConfirm", async () => {
    useProjectStore.setState({ parsedDb: FAKE_DB })
    let called = false
    render(
      <MemoryRouter>
        <XlsxVerifyWizard onConfirm={() => { called = true }} />
      </MemoryRouter>,
    )
    await userEvent.click(screen.getByRole("button", { name: /Confirmar/i }))
    expect(called).toBe(true)
  })

  it("renders font dropdown with curated list", () => {
    useProjectStore.setState({ parsedDb: FAKE_DB })
    render(
      <MemoryRouter>
        <XlsxVerifyWizard onConfirm={() => {}} />
      </MemoryRouter>,
    )
    const select = screen.getByLabelText(/Fuente/i) as HTMLSelectElement
    expect(select.options.length).toBeGreaterThan(5)
  })
})
```

- [ ] **Step 2: Run failing**

Run: `cd frontend && npm test -- Wizard`
Expected: ImportError.

- [ ] **Step 3: Implement Wizard**

Create `frontend/src/pages/Wizard/XlsxVerifyWizard.tsx`:

```tsx
import { Check, AlertTriangle } from "lucide-react"
import { useState } from "react"
import { useProjectStore } from "../../store/project"

const FONTS = [
  "Default del template",
  "Arial",
  "Calibri",
  "Helvetica",
  "Times New Roman",
  "Roboto",
  "Open Sans",
  "Lato",
  "Montserrat",
  "Inter",
  "Custom",
]

interface Props {
  onConfirm(): void
}

export default function XlsxVerifyWizard({ onConfirm }: Props) {
  const parsedDb = useProjectStore((s) => s.parsedDb)
  const setState = useProjectStore((s) => s.state)
  const updateState = (mut: (prev: NonNullable<typeof setState>) => NonNullable<typeof setState>) => {
    const cur = useProjectStore.getState().state
    if (cur) useProjectStore.setState({ state: mut(cur) })
  }
  const [font, setFont] = useState(FONTS[0])
  const [customFont, setCustomFont] = useState("")

  if (!parsedDb) return <div className="p-6">No hay datos detectados. Volvé a subir el xlsx.</div>

  const handleConfirm = () => {
    const finalFont = font === "Default del template" ? null : font === "Custom" ? customFont : font
    updateState((p) => ({ ...p, inputs: { ...p.inputs, font_override: finalFont } }))
    onConfirm()
  }

  return (
    <div className="max-w-2xl mx-auto p-6 text-neutral-100">
      <h2 className="text-lg font-semibold mb-1">Verificación de datos detectados</h2>
      <p className="text-sm text-neutral-400 mb-6">Revisá lo detectado por la heurística. 1 click para confirmar.</p>

      <section className="mb-6">
        <h3 className="text-sm font-semibold text-neutral-300 mb-2">Preguntas detectadas ({parsedDb.questions.length})</h3>
        <ul className="space-y-1 text-sm">
          {parsedDb.questions.map((q) => (
            <li key={q.id} className="flex items-center gap-2 bg-neutral-800 rounded px-3 py-2">
              {q.confidence >= 0.9 ? <Check size={14} className="text-green-400" /> : <AlertTriangle size={14} className="text-amber-400" />}
              <span className="font-semibold">{q.code}:</span> <span className="truncate">{q.text}</span>
              <span className="ml-auto text-xs text-neutral-500">({q.options.length} opciones)</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="mb-6">
        <h3 className="text-sm font-semibold text-neutral-300 mb-2">Breakdowns ({parsedDb.breakdowns.length})</h3>
        <ul className="space-y-1 text-sm">
          {parsedDb.breakdowns.map((b) => (
            <li key={b.id} className="bg-neutral-800 rounded px-3 py-2">
              <span className="font-semibold">{b.label}:</span>{" "}
              <span className="text-neutral-400">{b.categories.join(", ")}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="mb-6 text-sm">
        <div>Sample size: <strong>{parsedDb.sample_size}</strong></div>
        <div>Bloques cols — Counts: {parsedDb.data_blocks.counts_cols.join("–")} · %Row: {parsedDb.data_blocks.pct_row_cols.join("–")} · %Col: {parsedDb.data_blocks.pct_col_cols.join("–")}</div>
      </section>

      <section className="mb-6">
        <label htmlFor="font-select" className="block text-xs font-medium text-neutral-400 mb-1">Fuente (opcional)</label>
        <select
          id="font-select"
          value={font}
          onChange={(e) => setFont(e.target.value)}
          className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
        >
          {FONTS.map((f) => <option key={f} value={f}>{f}</option>)}
        </select>
        {font === "Custom" && (
          <input
            value={customFont}
            onChange={(e) => setCustomFont(e.target.value)}
            placeholder="Nombre exacto de la fuente"
            className="w-full mt-2 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
          />
        )}
      </section>

      <div className="flex justify-end gap-2">
        <button className="px-4 py-2 text-sm rounded bg-neutral-700 hover:bg-neutral-600">Editar mapping manual</button>
        <button onClick={handleConfirm} className="px-4 py-2 text-sm rounded bg-accent text-neutral-900 font-semibold">Confirmar</button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Wire wizard into EditorPage**

Overwrite `frontend/src/pages/Editor/EditorPage.tsx`:

```tsx
import { useSearchParams } from "react-router-dom"
import XlsxVerifyWizard from "../Wizard/XlsxVerifyWizard"

export default function EditorPage() {
  const [params, setParams] = useSearchParams()
  const showWizard = params.get("wizard") === "1"

  if (showWizard) {
    return <XlsxVerifyWizard onConfirm={() => setParams({})} />
  }

  return (
    <div className="grid grid-cols-[130px_1fr_320px] h-full">
      <aside className="bg-neutral-900 border-r border-neutral-700 p-2 text-xs">Slides (vacío — M3)</aside>
      <section className="bg-neutral-800 flex items-center justify-center text-neutral-500">Preview (M3)</section>
      <aside className="bg-neutral-900 border-l border-neutral-700 p-3 text-sm">Config (M3)</aside>
    </div>
  )
}
```

- [ ] **Step 5: Run, verify pass**

Run: `cd frontend && npm test`
Expected: all PASS (now ~11+ tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Wizard/XlsxVerifyWizard.tsx frontend/src/pages/Editor/EditorPage.tsx frontend/tests/Wizard.test.tsx
git commit -m "feat(frontend): wizard verificación xlsx con confirmación 1-click + font picker"
```

---

### Task 10: Smoke E2E manual + M2 wrap-up

**Files:** none

- [ ] **Step 1: Full test suite**

Run: `cd frontend && npm test`
Expected: all PASS.

Run: `cd backend && .venv/bin/pytest -v`
Expected: all PASS (M1 still green).

- [ ] **Step 2: Manual smoke**

Terminal A: `make dev-backend`
Terminal B: `make dev-frontend`

Open http://localhost:5173.
- Click "DB (xlsx)" → seleccionar `/Users/joaquincardenas/Downloads/BD Aurora ejemplo.xlsx`
- Click "Template (pptx)" → seleccionar el `template.pptx` armado en M1 (o generar uno con el fixture: `cd backend && .venv/bin/python -c "from tests.conftest import *; import pytest; ..."` — alternativa: armar uno manualmente con 2 slides y `@Titulo`).
- Click "Continuar" → debería navegar a `/editor?wizard=1` y mostrar lista de preguntas + breakdowns + sample size 500.
- Click "Confirmar" → editor stub con 3 columnas.

Expected: full flow works without console errors.

- [ ] **Step 3: Tag**

```bash
git tag m2-frontend-skeleton
git log --oneline | head -20
```

---

## M2 Done When

- Frontend boots con `make dev-frontend`
- Vite proxy `/api` → :8000 funciona
- Welcome page acepta 3 inputs y llama backend
- Wizard muestra preguntas/breakdowns detectados con confidence indicator
- Confirmar avanza a Editor stub
- Topbar muestra tabs + pills DB/Template/Font
- Zustand store maneja state + undo/redo + herencia título separador
- Tests pasan (~15 frontend tests + ~25 backend tests)
- Git tag `m2-frontend-skeleton`
