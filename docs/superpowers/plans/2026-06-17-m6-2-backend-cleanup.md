# M6.2 — Backend Cleanup + Module Scaffolding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete obsolete M4/M5 backend modules (`layout_matcher.py`, `layout_engine.py`, `training_extractor.py`) and their tests. Create stub modules for the full M6 pipeline with module docstrings. Extend `config.py` with new directory helpers. Stub `pptx_generator.build_pptx` to call the new pipeline (no-op stubs keep charts rendering). Wire `migrate_legacy_files()` into API startup.

**Architecture:** Clean-break approach — delete obsolete code, scaffold new modules as stubs so imports resolve, keep existing chart insertion logic as temp fallback in `pptx_generator` until M6.6 replaces it.

**Tech Stack adds:** None. Pure stdlib + existing deps.

---

## File Structure

**Delete (backend):**
- `backend/aurum_encuestas/layout_matcher.py`
- `backend/aurum_encuestas/layout_engine.py`
- `backend/aurum_encuestas/training_extractor.py`
- `backend/tests/test_layout_matcher.py`
- `backend/tests/test_layout_engine.py` (if exists)
- `backend/tests/test_training_extractor.py`

**Create (backend stubs):**
- `backend/aurum_encuestas/style_guide_analyzer.py`
- `backend/aurum_encuestas/pattern_classifier.py`
- `backend/aurum_encuestas/pattern_renderer.py`
- `backend/aurum_encuestas/color_resolver.py`
- `backend/aurum_encuestas/training_sets.py`
- `backend/aurum_encuestas/element_renderers/__init__.py`
- `backend/aurum_encuestas/element_renderers/chart_renderer.py`
- `backend/aurum_encuestas/element_renderers/table_renderer.py`
- `backend/aurum_encuestas/element_renderers/text_renderer.py`
- `backend/aurum_encuestas/element_renderers/shape_renderer.py`
- `backend/aurum_encuestas/element_renderers/image_renderer.py`

**Modify (backend):**
- `backend/aurum_encuestas/config.py` — add `get_corpus_dir()`, `get_style_guide_path()`, `get_render_cache_dir()`, `get_ai_logs_dir()`
- `backend/aurum_encuestas/pptx_generator.py` — stub new pipeline call (existing chart logic preserved as fallback)
- `backend/aurum_encuestas/api.py` — call `migrate_legacy_files()` in lifespan startup

---

### Task 1: Delete obsolete modules + their tests

**Files:**
- Delete: `backend/aurum_encuestas/layout_matcher.py`
- Delete: `backend/aurum_encuestas/layout_engine.py`
- Delete: `backend/aurum_encuestas/training_extractor.py`
- Delete: `backend/tests/test_layout_matcher.py`
- Delete: `backend/tests/test_layout_engine.py`
- Delete: `backend/tests/test_training_extractor.py`

- [ ] **Step 1: Remove obsolete source files**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend"
rm -f aurum_encuestas/layout_matcher.py
rm -f aurum_encuestas/layout_engine.py
rm -f aurum_encuestas/training_extractor.py
```

- [ ] **Step 2: Remove obsolete test files**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend"
rm -f tests/test_layout_matcher.py
rm -f tests/test_layout_engine.py
rm -f tests/test_training_extractor.py
```

- [ ] **Step 3: Verify no stray imports remain**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend"
grep -rn "layout_matcher\|layout_engine\|training_extractor" aurum_encuestas/ tests/ || echo "Clean — no remaining imports"
```
Expected: "Clean — no remaining imports" (or only benign references in comments).

Fix any import remaining (likely in `pptx_generator.py` or `api.py`) by removing or replacing those import lines before proceeding.

- [ ] **Step 4: Verify test suite still loads**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest --collect-only 2>&1 | tail -20
```
Expected: collection succeeds (no ImportError).

- [ ] **Step 5: Commit**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git add -u
git commit -m "$(cat <<'EOF'
chore(backend/m6.2): delete obsolete modules — layout_matcher, layout_engine, training_extractor + their tests

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Create stub modules for M6 pipeline + element_renderers package

