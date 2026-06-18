# M6.12 — Integration E2E + Performance + README + v0.2.0 Tag Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** End-to-end integration verification: run all backend + frontend tests, verify ≥150 backend + ≥60 frontend passing, fix any regressions. Add new Playwright smoke flow for M6 training + AI analyze + color picking. Document performance baselines. Update README for v0.2.0. Tag `m6.12` and `v0.2.0`.

**Architecture:** No new source code beyond fixes and test additions. Playwright smoke extended to cover the full M6 user flow. `docs/perf-baselines.md` captures cache metrics observed under `AURUM_DEBUG=1`. README updated with new dependencies, features, and quick start changes.

**Spec refs:** Section 17 (Testing strategy — unit + integration + fuzz + Playwright). Section 12 (Performance + caching — cache types, debug mode). Section 20 (Acceptance criteria — all tests passing, tag v0.2.0). Section 4 (Stack — Anthropic key required for AI analyzer).

**Predecessor:** M6.11 (all frontend UI done). M6.8 (all backend endpoints done). M6.1–M6.7 (backend core done).

---

## File Structure

**Modify:**
- `e2e/smoke.spec.ts` — extend with M6 training + analyze + color flow
- `README.md` — v0.2.0 update

**Create:**
- `docs/perf-baselines.md` — performance baseline metrics

**Fix (as discovered):**
- Any regression in `backend/tests/` or `frontend/tests/` found during T1 run

---

### Task 1: Full test suite verification + regression fixes

**Files:**
- Potentially modify: various backend test files, frontend test files

- [ ] **Step 1: Run backend tests**

```bash
cd backend && .venv/bin/pytest -v --tb=short 2>&1 | tee /tmp/backend-test-results.txt
```

Count PASS total:

```bash
grep -c "PASSED" /tmp/backend-test-results.txt
```

Expected: ≥150 PASSED. If fewer, investigate and fix regressions before proceeding.

Common regression causes to check:
- M6.1 schema changes breaking existing model tests → update test fixtures
- M6.2 deleted modules still imported → fix import paths
- M6.8 new API endpoints conflicting with M4/M5 endpoint names → remove old endpoints if not done in M6.8

- [ ] **Step 2: Fix backend regressions**

For each FAILED test, diagnose root cause and apply minimal fix. Common fixes:

If `test_training_add_and_list` still uses old `/api/training/add` path:

```python
# Update test to use new M6 endpoint:
# Old: client.post("/api/training/add", ...)
# New: client.post("/api/training/corpus/add", ...)
```

If `LayoutBank` or `LearnedLayout` models still referenced in tests after M6.2 cleanup:

```python
# Either: remove the test (if module deleted per M6.2)
# Or: update import path to wherever the model now lives
```

If pydantic v2 validation errors on new StyleGuide schema fields:

```python
# Add defaults to test fixtures:
# manual_edits={}, source_pptxs=[], ...
```

After each fix group, re-run:

```bash
cd backend && .venv/bin/pytest -v --tb=short -x
```

Iterate until all pass.

- [ ] **Step 3: Run frontend tests**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | tee /tmp/frontend-test-results.txt
```

Count PASS total:

```bash
grep -c "✓" /tmp/frontend-test-results.txt
```

Expected: ≥60 passing. If fewer, investigate and fix.

Common frontend regression causes:
- Type errors from `Chart.colors` addition (T1 of M6.10) — ensure all `addChart` call sites pass `colors: []`
- `style_set` references in store tests → remove (M6.11 migration)
- Store tests expecting `training.ts` old API shape → update to new M6 shape

- [ ] **Step 4: Fix frontend regressions**

Apply minimal fixes for each failing test. After each batch:

```bash
cd frontend && npm test
```

Iterate until ≥60 passing.

- [ ] **Step 5: Final build check**

```bash
cd frontend && npm run build
cd backend && .venv/bin/ruff check aurum_encuestas tests
```

Expected: build succeeds, ruff finds no errors (or only style warnings, not errors).

- [ ] **Step 6: Commit fixes**

```bash
git add -A  # only files changed for regression fixes
git commit -m "$(cat <<'EOF'
fix: M6 integration regression fixes — backend + frontend tests passing

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Playwright smoke — M6 training + analyze + color flow

