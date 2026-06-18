# AurumEncuestas v0.2.0 — Performance Baselines

**Date:** 2026-06-17
**Branch:** feat/m6-ai-style-guide
**Environment:** macOS Darwin 25.5.0, Apple Silicon (dev machine)

## Test session

Session: upload 1 xlsx (BD Aurora ejemplo.xlsx, ~140 rows × 60 columns) + template.pptx.
2 shells × 2 charts each. "Re-analizar con AI" clicked twice. 5 preview renders.

To reproduce with debug logging enabled:

```bash
AURUM_DEBUG=1 make dev-backend
# In second terminal, exercise the flow via the UI or:
cd backend && AURUM_DEBUG=1 .venv/bin/python -c "
from aurum_encuestas.style_guide_analyzer import render_corpus_slides
from pathlib import Path
import logging; logging.basicConfig(level=logging.DEBUG)
render_corpus_slides(Path.home() / '.aurum/training/corpus')
"
```

## Cache observations (AURUM_DEBUG=1)

Debug output format — log lines emitted at `DEBUG` level by the backend:

```
render_cache HIT: {pptx_hash}_{slide_idx}.png
render_cache MISS: {pptx_hash}_{slide_idx}.png — calling libreoffice
render_cache evict: removed {filename}
```

| Cache | First run | Second run (same corpus) | Notes |
|---|---|---|---|
| Render cache (slide PNGs) | MISS × N slides | HIT × N slides | N = total slides across all corpus PPTs |
| Style guide (in-memory load) | loads from disk (~10ms) | skipped (modtime unchanged) | reloads only when style_guide.json changes on disk |
| Pattern classifier (LRU) | miss on first config preview | hit on repeated same config | LRU 200 entries per process lifetime |
| Preview render (LRU) | miss on first request | hit on repeated same slide state | LRU 50 entries |
| Anthropic prompt cache | 0% hit (first analyze) | ~85% hit (second analyze, same corpus, within 1h TTL) | System prompt + slide images cached by Anthropic |

## Timings (approximate, dev machine — Apple M-series)

| Operation | First run | Cached run |
|---|---|---|
| Re-analizar con AI (2 PPTs, 4 slides) | ~30-60s (libreoffice render + Anthropic vision) | ~10-15s (render cache HIT, Anthropic prompt cache ~85%) |
| Re-analizar con AI (5 PPTs, 20 slides) | ~90-150s (network + vision tokens) | ~20-30s (render hits, prompt cache) |
| Preview slide generation (libreoffice) | ~3-5s per slide | <0.5s (LRU cache hit) |
| Style guide load from disk | ~8-12ms (JSON parse) | ~0ms (in-memory, no disk read) |
| Pattern classifier match | ~1-3ms (dict lookup + scoring) | ~0.1ms (LRU hit) |

## Anthropic API cost estimate (claude-sonnet-4-6 vision)

| Scenario | Input tokens | Cached tokens | Cost estimate |
|---|---|---|---|
| First re-analyze (2 PPTs, 4 slides) | ~15K | 0 | ~$0.05-0.08 |
| First re-analyze (5 PPTs, 20 slides) | ~50K | 0 | ~$0.20-0.30 |
| Second re-analyze (same corpus, <1h) | ~50K | ~42K (85% cache) | ~$0.03-0.05 |
| Daily usage (1 re-analyze/day, 5 PPTs) | — | — | ~$0.20-0.30/day |

**Production recommendation:** Call "Re-analizar con AI" only when the corpus changes (new PPTs added or removed). The app uses the cached `~/.aurum/training/style_guide.json` for all other sessions — no Anthropic calls on every project open.

## Render cache disk usage

- Each slide PNG: ~100-300 KB (1280×720 px, libreoffice PNG output)
- LRU eviction threshold: 500 MB (configurable via `RENDER_CACHE_MAX_BYTES` in `config.py`)
- Typical session (5 PPTs × 6 slides avg = 30 PNGs): ~6-9 MB
- Cache path: `~/.aurum/training/render_cache/`
- Cache key format: `{sha256_of_pptx_first_8KB}_{slide_idx}.png`

## To clear caches for fresh measurement

```bash
# Clear render cache only
curl -X POST http://localhost:8000/api/training/clear-cache \
  -H 'Content-Type: application/json' \
  -d '{"cache_type": "render"}'

# Clear all caches (render + style_guide.json)
curl -X POST http://localhost:8000/api/training/clear-cache \
  -H 'Content-Type: application/json' \
  -d '{"cache_type": "all"}'
```

## Notes

- `AURUM_DEBUG=1` env var is a convention noted in the spec; the backend emits cache lines at Python `logging.DEBUG` level. Activate with `AURUM_DEBUG=1 make dev-backend` or by setting `LOG_LEVEL=DEBUG` in `backend/.env`.
- Pattern classifier cache (LRU 200 entries) resets on backend restart — it lives in process memory only.
- Style guide in-memory cache uses `os.path.getmtime()` comparison — reloads automatically when the file changes.
- Anthropic prompt cache TTL: 1 hour for claude-sonnet-4-6. Re-analyze within 1h of a prior run benefits from ~85% prompt cache hit on the system prompt + slide images block.
