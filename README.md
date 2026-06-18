# AurumEncuestas v0.2.0

App local web para generar presentaciones PPT editables desde encuestas tabuladas.

## Quick Start

```bash
# Install dependencies
make install

# Terminal 1: Backend
make dev-backend

# Terminal 2: Frontend
make dev-frontend

# Open the app
open http://localhost:5173
```

> **Recommended first step:** Go to tab **"Entrenamiento"** → upload 1+ training PPTs from past projects → click **"Re-analizar con AI"**.
> This builds your style guide (`~/.aurum/training/style_guide.json`) with learned layout patterns.
> Without this step, the app uses the built-in generic style guide (5 patterns, no brand-specific colors).

```bash
# Terminal 3: E2E tests (optional — requires both servers running)
make e2e

# Generate E2E fixtures (training_sample.pptx for M6 smoke test)
make e2e-fixtures
```

- Backend: http://localhost:8000 (API docs: http://localhost:8000/docs)
- Frontend: http://localhost:5173

## Requirements

- Python 3.11+
- Node.js 18+
- **LibreOffice** (headless) — required for training corpus slide rendering
  - macOS: `brew install --cask libreoffice`
  - Linux: `apt-get install libreoffice`
  - Windows: Download from libreoffice.org
- **poppler** (for `pdftoppm`, used in some render paths)
  - macOS: `brew install poppler`
  - Linux: `apt-get install poppler-utils`
- **ANTHROPIC_API_KEY** — required for "Re-analizar con AI". Without it, the app uses the built-in generic style guide. Set in `backend/.env`:
  ```
  ANTHROPIC_API_KEY=sk-ant-...
  ```

## v0.2.0 — AI Style Guide (M6)

- **AI Style Guide Analyzer**: upload training PPTs to `~/.aurum/training/corpus/`, click "Re-analizar con AI" — Claude Sonnet 4.6 vision analyzes slide layouts and synthesizes a structured style guide JSON with 8-15 layout patterns
- **Pattern-based Generator**: new slide renderer matches slide config against learned patterns (chart type, breakdown, n-charts per slide); falls back to built-in 5-pattern generic style guide when no corpus is loaded
- **ColorPicker**: full color picker per chart slot — grid swatches, hex input, Auto cascade (derives from style guide), Recientes (last 5 used), Sugeridas del training (colors extracted from corpus)
- **Pattern Matched Indicator**: ConfigPanel shows which pattern matched each slide (e.g. `binary_general_demographics`) or "fallback heurístico" when using generic style
- **Training Tab Rewrite**: flat corpus list with per-file metadata + style guide viewer with per-pattern JSON edit modal + Re-analizar progress modal with estimated cost tracking + error display
- **Render cache**: libreoffice slide PNGs cached in `~/.aurum/training/render_cache/` (500MB LRU eviction). Second "Re-analizar" on the same corpus skips libreoffice entirely.
- **Anthropic prompt cache**: ~85% token cache hit rate on repeated analysis of the same corpus within 1h (~$0.03-0.05 vs $0.20-0.30 for first run)

## Features (M1-M6 complete)

- **M1**: Parse XLSX heuristic + wizard verification
- **M2**: React editor with slide rail, config panel, preview
- **M3**: PPT generation + charts + analyses (fallback text)
- **M4**: AI-powered analysis generation (Anthropic Haiku)
- **M5**: Layout learning from training PPTs, auto-save, recent projects, E2E tests, docs
- **M6**: AI style guide analyzer, pattern-based renderer, ColorPicker, render cache

## Project structure

- `backend/` — FastAPI + python-pptx + openpyxl + anthropic
- `frontend/` — React + Vite + TypeScript + Tailwind
- `e2e/` — Playwright smoke tests
- `e2e_fixtures/` — PPT and template fixtures for E2E tests
- `docs/` — Feature specs, implementation plans, API reference, perf baselines

## Feature walkthrough (3-input flow)

1. **Train** (recommended): Upload past presentation PPTs → "Re-analizar con AI" → style guide learned
2. **Upload**: Excel file (survey data) + PowerPoint template (branding)
3. **Verify**: Auto-detect questions, breakdowns, sample size → 1-click confirm
4. **Build**: Add separators + slides → add charts (pick question + breakdown + colors) → AI-generate analyses → reorder → export

## Configuration

### Environment (backend/.env)

```env
# Required for AI style guide analysis
ANTHROPIC_API_KEY=sk-ant-...

# Optional: set log level (DEBUG shows cache hit/miss logs)
LOG_LEVEL=DEBUG
```

### AURUM_DEBUG mode

Set `AURUM_DEBUG=1` or `LOG_LEVEL=DEBUG` to activate per-request cache logging:

```
render_cache HIT: {hash}_{idx}.png
render_cache MISS: {hash}_{idx}.png — calling libreoffice
```

See `docs/perf-baselines.md` for observed cache hit rates, timings, and cost estimates.

## Testing

```bash
# Backend unit tests (245 tests)
cd backend && .venv/bin/pytest -v

# Frontend unit tests (115 tests)
cd frontend && npm test

# Lint
cd backend && .venv/bin/ruff check aurum_encuestas tests
cd frontend && npm run lint

# Build frontend
cd frontend && npm run build

# E2E smoke (requires both servers running)
make e2e
```

Expected: 245 backend tests + 115 frontend tests all pass. Build succeeds.

## Architecture highlights

- **AI style guide**: Anthropic claude-sonnet-4-6 vision analyzes corpus slide PNGs → synthesizes JSON patterns
- **Pattern-based renderer**: matches (chart_type, breakdown, n_charts) to learned layout patterns; falls back to built-in generic style when no corpus loaded
- **Render cache**: SHA-256-keyed PNG disk cache (500MB LRU); skips libreoffice on repeated analysis
- **ColorPicker**: per-slot color override with Auto cascade, hex input, and training-derived suggestions
- **Preview rendering**: LibreOffice headless + PIL → PNG thumbnails
- **Auto-save**: every 5s when project path is set
- **Recents**: last 5 projects in dropdown (click to restore full state)

## Milestones

| Milestone | Description | Tag |
|---|---|---|
| M1 | XLSX parsing + wizard | — |
| M2 | React editor + slide builder | — |
| M3 | PPT export with charts | — |
| M4 | AI analysis generation (Haiku) | — |
| M5 | Layout learning, auto-save, recents, E2E, docs | `v0.1.0` |
| M6 | AI Style Guide + Pattern-based Generator + ColorPicker | `v0.2.0` |

See `docs/superpowers/plans/` for detailed implementation plans per milestone.

## Files

- `docs/xlsx-schema.md` — XLSX convention (rows, columns, breakdowns)
- `docs/template-spec.md` — PowerPoint template spec
- `docs/api.md` — Backend API endpoints reference
- `docs/perf-baselines.md` — v0.2.0 performance baselines (cache rates, timings, cost)