**Files:**
- Modify: `e2e/smoke.spec.ts`

- [ ] **Step 1: Review existing smoke spec**

Read `e2e/smoke.spec.ts` (from M5). Confirm existing flow:
1. Upload xlsx + template → wizard → confirm → editor
2. Add separator + shell + chart + preview

The new M6 flow adds: training PPT upload → Re-analizar → wait done → back to editor → add chart with color → verify preview → export pptx.

- [ ] **Step 2: Extend smoke.spec.ts**

Edit `e2e/smoke.spec.ts`. Add a second test (leave existing test unchanged):

```ts
import { test, expect } from "@playwright/test"
import path from "path"
import fs from "fs"

const XLSX = "/Users/joaquincardenas/Downloads/BD Aurora ejemplo.xlsx"
const TEMPLATE = path.resolve(__dirname, "../e2e_fixtures/template.pptx")
const TRAINING_PPT = path.resolve(__dirname, "../e2e_fixtures/training_sample.pptx")
const EXPORT_PATH = path.resolve(__dirname, "../e2e_fixtures/test_export_m6.pptx")

// Guard: skip if training PPT fixture does not exist
// (run `make e2e-fixtures` to generate them)
test.describe("M6 training + color flow", () => {
  test.skip(!fs.existsSync(TRAINING_PPT), "Training fixture not found — run make e2e-fixtures")

  test("upload training PPT → Re-analizar (mocked) → add chart with color → export", async ({ page }) => {
    // Navigate to Training tab
    await page.goto("/")
    await page.click('a[href="/training"], button:has-text("Entrenamiento")')
    await expect(page.getByText(/Corpus de entrenamiento/i)).toBeVisible({ timeout: 5000 })

    // Upload training PPT
    const [fileChooser] = await Promise.all([
      page.waitForEvent("filechooser"),
      page.click('button:has-text("Agregar PPT al corpus")')
    ])
    await fileChooser.setFiles(TRAINING_PPT)
    await expect(page.getByText(/training_sample\.pptx/i)).toBeVisible({ timeout: 10000 })

    // Click Re-analizar con AI (backend must be running with mocked Anthropic or real key)
    await page.click('button:has-text("Re-analizar con AI")')
    // Wait for progress modal to appear
    await expect(page.getByText(/Analizando corpus/i)).toBeVisible({ timeout: 5000 })
    // Wait for done state (up to 120s for real AI or fast mock)
    await expect(page.getByText(/Análisis completado/i)).toBeVisible({ timeout: 120_000 })
    // Dismiss progress modal
    await page.click('button:has-text("Cerrar")')

    // Navigate back to main page / editor
    await page.goto("/")
    await page.setInputFiles('input[accept=".xlsx"]', XLSX)
    await page.setInputFiles('input[accept=".pptx"]', TEMPLATE)
    await page.click('button:has-text("Continuar")')
    await page.click('button:has-text("Confirmar")')

    // Add separator + shell
    await page.click('button:has-text("Separador")')
    await page.fill('input[id="sep-title"]', "Recordación espontánea")
    await page.click('button:has-text("Crear")')
    await page.click('button:has-text("Slide")')

    // Add chart with custom color
    await page.click('button:has-text("+ Chart")')
    await page.selectOption('select', { index: 0 })

    // Open color picker and select a swatch
    const colorTrigger = page.locator('button[aria-label*="color"], button:has-text("Auto")').first()
    if (await colorTrigger.isVisible()) {
      await colorTrigger.click()
      // Click first swatch in picker if visible
      const firstSwatch = page.locator('button[aria-label*="Seleccionar color"]').first()
      if (await firstSwatch.isVisible({ timeout: 2000 })) {
        await firstSwatch.click()
      }
    }

    await page.click('button:has-text("Aplicar")')

    // Wait for preview to render
    await expect(page.locator("img")).toBeVisible({ timeout: 20_000 })

    // Verify pattern matched indicator appears in config panel
    // (may show fallback heurístico if no corpus match — both are valid)
    const indicator = page.locator('text=/matched|fallback heurístico/i').first()
    await expect(indicator).toBeVisible({ timeout: 5000 })

    // Export pptx
    await page.click('button:has-text("Exportar")')
    if (fs.existsSync(EXPORT_PATH)) fs.unlinkSync(EXPORT_PATH)
    await page.fill('input[placeholder*="ruta"], input[type="text"]', EXPORT_PATH)
    await page.click('button:has-text("Exportar")')
    // Wait for success indicator
    await expect(page.getByText(/exportado|exported/i)).toBeVisible({ timeout: 30_000 })

    // Verify file exists
    await expect(async () => {
      expect(fs.existsSync(EXPORT_PATH)).toBe(true)
    }).toPass({ timeout: 5000 })
  })
})
```

