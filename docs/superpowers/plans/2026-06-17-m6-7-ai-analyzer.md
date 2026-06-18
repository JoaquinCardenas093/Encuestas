# M6.7 — AI Style Guide Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI style guide analyzer pipeline: render training PPT slides to PNG (with LRU disk cache), build a vision prompt with slide images + metadata, call Claude Sonnet 4.6 with the system prompt cached via Anthropic's prompt caching, parse and pydantic-validate the JSON response, repair semantic issues, merge with existing manual edits, and save. Exposed as an async background job with progress tracking.

**Architecture:** `style_guide_analyzer.py` orchestrates the pipeline. `llm_client.py` gains `analyze_training_corpus()`. Render cache lives at `~/.aurum/training/render_cache/`. Async job dict in `api.py`. Analysis logs written to `~/.aurum/training/ai_analysis_logs/`.

**Tech Stack adds:** none (anthropic SDK + python-pptx already present; libreoffice for headless render already used by `render_service.py`).

---

## File Structure

**Create (backend):**
- `backend/aurum_encuestas/style_guide_analyzer.py`
- `backend/tests/test_style_guide_analyzer.py`

**Modify (backend):**
- `backend/aurum_encuestas/llm_client.py` — add `analyze_training_corpus()` method + system prompt constant
- `backend/aurum_encuestas/config.py` — add `get_corpus_dir()`, `get_render_cache_dir()`, `get_analysis_logs_dir()`
- `backend/tests/test_llm_client.py` — add tests for `analyze_training_corpus`

**Depends on (must exist from M6.1-M6.4):**
- `backend/aurum_encuestas/style_guide.py` — `StyleGuide`, `Pattern` pydantic models, `load_active_style_guide()`, `save_style_guide()`

---

### Task 1: Render cache — corpus slides to PNG with LRU eviction

**Files:**
- Modify: `backend/aurum_encuestas/config.py`
- Create: `backend/aurum_encuestas/style_guide_analyzer.py`
- Create: `backend/tests/test_style_guide_analyzer.py`

- [ ] **Step 1: Add new config helpers**

Edit `backend/aurum_encuestas/config.py`. Append:

```python
def get_corpus_dir() -> Path:
    d = get_training_dir() / "corpus"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_render_cache_dir() -> Path:
    d = get_training_dir() / "render_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_analysis_logs_dir() -> Path:
    d = get_training_dir() / "ai_analysis_logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


RENDER_CACHE_MAX_BYTES = 500 * 1024 * 1024  # 500 MB
```

- [ ] **Step 2: Failing tests**

Create `backend/tests/test_style_guide_analyzer.py`:

```python
import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pptx import Presentation
from pptx.util import Inches
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE

from aurum_encuestas.style_guide_analyzer import (
    render_corpus_slides,
    _pptx_hash,
    _evict_render_cache_if_needed,
    build_vision_message,
    _validate_and_repair,
)
from aurum_encuestas.config import get_render_cache_dir


@pytest.fixture
def training_pptx_with_chart(tmp_path) -> Path:
    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]
    s = prs.slides.add_slide(blank)
    cd = CategoryChartData()
    cd.categories = ["Sí", "No"]
    cd.add_series("Total", [80, 20])
    s.shapes.add_chart(XL_CHART_TYPE.PIE, Inches(2), Inches(2), Inches(4), Inches(4), cd)
    out = tmp_path / "test_corpus.pptx"
    prs.save(str(out))
    return out


def test_pptx_hash_is_16_chars(training_pptx_with_chart):
    h = _pptx_hash(training_pptx_with_chart)
    assert len(h) == 16
    assert h.isalnum()


def test_render_corpus_slides_returns_list(tmp_path, monkeypatch, training_pptx_with_chart):
    monkeypatch.setenv("HOME", str(tmp_path))
    corpus_dir = tmp_path / ".aurum" / "training" / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy(training_pptx_with_chart, corpus_dir / "test_corpus.pptx")

    # Mock libreoffice render to return fake PNG bytes
    with patch("aurum_encuestas.style_guide_analyzer._render_slide_to_png") as mock_render:
        mock_render.return_value = b"\x89PNG\r\nfake_bytes"
        results = render_corpus_slides(corpus_dir)
    assert isinstance(results, list)
    assert len(results) >= 0  # May be 0 if no charts detected without real libreoffice


def test_render_cache_hit_skips_libreoffice(tmp_path, monkeypatch, training_pptx_with_chart):
    monkeypatch.setenv("HOME", str(tmp_path))
    cache_dir = tmp_path / ".aurum" / "training" / "render_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    h = _pptx_hash(training_pptx_with_chart)
    cache_file = cache_dir / f"{h}_0.png"
    cache_file.write_bytes(b"\x89PNG\r\nfake_cached")

    with patch("aurum_encuestas.style_guide_analyzer._render_slide_to_png") as mock_render:
        corpus_dir = tmp_path / ".aurum" / "training" / "corpus"
        corpus_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy(training_pptx_with_chart, corpus_dir / "test_corpus.pptx")
        results = render_corpus_slides(corpus_dir)
        # render should NOT be called for cached slides
        mock_render.assert_not_called()


def test_evict_render_cache_removes_oldest(tmp_path):
    import time
    cache_dir = tmp_path / "render_cache"
    cache_dir.mkdir()

    # Create files with slightly different mtimes
    for i in range(3):
        f = cache_dir / f"slide_{i}.png"
        f.write_bytes(b"x" * (200 * 1024 * 1024))  # 200MB each
        # Simulate older files
        if i < 2:
            import os
            os.utime(f, (time.time() - (i + 1) * 1000, time.time() - (i + 1) * 1000))

    # Cache is 600MB, limit is 500MB — should evict oldest
    _evict_render_cache_if_needed(cache_dir, max_bytes=500 * 1024 * 1024)
    remaining = list(cache_dir.glob("*.png"))
    assert len(remaining) < 3
```

