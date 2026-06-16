# AurumEncuestas

App local web para generar presentaciones PPT editables desde encuestas tabuladas.

## Quick start

```bash
make install
make dev
```

Backend en http://localhost:8000. Docs en http://localhost:8000/docs.

## Estructura

- `backend/` — FastAPI + python-pptx + openpyxl
- `frontend/` — React + Vite (M2)
- `docs/superpowers/specs/` — diseño
- `docs/superpowers/plans/` — plan implementación por milestones

## Env

Copiar `.env.example` a `backend/.env` y completar `ANTHROPIC_API_KEY`.