**Files:**
- Create: `backend/aurum_encuestas/style_guide_analyzer.py`
- Create: `backend/aurum_encuestas/pattern_classifier.py`
- Create: `backend/aurum_encuestas/pattern_renderer.py`
- Create: `backend/aurum_encuestas/color_resolver.py`
- Create: `backend/aurum_encuestas/training_sets.py`
- Create: `backend/aurum_encuestas/element_renderers/__init__.py`
- Create: `backend/aurum_encuestas/element_renderers/chart_renderer.py`
- Create: `backend/aurum_encuestas/element_renderers/table_renderer.py`
- Create: `backend/aurum_encuestas/element_renderers/text_renderer.py`
- Create: `backend/aurum_encuestas/element_renderers/shape_renderer.py`
- Create: `backend/aurum_encuestas/element_renderers/image_renderer.py`

- [ ] **Step 1: Create style_guide_analyzer.py stub**

Create `backend/aurum_encuestas/style_guide_analyzer.py`:

```python
"""M6 Style Guide Analyzer — Claude Sonnet 4.6 vision wrapper.

Analyzes training corpus PPTs and synthesizes a unified StyleGuide JSON.
Full implementation in M6.7. This stub provides the public interface
so other modules can import without errors.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .style_guide import StyleGuide


def analyze_corpus(corpus_pptx_paths: list[str], existing_style_guide=None) -> "StyleGuide":
    """Stub: analyze training corpus with AI vision.

    Returns BUILTIN_STYLE_GUIDE until M6.7 implements the real pipeline.
    """
    from .style_guide import load_active
    return load_active()


def get_render_cache_path(pptx_hash: str, slide_idx: int) -> str:
    """Return the expected PNG cache path for a slide render."""
    from .config import get_render_cache_dir
    return str(get_render_cache_dir() / f"{pptx_hash}_{slide_idx}.png")
```

- [ ] **Step 2: Create pattern_classifier.py stub**

Create `backend/aurum_encuestas/pattern_classifier.py`:

```python
"""M6 Pattern Classifier — matches slide_config against StyleGuide patterns.

Evaluates trigger operators ($eq/$neq/$gt/$gte/$lt/$lte/$in/$nin/$and/$or/$not)
and returns the first matching Pattern sorted by priority asc.
Full implementation in M6.3. This stub always returns None (fallback to generic grid).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .style_guide import Pattern, StyleGuide


def classify(slide_config: dict, parsed_db: dict, style_guide) -> Optional["Pattern"]:
    """Stub: classify slide config against style guide patterns.

    Returns None until M6.3 implements trigger evaluation.
    Callers must handle None by using a generic fallback layout.
    """
    return None


def evaluate_trigger(trigger, context: dict) -> bool:
    """Stub: evaluate a single Trigger node against a field context dict.

    Returns False (no match) until M6.3 implements recursive evaluation.
    """
    return False
```

- [ ] **Step 3: Create pattern_renderer.py stub**

Create `backend/aurum_encuestas/pattern_renderer.py`:

```python
"""M6 Pattern Renderer — orchestrates element rendering for a matched pattern.

Resolves positions (rel→abs via free_area), resolves data sources, resolves
color roles, and dispatches to element_renderers[kind].
Full implementation in M6.6. This stub is a no-op.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pptx.slide import Slide as PptxSlide
    from .style_guide import Pattern


def render_pattern(
    pattern: "Pattern",
    slide: "PptxSlide",
    slide_config: dict,
    parsed_db: dict,
    free_area: dict,
    chart_colors: list[str],
    project_palette: dict | None,
    style_guide: Any,
) -> None:
    """Stub: render all elements of a matched pattern onto a python-pptx slide.

    No-op until M6.6. The caller (pptx_generator) falls back to legacy chart
    insertion when this returns without adding shapes.
    """
    pass
```

- [ ] **Step 4: Create color_resolver.py stub**

Create `backend/aurum_encuestas/color_resolver.py`:

