# Backend API

Base: `http://localhost:8000`

| Method | Path | Body / Form | Response |
|---|---|---|---|
| GET | `/api/health` | — | `{status: "ok"}` |
| POST | `/api/parse-xlsx` | multipart `file` | `ParsedDB` |
| POST | `/api/parse-template` | multipart `file` | `TemplateInfo` |
| POST | `/api/save-project` | `{path, state: ProjectState}` | `{saved, path}` |
| POST | `/api/load-project` | `{path}` | `ProjectState` |
| GET | `/api/recents` | — | `{recents: [...]}` |
| POST | `/api/preview-slide` | `{state, slide_index}` | `{png_base64}` |
| POST | `/api/export-pptx` | `{state, path}` | `{exported, path, size}` |
| POST | `/api/generate-analysis` | `{scope, context}` | `{text, fallback}` |
| POST | `/api/suggest-layout` | `{n_charts, chart_types, ..., free_area}` | `{source, elements}` |
| POST | `/api/training/add` | multipart `file` | `{filename, layouts_extracted, added_at}` |
| GET | `/api/training/list` | — | `{pptxs, bank_size}` |
| POST | `/api/training/delete` | `{filename}` | `{deleted}` |
| POST | `/api/training/reprocess` | — | `{reprocessed, bank_size}` |
| GET | `/api/training/bank` | — | `LayoutBank` |

## Errores

Status 400: `{code: "xlsx_parse_error"|"template_invalid", message}`
Status 500: errores generales
Status 502: `{code: "llm_error", message}` — LLM API issues

Detalles de tipos: ver `backend/aurum_encuestas/models.py` (pydantic) y `frontend/src/types/index.ts` (TS mirror).