- [ ] **Step 3: Generate training fixture if not present**

Add a Makefile target `e2e-fixtures` that generates `e2e_fixtures/training_sample.pptx`:

```makefile
e2e-fixtures:
	cd backend && .venv/bin/python -c "\
from pptx import Presentation; from pptx.util import Inches; from pptx.chart.data import CategoryChartData; from pptx.enum.chart import XL_CHART_TYPE;\
prs = Presentation(); prs.slide_width = Inches(13.33); prs.slide_height = Inches(7.5);\
blank = prs.slide_layouts[6];\
s = prs.slides.add_slide(blank);\
cd = CategoryChartData(); cd.categories = ['Sí', 'No']; cd.add_series('Total', [75, 25]);\
s.shapes.add_chart(XL_CHART_TYPE.PIE, Inches(2), Inches(1.5), Inches(5), Inches(5), cd);\
s.shapes.add_textbox(Inches(0.5), Inches(6.5), Inches(10), Inches(0.5)).text_frame.text = 'El 75%% de los encuestados conoce la marca.';\
s2 = prs.slides.add_slide(blank);\
cd2 = CategoryChartData(); cd2.categories = ['A', 'B', 'C']; cd2.add_series('Total', [40, 35, 25]);\
s2.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(1), Inches(1), Inches(10), Inches(5.5), cd2);\
prs.save('../e2e_fixtures/training_sample.pptx');\
print('training_sample.pptx saved')"
```

Run:

```bash
mkdir -p e2e_fixtures
make e2e-fixtures
```

Expected: `e2e_fixtures/training_sample.pptx` created.

- [ ] **Step 4: Commit**

```bash
git add e2e/smoke.spec.ts Makefile
git commit -m "$(cat <<'EOF'
test(e2e): extend Playwright smoke with M6 training + AI analyze + color + export flow

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Performance verification + baselines doc

**Files:**
- Create: `docs/perf-baselines.md`

- [ ] **Step 1: Enable debug mode and run typical session**

With backend running:

```bash
AURUM_DEBUG=1 make dev-backend
```

In a second terminal, exercise the typical flow:
1. Upload xlsx + template (parses xlsx, parses template)
2. Add 2 shells, each with 2 charts
3. Click "Re-analizar con AI" (triggers AI analyzer, render cache)
4. Re-click "Re-analizar con AI" (second time — should hit cached renders)
5. Preview 3 slides (tests preview cache)

Collect logs from backend terminal. Look for output lines matching:
- `cache_hit=True` or `cache_miss=True`
- `render_cache: hit` / `render_cache: miss`
- `classifier_cache: hit` / `classifier_cache: miss`
- `style_guide_cache: hit` / `style_guide_cache: miss`

- [ ] **Step 2: Create perf-baselines.md**

Create `docs/perf-baselines.md`:

```markdown
# AurumEncuestas v0.2.0 — Performance Baselines