```python
"""M6 Color Resolver — symbolic color role → hex cascade.

Cascade: chart.colors[i] → project.palette[role] → style_guide.suggested_palette[i] → built-in greys.
Auto-derive N colors from primary via lumMod variations.
Full implementation in M6.4. This stub returns sensible built-in defaults.
"""
from __future__ import annotations

from typing import Optional

_BUILTIN_DEFAULTS = ["#7F7F7F", "#BFBFBF", "#FFC000", "#404040", "#D9D9D9", "#A6A6A6", "#595959", "#D6D6D6"]


def resolve(
    role: str,
    chart_colors: list[str],
    project_palette: dict | None,
    style_guide,
    element_idx: int = 0,
) -> str:
    """Stub: resolve symbolic color role to hex.

    Returns a built-in grey until M6.4 implements the full cascade.
    """
    if chart_colors and element_idx < len(chart_colors):
        return chart_colors[element_idx]
    if project_palette and role in project_palette:
        return project_palette[role]
    return _BUILTIN_DEFAULTS[element_idx % len(_BUILTIN_DEFAULTS)]


def auto_derive(primary_hex: str, n: int) -> list[str]:
    """Stub: derive N colors from primary via lumMod variations.

    Returns [primary_hex] repeated n times until M6.4 implements real lumMod.
    """
    return [primary_hex] * n


def update_recent(hex_color: str) -> None:
    """Stub: write hex_color to ~/.aurum/config.json recent_colors list.

    No-op until M6.4.
    """
    pass
```

- [ ] **Step 5: Create training_sets.py stub**

Create `backend/aurum_encuestas/training_sets.py`:

```python
"""M6 Training Sets — corpus CRUD helpers.

Flat corpus (not sets): all PPTs live in ~/.aurum/training/corpus/.
Replaces the training_extractor.py concept from M4/M5.
Full CRUD implemented in M6.8 alongside API endpoints.
"""
from __future__ import annotations

from pathlib import Path


def get_corpus_pptxs() -> list[Path]:
    """Return all PPT files in the corpus directory."""
    from .config import get_corpus_dir
    return sorted(get_corpus_dir().glob("*.pptx"))


def add_pptx_to_corpus(source_path: Path, filename: str) -> Path:
    """Copy a PPT into the corpus directory. Returns destination path."""
    from .config import get_corpus_dir
    dest = get_corpus_dir() / filename
    import shutil
    shutil.copy2(source_path, dest)
    return dest


def delete_pptx_from_corpus(filename: str) -> bool:
    """Delete a PPT from corpus by filename. Returns True if deleted."""
    from .config import get_corpus_dir
    p = get_corpus_dir() / filename
    if p.exists():
        p.unlink()
        return True
    return False


def count_chart_slides(pptx_path: Path) -> int:
    """Count slides that contain at least one chart shape."""
    try:
        from pptx import Presentation
        prs = Presentation(str(pptx_path))
        return sum(
            1 for slide in prs.slides
            if any(getattr(sh, "has_chart", False) for sh in slide.shapes)
        )
    except Exception:
        return 0
```

- [ ] **Step 6: Create element_renderers package**

Create `backend/aurum_encuestas/element_renderers/__init__.py`:

```python
"""M6 Element Renderers package.

Each submodule handles one element kind from the style guide schema:
  chart_renderer   — PIE, BAR_HORIZONTAL, etc.  (M6.5)
  table_renderer   — segmented_breakdowns, etc.  (M6.5)
  text_renderer    — analysis text boxes         (M6.5)
  shape_renderer   — lines, rectangles           (M6.5)
  image_renderer   — template image refs         (M6.5)

All render functions are stubs until M6.5.
"""

from .chart_renderer import render_chart
from .table_renderer import render_table
from .text_renderer import render_text
from .shape_renderer import render_shape
from .image_renderer import render_image

__all__ = ["render_chart", "render_table", "render_text", "render_shape", "render_image"]
```

Create `backend/aurum_encuestas/element_renderers/chart_renderer.py`:

