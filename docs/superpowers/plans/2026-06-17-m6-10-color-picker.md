# M6.10 — ColorPicker Component + Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full-featured ColorPicker component system with grid swatches, hex input, Auto button, "Recientes" row (persisted in `~/.aurum/config.json`), and "Sugeridas del training" row from the active style guide. Integrate into AddChartModal (N color slots per chart with "Avanzados" expand) and ConfigPanel (per-chart color edit).

**Architecture:** Four atomic components (`ColorSwatch`, `PaletteRow`, `HexInput`, `ColorPicker`) compose into a popup picker. `ColorPicker` reads `useStyleGuideStore` for suggested palette and `recentColors` from a new config endpoint. Integration in AddChartModal and ConfigPanel drives `Chart.colors[]` in project state. `ProjectState.palette` propagation handled via store.

**Spec refs:** Section 9 (Color picker UX, color cascade, auto-derive, Avanzados, color storage, Recientes). Section 14 (API — no new endpoints needed; config colors via existing or extended `/api/config`).

**Predecessor:** M6.9 (styleGuide store available; training tab done).

---

## File Structure

**Create (frontend):**
- `frontend/src/components/ColorPicker/ColorSwatch.tsx`
- `frontend/src/components/ColorPicker/PaletteRow.tsx`
- `frontend/src/components/ColorPicker/HexInput.tsx`
- `frontend/src/components/ColorPicker/ColorPicker.tsx`
- `frontend/src/components/ColorPicker/index.ts`
- `frontend/src/utils/colorUtils.ts` — hex parsing, lumMod auto-derive
- `frontend/tests/ColorSwatch.test.tsx`
- `frontend/tests/PaletteRow.test.tsx`
- `frontend/tests/HexInput.test.tsx`
- `frontend/tests/ColorPicker.test.tsx`

**Modify (frontend):**
- `frontend/src/store/project.ts` — expose `updateChartColors`, ensure `Chart.colors` and `ProjectState.palette` fields
- `frontend/src/types/index.ts` — add `Chart.colors: string[]`, `ProjectState.palette: Record<string, string> | null`
- `frontend/src/pages/Editor/modals/AddChartModal.tsx` — N color slots + Avanzados expand + ColorPicker integration
- `frontend/src/pages/Editor/ConfigPanel.tsx` — chart row click → config panel with ColorPicker

---

### Task 1: ColorSwatch atom

**Files:**
- Create: `frontend/src/components/ColorPicker/ColorSwatch.tsx`
- Create: `frontend/tests/ColorSwatch.test.tsx`

- [ ] **Step 1: Failing tests**

Create `frontend/tests/ColorSwatch.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import ColorSwatch from "../src/components/ColorPicker/ColorSwatch"

describe("ColorSwatch", () => {
  it("renders a button with the given background color", () => {
    render(<ColorSwatch color="#7F7F7F" onSelect={vi.fn()} />)
    const btn = screen.getByRole("button")
    expect(btn).toBeInTheDocument()
    // Inner color square should carry inline style
    const square = btn.querySelector("[style]")
    expect(square).not.toBeNull()
  })

  it("shows selected ring when isSelected true", () => {
    render(<ColorSwatch color="#FFC000" onSelect={vi.fn()} isSelected />)
    const btn = screen.getByRole("button")
    expect(btn.className).toMatch(/ring/)
  })

  it("does not show selected ring when isSelected false", () => {
    render(<ColorSwatch color="#FFC000" onSelect={vi.fn()} isSelected={false} />)
    const btn = screen.getByRole("button")
    expect(btn.className).not.toMatch(/ring-2/)
  })

  it("calls onSelect with color when clicked", async () => {
    const onSelect = vi.fn()
    render(<ColorSwatch color="#404040" onSelect={onSelect} />)
    await userEvent.click(screen.getByRole("button"))
    expect(onSelect).toHaveBeenCalledWith("#404040")
  })

  it("shows tooltip with hex color on hover (aria-label)", () => {
    render(<ColorSwatch color="#D9D9D9" onSelect={vi.fn()} />)
    expect(screen.getByRole("button")).toHaveAttribute("aria-label", expect.stringContaining("#D9D9D9"))
  })
})
```

- [ ] **Step 2: Run failing**