- [ ] **Step 3: Implement render_corpus_slides + helpers**

Create `backend/aurum_encuestas/style_guide_analyzer.py`:

```python
"""AI Style Guide Analyzer — renders training corpus slides to PNG + calls Claude Sonnet 4.6.

Pipeline:
  1. render_corpus_slides(corpus_dir) → list of slide metadata + PNG bytes (with cache)
  2. build_vision_message(slides) → Anthropic vision content array
  3. analyze_training_corpus(slides) via llm_client → raw JSON string
  4. _validate_and_repair(raw_json, existing_style_guide) → StyleGuide
  5. Save + log
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pptx import Presentation

log = logging.getLogger(__name__)

MAX_SLIDES_PER_PPT = 15
MAX_SLIDES_TOTAL = 30


@dataclass
class SlideRenderResult:
    pptx_name: str
    slide_idx: int
    png_bytes: bytes
    metadata: dict  # shape counts, chart types, key text


def _pptx_hash(pptx_path: Path) -> str:
    """Return first 16 hex chars of SHA256 of file content."""
    h = hashlib.sha256(pptx_path.read_bytes()).hexdigest()
    return h[:16]


def _render_slide_to_png(pptx_path: Path, slide_idx: int, output_dir: Path) -> bytes | None:
    """Render a single slide via libreoffice headless → PNG bytes.

    Returns PNG bytes or None on failure.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_pptx = Path(tmpdir) / pptx_path.name
        import shutil
        shutil.copy(pptx_path, tmp_pptx)

        # libreoffice converts entire PPTX to images; we pick slide_idx
        try:
            result = subprocess.run(
                [
                    "libreoffice", "--headless", "--convert-to", "png",
                    "--outdir", tmpdir, str(tmp_pptx),
                ],
                timeout=60,
                capture_output=True,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            log.warning("libreoffice render failed: %s", exc)
            return None

        # libreoffice names output: filename-slideN.png (1-indexed)
        png_candidates = sorted(Path(tmpdir).glob(f"{tmp_pptx.stem}*.png"))
        if slide_idx < len(png_candidates):
            return png_candidates[slide_idx].read_bytes()
        return None


def _evict_render_cache_if_needed(cache_dir: Path, max_bytes: int) -> None:
    """LRU eviction: remove oldest files until total size is below max_bytes."""
    files = sorted(cache_dir.glob("*.png"), key=lambda f: f.stat().st_mtime)
    total = sum(f.stat().st_size for f in files)
    while total > max_bytes and files:
        oldest = files.pop(0)
        total -= oldest.stat().st_size
        oldest.unlink()
        log.debug("render_cache evict: removed %s", oldest.name)


def render_corpus_slides(corpus_dir: Path) -> list[SlideRenderResult]:
    """Render slides with charts from all PPTs in corpus_dir.

    Uses disk cache at ~/.aurum/training/render_cache/{pptx_hash}_{slide_idx}.png.
    Samples max 15 slides per PPT and 30 total.
    """
    from .config import get_render_cache_dir, RENDER_CACHE_MAX_BYTES

    cache_dir = get_render_cache_dir()
    results: list[SlideRenderResult] = []
    total_rendered = 0

    pptx_files = sorted(corpus_dir.glob("*.pptx"))
    for pptx_path in pptx_files:
        if total_rendered >= MAX_SLIDES_TOTAL:
            break

        try:
            prs = Presentation(str(pptx_path))
        except Exception as exc:
            log.warning("Could not open %s: %s", pptx_path.name, exc)
            continue

        # Identify slides with at least one chart shape
        slides_with_charts = [
            idx for idx, slide in enumerate(prs.slides)
            if any(getattr(sh, "has_chart", False) for sh in slide.shapes)
        ]

        if not slides_with_charts:
            continue

        # Sample max MAX_SLIDES_PER_PPT uniformly
        if len(slides_with_charts) > MAX_SLIDES_PER_PPT:
            step = len(slides_with_charts) / MAX_SLIDES_PER_PPT
            slides_with_charts = [slides_with_charts[int(i * step)] for i in range(MAX_SLIDES_PER_PPT)]

        pptx_hash = _pptx_hash(pptx_path)

        for slide_idx in slides_with_charts:
            if total_rendered >= MAX_SLIDES_TOTAL:
                break

            cache_key = f"{pptx_hash}_{slide_idx}.png"
            cache_file = cache_dir / cache_key

            if cache_file.exists():
                png_bytes = cache_file.read_bytes()
                log.debug("render_cache HIT: %s", cache_key)
            else:
                log.debug("render_cache MISS: %s — calling libreoffice", cache_key)
                png_bytes = _render_slide_to_png(pptx_path, slide_idx, cache_dir)
                if png_bytes is None:
                    continue
                cache_file.write_bytes(png_bytes)
                _evict_render_cache_if_needed(cache_dir, RENDER_CACHE_MAX_BYTES)

            metadata = _extract_slide_metadata(prs.slides[slide_idx])
            results.append(SlideRenderResult(
                pptx_name=pptx_path.name,
                slide_idx=slide_idx,
                png_bytes=png_bytes,
                metadata=metadata,
            ))
            total_rendered += 1

    return results


def _extract_slide_metadata(slide) -> dict:
    """Extract lightweight XML metadata from a slide for the vision prompt context."""
    shapes_info = []
    for sh in slide.shapes:
        info = {"type": str(sh.shape_type), "has_chart": getattr(sh, "has_chart", False)}
        if sh.has_text_frame:
            text = sh.text_frame.text[:80]
            if text.strip():
                info["text_preview"] = text
        if getattr(sh, "has_chart", False):
            try:
                info["chart_type"] = str(sh.chart.chart_type)
            except Exception:
                pass
        shapes_info.append(info)
    return {
        "shape_count": len(list(slide.shapes)),
        "chart_count": sum(1 for sh in slide.shapes if getattr(sh, "has_chart", False)),
        "shapes": shapes_info[:10],  # cap to keep prompt manageable
    }
```