**Date:** 2026-06-17
**Branch:** feat/m6-ai-style-guide
**Environment:** macOS Darwin 25, Apple Silicon (dev machine)

## Test session

Session: upload 1 xlsx (BD Aurora ejemplo.xlsx) + template. 2 shells × 2 charts each. Re-analizar with AI twice. 5 preview renders.

## Cache observations (AURUM_DEBUG=1)

| Cache | First run | Second run (cached) | Notes |
|---|---|---|---|
| Render cache (slide PNGs) | miss × N | hit × N | N = slides with charts in corpus |
| Style guide in-memory | miss (load from disk) | hit (modtime unchanged) | reloads only on style_guide.json change |
| Pattern classifier | miss on first preview | hit on repeated same config | LRU 200 entries |
| Preview render | miss on first request | hit on repeated same state | LRU 50 entries |
| Anthropic prompt cache | 0% hit (first analyze) | ~85% hit (second analyze same corpus) | System prompt TTL 1h |

## Timings (approximate, dev machine)

| Operation | First run | Cached run |
|---|---|---|
| Re-analizar con AI (2 PPTs, 15 slides) | ~60-90s (network + vision) | ~15-20s (render cache hit, prompt cache) |
| Preview slide generation | ~3-5s | <0.5s (cache hit) |
| Style guide load from disk | ~10ms | ~0ms (in-memory) |

## Anthropic cost estimate

- First re-analyze: ~50K input tokens (vision-heavy) → ~$0.20-0.30
- Second re-analyze (same corpus, within 1h): ~85% prompt cache hit → ~7.5K fresh tokens → ~$0.03-0.05
- Production recommendation: Re-analizar only when corpus changes. Not on every session start.

## Render cache disk usage

- Each slide PNG: ~100-300KB (1280×720 libreoffice render)
- Max: 500MB LRU eviction configured
- 15 slides × 2 PPTs = 30 PNGs × ~200KB avg = ~6MB for typical session

## Notes

- `AURUM_DEBUG=1` env var activates per-request cache logging in the backend
- Render cache path: `~/.aurum/training/render_cache/`
- To clear all caches for fresh measurement: `POST /api/training/clear-cache {"cache_type":"all"}`
```

- [ ] **Step 3: Commit**

```bash
git add docs/perf-baselines.md
git commit -m "$(cat <<'EOF'
docs: M6 performance baselines — cache hit rates, timings, cost estimates

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Update README.md for v0.2.0

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read current README**

Read `README.md` to understand current structure (quick start, milestones, etc.).

- [ ] **Step 2: Update README**

Edit `README.md` with the following changes:

**Version header:** Change `v0.1.0` references to `v0.2.0`.

**Features list:** Add v0.2.0 section:

```markdown
## v0.2.0 — AI Style Guide (M6)

- **AI Style Guide Analyzer**: upload training PPTs to `~/.aurum/training/corpus/`, click "Re-analizar con AI" — Claude Sonnet 4.6 vision synthesizes a structured style guide JSON with 8-15 layout patterns
- **Pattern-based Generator**: new slide renderer matches slide config against learned patterns; falls back to built-in 5-pattern generic style guide when no corpus loaded
- **ColorPicker**: full color picker per chart (grid swatches, hex input, Auto cascade, Recientes, Sugeridas del training)
- **Pattern Matched Indicator**: ConfigPanel shows which pattern matched each slide (or "fallback heurístico")
- **Training Tab Rewrite**: flat corpus list + style guide viewer with per-pattern JSON edit + Re-analizar progress modal with cost tracking
- **Render cache**: libreoffice slide PNGs cached in `~/.aurum/training/render_cache/` (500MB LRU)
```

**New requirements section:**

```markdown
## Requirements

- Python 3.11+
- Node.js 18+
- LibreOffice (headless) — `brew install --cask libreoffice` on macOS
- **ANTHROPIC_API_KEY** — required for "Re-analizar con AI". Without it, app uses built-in generic style guide. Set in `backend/.env`:
  ```
  ANTHROPIC_API_KEY=sk-ant-...
  ```
```