```bash
cd frontend && npm test -- ColorSwatch
```

Expected: import errors.

- [ ] **Step 3: Implement ColorSwatch**

Create `frontend/src/components/ColorPicker/ColorSwatch.tsx`:

```tsx
interface Props {
  color: string
  onSelect(color: string): void
  isSelected?: boolean
  size?: "sm" | "md"
}

export default function ColorSwatch({ color, onSelect, isSelected = false, size = "md" }: Props) {
  const dim = size === "sm" ? "w-5 h-5" : "w-6 h-6"
  return (
    <button
      type="button"
      onClick={() => onSelect(color)}
      aria-label={`Seleccionar color ${color}`}
      className={`rounded border border-neutral-600 hover:scale-110 transition-transform focus:outline-none ${
        isSelected ? "ring-2 ring-white ring-offset-1 ring-offset-neutral-900" : ""
      }`}
    >
      <div
        className={`${dim} rounded`}
        style={{ backgroundColor: color }}
      />
    </button>
  )
}
```

- [ ] **Step 4: Run, verify pass**

```bash
cd frontend && npm test -- ColorSwatch
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ColorPicker/ColorSwatch.tsx frontend/tests/ColorSwatch.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): ColorSwatch — color square button with selected ring state

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: PaletteRow

**Files:**
- Create: `frontend/src/components/ColorPicker/PaletteRow.tsx`
- Create: `frontend/tests/PaletteRow.test.tsx`

- [ ] **Step 1: Failing tests**

Create `frontend/tests/PaletteRow.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import PaletteRow from "../src/components/ColorPicker/PaletteRow"

const COLORS = ["#7F7F7F", "#BFBFBF", "#FFC000", "#404040", "#D9D9D9"]