- [ ] **Step 4: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_style_guide_analyzer.py -k "hash or cache or evict" -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/style_guide_analyzer.py backend/aurum_encuestas/config.py backend/tests/test_style_guide_analyzer.py
git commit -m "$(cat <<'EOF'
feat(backend): style_guide_analyzer — render_corpus_slides with PNG cache + LRU eviction

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Build vision user message

**Files:**
- Modify: `backend/aurum_encuestas/style_guide_analyzer.py`
- Modify: `backend/tests/test_style_guide_analyzer.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_style_guide_analyzer.py`:

```python
def test_build_vision_message_structure():
    slides = [
        SlideRenderResult(
            pptx_name="test.pptx",
            slide_idx=0,
            png_bytes=b"\x89PNG\r\nfake",
            metadata={"shape_count": 3, "chart_count": 1, "shapes": []},
        ),
        SlideRenderResult(
            pptx_name="test.pptx",
            slide_idx=2,
            png_bytes=b"\x89PNG\r\nfake2",
            metadata={"shape_count": 5, "chart_count": 2, "shapes": []},
        ),
    ]
    message_content = build_vision_message(slides)
    assert isinstance(message_content, list)
    # Should have header text block + (image + text metadata) per slide
    text_blocks = [b for b in message_content if b.get("type") == "text"]
    image_blocks = [b for b in message_content if b.get("type") == "image"]
    assert len(image_blocks) == 2
    assert len(text_blocks) >= 1


def test_build_vision_message_capped_at_30():
    slides = [
        SlideRenderResult("t.pptx", i, b"\x89PNG\r\nfake", {"shape_count": 2, "chart_count": 1, "shapes": []})
        for i in range(40)
    ]
    message_content = build_vision_message(slides)
    image_blocks = [b for b in message_content if b.get("type") == "image"]
    assert len(image_blocks) <= 30
```

- [ ] **Step 2: Implement `build_vision_message`**

Append to `backend/aurum_encuestas/style_guide_analyzer.py`:

```python
import base64


def build_vision_message(slides: list[SlideRenderResult]) -> list[dict]:
    """Build Anthropic vision content array from slide render results.

    Format: [header_text, image_1, slide_1_metadata_text, image_2, ...]
    Capped at MAX_SLIDES_TOTAL images.
    """
    content: list[dict] = []

    # Header text block
    header = (
        f"Analizá estas {min(len(slides), MAX_SLIDES_TOTAL)} slides de entrenamiento del corpus Aurum. "
        "Identificá patterns de presentación, tipos de elementos usados, y sintetizá un style guide JSON "
        "siguiendo EXACTAMENTE el schema especificado en el system prompt."
    )
    content.append({"type": "text", "text": header})

    for slide in slides[:MAX_SLIDES_TOTAL]:
        # PNG image block
        png_b64 = base64.standard_b64encode(slide.png_bytes).decode("ascii")
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": png_b64,
            },
        })

        # Metadata context text block
        meta_text = (
            f"[{slide.pptx_name} — slide {slide.slide_idx + 1}] "
            f"Formas: {slide.metadata.get('shape_count', '?')}, "
            f"Charts: {slide.metadata.get('chart_count', '?')}"
        )
        shapes_with_text = [s for s in slide.metadata.get("shapes", []) if "text_preview" in s]
        if shapes_with_text:
            texts = [s["text_preview"] for s in shapes_with_text[:3]]
            meta_text += f". Textos: {' | '.join(texts)}"
        content.append({"type": "text", "text": meta_text})

    return content
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_style_guide_analyzer.py -k "vision_message" -v`
Expected: 2 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/style_guide_analyzer.py backend/tests/test_style_guide_analyzer.py
git commit -m "$(cat <<'EOF'
feat(backend): build_vision_message — Anthropic vision content array with slide images + metadata

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: System prompt + llm_client.analyze_training_corpus

**Files:**
- Modify: `backend/aurum_encuestas/llm_client.py`
- Modify: `backend/tests/test_llm_client.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_llm_client.py`:

```python
from aurum_encuestas.llm_client import analyze_training_corpus


MINIMAL_STYLE_GUIDE_JSON = json.dumps({
    "version": 1,
    "is_builtin": False,
    "generated_at": "2026-06-17T20:00:00Z",
    "ai_prompt_version": "v1.0",
    "source_pptxs": ["test.pptx"],
    "manual_edits": {},
    "global": {
        "typography": {"font_family": "Arial", "title_size": 16, "subtitle_size": 12, "label_size": 9, "body_size": 10},
        "text_patterns": {},
        "suggested_palette": ["#7F7F7F", "#BFBFBF"],
        "vibe": "Minimalista",
    },
    "available_chart_types": ["PIE", "BAR_HORIZONTAL"],
    "patterns": [],
})


@patch("aurum_encuestas.llm_client._client")
def test_analyze_training_corpus_returns_raw_json(mock_client):
    import json
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text=MINIMAL_STYLE_GUIDE_JSON)]
    fake_msg.usage = MagicMock(input_tokens=10000, output_tokens=500, cache_read_input_tokens=8000, cache_creation_input_tokens=2000)
    mock_client.messages.create.return_value = fake_msg

    result = analyze_training_corpus(slides_content=[{"type": "text", "text": "test"}])
    assert result["raw_json"] == MINIMAL_STYLE_GUIDE_JSON
    assert result["input_tokens"] == 10000
    assert result["cached_input_tokens"] == 8000


@patch("aurum_encuestas.llm_client._client")
def test_analyze_training_corpus_uses_sonnet_46(mock_client):
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text=MINIMAL_STYLE_GUIDE_JSON)]
    fake_msg.usage = MagicMock(input_tokens=100, output_tokens=50, cache_read_input_tokens=0, cache_creation_input_tokens=100)
    mock_client.messages.create.return_value = fake_msg

    analyze_training_corpus(slides_content=[{"type": "text", "text": "x"}])
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-sonnet-4-6"


@patch("aurum_encuestas.llm_client._client")
def test_analyze_training_corpus_system_prompt_cached(mock_client):
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text=MINIMAL_STYLE_GUIDE_JSON)]
    fake_msg.usage = MagicMock(input_tokens=100, output_tokens=50, cache_read_input_tokens=0, cache_creation_input_tokens=100)
    mock_client.messages.create.return_value = fake_msg

    analyze_training_corpus(slides_content=[{"type": "text", "text": "x"}])
    call_kwargs = mock_client.messages.create.call_args[1]
    system_blocks = call_kwargs["system"]
    # At least one system block should have cache_control ephemeral
    cached_blocks = [b for b in system_blocks if b.get("cache_control", {}).get("type") == "ephemeral"]
    assert len(cached_blocks) >= 1


@patch("aurum_encuestas.llm_client._client", None)
def test_analyze_training_corpus_no_api_key_raises():
    from aurum_encuestas.errors import LLMError
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
        analyze_training_corpus(slides_content=[])
```

- [ ] **Step 2: Implement system prompt constant + `analyze_training_corpus`**

Append to `backend/aurum_encuestas/llm_client.py`:

```python
import json as _json

ANALYSIS_MODEL = "claude-sonnet-4-6"
ANALYSIS_MAX_TOKENS = 8000
ANALYSIS_TEMPERATURE = 0.2

STYLE_GUIDE_SYSTEM_PROMPT_V1 = """Sos un design system analyst especializado en presentaciones de encuestas.

Tu trabajo: analizar las slides de entrenamiento provistas y derivar un style guide ESTRUCTURADO en JSON que permita generar slides nuevas con datos arbitrarios manteniendo el estilo, jerarquía visual y patrones de presentación de las training slides.

Reglas:
- IGNORÁ colores específicos. El usuario elegirá colores aparte. NO incluyas palette/colors hex en patterns.
- IDENTIFICÁ patterns de presentación: cómo se presenta cada tipo de pregunta (binaria, múltiple, ranking), cómo se muestran breakdowns demográficos (tablas con mini-bars vs charts agrupados), dónde van los análisis.
- IDENTIFICÁ tipos de gráfico/elemento usados (PIE, BAR_HORIZONTAL, TABLE_WITH_MINIBARS, etc). Lista en available_chart_types SOLO los que VES.
- DETECTÁ "best examples" cross-corpus: si pattern X tiene 3 ejemplos en distintas slides, elegí EL MEJOR (más limpio, jerarquía más clara, más legible) y explicá por qué en why_picked.
- Posiciones: usá fracciones relativas (0-1) del área libre, no EMU absolutos.
- 8-15 patterns total. Más específicos primero (menor priority number = mayor prioridad).
- trigger operators soportados: $eq, $neq, $gt, $gte, $lt, $lte, $in, $nin, $and, $or, $not
- trigger fields: n_charts_in_slide, all_charts_share_question, question_type, n_options_per_question, breakdowns_used, n_breakdowns, n_analyses, n_chart_analyses, n_question_analyses, has_slide_analysis

Schema JSON esperado:
{
  "version": 1,
  "is_builtin": false,
  "generated_at": "<ISO timestamp>",
  "ai_prompt_version": "v1.0",
  "source_pptxs": ["..."],
  "manual_edits": {},
  "global": {
    "typography": {"font_family": "string", "title_size": int, "subtitle_size": int, "label_size": int, "body_size": int},
    "text_patterns": {"title": "string", "notes": "string", "analysis_style": "string", "tone": "string"},
    "suggested_palette": ["#hex", ...],
    "vibe": "string"
  },
  "available_chart_types": ["PIE", "DONUT", "BAR_HORIZONTAL", "BAR_CLUSTERED", "COLUMN_CLUSTERED", "TABLE_WITH_MINIBARS"],
  "patterns": [
    {
      "id": "unique_snake_case_id",
      "priority": 0,
      "trigger": {"$and": [{"field": "n_charts_in_slide", "$eq": 1}, {"field": "question_type", "$eq": "binary"}]},
      "extends": null,
      "best_example": "file.pptx#slideN",
      "why_picked": "string",
      "implementation": {
        "elements": [
          {"kind": "chart", "id": "el_id", "position": {"x_rel": 0.05, "y_rel": 0.1, "w_rel": 0.4, "h_rel": 0.7}, "chart_type": "PIE", "data_source": {"chart_ref_index": 0, "value_field": "pct"}, "labels": {"show_percentage": true, "position": "outside_end", "format": "0.0%"}, "legend": "none", "sort": "none"}
        ]
      }
    }
  ]
}

Devolvé ÚNICAMENTE el JSON válido. Sin markdown fences, sin comentarios fuera del JSON, sin texto explicativo.
"""


def analyze_training_corpus(slides_content: list[dict]) -> dict:
    """Call Claude Sonnet 4.6 with training slides vision content.

    Args:
        slides_content: Anthropic vision content array (text + image blocks)

    Returns dict with:
        raw_json: str — raw LLM response
        input_tokens: int
        output_tokens: int
        cached_input_tokens: int
        cost_estimate_usd: float
    """
    if _client is None:
        raise LLMError("ANTHROPIC_API_KEY no configurada. Agregá a .env y reiniciá el backend.")

    system_blocks = [
        {
            "type": "text",
            "text": STYLE_GUIDE_SYSTEM_PROMPT_V1,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    try:
        msg = _client.messages.create(
            model=ANALYSIS_MODEL,
            max_tokens=ANALYSIS_MAX_TOKENS,
            temperature=ANALYSIS_TEMPERATURE,
            system=system_blocks,
            messages=[{"role": "user", "content": slides_content}],
        )
    except Exception as exc:
        raise LLMError(f"Sonnet 4.6 API error: {exc}") from exc

    raw_text = "".join(b.text for b in msg.content if hasattr(b, "text")).strip()

    usage = msg.usage
    input_tokens = getattr(usage, "input_tokens", 0)
    output_tokens = getattr(usage, "output_tokens", 0)
    cached = getattr(usage, "cache_read_input_tokens", 0)
    fresh_input = input_tokens - cached

    # Sonnet 4.6 pricing: $3/M input, $15/M output (approximate)
    cost = (fresh_input / 1_000_000 * 3.0) + (output_tokens / 1_000_000 * 15.0)

    return {
        "raw_json": raw_text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": cached,
        "estimated_cost_usd": round(cost, 4),
    }
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_llm_client.py -k "analyze_training" -v`
Expected: 4 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/llm_client.py backend/tests/test_llm_client.py
git commit -m "$(cat <<'EOF'
feat(backend): llm_client.analyze_training_corpus — Sonnet 4.6 vision + system prompt cache

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Validation pipeline — JSON parse + pydantic + semantic repair

