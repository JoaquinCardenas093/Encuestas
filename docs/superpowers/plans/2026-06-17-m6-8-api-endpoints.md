# M6.8 — Backend API Endpoints (Training Corpus + Style Guide) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the M4-era training endpoints (list/add/delete/reprocess/bank) with the new corpus-based API, add style guide read/edit endpoints, add a cache-clear endpoint, and wire async analysis job endpoints (analyze-with-ai and analysis-status are added in M6.7 — this plan wires the remaining endpoints and removes the old ones).

**Architecture:** `api.py` is the single backend router. New endpoints mirror the spec section 14 API table. Old M4 endpoints removed cleanly. Style guide read/write uses `style_guide.py` helpers. Corpus CRUD uses `config.get_corpus_dir()`.

**Tech Stack adds:** none.

---

## File Structure

**Modify (backend):**
- `backend/aurum_encuestas/api.py` — remove old endpoints, add new corpus + style guide + cache endpoints
- `backend/tests/test_api.py` — remove old tests, add new endpoint tests

**Depends on (must exist from M6.1-M6.7):**
- `backend/aurum_encuestas/config.py` — `get_corpus_dir()`, `get_render_cache_dir()`
- `backend/aurum_encuestas/style_guide.py` — `load_active_style_guide()`, `save_style_guide()`, `StyleGuide`, `Pattern`
- `backend/aurum_encuestas/style_guide_analyzer.py` — `run_full_analysis_pipeline()` (already wired via M6.7 endpoints)
- `backend/aurum_encuestas/pattern_classifier.py` — `_classifier_cache` dict for cache clearing

---

### Task 1: Remove old M4 training endpoints + their tests

**Files:**
- Modify: `backend/aurum_encuestas/api.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Identify and remove old endpoints**

Edit `backend/aurum_encuestas/api.py`. Remove the following endpoints and any helper functions used only by them:
- `POST /api/training/add`
- `GET /api/training/list`
- `POST /api/training/delete`
- `POST /api/training/reprocess`
- `GET /api/training/bank`

Also remove imports only used by those endpoints:
- `from .training_extractor import build_bank_from_pptxs, extract_layouts_from_pptx` (if no longer needed)
- `_save_bank()` helper function (corpus no longer needs layout_bank.json)

> **Note:** `analyze-with-ai` and `analysis-status` endpoints were added in M6.7 — keep them.

- [ ] **Step 2: Remove old training tests**

Edit `backend/tests/test_api.py`. Remove or comment out:
- `test_training_add_and_list`
- `test_training_bank_returns_layouts`
- `test_training_delete`

Replace with a placeholder confirming removal:

```python
# M4 training endpoints (add/list/delete/reprocess/bank) removed in M6.8.
# Tests for new corpus endpoints are in test_api.py Tasks 2-5 below.
```

- [ ] **Step 3: Run existing tests to verify no regressions in non-training tests**

Run: `cd backend && .venv/bin/pytest tests/test_api.py -v -k "not training"`
Expected: PASS (non-training tests unaffected).

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/api.py backend/tests/test_api.py
git commit -m "$(cat <<'EOF'
refactor(backend): remove M4 training endpoints (add/list/delete/reprocess/bank)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Corpus CRUD endpoints — add, delete, list

**Files:**
- Modify: `backend/aurum_encuestas/api.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_api.py`:

```python
import io
from pathlib import Path