```python
"""M6 Chart Element Renderer — stub.

Renders ElementChart onto a python-pptx slide.
Full implementation in M6.5.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pptx.slide import Slide as PptxSlide


def render_chart(element: Any, slide: "PptxSlide", data: dict, free_area: dict, resolved_colors: list[str]) -> None:
    """Stub: render chart element. No-op until M6.5."""
    pass
```

Create `backend/aurum_encuestas/element_renderers/table_renderer.py`:

```python
"""M6 Table Element Renderer — stub.

Renders ElementTable (segmented_breakdowns, comparison_grid, simple_data)
onto a python-pptx slide using native table shapes.
Full implementation in M6.5.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pptx.slide import Slide as PptxSlide


def render_table(element: Any, slide: "PptxSlide", data: dict, free_area: dict, resolved_colors: dict) -> None:
    """Stub: render table element. No-op until M6.5."""
    pass
```

Create `backend/aurum_encuestas/element_renderers/text_renderer.py`:

```python
"""M6 Text Element Renderer — stub.

Renders ElementText (analysis/static/computed content) onto a python-pptx slide
as a text box with styled runs.
Full implementation in M6.5.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pptx.slide import Slide as PptxSlide


def render_text(element: Any, slide: "PptxSlide", context: dict, free_area: dict, resolved_colors: dict) -> None:
    """Stub: render text element. No-op until M6.5."""
    pass
```

Create `backend/aurum_encuestas/element_renderers/shape_renderer.py`:

```python
"""M6 Shape Element Renderer — stub.

Renders ElementShape (line, rectangle) onto a python-pptx slide.
Full implementation in M6.5.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pptx.slide import Slide as PptxSlide


def render_shape(element: Any, slide: "PptxSlide", free_area: dict, resolved_colors: dict) -> None:
    """Stub: render shape element. No-op until M6.5."""
    pass
```

Create `backend/aurum_encuestas/element_renderers/image_renderer.py`:

```python
"""M6 Image Element Renderer — stub.

Renders ElementImage (template shape reference) onto a python-pptx slide.
Full implementation in M6.5.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pptx.slide import Slide as PptxSlide


def render_image(element: Any, slide: "PptxSlide", template_shapes: list, free_area: dict) -> None:
    """Stub: render image element. No-op until M6.5."""
    pass
```

- [ ] **Step 7: Verify all stubs import cleanly**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend"
.venv/bin/python -c "
from aurum_encuestas.style_guide_analyzer import analyze_corpus
from aurum_encuestas.pattern_classifier import classify, evaluate_trigger
from aurum_encuestas.pattern_renderer import render_pattern
from aurum_encuestas.color_resolver import resolve, auto_derive, update_recent
from aurum_encuestas.training_sets import get_corpus_pptxs
from aurum_encuestas.element_renderers import render_chart, render_table, render_text, render_shape, render_image
print('All stubs import OK')
"
```
Expected: `All stubs import OK`.

- [ ] **Step 8: Commit**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git add backend/aurum_encuestas/style_guide_analyzer.py \
        backend/aurum_encuestas/pattern_classifier.py \
        backend/aurum_encuestas/pattern_renderer.py \
        backend/aurum_encuestas/color_resolver.py \
        backend/aurum_encuestas/training_sets.py \
        backend/aurum_encuestas/element_renderers/
git commit -m "$(cat <<'EOF'
feat(backend/m6.2): scaffold M6 stub modules — analyzer, classifier, renderer, color_resolver, training_sets, element_renderers pkg

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: config.py — new directory helpers for M6 filesystem layout

**Files:**
- Modify: `backend/aurum_encuestas/config.py`
- Modify: `backend/tests/test_config.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_config.py`:

```python
from aurum_encuestas.config import (
    get_corpus_dir,
    get_style_guide_path,
    get_render_cache_dir,
    get_ai_logs_dir,
)


def test_get_corpus_dir_creates_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    d = get_corpus_dir()
    assert d.exists()
    assert d.is_dir()
    assert d.name == "corpus"
    assert d.parent.name == "training"