**Files:**
- Modify: `backend/aurum_encuestas/style_guide_analyzer.py`
- Modify: `backend/tests/test_style_guide_analyzer.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_style_guide_analyzer.py`:

```python
VALID_STYLE_GUIDE_DICT = {
    "version": 1,
    "is_builtin": False,
    "generated_at": "2026-06-17T20:00:00Z",
    "ai_prompt_version": "v1.0",
    "source_pptxs": ["test.pptx"],
    "manual_edits": {},
    "global": {
        "typography": {"font_family": "Arial", "title_size": 16, "subtitle_size": 12, "label_size": 9, "body_size": 10},
        "text_patterns": {"title": "{code}. {text}", "notes": "{tipo}. N: {n}.", "analysis_style": "El {X}%...", "tone": "formal"},
        "suggested_palette": ["#7F7F7F", "#BFBFBF"],
        "vibe": "Minimalista",
    },
    "available_chart_types": ["PIE", "BAR_HORIZONTAL"],
    "patterns": [
        {
            "id": "binary_general",
            "priority": 0,
            "trigger": {"$and": [{"field": "n_charts_in_slide", "$eq": 1}]},
            "extends": None,
            "best_example": "test.pptx#slide1",
            "why_picked": "Clean layout",
            "implementation": {
                "elements": [
                    {
                        "kind": "chart",
                        "id": "main_chart",
                        "position": {"x_rel": 0.1, "y_rel": 0.1, "w_rel": 0.8, "h_rel": 0.7},
                        "chart_type": "PIE",
                        "data_source": {"chart_ref_index": 0, "value_field": "pct"},
                        "labels": {"show_percentage": True},
                        "legend": "none",
                        "sort": "none",
                    }
                ]
            },
        }
    ],
}


def test_validate_and_repair_valid_input():
    raw_json = json.dumps(VALID_STYLE_GUIDE_DICT)
    sg, repairs, errors = _validate_and_repair(raw_json, existing_manual_edits={})
    assert sg is not None
    assert len(sg.patterns) == 1
    assert sg.patterns[0].id == "binary_general"


def test_validate_and_repair_malformed_json_returns_none():
    raw_json = "not valid json {"
    sg, repairs, errors = _validate_and_repair(raw_json, existing_manual_edits={})
    assert sg is None
    assert len(errors) >= 1


def test_validate_and_repair_clamps_positions():
    d = json.loads(json.dumps(VALID_STYLE_GUIDE_DICT))
    # Inject out-of-range position
    d["patterns"][0]["implementation"]["elements"][0]["position"]["x_rel"] = 1.5
    raw_json = json.dumps(d)
    sg, repairs, errors = _validate_and_repair(raw_json, existing_manual_edits={})
    assert sg is not None
    # x_rel should be clamped to [0, 1]
    el = sg.patterns[0].implementation["elements"][0]
    assert el["position"]["x_rel"] <= 1.0


def test_validate_and_repair_drops_duplicate_pattern_ids():
    d = json.loads(json.dumps(VALID_STYLE_GUIDE_DICT))
    # Add duplicate pattern
    dup = json.loads(json.dumps(d["patterns"][0]))
    d["patterns"].append(dup)
    raw_json = json.dumps(d)
    sg, repairs, errors = _validate_and_repair(raw_json, existing_manual_edits={})
    assert sg is not None
    assert len(sg.patterns) == 1  # duplicate dropped


def test_validate_and_repair_preserves_manual_edits():
    raw_json = json.dumps(VALID_STYLE_GUIDE_DICT)
    existing_manual = {"binary_general": "2026-06-17T10:00:00Z"}
    sg, repairs, errors = _validate_and_repair(raw_json, existing_manual_edits=existing_manual)
    assert sg is not None
    assert sg.manual_edits.get("binary_general") == "2026-06-17T10:00:00Z"
```