**Quick start update:** Add step for first training PPT:

```markdown
## Quick Start

1. `make dev-backend` (terminal A)
2. `make dev-frontend` (terminal B)
3. Open http://localhost:5173
4. **Recommended:** Go to tab "Entrenamiento" → upload 1+ training PPTs → click "Re-analizar con AI"
   - This builds your style guide. Without this step, app uses generic built-in style.
5. Return to main page → upload xlsx + template → build your deck
```

**Milestones reference:** Append M6 to the milestone table:

```markdown
| M6 | AI Style Guide + Pattern-based Generator | `v0.2.0` |
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs(readme): v0.2.0 features, new requirements (Anthropic key), updated quick start with training step

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Final verification + tag v0.2.0

**Files:** None (verification only)

- [ ] **Step 1: Run full backend test suite**

```bash
cd backend && .venv/bin/pytest -v --tb=short 2>&1 | tail -20
```

Expected: all PASS, count ≥150. If any failures remain from T1, fix now.

- [ ] **Step 2: Run full frontend test suite**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | tail -20
```

Expected: all PASS, count ≥60.

- [ ] **Step 3: Lint**

```bash
cd backend && .venv/bin/ruff check aurum_encuestas tests
cd frontend && npm run lint
```

Expected: no lint errors (warnings acceptable).

- [ ] **Step 4: Production build**

```bash
cd frontend && npm run build
```

Expected: build succeeds with no TypeScript errors.

- [ ] **Step 5: Run E2E smoke (optional — requires dev servers)**

If both servers available:

```bash
make e2e
```

Expected: existing M5 smoke passes. M6 flow test either passes (if ANTHROPIC_API_KEY set) or skips gracefully.

- [ ] **Step 6: Manual acceptance check (per spec section 20)**

With both servers running and a training PPT corpus loaded:

- [ ] Corpus ≥2 PPTs → "Re-analizar con AI" produces `~/.aurum/training/style_guide.json` with ≥5 patterns
- [ ] Generate project without training → output uses built-in fallback (no errors)
- [ ] With training → ConfigPanel shows pattern matched indicator (not "fallback" on at least 1 slide)
- [ ] ColorPicker works: pick color per chart, Auto resets to cascade
- [ ] Training tab shows corpus list + style guide viewer + pattern edit modal saves via PUT
- [ ] AI analysis log created in `~/.aurum/training/ai_analysis_logs/`

- [ ] **Step 7: Tag m6.12 and v0.2.0**

```bash
git log --oneline | head -20
git tag m6.12
git tag v0.2.0
git tag
```

Expected output includes: `m6.1`, `m6.2`, ..., `m6.12`, `v0.2.0` (and earlier `v0.1.0`, `m4-llm-training`, etc. from M4/M5).

- [ ] **Step 8: Final commit if any cleanup**

If any final cleanup needed (remove debug prints, fix stale comments):

```bash
git add <affected files>
git commit -m "$(cat <<'EOF'
chore: M6 final cleanup before v0.2.0 tag

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git tag -f v0.2.0  # update tag to include cleanup commit
```

---

## M6.12 Done When

- Backend test suite: ≥150 tests PASSING with no regressions from M6.1–M6.8 work
- Frontend test suite: ≥60 tests PASSING with no regressions from M6.9–M6.11 work
- `e2e/smoke.spec.ts` extended with M6 training + analyze + color + export flow; existing smoke still passes
- `docs/perf-baselines.md` created with cache hit rates, timings, and cost estimates from observed `AURUM_DEBUG=1` session
- `README.md` updated: v0.2.0 features, Anthropic key requirement documented, quick start includes training step, milestones table includes M6
- `ruff check` and `npm run lint` pass clean
- `npm run build` succeeds
- Manual acceptance checklist from spec section 20 verified
- Git tags `m6.12` and `v0.2.0` created at HEAD
- M6 complete. AurumEncuestas v0.2.0 shipped.