def test_get_style_guide_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = get_style_guide_path()
    assert p.name == "style_guide.json"
    assert p.parent.name == "training"


def test_get_render_cache_dir_creates_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    d = get_render_cache_dir()
    assert d.exists()
    assert d.is_dir()
    assert d.name == "render_cache"


def test_get_ai_logs_dir_creates_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    d = get_ai_logs_dir()
    assert d.exists()
    assert d.is_dir()
    assert d.name == "ai_analysis_logs"
```

- [ ] **Step 2: Add helpers to config.py**

Append to `backend/aurum_encuestas/config.py`:

```python
# ────────────────────────────────────────────────────────────────────────────
# M6 directory helpers
# ────────────────────────────────────────────────────────────────────────────

def get_corpus_dir() -> Path:
    """~/.aurum/training/corpus/ — flat list of training PPTs."""
    d = get_training_dir() / "corpus"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_style_guide_path() -> Path:
    """~/.aurum/training/style_guide.json — AI-generated global style guide."""
    return get_training_dir() / "style_guide.json"


def get_render_cache_dir() -> Path:
    """~/.aurum/training/render_cache/ — PNG slides cache (max 500MB LRU)."""
    d = get_training_dir() / "render_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_ai_logs_dir() -> Path:
    """~/.aurum/training/ai_analysis_logs/ — per-analysis JSON logs."""
    d = get_training_dir() / "ai_analysis_logs"
    d.mkdir(parents=True, exist_ok=True)
    return d
```

- [ ] **Step 3: Run, verify pass**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_config.py -v
```
Expected: all PASS including new 4 tests.

- [ ] **Step 4: Commit**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git add backend/aurum_encuestas/config.py backend/tests/test_config.py
git commit -m "$(cat <<'EOF'
feat(backend/m6.2): config.py — get_corpus_dir, get_style_guide_path, get_render_cache_dir, get_ai_logs_dir

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: pptx_generator.py — stub new pipeline, preserve legacy chart fallback

**Files:**
- Modify: `backend/aurum_encuestas/pptx_generator.py`
- Modify: `backend/tests/test_pptx_generator.py`

- [ ] **Step 1: Remove obsolete imports from pptx_generator.py**

Edit `backend/aurum_encuestas/pptx_generator.py`:

Remove any imports that reference deleted modules:
- `from .layout_matcher import match_layout` — remove
- `from .layout_engine import compute_layout` — remove
- Any `_apply_training_style` function call or definition involving `layout_bank` — remove

Replace the removed `match_layout` call (in `_append_shell` or `build_pptx`) with a TODO comment + direct call to the new pipeline stubs.

The new pipeline call block (after the slide is created, before chart insertion):

```python
# M6 pipeline (stubs — will be fully implemented in M6.6)
from .style_guide import load_active
from .pattern_classifier import classify
from .pattern_renderer import render_pattern

_style_guide = load_active()
_slide_config = {
    "n_charts": len(slide_def.charts),
    "charts": [c.model_dump() for c in slide_def.charts],
    "analyses": [a.model_dump() for a in slide_def.analyses],
    "free_area": free_area,
}
_matched_pattern = classify(_slide_config, {}, _style_guide)
if _matched_pattern is not None:
    render_pattern(
        pattern=_matched_pattern,
        slide=slide,
        slide_config=_slide_config,
        parsed_db={},
        free_area=free_area,
        chart_colors=[],
        project_palette=state.palette,
        style_guide=_style_guide,
    )
    # Pattern renderer handled all elements; skip legacy chart insertion below.
    return  # ← only if render_pattern actually adds shapes; stubs are no-ops so fall through

# Legacy chart insertion (temp fallback during M6.2 while stubs are no-ops)
# This block remains until M6.6 replaces it with the real pattern_renderer.
```

Note to implementer: since `render_pattern` is a no-op stub, add a flag or check so the legacy code still executes during M6.2. The simplest approach: only skip legacy insertion if `_matched_pattern is not None AND render_pattern returned True` — but since the stub always returns None from classify, the condition `if _matched_pattern is not None` will be False and legacy code runs. No `return` needed yet.

