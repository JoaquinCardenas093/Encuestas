# AurumEncuestas v0.1.0

App local web para generar presentaciones PPT editables desde encuestas tabuladas.

## Quick start

```bash
# Install dependencies
make install

# Terminal 1: Backend
make dev-backend

# Terminal 2: Frontend (new terminal)
make dev-frontend

# Terminal 3: E2E tests (optional, requires backend + frontend running)
make e2e
```

- Backend: http://localhost:8000 (API docs: http://localhost:8000/docs)
- Frontend: http://localhost:5173

## System requirements

- Python 3.11+
- Node 18+
- LibreOffice (for rendering previews)
  - macOS: `brew install libreoffice`
  - Linux: `apt-get install libreoffice`
  - Windows: Download from libreoffice.org

## Project structure

- `backend/` — FastAPI + python-pptx + openpyxl
- `frontend/` — React + Vite + TypeScript
- `e2e/` — Playwright smoke tests
- `docs/` — Feature specs, implementation plans, API reference

## Feature walkthrough (3-input flow)

1. **Upload**: Excel file (survey data) + PowerPoint template (branding)
2. **Verify**: Auto-detect questions, breakdowns, sample size → 1-click confirm
3. **Build**: Add separators + slides → add charts (auto-detect Q + breakdown) → AI-generate analyses (optional) → reorder → export

## Features (M1-M5 complete)

- **M1**: Parse XLSX heuristic + wizard verification
- **M2**: React editor with slide rail, config panel, preview
- **M3**: PPT generation + charts + analyses (fallback text)
- **M4**: AI-powered analysis generation (Anthropic Haiku)
- **M5**: Layout learning from training PPTs, auto-save, recent projects, E2E tests, docs

## Configuration

### Environment

Create `backend/.env` for AI analysis (optional):

```
ANTHROPIC_API_KEY=sk-ant-...
```

Without this, analyses use fallback placeholder text (still editable in PPT).

### Layout training

1. Open app → "Entrenamiento" tab
2. Upload PPT files you've manually designed
3. App learns layouts from these → uses them when matching new projects
4. View learned layouts in "Ver layouts aprendidos"

## Files

- `docs/xlsx-schema.md` — XLSX convention (rows, columns, breakdowns)
- `docs/template-spec.md` — PowerPoint template spec
- `docs/api.md` — Backend API endpoints reference

## Testing

```bash
# Backend unit tests
cd backend && .venv/bin/pytest -v

# Frontend unit tests
cd frontend && npm test

# Build frontend
cd frontend && npm run build

# E2E smoke (requires servers running)
make e2e
```

Expected: ~70 backend tests + 38 frontend tests all pass.

## Architecture highlights

- **Layout matching**: Bank signature-based → heuristic fallback
- **Preview rendering**: LibreOffice Calc + PIL screen capture
- **Auto-save**: Every 5s when path is known
- **Recents**: Last 5 projects in dropdown (click to load)
- **Font override**: User-selected font applied to all analyses + charts in output

## Milestones

- **M1** (Jan 2025): XLSX parsing + wizard
- **M2** (Feb 2025): React editor + slide builder
- **M3** (Feb 2025): PPT export with charts
- **M4** (Mar 2025): AI analysis generation (Haiku)
- **M5** (Jun 2025): Polish — layout learning, auto-save, recents, E2E, docs

See `docs/superpowers/plans/` for detailed implementation specs.