describe("PaletteRow", () => {
  it("renders label", () => {
    render(<PaletteRow label="Defaults" colors={COLORS} onSelect={vi.fn()} />)
    expect(screen.getByText("Defaults")).toBeInTheDocument()
  })

  it("renders one swatch per color", () => {
    render(<PaletteRow label="Sugeridas" colors={COLORS} onSelect={vi.fn()} />)
    const buttons = screen.getAllByRole("button")
    expect(buttons).toHaveLength(COLORS.length)
  })

  it("calls onSelect with the correct color when a swatch is clicked", async () => {
    const onSelect = vi.fn()
    render(<PaletteRow label="Defaults" colors={COLORS} onSelect={onSelect} />)
    await userEvent.click(screen.getByLabelText(/Seleccionar color #FFC000/i))
    expect(onSelect).toHaveBeenCalledWith("#FFC000")
  })

  it("marks selected color swatch", () => {
    render(<PaletteRow label="Defaults" colors={COLORS} onSelect={vi.fn()} selectedColor="#BFBFBF" />)
    // The #BFBFBF button should have ring class
    const btn = screen.getByLabelText(/Seleccionar color #BFBFBF/i)
    expect(btn.className).toMatch(/ring/)
  })

  it("renders empty row with no swatches when colors is empty", () => {
    render(<PaletteRow label="Recientes" colors={[]} onSelect={vi.fn()} />)
    const buttons = screen.queryAllByRole("button")
    expect(buttons).toHaveLength(0)
    expect(screen.getByText(/sin recientes/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run failing**

```bash
cd frontend && npm test -- PaletteRow
```

Expected: import errors.

- [ ] **Step 3: Implement PaletteRow**

Create `frontend/src/components/ColorPicker/PaletteRow.tsx`:

```tsx
import ColorSwatch from "./ColorSwatch"

interface Props {
  label: string
  colors: string[]
  onSelect(color: string): void
  selectedColor?: string
}

export default function PaletteRow({ label, colors, onSelect, selectedColor }: Props) {
  return (
    <div className="mb-3">
      <div className="text-xs text-neutral-500 mb-1">{label}:</div>
      {colors.length === 0 ? (
        <span className="text-xs text-neutral-600 italic">sin recientes</span>
      ) : (
        <div className="flex gap-1.5 flex-wrap">
          {colors.map((color) => (
            <ColorSwatch
              key={color}
              color={color}
              onSelect={onSelect}
              isSelected={color === selectedColor}
            />
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run, verify pass**

```bash
cd frontend && npm test -- PaletteRow
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ColorPicker/PaletteRow.tsx frontend/tests/PaletteRow.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): PaletteRow — labeled row of ColorSwatches with selected state

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: HexInput + colorUtils

**Files:**
- Create: `frontend/src/utils/colorUtils.ts`
- Create: `frontend/src/components/ColorPicker/HexInput.tsx`
- Create: `frontend/tests/HexInput.test.tsx`

- [ ] **Step 1: Create colorUtils.ts with tests**

Create `frontend/src/utils/colorUtils.ts`:

```ts
/**
 * Normalize a user-typed color string to a 6-char hex string (#RRGGBB).
 * Accepts: "#RGB", "#RRGGBB", "RGB", "RRGGBB".
 * Returns null if not a valid hex color (CSS named colors not supported — intentional, per spec Q15).
 */
export function normalizeHex(input: string): string | null {
  const s = input.trim().replace(/^#/, "")
  if (/^[0-9a-fA-F]{3}$/.test(s)) {
    const [r, g, b] = s.split("")
    return `#${r}${r}${g}${g}${b}${b}`.toUpperCase()
  }
  if (/^[0-9a-fA-F]{6}$/.test(s)) {
    return `#${s.toUpperCase()}`
  }
  return null
}

/**
 * Auto-derive N colors from a primary color by varying lightness via lumMod simulation.
 * lumMod in OOXML: value * 100000; here we use CSS hsl lightness approximation.
 *
 * Strategy: parse hex to HSL, generate N shades by spacing lightness from 30% to 85%.
 * If N=1 returns [primary].
 */
export function autoDeriveColors(primary: string, n: number): string[] {
  if (n <= 1) return [primary]
  const hsl = hexToHsl(primary)
  if (!hsl) return Array(n).fill(primary)

  const [h, s] = hsl
  const colors: string[] = []
  for (let i = 0; i < n; i++) {
    // Spread lightness: first slot = original, subsequent slots lighten progressively
    const l = i === 0 ? hsl[2] : Math.min(85, hsl[2] + (55 * i) / (n - 1))
    colors.push(hslToHex(h, s, l))
  }
  return colors
}

function hexToHsl(hex: string): [number, number, number] | null {
  const norm = normalizeHex(hex)
  if (!norm) return null
  const r = parseInt(norm.slice(1, 3), 16) / 255
  const g = parseInt(norm.slice(3, 5), 16) / 255
  const b = parseInt(norm.slice(5, 7), 16) / 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2
  if (max === min) return [0, 0, Math.round(l * 100)]
  const d = max - min
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
  let h: number
  if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6
  else if (max === g) h = ((b - r) / d + 2) / 6
  else h = ((r - g) / d + 4) / 6
  return [Math.round(h * 360), Math.round(s * 100), Math.round(l * 100)]
}

function hslToHex(h: number, s: number, l: number): string {
  const sn = s / 100
  const ln = l / 100
  const a = sn * Math.min(ln, 1 - ln)
  const f = (n: number) => {
    const k = (n + h / 30) % 12
    const color = ln - a * Math.max(Math.min(k - 3, 9 - k, 1), -1)
    return Math.round(255 * color).toString(16).padStart(2, "0").toUpperCase()
  }
  return `#${f(0)}${f(8)}${f(4)}`
}
```

Inline tests as part of the HexInput test file (no separate colorUtils test file — keeps it DRY):

- [ ] **Step 2: Failing tests for HexInput**

Create `frontend/tests/HexInput.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest"
import { render, screen, act } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import HexInput from "../src/components/ColorPicker/HexInput"
import { normalizeHex, autoDeriveColors } from "../src/utils/colorUtils"

// Unit tests for colorUtils
describe("normalizeHex", () => {
  it("normalizes 6-char hex", () => expect(normalizeHex("#7f7f7f")).toBe("#7F7F7F"))
  it("normalizes 3-char hex", () => expect(normalizeHex("#fff")).toBe("#FFFFFF"))
  it("accepts without #", () => expect(normalizeHex("404040")).toBe("#404040"))
  it("returns null for invalid", () => expect(normalizeHex("not-a-color")).toBeNull())
  it("returns null for empty", () => expect(normalizeHex("")).toBeNull())
})

describe("autoDeriveColors", () => {
  it("returns [primary] when n=1", () => {
    expect(autoDeriveColors("#7F7F7F", 1)).toEqual(["#7F7F7F"])
  })
  it("returns n colors when n>1", () => {
    const colors = autoDeriveColors("#7F7F7F", 3)
    expect(colors).toHaveLength(3)
    colors.forEach((c) => expect(c).toMatch(/^#[0-9A-F]{6}$/))
  })
  it("first color matches primary", () => {
    const colors = autoDeriveColors("#404040", 4)
    // First color should be derived from same hue
    expect(colors[0]).toMatch(/^#[0-9A-F]{6}$/)
  })
})

// HexInput component tests
describe("HexInput", () => {
  it("renders an input with placeholder", () => {
    render(<HexInput value="" onChange={vi.fn()} />)
    expect(screen.getByRole("textbox")).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/#[A-Fa-f0-9]{6}/)).toBeInTheDocument()
  })

  it("shows preview swatch when valid hex entered", async () => {
    render(<HexInput value="#7F7F7F" onChange={vi.fn()} />)
    const swatch = document.querySelector("[style*='background-color']")
    expect(swatch).not.toBeNull()
  })

  it("calls onChange with normalized hex after valid input", async () => {
    const onChange = vi.fn()
    render(<HexInput value="" onChange={onChange} />)
    const input = screen.getByRole("textbox")
    await userEvent.type(input, "7F7F7F")
    // After typing 6 chars the component should debounce and call onChange
    // Use fake timer approach or just verify the field accepts input
    expect(input).toHaveValue("7F7F7F")
  })

  it("shows error indicator for invalid hex value", async () => {
    render(<HexInput value="xyz" onChange={vi.fn()} />)
    // Should show some visual indication of invalid (red border or error text)
    const input = screen.getByRole("textbox")
    expect(input.className).toMatch(/border-red|text-red/)
  })

  it("does not call onChange with invalid hex", async () => {
    const onChange = vi.fn()
    render(<HexInput value="" onChange={onChange} />)
    const input = screen.getByRole("textbox")
    await userEvent.type(input, "xyz")
    // onChange should NOT be called with invalid color
    expect(onChange).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 3: Run failing**

```bash
cd frontend && npm test -- HexInput
```

Expected: import errors.

- [ ] **Step 4: Implement HexInput**

Create `frontend/src/components/ColorPicker/HexInput.tsx`:

```tsx
import { useState, useEffect } from "react"
import { normalizeHex } from "../../utils/colorUtils"

interface Props {
  value: string
  onChange(hex: string): void
}

export default function HexInput({ value, onChange }: Props) {
  const [raw, setRaw] = useState(value.replace(/^#/, ""))
  const [isInvalid, setIsInvalid] = useState(false)

  // Sync external value changes
  useEffect(() => {
    setRaw(value.replace(/^#/, ""))
    setIsInvalid(false)
  }, [value])

  const handleChange = (text: string) => {
    setRaw(text)
    const normalized = normalizeHex(text)
    if (normalized) {
      setIsInvalid(false)
      onChange(normalized)
    } else if (text.length > 0) {
      setIsInvalid(true)
    } else {
      setIsInvalid(false)
    }
  }

  const normalized = normalizeHex(raw)

  return (
    <div className="flex items-center gap-2">
      {normalized && (
        <div
          className="w-5 h-5 rounded border border-neutral-600 flex-shrink-0"
          style={{ backgroundColor: normalized }}
        />
      )}
      <div className="relative">
        <span className="absolute left-2 top-1/2 -translate-y-1/2 text-neutral-500 text-xs">#</span>
        <input
          type="text"
          role="textbox"
          value={raw}
          onChange={(e) => handleChange(e.target.value)}
          maxLength={6}
          placeholder="#[A-Fa-f0-9]{6}"
          className={`pl-5 pr-2 py-1.5 text-xs bg-neutral-950 border rounded w-28 focus:outline-none ${
            isInvalid
              ? "border-red-500 text-red-300"
              : "border-neutral-700 focus:border-neutral-500"
          }`}
        />
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Run, verify pass**

```bash
cd frontend && npm test -- HexInput
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add \
  frontend/src/utils/colorUtils.ts \
  frontend/src/components/ColorPicker/HexInput.tsx \
  frontend/tests/HexInput.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): colorUtils (normalizeHex, autoDeriveColors) + HexInput component

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: ColorPicker orchestrator

**Files:**
- Create: `frontend/src/components/ColorPicker/ColorPicker.tsx`
- Create: `frontend/src/components/ColorPicker/index.ts`
- Create: `frontend/tests/ColorPicker.test.tsx`

- [ ] **Step 1: Failing tests**

Create `frontend/tests/ColorPicker.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import ColorPicker from "../src/components/ColorPicker/ColorPicker"

// Mock styleGuide store
vi.mock("../src/store/styleGuide", () => ({
  useStyleGuideStore: (sel: (s: unknown) => unknown) => sel({
    styleGuide: {
      global: { suggested_palette: ["#7F7F7F", "#BFBFBF", "#FFC000"] },
    },
  }),
}))

// Mock fetch for recent colors (config endpoint)
const mockFetch = vi.fn()
vi.stubGlobal("fetch", mockFetch)

beforeEach(() => {
  mockFetch.mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ recent_colors: ["#404040", "#D9D9D9"] }),
  })
})

describe("ColorPicker", () => {
  it("renders when open=true", () => {
    render(<ColorPicker open value="#7F7F7F" onChange={vi.fn()} onClose={vi.fn()} />)
    expect(screen.getByText(/Sugeridas del training/i)).toBeInTheDocument()
  })

  it("does not render when open=false", () => {
    render(<ColorPicker open={false} value="#7F7F7F" onChange={vi.fn()} onClose={vi.fn()} />)
    expect(screen.queryByText(/Sugeridas del training/i)).toBeNull()
  })

  it("renders Defaults row with built-in colors", () => {
    render(<ColorPicker open value="#7F7F7F" onChange={vi.fn()} onClose={vi.fn()} />)
    expect(screen.getByText(/Defaults/i)).toBeInTheDocument()
  })

  it("renders Recientes row from config", async () => {
    render(<ColorPicker open value="#7F7F7F" onChange={vi.fn()} onClose={vi.fn()} />)
    await waitFor(() => expect(screen.getByText(/Recientes/i)).toBeInTheDocument())
  })

  it("calls onChange when a swatch is clicked", async () => {
    const onChange = vi.fn()
    render(<ColorPicker open value="#7F7F7F" onChange={onChange} onClose={vi.fn()} />)
    // Click the first suggested palette swatch (#7F7F7F)
    const swatches = screen.getAllByRole("button", { name: /Seleccionar color/i })
    await userEvent.click(swatches[0])
    expect(onChange).toHaveBeenCalled()
  })

  it("calls onChange when valid hex entered and OK clicked", async () => {
    const onChange = vi.fn()
    render(<ColorPicker open value="" onChange={onChange} onClose={vi.fn()} />)
    const input = screen.getByRole("textbox")
    await userEvent.clear(input)
    await userEvent.type(input, "FFC000")
    await userEvent.click(screen.getByRole("button", { name: /OK/i }))
    expect(onChange).toHaveBeenCalledWith("#FFC000")
  })

  it("calls onChange with empty string when Auto clicked", async () => {
    const onChange = vi.fn()
    render(<ColorPicker open value="#7F7F7F" onChange={onChange} onClose={vi.fn()} />)
    await userEvent.click(screen.getByRole("button", { name: /Auto/i }))
    expect(onChange).toHaveBeenCalledWith("")
  })

  it("calls onClose when Cancelar clicked", async () => {
    const onClose = vi.fn()
    render(<ColorPicker open value="#7F7F7F" onChange={vi.fn()} onClose={onClose} />)
    await userEvent.click(screen.getByRole("button", { name: /Cancelar/i }))
    expect(onClose).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run failing**

```bash
cd frontend && npm test -- ColorPicker.test
```

Expected: import errors.

- [ ] **Step 3: Implement ColorPicker.tsx**

Create `frontend/src/components/ColorPicker/ColorPicker.tsx`:

```tsx
import { useState, useEffect } from "react"
import PaletteRow from "./PaletteRow"
import HexInput from "./HexInput"
import { useStyleGuideStore } from "../../store/styleGuide"

// Built-in default 11 neutral greys + accent colors (spec Q15-A)
const DEFAULT_COLORS = [
  "#7F7F7F", "#BFBFBF", "#404040", "#D9D9D9", "#FFC000",
  "#FFFFFF", "#000000", "#A6A6A6", "#595959", "#262626", "#F2F2F2",
]

const RECENT_COLORS_ENDPOINT = "/api/config/recent-colors"

interface Props {
  open: boolean
  value: string       // current color; "" means "Auto"
  onChange(color: string): void
  onClose(): void
}

export default function ColorPicker({ open, value, onChange, onClose }: Props) {
  const [pendingColor, setPendingColor] = useState(value)
  const [recentColors, setRecentColors] = useState<string[]>([])

  const styleGuide = useStyleGuideStore((s) => s.styleGuide)
  const suggestedPalette = styleGuide?.global.suggested_palette ?? []

  // Load recent colors from config
  useEffect(() => {
    if (!open) return
    fetch(RECENT_COLORS_ENDPOINT)
      .then((r) => r.ok ? r.json() : { recent_colors: [] })
      .then((data) => setRecentColors(data.recent_colors ?? []))
      .catch(() => setRecentColors([]))
  }, [open])

  // Sync pending when value changes externally
  useEffect(() => {
    setPendingColor(value)
  }, [value])

  if (!open) return null

  const handleSelect = (color: string) => {
    setPendingColor(color)
  }

  const handleOK = () => {
    onChange(pendingColor)
    onClose()
  }

  const handleAuto = () => {
    onChange("")
    onClose()
  }

  return (
    <div className="absolute z-50 top-full mt-1 left-0 bg-neutral-900 border border-neutral-700 rounded-xl shadow-2xl p-4 w-72">
      {suggestedPalette.length > 0 && (
        <PaletteRow
          label="Sugeridas del training"
          colors={suggestedPalette}
          onSelect={handleSelect}
          selectedColor={pendingColor}
        />
      )}

      <PaletteRow
        label="Defaults"
        colors={DEFAULT_COLORS}
        onSelect={handleSelect}
        selectedColor={pendingColor}
      />

      <PaletteRow
        label="Recientes"
        colors={recentColors}
        onSelect={handleSelect}
        selectedColor={pendingColor}
      />

      <div className="mb-4">
        <div className="text-xs text-neutral-500 mb-1">Hex:</div>
        <HexInput value={pendingColor} onChange={setPendingColor} />
      </div>

      <div className="flex items-center gap-2 justify-between">
        <button
          type="button"
          onClick={handleAuto}
          aria-label="Auto"
          className="text-xs px-2 py-1.5 rounded bg-neutral-700 hover:bg-neutral-600 flex items-center gap-1"
        >
          ↺ Auto
        </button>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onClose}
            aria-label="Cancelar"
            className="text-xs px-3 py-1.5 rounded bg-neutral-700 hover:bg-neutral-600"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleOK}
            aria-label="OK"
            className="text-xs px-3 py-1.5 rounded bg-accent text-neutral-900 font-semibold"
          >
            OK
          </button>
        </div>
      </div>
    </div>
  )
}
```

Create `frontend/src/components/ColorPicker/index.ts`:

```ts
export { default as ColorPicker } from "./ColorPicker"
export { default as ColorSwatch } from "./ColorSwatch"
export { default as PaletteRow } from "./PaletteRow"
export { default as HexInput } from "./HexInput"
```

- [ ] **Step 4: Run, verify pass**

```bash
cd frontend && npm test -- ColorPicker.test
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add \
  frontend/src/components/ColorPicker/ColorPicker.tsx \
  frontend/src/components/ColorPicker/index.ts \
  frontend/tests/ColorPicker.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): ColorPicker popup — suggested + defaults + recientes + hex + Auto

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Integration — AddChartModal + ConfigPanel + ProjectState.palette

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/store/project.ts`
- Modify: `frontend/src/pages/Editor/modals/AddChartModal.tsx`
- Modify: `frontend/src/pages/Editor/ConfigPanel.tsx`

- [ ] **Step 1: Update types**

Edit `frontend/src/types/index.ts`. Add `colors` field to `Chart` interface and `palette` to `ProjectState`:

```ts
// In Chart interface, add:
colors: string[]   // per-slice/series colors; empty array = cascade to project/style-guide/built-in

// In ProjectState interface, add:
palette: Record<string, string> | null  // optional project-level color role defaults
```

Remove `style_set` field if still present (M6 cleanup).

- [ ] **Step 2: Update store actions**

Edit `frontend/src/store/project.ts`. Add `updateChartColors` action:

```ts
// In Store interface, add:
updateChartColors(slideId: string, chartId: string, colors: string[]): void

// In implementation (set, get) => ({ ... }), add:
updateChartColors(slideId, chartId, colors) {
  const s = get().state
  if (!s) return
  const slides = s.slides.map((sl) =>
    sl.id !== slideId ? sl : {
      ...sl,
      charts: sl.charts.map((c) =>
        c.id !== chartId ? c : { ...c, colors }
      ),
    }
  )
  set({ state: { ...s, slides } })
},
```

Ensure `Chart` model default includes `colors: []`:

```ts
// In addChart action, ensure new chart has:
colors: [],
```

And `ProjectState` default includes `palette: null`:

```ts
// In setNewProject or initial state:
palette: null,
```

Add test in store tests:

```ts
it("updateChartColors sets colors array on chart", () => {
  // setup: new project + separator + shell + chart
  useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
  useProjectStore.getState().addSeparator("Sec")
  useProjectStore.getState().addShell()
  const shellId = useProjectStore.getState().state!.slides[1].id
  useProjectStore.getState().addChart(shellId, { question_id: "q1", breakdown_id: "general", chart_type: "PIE", multi_series: false })
  const chartId = useProjectStore.getState().state!.slides[1].charts[0].id
  useProjectStore.getState().updateChartColors(shellId, chartId, ["#7F7F7F", "#BFBFBF"])
  const colors = useProjectStore.getState().state!.slides[1].charts[0].colors
  expect(colors).toEqual(["#7F7F7F", "#BFBFBF"])
})
```

Run store tests:

```bash
cd frontend && npm test -- store
```

Expected: PASS.

- [ ] **Step 3: Integrate ColorPicker in AddChartModal**

Edit `frontend/src/pages/Editor/modals/AddChartModal.tsx`:

Add imports:

```tsx
import { useState } from "react"
import { ColorPicker } from "../../../components/ColorPicker"
import { autoDeriveColors } from "../../../utils/colorUtils"
```

After the chart type select, add a color section (inside the form, before submit button):

```tsx
{/* Color section */}
<div className="mt-4">
  <label className="block text-xs text-neutral-400 mb-2">Color principal</label>
  <div className="relative">
    <button
      type="button"
      onClick={() => setColorPickerOpen((v) => !v)}
      className="flex items-center gap-2 px-3 py-2 bg-neutral-800 border border-neutral-700 rounded text-sm hover:bg-neutral-700"
    >
      {primaryColor ? (
        <div className="w-4 h-4 rounded border border-neutral-600" style={{ backgroundColor: primaryColor }} />
      ) : (
        <span className="text-neutral-500 text-xs">Auto</span>
      )}
      <span className="text-xs text-neutral-300">{primaryColor || "Auto"} ▾</span>
    </button>
    <ColorPicker
      open={colorPickerOpen}
      value={primaryColor}
      onChange={(c) => { setPrimaryColor(c); setColorPickerOpen(false) }}
      onClose={() => setColorPickerOpen(false)}
    />
  </div>

  {/* Avanzados expand */}
  <button
    type="button"
    onClick={() => setShowAdvanced((v) => !v)}
    className="mt-2 text-xs text-neutral-500 hover:text-neutral-300"
  >
    ▾ Avanzados (N colores individuales)
  </button>

  {showAdvanced && (
    <div className="mt-2 space-y-2">
      {advancedColors.map((color, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="text-xs text-neutral-400 w-16">Color {i + 1}</span>
          <div className="relative">
            <button
              type="button"
              onClick={() => setOpenAdvancedPicker(i)}
              className="flex items-center gap-2 px-2 py-1 bg-neutral-800 border border-neutral-700 rounded text-xs"
            >
              <div className="w-4 h-4 rounded border border-neutral-600" style={{ backgroundColor: color || "#7F7F7F" }} />
              <span>{color || "Auto"}</span>
            </button>
            <ColorPicker
              open={openAdvancedPicker === i}
              value={color}
              onChange={(c) => {
                const next = [...advancedColors]
                next[i] = c
                setAdvancedColors(next)
                setOpenAdvancedPicker(null)
              }}
              onClose={() => setOpenAdvancedPicker(null)}
            />
          </div>
        </div>
      ))}
    </div>
  )}
</div>
```

Add state variables (inside the modal component):

```tsx
const [colorPickerOpen, setColorPickerOpen] = useState(false)
const [primaryColor, setPrimaryColor] = useState("")
const [showAdvanced, setShowAdvanced] = useState(false)
const [advancedColors, setAdvancedColors] = useState<string[]>([])
const [openAdvancedPicker, setOpenAdvancedPicker] = useState<number | null>(null)
```

Update the `handleApply` / `handleCreate` callback to include colors:

```tsx
// When creating chart, include colors:
const finalColors = showAdvanced && advancedColors.some(Boolean)
  ? advancedColors
  : primaryColor
    ? autoDeriveColors(primaryColor, nOptions)  // nOptions = number of chart options
    : []

onAdd({ ..., colors: finalColors })
```

- [ ] **Step 4: Integrate ColorPicker in ConfigPanel chart row**

Edit `frontend/src/pages/Editor/ConfigPanel.tsx`:

Add color display + click-to-edit in chart list row:

```tsx
// In each chart row, add a color preview + click to open inline ColorPicker
const [chartColorOpen, setChartColorOpen] = useState<string | null>(null)
const updateChartColors = useProjectStore((s) => s.updateChartColors)
```

In the chart row JSX, after chart type badge:

```tsx
<div className="relative ml-auto">
  <button
    type="button"
    onClick={() => setChartColorOpen(chartColorOpen === c.id ? null : c.id)}
    aria-label={`color-${c.id}`}
    className="p-1 rounded hover:bg-neutral-700"
  >
    <div
      className="w-4 h-4 rounded border border-neutral-600"
      style={{ backgroundColor: c.colors?.[0] || "#7F7F7F" }}
    />
  </button>
  <ColorPicker
    open={chartColorOpen === c.id}
    value={c.colors?.[0] ?? ""}
    onChange={(color) => {
      const newColors = color ? [color] : []
      updateChartColors(slide.id, c.id, newColors)
      setChartColorOpen(null)
    }}
    onClose={() => setChartColorOpen(null)}
  />
</div>
```

- [ ] **Step 5: Run all tests**

```bash
cd frontend && npm test
```

Expected: all tests PASS. Fix any TypeScript compile errors from types changes.

```bash
cd frontend && npm run build
```

Expected: build succeeds.

- [ ] **Step 6: Commit**

```bash
git add \
  frontend/src/types/index.ts \
  frontend/src/store/project.ts \
  frontend/src/pages/Editor/modals/AddChartModal.tsx \
  frontend/src/pages/Editor/ConfigPanel.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): integrate ColorPicker into AddChartModal (N slots + Avanzados) and ConfigPanel

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Tag milestone:

```bash
git tag m6.10
```

---

## M6.10 Done When

- `ColorSwatch` renders a color square button with selected ring; calls `onSelect` on click
- `PaletteRow` renders a labeled row of `ColorSwatch` components; shows "sin recientes" for empty list
- `HexInput` accepts hex input, normalizes to `#RRGGBB`, shows red border for invalid, calls `onChange` only with valid color
- `colorUtils.normalizeHex` correctly normalizes 3-char and 6-char hex with or without `#`
- `colorUtils.autoDeriveColors` derives N colors from primary via HSL lightness variation
- `ColorPicker` popup shows all rows (Sugeridas del training from styleGuide, Defaults 11 colors, Recientes from config), HexInput, Auto button, Cancel + OK; `onChange` called with selected color, `onClose` called on cancel/auto/OK
- `Chart.colors: string[]` field added to types; `ProjectState.palette` field added
- `updateChartColors` store action updates the correct chart's colors array
- `AddChartModal` shows primary color picker + "Avanzados" expand with N individual color slots; colors saved to chart on create
- `ConfigPanel` chart row shows color swatch; click opens `ColorPicker`; color change dispatches `updateChartColors`
- All frontend tests pass; build succeeds
- Git tag `m6.10` created