- [ ] **Step 2: Verify pptx_generator tests still pass**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_pptx_generator.py -v
```
Expected: all PASS (legacy chart insertion still works).

- [ ] **Step 3: Commit**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git add backend/aurum_encuestas/pptx_generator.py
git commit -m "$(cat <<'EOF'
feat(backend/m6.2): pptx_generator — stub new M6 pipeline call, preserve legacy chart insertion as fallback

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: api.py — run migrate_legacy_files() on startup + remove obsolete training endpoints

**Files:**
- Modify: `backend/aurum_encuestas/api.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Add migration call to lifespan startup**

Edit `backend/aurum_encuestas/api.py`. If using FastAPI lifespan:

```python
from contextlib import asynccontextmanager
from .style_guide import migrate_legacy_files
import logging

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    # Startup
    try:
        migrate_legacy_files()
        log.info("M6 migration check complete")
    except Exception as exc:
        log.warning("migrate_legacy_files failed (non-fatal): %s", exc)
    yield
    # Shutdown (nothing to do)


app = FastAPI(lifespan=lifespan)
```

If `app = FastAPI()` already exists without lifespan, replace it with `app = FastAPI(lifespan=lifespan)` and add the lifespan context manager above.

- [ ] **Step 2: Remove obsolete M4/M5 training endpoints**

Remove from `api.py` the following endpoints (they will be replaced by new M6.8 endpoints):
- `POST /api/training/add`
- `GET /api/training/list`
- `POST /api/training/delete`
- `POST /api/training/reprocess`
- `GET /api/training/bank`

Add placeholder comment:

```python
# TODO M6.8: new training endpoints (corpus CRUD + AI analyze + style-guide GET/PUT)
```

- [ ] **Step 3: Run API tests to catch regressions**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_api.py -v
```
Expected: existing non-training tests PASS. Training-related tests (for deleted endpoints) should be removed or updated if they now 404.

Remove from `backend/tests/test_api.py` any test functions that hit the deleted training endpoints (e.g., `test_training_add_and_list`, `test_training_bank_returns_layouts`, `test_training_delete`). Those will be replaced by new M6.8 tests.

- [ ] **Step 4: Final full suite run**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git add backend/aurum_encuestas/api.py backend/tests/test_api.py
git commit -m "$(cat <<'EOF'
feat(backend/m6.2): api.py — migrate_legacy_files on startup + remove obsolete M4/M5 training endpoints

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6 (final): Run all tests + tag M6.2

**Files:** none

- [ ] **Step 1: Full backend test suite**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest -v
```
Expected: all PASS.

- [ ] **Step 2: Verify all new stub modules importable**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend"
.venv/bin/python -c "
import aurum_encuestas.style_guide_analyzer
import aurum_encuestas.pattern_classifier
import aurum_encuestas.pattern_renderer
import aurum_encuestas.color_resolver
import aurum_encuestas.training_sets
import aurum_encuestas.element_renderers
print('OK')
"
```
Expected: `OK`.

- [ ] **Step 3: Tag M6.2**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git tag m6.2-backend-cleanup
git log --oneline | head -15
```

---

## M6.2 Done When

- [ ] `layout_matcher.py`, `layout_engine.py`, `training_extractor.py` deleted — no references remain in any module
- [ ] Stub modules created and importable: `style_guide_analyzer`, `pattern_classifier`, `pattern_renderer`, `color_resolver`, `training_sets`, `element_renderers` package with all 5 renderer stubs
- [ ] `config.py` gains `get_corpus_dir()`, `get_style_guide_path()`, `get_render_cache_dir()`, `get_ai_logs_dir()` — all auto-create dirs
- [ ] `pptx_generator.py` calls new pipeline stubs on each shell slide (pattern is None → legacy fallback still runs → charts render fine)
- [ ] `api.py` calls `migrate_legacy_files()` in lifespan startup; obsolete M4/M5 training endpoints removed
- [ ] All existing tests pass — no regressions from removals
- [ ] Git tag `m6.2-backend-cleanup` created