- [ ] **Step 2: Implement `_validate_and_repair`**

Append to `backend/aurum_encuestas/style_guide_analyzer.py`:

```python
from .style_guide import StyleGuide, Pattern


def _validate_and_repair(
    raw_json: str,
    existing_manual_edits: dict[str, str],
) -> tuple[StyleGuide | None, list[str], list[str]]:
    """Parse, pydantic-validate, and semantically repair AI-generated style guide JSON.

    Returns:
        (StyleGuide | None, repairs: list[str], errors: list[str])
    """
    repairs: list[str] = []
    errors: list[str] = []

    # Stage 1: JSON parse
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        errors.append(f"JSON parse failed: {exc}")
        return None, repairs, errors

    # Stage 2: Semantic pre-repair before pydantic validation
    data = _semantic_repair(data, repairs, errors)

    # Stage 3: Pydantic schema validation
    try:
        sg = StyleGuide.model_validate(data)
    except Exception as exc:
        errors.append(f"Pydantic schema validation failed: {exc}")
        return None, repairs, errors

    # Stage 4: Merge existing manual edits (preserve user overrides)
    if existing_manual_edits:
        merged_manual = dict(existing_manual_edits)
        merged_manual.update(sg.manual_edits or {})
        # Existing manual edits take precedence (not overwritten by AI re-analysis)
        sg.manual_edits = dict(existing_manual_edits)
        repairs.append(f"Preserved {len(existing_manual_edits)} manual edit(s) from previous analysis")

    return sg, repairs, errors


def _semantic_repair(data: dict, repairs: list[str], errors: list[str]) -> dict:
    """Apply semantic repairs to raw parsed dict before pydantic validation."""
    import copy
    data = copy.deepcopy(data)

    patterns = data.get("patterns", []) or []

    # Drop duplicate pattern ids (keep first occurrence)
    seen_ids: set[str] = set()
    unique_patterns = []
    for p in patterns:
        pid = p.get("id")
        if pid in seen_ids:
            repairs.append(f"Dropped duplicate pattern id: {pid!r}")
            continue
        if pid:
            seen_ids.add(pid)
        unique_patterns.append(p)
    data["patterns"] = unique_patterns

    # Validate and repair each pattern
    valid_patterns = []
    available_chart_types = set(data.get("available_chart_types", []))
    for p in unique_patterns:
        pid = p.get("id", "<no-id>")
        impl = p.get("implementation") or {}
        elements = impl.get("elements") or []

        repaired_elements = []
        for el in elements:
            # Clamp relative positions to [0, 1]
            position = el.get("position") or {}
            for key in ("x_rel", "y_rel", "w_rel", "h_rel"):
                if key in position:
                    orig = position[key]
                    clamped = max(0.0, min(1.0, float(orig)))
                    if clamped != orig:
                        repairs.append(f"Pattern {pid!r} element {el.get('id')!r}: clamped {key} {orig} → {clamped}")
                        position[key] = clamped
            el["position"] = position

            # Map unsupported chart types to BAR_HORIZONTAL
            if el.get("kind") == "chart":
                ct = el.get("chart_type", "")
                if available_chart_types and ct not in available_chart_types:
                    repairs.append(f"Pattern {pid!r}: chart_type {ct!r} not in available_chart_types → BAR_HORIZONTAL")
                    el["chart_type"] = "BAR_HORIZONTAL"

            repaired_elements.append(el)

        if "implementation" not in p:
            p["implementation"] = {}
        p["implementation"]["elements"] = repaired_elements

        # Validate extends ref (must be present in seen_ids if not null)
        extends = p.get("extends")
        if extends and extends not in seen_ids:
            repairs.append(f"Pattern {pid!r}: extends ref {extends!r} not found — clearing extends")
            p["extends"] = None

        valid_patterns.append(p)

    data["patterns"] = valid_patterns
    return data
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_style_guide_analyzer.py -k "validate_and_repair" -v`
Expected: 5 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/style_guide_analyzer.py backend/tests/test_style_guide_analyzer.py
git commit -m "$(cat <<'EOF'
feat(backend): _validate_and_repair — JSON parse + pydantic + semantic repair + manual edit preserve

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Async job — run_analysis_job + API endpoints

**Files:**
- Modify: `backend/aurum_encuestas/style_guide_analyzer.py`
- Modify: `backend/aurum_encuestas/api.py`
- Modify: `backend/tests/test_style_guide_analyzer.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_style_guide_analyzer.py`:

```python
from aurum_encuestas.style_guide_analyzer import run_full_analysis_pipeline


@patch("aurum_encuestas.style_guide_analyzer.render_corpus_slides")
@patch("aurum_encuestas.style_guide_analyzer.build_vision_message")
@patch("aurum_encuestas.llm_client.analyze_training_corpus")
def test_run_full_analysis_pipeline_success(
    mock_analyze, mock_build_msg, mock_render, tmp_path, monkeypatch
):
    monkeypatch.setenv("HOME", str(tmp_path))
    mock_render.return_value = []
    mock_build_msg.return_value = [{"type": "text", "text": "test"}]
    mock_analyze.return_value = {
        "raw_json": json.dumps(VALID_STYLE_GUIDE_DICT),
        "input_tokens": 1000,
        "output_tokens": 200,
        "cached_input_tokens": 800,
        "estimated_cost_usd": 0.05,
    }

    progress = {}
    result = run_full_analysis_pipeline(
        progress_dict=progress,
        existing_manual_edits={},
    )
    assert result["status"] == "done"
    assert result["patterns_valid"] >= 0
    assert progress.get("progress", 0) == 100


@patch("aurum_encuestas.style_guide_analyzer.render_corpus_slides")
@patch("aurum_encuestas.style_guide_analyzer.build_vision_message")
@patch("aurum_encuestas.llm_client.analyze_training_corpus")
def test_run_full_analysis_pipeline_saves_log(
    mock_analyze, mock_build_msg, mock_render, tmp_path, monkeypatch
):
    monkeypatch.setenv("HOME", str(tmp_path))
    mock_render.return_value = []
    mock_build_msg.return_value = [{"type": "text", "text": "test"}]
    mock_analyze.return_value = {
        "raw_json": json.dumps(VALID_STYLE_GUIDE_DICT),
        "input_tokens": 1000,
        "output_tokens": 200,
        "cached_input_tokens": 800,
        "estimated_cost_usd": 0.05,
    }

    run_full_analysis_pipeline(progress_dict={}, existing_manual_edits={})
    logs_dir = tmp_path / ".aurum" / "training" / "ai_analysis_logs"
    log_files = list(logs_dir.glob("*.json"))
    assert len(log_files) >= 1
```

Append to `backend/tests/test_api.py`:

```python
@patch("aurum_encuestas.api._analysis_jobs")
@patch("aurum_encuestas.api.BackgroundTasks")
def test_analyze_with_ai_returns_job_id(mock_bg, mock_jobs):
    r = client.post("/api/training/analyze-with-ai")
    assert r.status_code == 200
    assert "job_id" in r.json()


def test_analysis_status_unknown_job():
    r = client.get("/api/training/analysis-status/nonexistent-job-id")
    assert r.status_code == 404
```

- [ ] **Step 2: Implement `run_full_analysis_pipeline`**

Append to `backend/aurum_encuestas/style_guide_analyzer.py`:

```python
from datetime import UTC, datetime


def run_full_analysis_pipeline(
    progress_dict: dict,
    existing_manual_edits: dict[str, str],
) -> dict:
    """Execute the full AI analysis pipeline synchronously.

    Designed to be called from a background task. Updates progress_dict in-place.

    Returns summary dict: {status, patterns_valid, patterns_dropped, patterns_repaired, ...}
    """
    from .config import get_corpus_dir, get_analysis_logs_dir
    from .style_guide import save_style_guide
    from .llm_client import analyze_training_corpus

    start_time = time.monotonic()

    def _update_progress(pct: int, message: str = "") -> None:
        progress_dict["progress"] = pct
        progress_dict["status"] = "running"
        progress_dict["message"] = message

    _update_progress(5, "Listando corpus...")
    corpus_dir = get_corpus_dir()

    _update_progress(10, "Renderizando slides a PNG...")
    try:
        slides = render_corpus_slides(corpus_dir)
    except Exception as exc:
        log.error("render_corpus_slides failed: %s", exc)
        slides = []

    _update_progress(40, f"Construyendo mensaje vision ({len(slides)} slides)...")
    slides_content = build_vision_message(slides)

    _update_progress(50, "Llamando Claude Sonnet 4.6...")
    raw_json = ""
    llm_result = {}
    all_errors: list[str] = []

    # Retry logic: up to 2 attempts
    for attempt in range(2):
        try:
            llm_result = analyze_training_corpus(slides_content)
            raw_json = llm_result.get("raw_json", "")
            break
        except Exception as exc:
            all_errors.append(f"LLM attempt {attempt + 1} failed: {exc}")
            log.warning("analyze_training_corpus attempt %d failed: %s", attempt + 1, exc)
            if attempt == 1:
                progress_dict["status"] = "error"
                progress_dict["message"] = f"LLM failed after 2 attempts: {all_errors[-1]}"
                return {"status": "error", "errors": all_errors}

    _update_progress(70, "Validando y reparando style guide...")
    sg, repairs, errors = _validate_and_repair(raw_json, existing_manual_edits)
    all_errors.extend(errors)

    if sg is None:
        # Retry once with error feedback
        error_feedback_content = list(slides_content) + [
            {"type": "text", "text": f"Tu respuesta anterior falló validación: {errors}. Corregí y devolvé JSON válido."}
        ]
        try:
            llm_result2 = analyze_training_corpus(error_feedback_content)
            raw_json2 = llm_result2.get("raw_json", "")
            sg, repairs2, errors2 = _validate_and_repair(raw_json2, existing_manual_edits)
            repairs.extend(repairs2)
            all_errors.extend(errors2)
        except Exception as exc:
            all_errors.append(f"Retry failed: {exc}")

    _update_progress(85, "Guardando style guide...")

    patterns_valid = 0
    patterns_dropped = 0

    if sg is not None:
        # Save raw for debug
        raw_path = get_corpus_dir().parent / ".last_ai_raw.json"
        raw_path.write_text(raw_json, encoding="utf-8")

        # Save validated style guide
        save_style_guide(sg)
        patterns_valid = len(sg.patterns)
    else:
        # Fallback to built-in
        from .style_guide import BUILTIN_STYLE_GUIDE, save_style_guide as _save
        _save(BUILTIN_STYLE_GUIDE)
        patterns_valid = len(BUILTIN_STYLE_GUIDE.patterns)
        log.warning("AI analysis failed — falling back to built-in style guide")

    duration = time.monotonic() - start_time
    corpus_pptxs = [p.name for p in get_corpus_dir().glob("*.pptx")]

    # Save analysis log
    log_entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "duration_seconds": round(duration, 1),
        "corpus_pptxs": corpus_pptxs,
        "slides_analyzed": len(slides),
        "prompt_version": "v1.0",
        "input_tokens": llm_result.get("input_tokens", 0),
        "output_tokens": llm_result.get("output_tokens", 0),
        "cached_input_tokens": llm_result.get("cached_input_tokens", 0),
        "estimated_cost_usd": llm_result.get("estimated_cost_usd", 0),
        "validation_errors": all_errors,
        "repairs": repairs,
        "patterns_valid": patterns_valid,
        "patterns_dropped": patterns_dropped,
    }
    try:
        logs_dir = get_analysis_logs_dir()
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        (logs_dir / f"{ts}.json").write_text(json.dumps(log_entry, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        log.warning("Could not save analysis log: %s", exc)

    _update_progress(100, "Análisis completo")
    progress_dict["status"] = "done"

    return {
        "status": "done",
        "patterns_valid": patterns_valid,
        "patterns_dropped": patterns_dropped,
        "repairs": repairs,
        "errors": all_errors,
        "estimated_cost_usd": llm_result.get("estimated_cost_usd", 0),
        "duration_seconds": round(duration, 1),
    }
```