def test_corpus_add_pptx(tmp_path, monkeypatch, training_pptx_path):
    """POST /api/training/corpus/add saves PPT to corpus dir and returns metadata."""
    monkeypatch.setenv("HOME", str(tmp_path))
    with open(training_pptx_path, "rb") as f:
        r = client.post(
            "/api/training/corpus/add",
            files={"file": ("demo.pptx", f, "application/octet-stream")},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "demo.pptx"
    assert "slides_with_charts" in body
    assert "added_at" in body

    # Verify file actually saved
    corpus_dir = tmp_path / ".aurum" / "training" / "corpus"
    assert (corpus_dir / "demo.pptx").exists()


def test_corpus_add_rejects_non_pptx(tmp_path, monkeypatch):
    """Only .pptx files should be accepted."""
    monkeypatch.setenv("HOME", str(tmp_path))
    fake_csv = io.BytesIO(b"col1,col2\n1,2")
    r = client.post(
        "/api/training/corpus/add",
        files={"file": ("data.csv", fake_csv, "text/csv")},
    )
    assert r.status_code == 400
    assert "pptx" in r.json()["detail"].lower()


def test_corpus_list_returns_pptxs(tmp_path, monkeypatch, training_pptx_path):
    """GET /api/training/corpus/list returns list of corpus PPTs with metadata."""
    monkeypatch.setenv("HOME", str(tmp_path))
    corpus_dir = tmp_path / ".aurum" / "training" / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy(training_pptx_path, corpus_dir / "deck_a.pptx")
    shutil.copy(training_pptx_path, corpus_dir / "deck_b.pptx")

    r = client.get("/api/training/corpus/list")
    assert r.status_code == 200
    body = r.json()
    assert "pptxs" in body
    filenames = [p["filename"] for p in body["pptxs"]]
    assert "deck_a.pptx" in filenames
    assert "deck_b.pptx" in filenames
    # Each item should have filename, slides_with_charts, added_at
    for pptx_info in body["pptxs"]:
        assert "filename" in pptx_info
        assert "added_at" in pptx_info
        assert "slides_with_charts" in pptx_info


def test_corpus_list_empty_when_no_corpus(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    r = client.get("/api/training/corpus/list")
    assert r.status_code == 200
    assert r.json()["pptxs"] == []


def test_corpus_delete_removes_file(tmp_path, monkeypatch, training_pptx_path):
    """POST /api/training/corpus/delete removes file from corpus."""
    monkeypatch.setenv("HOME", str(tmp_path))
    corpus_dir = tmp_path / ".aurum" / "training" / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy(training_pptx_path, corpus_dir / "to_delete.pptx")

    r = client.post("/api/training/corpus/delete", json={"filename": "to_delete.pptx"})
    assert r.status_code == 200
    assert r.json()["deleted"] is True
    assert not (corpus_dir / "to_delete.pptx").exists()


def test_corpus_delete_missing_file_still_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    r = client.post("/api/training/corpus/delete", json={"filename": "nonexistent.pptx"})
    assert r.status_code == 200
    assert r.json()["deleted"] is False
```

- [ ] **Step 2: Implement corpus endpoints**

Append to `backend/aurum_encuestas/api.py`:

```python
from datetime import UTC, datetime as dt
from fastapi import HTTPException, UploadFile, File

from .config import get_corpus_dir


def _count_slides_with_charts(pptx_path: Path) -> int:
    """Count slides in PPTX that have at least one chart shape."""
    try:
        from pptx import Presentation
        prs = Presentation(str(pptx_path))
        return sum(
            1 for slide in prs.slides
            if any(getattr(sh, "has_chart", False) for sh in slide.shapes)
        )
    except Exception:
        return 0


@app.post("/api/training/corpus/add")
async def corpus_add(file: UploadFile = File(...)):
    """Save an uploaded PPT to the corpus directory."""
    filename = file.filename or "upload.pptx"
    if not filename.lower().endswith(".pptx"):
        raise HTTPException(status_code=400, detail="Only .pptx files are accepted for the training corpus.")

    corpus_dir = get_corpus_dir()
    dest = corpus_dir / filename
    contents = await file.read()
    dest.write_bytes(contents)

    slides_with_charts = _count_slides_with_charts(dest)
    return {
        "filename": filename,
        "slides_with_charts": slides_with_charts,
        "added_at": dt.now(UTC).isoformat(),
    }


@app.get("/api/training/corpus/list")
async def corpus_list():
    """List all PPTs in the corpus directory with metadata."""
    corpus_dir = get_corpus_dir()
    pptxs = []
    for p in sorted(corpus_dir.glob("*.pptx")):
        pptxs.append({
            "filename": p.name,
            "slides_with_charts": _count_slides_with_charts(p),
            "added_at": dt.fromtimestamp(p.stat().st_mtime, UTC).isoformat(),
            "size_bytes": p.stat().st_size,
        })
    return {"pptxs": pptxs}


class CorpusDeleteRequest(BaseModel):
    filename: str


@app.post("/api/training/corpus/delete")
async def corpus_delete(req: CorpusDeleteRequest):
    """Delete a PPT from the corpus by filename."""
    corpus_dir = get_corpus_dir()
    target = corpus_dir / req.filename
    if not target.exists():
        return {"deleted": False, "message": f"{req.filename} not found in corpus"}
    # Safety: only delete .pptx files within corpus dir
    if not str(target.resolve()).startswith(str(corpus_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid filename — path traversal not allowed.")
    target.unlink()
    return {"deleted": True}
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_api.py -k "corpus" -v`
Expected: 6 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/api.py backend/tests/test_api.py
git commit -m "$(cat <<'EOF'
feat(backend): corpus CRUD endpoints — /corpus/add, /corpus/list, /corpus/delete

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Verify analyze-with-ai + analysis-status from M6.7 are wired

**Files:**
- Modify: `backend/tests/test_api.py`

> **Note:** These endpoints were implemented in M6.7 plan Task 5. This task verifies they exist and pass integration-level tests.

- [ ] **Step 1: Full async job integration test**

Append to `backend/tests/test_api.py`:

```python
import time


def test_analyze_with_ai_endpoint_returns_job_id():
    r = client.post("/api/training/analyze-with-ai")
    assert r.status_code == 200
    body = r.json()
    assert "job_id" in body
    assert isinstance(body["job_id"], str)


def test_analysis_status_returns_progress_for_valid_job():
    r = client.post("/api/training/analyze-with-ai")
    job_id = r.json()["job_id"]

    # Poll status immediately — job may still be running
    r2 = client.get(f"/api/training/analysis-status/{job_id}")
    assert r2.status_code == 200
    body = r2.json()
    assert "progress" in body
    assert "status" in body
    assert body["status"] in ("running", "done", "error")


def test_analysis_status_404_for_unknown_job():
    r = client.get("/api/training/analysis-status/nonexistent-job-id-xyz")
    assert r.status_code == 404
```

- [ ] **Step 2: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_api.py -k "analyze_with_ai or analysis_status" -v`
Expected: 3 PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_api.py
git commit -m "$(cat <<'EOF'
test(backend): integration tests for analyze-with-ai and analysis-status endpoints

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Style guide read + manual pattern edit endpoints

**Files:**
- Modify: `backend/aurum_encuestas/api.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_api.py`:

```python
MINIMAL_STYLE_GUIDE = {
    "version": 1,
    "is_builtin": False,
    "generated_at": "2026-06-17T20:00:00Z",
    "ai_prompt_version": "v1.0",
    "source_pptxs": ["test.pptx"],
    "manual_edits": {},
    "global": {
        "typography": {"font_family": "Arial", "title_size": 16, "subtitle_size": 12, "label_size": 9, "body_size": 10},
        "text_patterns": {"title": "T", "notes": "N", "analysis_style": "A", "tone": "formal"},
        "suggested_palette": ["#7F7F7F"],
        "vibe": "Min",
    },
    "available_chart_types": ["PIE"],
    "patterns": [
        {
            "id": "binary_general",
            "priority": 0,
            "trigger": {"field": "n_charts_in_slide", "$eq": 1},
            "extends": None,
            "best_example": "test.pptx#slide1",
            "why_picked": "Clean",
            "implementation": {"elements": []},
        }
    ],
}


def test_get_style_guide_returns_builtin_when_none_exists(tmp_path, monkeypatch):
    """When no style_guide.json exists, returns the built-in fallback."""
    monkeypatch.setenv("HOME", str(tmp_path))
    r = client.get("/api/training/style-guide")
    assert r.status_code == 200
    body = r.json()
    assert "patterns" in body
    assert "global" in body
    # Should have is_builtin True if falling back
    assert isinstance(body["patterns"], list)


def test_get_style_guide_returns_saved_guide(tmp_path, monkeypatch):
    """When style_guide.json exists, returns it."""
    monkeypatch.setenv("HOME", str(tmp_path))
    training_dir = tmp_path / ".aurum" / "training"
    training_dir.mkdir(parents=True, exist_ok=True)
    sg_path = training_dir / "style_guide.json"
    import json
    sg_path.write_text(json.dumps(MINIMAL_STYLE_GUIDE), encoding="utf-8")

    r = client.get("/api/training/style-guide")
    assert r.status_code == 200
    body = r.json()
    assert body["source_pptxs"] == ["test.pptx"]
    assert len(body["patterns"]) == 1


def test_put_style_guide_pattern_updates_pattern(tmp_path, monkeypatch):
    """PUT /api/training/style-guide/pattern/{pattern_id} updates a pattern and marks manual_edits."""
    monkeypatch.setenv("HOME", str(tmp_path))
    training_dir = tmp_path / ".aurum" / "training"
    training_dir.mkdir(parents=True, exist_ok=True)
    import json
    (training_dir / "style_guide.json").write_text(json.dumps(MINIMAL_STYLE_GUIDE), encoding="utf-8")

    updated_pattern = dict(MINIMAL_STYLE_GUIDE["patterns"][0])
    updated_pattern["why_picked"] = "Updated by user"

    r = client.put("/api/training/style-guide/pattern/binary_general", json=updated_pattern)
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # Reload and verify
    r2 = client.get("/api/training/style-guide")
    body = r2.json()
    pat = next(p for p in body["patterns"] if p["id"] == "binary_general")
    assert pat["why_picked"] == "Updated by user"
    assert "binary_general" in body["manual_edits"]


def test_put_style_guide_pattern_404_when_not_found(tmp_path, monkeypatch):
    """PUT to non-existent pattern_id returns 404."""
    monkeypatch.setenv("HOME", str(tmp_path))
    training_dir = tmp_path / ".aurum" / "training"
    training_dir.mkdir(parents=True, exist_ok=True)
    import json
    (training_dir / "style_guide.json").write_text(json.dumps(MINIMAL_STYLE_GUIDE), encoding="utf-8")

    r = client.put("/api/training/style-guide/pattern/nonexistent_id", json={"id": "nonexistent_id", "priority": 99})
    assert r.status_code == 404
```

- [ ] **Step 2: Implement style guide endpoints**

Append to `backend/aurum_encuestas/api.py`:

```python
from .style_guide import load_active_style_guide, save_style_guide, BUILTIN_STYLE_GUIDE


@app.get("/api/training/style-guide")
async def get_style_guide():
    """Return the active style guide (AI-generated or built-in fallback)."""
    try:
        sg = load_active_style_guide()
    except Exception:
        sg = BUILTIN_STYLE_GUIDE
    return sg.model_dump()


class PatternUpdateRequest(BaseModel):
    id: str
    priority: int = 0
    trigger: dict = {}
    extends: str | None = None
    best_example: str = ""
    why_picked: str = ""
    implementation: dict = {}


@app.put("/api/training/style-guide/pattern/{pattern_id}")
async def update_style_guide_pattern(pattern_id: str, req: PatternUpdateRequest):
    """Manually edit a single pattern in the active style guide.

    Marks manual_edits[pattern_id] = current timestamp so future AI re-analysis
    can detect which patterns have been user-modified.
    """
    try:
        sg = load_active_style_guide()
    except Exception:
        sg = BUILTIN_STYLE_GUIDE

    # Find the pattern to update
    pattern_idx = next(
        (i for i, p in enumerate(sg.patterns) if p.id == pattern_id),
        None,
    )
    if pattern_idx is None:
        raise HTTPException(status_code=404, detail=f"Pattern {pattern_id!r} not found in active style guide.")

    # Update the pattern fields
    existing = sg.patterns[pattern_idx]
    updated_data = existing.model_dump()
    req_dict = req.model_dump()
    updated_data.update({k: v for k, v in req_dict.items() if v is not None})

    from .style_guide import Pattern
    try:
        sg.patterns[pattern_idx] = Pattern.model_validate(updated_data)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid pattern data: {exc}")

    # Mark as manually edited
    if sg.manual_edits is None:
        sg.manual_edits = {}
    sg.manual_edits[pattern_id] = dt.now(UTC).isoformat()

    save_style_guide(sg)
    return {"ok": True, "pattern_id": pattern_id, "edited_at": sg.manual_edits[pattern_id]}
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_api.py -k "style_guide" -v`
Expected: 4 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/api.py backend/tests/test_api.py
git commit -m "$(cat <<'EOF'
feat(backend): style guide endpoints — GET /style-guide + PUT /style-guide/pattern/{id}

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Cache clear endpoint + full API test sweep

**Files:**
- Modify: `backend/aurum_encuestas/api.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_api.py`:

```python
def test_clear_cache_render(tmp_path, monkeypatch):
    """POST /api/training/clear-cache with cache_type=render clears PNG files from render_cache."""
    monkeypatch.setenv("HOME", str(tmp_path))
    render_cache = tmp_path / ".aurum" / "training" / "render_cache"
    render_cache.mkdir(parents=True, exist_ok=True)
    # Seed some fake PNG files
    (render_cache / "abc123_0.png").write_bytes(b"fake")
    (render_cache / "def456_1.png").write_bytes(b"fake2")

    r = client.post("/api/training/clear-cache", json={"cache_type": "render"})
    assert r.status_code == 200
    body = r.json()
    assert body["cleared"]["render"] >= 2
    assert not list(render_cache.glob("*.png"))


def test_clear_cache_classifier(tmp_path, monkeypatch):
    """POST /api/training/clear-cache with cache_type=classifier clears the in-memory classifier cache."""
    monkeypatch.setenv("HOME", str(tmp_path))
    r = client.post("/api/training/clear-cache", json={"cache_type": "classifier"})
    assert r.status_code == 200
    body = r.json()
    assert "classifier" in body["cleared"]


def test_clear_cache_all(tmp_path, monkeypatch):
    """POST /api/training/clear-cache with cache_type=all clears all caches."""
    monkeypatch.setenv("HOME", str(tmp_path))
    render_cache = tmp_path / ".aurum" / "training" / "render_cache"
    render_cache.mkdir(parents=True, exist_ok=True)
    (render_cache / "xyz_0.png").write_bytes(b"fake")

    r = client.post("/api/training/clear-cache", json={"cache_type": "all"})
    assert r.status_code == 200
    body = r.json()
    assert "render" in body["cleared"]
    assert "classifier" in body["cleared"]


def test_clear_cache_invalid_type_returns_422():
    r = client.post("/api/training/clear-cache", json={"cache_type": "unknown_type"})
    assert r.status_code == 422
```

- [ ] **Step 2: Implement cache clear endpoint**

Append to `backend/aurum_encuestas/api.py`:

```python
from typing import Literal
from .config import get_render_cache_dir


class ClearCacheRequest(BaseModel):
    cache_type: Literal["render", "classifier", "all"]


@app.post("/api/training/clear-cache")
async def clear_cache(req: ClearCacheRequest):
    """Clear one or all backend caches.

    cache_type options:
      - "render": deletes all PNG files in ~/.aurum/training/render_cache/
      - "classifier": clears in-memory pattern classifier LRU dict
      - "all": both of the above
    """
    cleared: dict[str, int] = {}

    if req.cache_type in ("render", "all"):
        cache_dir = get_render_cache_dir()
        png_files = list(cache_dir.glob("*.png"))
        for f in png_files:
            try:
                f.unlink()
            except Exception:
                pass
        cleared["render"] = len(png_files)

    if req.cache_type in ("classifier", "all"):
        try:
            from .pattern_classifier import _classifier_cache
            count = len(_classifier_cache)
            _classifier_cache.clear()
            cleared["classifier"] = count
        except (ImportError, AttributeError):
            cleared["classifier"] = 0

    return {"cleared": cleared, "cache_type": req.cache_type}
```

- [ ] **Step 3: Ensure `_classifier_cache` is exported from pattern_classifier**

Edit `backend/aurum_encuestas/pattern_classifier.py`. Add at module level (if not already present from M6.3):

```python
# Module-level LRU cache for pattern classifier results
# Key: (slide_config_hash, style_guide_hash) → matched pattern id or None
_classifier_cache: dict[str, str | None] = {}
```

- [ ] **Step 4: Run cache clear tests**

Run: `cd backend && .venv/bin/pytest tests/test_api.py -k "clear_cache" -v`
Expected: 4 PASS.

- [ ] **Step 5: Run full backend test suite**

Run: `cd backend && .venv/bin/pytest -v`
Expected: all PASS.

- [ ] **Step 6: Run linter**

Run: `cd backend && .venv/bin/ruff check aurum_encuestas tests`
Expected: no errors (fix any that appear before committing).

- [ ] **Step 7: Commit**

```bash
git add backend/aurum_encuestas/api.py backend/aurum_encuestas/pattern_classifier.py backend/tests/test_api.py
git commit -m "$(cat <<'EOF'
feat(backend): POST /api/training/clear-cache + full API sweep — all M6.8 endpoints done

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Tag the sub-milestone:

```bash
git tag m6.8
```

---

## M6.8 Done When

### Removed (M4 obsolete)
- `POST /api/training/add` — removed
- `GET /api/training/list` — removed
- `POST /api/training/delete` — removed
- `POST /api/training/reprocess` — removed
- `GET /api/training/bank` — removed
- All corresponding M4 tests removed from `test_api.py`

### Added (M6 corpus + style guide)
- `POST /api/training/corpus/add` — saves `.pptx` only, returns `{filename, slides_with_charts, added_at}`, rejects non-pptx with 400
- `GET /api/training/corpus/list` — returns `{pptxs: [{filename, slides_with_charts, added_at, size_bytes}]}`
- `POST /api/training/corpus/delete` — deletes by filename, returns `{deleted: bool}`, prevents path traversal
- `POST /api/training/analyze-with-ai` — (from M6.7) returns `{job_id}`, starts background task
- `GET /api/training/analysis-status/{job_id}` — (from M6.7) returns `{progress, status, message}`, 404 on unknown id
- `GET /api/training/style-guide` — returns active style guide or built-in fallback
- `PUT /api/training/style-guide/pattern/{pattern_id}` — updates pattern, sets `manual_edits[pattern_id]`, 404 if not found
- `POST /api/training/clear-cache` — accepts `{cache_type: "render"|"classifier"|"all"}`, 422 on invalid type

### Quality
- Full backend test suite passes with no regressions
- `ruff check` passes with no errors
- All new endpoints tested with monkeypatched HOME for filesystem isolation
- Git tag `m6.8`
