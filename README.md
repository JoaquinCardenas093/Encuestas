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

## Frontend

```bash
make frontend-install
make dev-frontend
```

App en http://localhost:5173. Proxy `/api/*` → http://localhost:8000.

Para correr todo: en una terminal `make dev-backend`, en otra `make dev-frontend`.

## Env

Para usar análisis con AI (M4+): copiá `.env.example` a `backend/.env` y completá `ANTHROPIC_API_KEY`. Sin esto, la app funciona pero los análisis devuelven texto fallback editable.