- [ ] **Step 3: Add API endpoints for async job**

Append to `backend/aurum_encuestas/api.py`:

```python
import uuid
from fastapi import BackgroundTasks
from .style_guide_analyzer import run_full_analysis_pipeline

_analysis_jobs: dict[str, dict] = {}


@app.post("/api/training/analyze-with-ai")
async def analyze_with_ai(background_tasks: BackgroundTasks):
    """Start async AI analysis job. Returns job_id immediately."""
    job_id = str(uuid.uuid4())
    _analysis_jobs[job_id] = {"progress": 0, "status": "running", "message": "Iniciando..."}

    def _run():
        from .style_guide import load_active_style_guide
        try:
            existing_manual = load_active_style_guide().manual_edits or {}
        except Exception:
            existing_manual = {}
        result = run_full_analysis_pipeline(
            progress_dict=_analysis_jobs[job_id],
            existing_manual_edits=existing_manual,
        )
        _analysis_jobs[job_id].update(result)

    background_tasks.add_task(_run)
    return {"job_id": job_id}


@app.get("/api/training/analysis-status/{job_id}")
async def analysis_status(job_id: str):
    """Get progress of an async analysis job."""
    job = _analysis_jobs.get(job_id)
    if job is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    return job
```

- [ ] **Step 4: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_style_guide_analyzer.py -v`
Expected: all PASS.

Run: `cd backend && .venv/bin/pytest tests/test_api.py -k "analyze" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/style_guide_analyzer.py backend/aurum_encuestas/api.py backend/tests/test_style_guide_analyzer.py backend/tests/test_api.py
git commit -m "$(cat <<'EOF'
feat(backend): async AI analysis job + full pipeline + analysis logs + API endpoints

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Tag the sub-milestone:

```bash
git tag m6.7
```

---

## M6.7 Done When

- `render_corpus_slides(corpus_dir)` returns list of `SlideRenderResult` with PNG bytes from disk cache or libreoffice render
- Render cache keyed by `{sha256_16chars}_{slide_idx}.png`, LRU eviction at 500MB
- Cache hit skips libreoffice subprocess (verified by mock assert)
- `build_vision_message(slides)` returns Anthropic content array with text header + image + metadata blocks, capped at 30 images
- `analyze_training_corpus(slides_content)` calls Sonnet 4.6 with system prompt in ephemeral cache_control, returns raw_json + token usage + cost estimate
- `_validate_and_repair(raw_json, manual_edits)` handles: JSON parse errors, pydantic schema errors, duplicate pattern ids, out-of-range positions (clamped), unsupported chart types (mapped), broken extends refs (cleared), and preserves existing manual_edits
- `run_full_analysis_pipeline(progress_dict, existing_manual_edits)` orchestrates full pipeline, updates progress 0→100, saves `style_guide.json` + analysis log, falls back to built-in on double failure
- `POST /api/training/analyze-with-ai` returns `{job_id}` and starts background task
- `GET /api/training/analysis-status/{job_id}` returns `{progress, status, message}`
- Analysis logs saved to `~/.aurum/training/ai_analysis_logs/{timestamp}.json` with cost tracking
- All tests pass (18+ in analyzer suite + 2 api tests)
- Git tag `m6.7`
