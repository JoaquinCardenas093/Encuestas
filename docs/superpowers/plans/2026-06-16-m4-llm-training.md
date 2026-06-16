# M4 — LLM Analyses + Training Corpus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire Claude Haiku 4.5 for generating analyses (3 scopes: slide, question, chart) with prompt caching. Build the Training tab: upload PPTs to `~/.aurum/training/`, extract layouts/styles into `layout_bank.json`, list/delete/reprocess corpus.

**Architecture:** Backend adds `llm_client.py` (Anthropic SDK with ephemeral cache), `training_extractor.py` (parse PPTs to extract layouts + chart styles + text styles), `config.py` (~/.aurum/ paths). Frontend adds analyses UI in ConfigPanel + AddAnalysisModal + dedicated Training page.

**Tech Stack adds:** anthropic SDK, python-dotenv.

---

## File Structure

**Create (backend):**
- `backend/aurum_encuestas/llm_client.py`
- `backend/aurum_encuestas/training_extractor.py`
- `backend/aurum_encuestas/config.py` — handles `~/.aurum/` dir
- `backend/tests/test_llm_client.py`
- `backend/tests/test_training_extractor.py`
- `backend/tests/test_config.py`

**Modify (backend):**
- `backend/aurum_encuestas/api.py` — endpoints `/api/generate-analysis`, `/api/training/add`, `/api/training/list`, `/api/training/delete`, `/api/training/reprocess`, `/api/training/bank`
- `backend/aurum_encuestas/models.py` — add `LayoutBank`, `LearnedLayout`, `TrainingPPT`
- `backend/tests/test_api.py` — endpoint tests

**Create (frontend):**
- `frontend/src/pages/Editor/modals/AddAnalysisModal.tsx`
- `frontend/src/pages/Training/TrainingPage.tsx` (real implementation)
- `frontend/src/api/training.ts` — training api wrappers
- `frontend/tests/AddAnalysisModal.test.tsx`
- `frontend/tests/TrainingPage.test.tsx`

**Modify (frontend):**
- `frontend/src/store/project.ts` — `addAnalysis`, `removeAnalysis`, `updateAnalysisText`
- `frontend/src/pages/Editor/ConfigPanel.tsx` — analysis list section
- `frontend/src/api/client.ts` — `generateAnalysis`

---

### Task 1: config — ~/.aurum/ dir + env loader

**Files:**
- Create: `backend/aurum_encuestas/config.py`
- Create: `backend/tests/test_config.py`

- [ ] **Step 1: Failing tests**

Create `backend/tests/test_config.py`:

```python
from pathlib import Path

import pytest

from aurum_encuestas.config import (
    AurumConfig, get_aurum_dir, get_training_dir, get_layout_bank_path, load_recents, add_recent,
)


def test_aurum_dir_default(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    d = get_aurum_dir()
    assert d == tmp_path / ".aurum"


def test_training_dir_created(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    d = get_training_dir()
    assert d.exists()
    assert d.is_dir()


def test_layout_bank_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = get_layout_bank_path()
    assert p.name == "layout_bank.json"


def test_recents_add_and_load(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    add_recent("/path/to/p1.aurum.json", "Proyecto 1")
    add_recent("/path/to/p2.aurum.json", "Proyecto 2")
    recs = load_recents()
    assert len(recs) == 2
    assert recs[0]["path"] == "/path/to/p2.aurum.json"  # most recent first


def test_recents_max_5(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    for i in range(8):
        add_recent(f"/p{i}.aurum.json", f"P{i}")
    recs = load_recents()
    assert len(recs) == 5
    assert recs[0]["path"] == "/p7.aurum.json"
```

- [ ] **Step 2: Run failing**

Run: `cd backend && .venv/bin/pytest tests/test_config.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement config.py**

Create `backend/aurum_encuestas/config.py`:

```python
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel


class AurumConfig(BaseModel):
    recents: list[dict] = []
    ui: dict = {"theme": "dark"}


def get_aurum_dir() -> Path:
    return Path(os.environ.get("HOME", os.path.expanduser("~"))) / ".aurum"


def get_training_dir() -> Path:
    d = get_aurum_dir() / "training"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_config_path() -> Path:
    return get_aurum_dir() / "config.json"


def get_layout_bank_path() -> Path:
    return get_training_dir() / "layout_bank.json"


def load_config() -> AurumConfig:
    p = get_config_path()
    if not p.exists():
        return AurumConfig()
    try:
        return AurumConfig.model_validate(json.loads(p.read_text()))
    except Exception:
        return AurumConfig()


def save_config(cfg: AurumConfig) -> None:
    p = get_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg.model_dump(), indent=2, ensure_ascii=False))


def add_recent(path: str, name: str) -> None:
    cfg = load_config()
    recents = [r for r in cfg.recents if r.get("path") != path]
    recents.insert(0, {"path": path, "name": name, "opened_at": datetime.now(UTC).isoformat()})
    cfg.recents = recents[:5]
    save_config(cfg)


def load_recents() -> list[dict]:
    return load_config().recents
```

- [ ] **Step 4: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_config.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/config.py backend/tests/test_config.py
git commit -m "feat(backend): config module — ~/.aurum/ dirs + recents (max 5)"
```

---

### Task 2: llm_client — Anthropic Haiku with prompt caching

**Files:**
- Create: `backend/aurum_encuestas/llm_client.py`
- Create: `backend/tests/test_llm_client.py`

- [ ] **Step 1: Failing tests**

Create `backend/tests/test_llm_client.py`:

```python
from unittest.mock import MagicMock, patch

import pytest

from aurum_encuestas.llm_client import generate_analysis
from aurum_encuestas.errors import LLMError


@patch("aurum_encuestas.llm_client._client")
def test_generate_analysis_chart_scope(mock_client):
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="El 50% respondió Sí.")]
    fake_msg.usage = MagicMock(input_tokens=200, output_tokens=20, cache_read_input_tokens=170)
    mock_client.messages.create.return_value = fake_msg

    text = generate_analysis(
        scope="chart",
        context={
            "section_title": "Test",
            "question_text": "?",
            "options": ["Sí", "No"],
            "breakdown_label": "General",
            "data": {"Total": {"Sí": {"count": 50, "pct": 0.5}, "No": {"count": 50, "pct": 0.5}}},
        },
    )
    assert "Sí" in text
    args, kwargs = mock_client.messages.create.call_args
    assert kwargs["model"] == "claude-haiku-4-5-20251001"
    system = kwargs["system"]
    assert isinstance(system, list)
    assert system[0]["cache_control"]["type"] == "ephemeral"


@patch("aurum_encuestas.llm_client._client", None)
def test_generate_analysis_no_api_key_raises():
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
        generate_analysis(scope="chart", context={"section_title": "x", "question_text": "y", "options": [], "breakdown_label": "z", "data": {}})


@patch("aurum_encuestas.llm_client._client")
def test_generate_analysis_truncates_long_response(mock_client):
    long_text = "x" * 1000
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text=long_text)]
    fake_msg.usage = MagicMock(input_tokens=200, output_tokens=20, cache_read_input_tokens=0)
    mock_client.messages.create.return_value = fake_msg

    text = generate_analysis(scope="chart", context={"section_title": "x", "question_text": "y", "options": [], "breakdown_label": "z", "data": {}})
    assert len(text) <= 500


@patch("aurum_encuestas.llm_client._client")
def test_generate_analysis_handles_api_error(mock_client):
    from anthropic import APIStatusError
    err = APIStatusError("rate limit", response=MagicMock(status_code=429), body=None)
    mock_client.messages.create.side_effect = err

    with pytest.raises(LLMError):
        generate_analysis(scope="chart", context={"section_title": "x", "question_text": "y", "options": [], "breakdown_label": "z", "data": {}})
```

- [ ] **Step 2: Run failing**

Run: `cd backend && .venv/bin/pytest tests/test_llm_client.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement llm_client**

Create `backend/aurum_encuestas/llm_client.py`:

```python
import json
import os
from typing import Optional

from anthropic import Anthropic, APIStatusError
from dotenv import load_dotenv

from .errors import LLMError


load_dotenv()

MODEL = "claude-haiku-4-5-20251001"
MAX_OUTPUT_TOKENS = 400
MAX_TEXT_LENGTH = 500

SYSTEM_PROMPT = """Sos analista de encuestas. Generás análisis técnicos breves en español neutral.

Tono: formal técnico, sin emojis, sin recomendaciones de acción salvo pedido.
Formato: 2-4 oraciones. Frases tipo "El X% de los encuestados...".
Datos: respetar números exactos provistos, no inventar cifras.

Si scope=chart: analizás SOLO ese chart específico (distribución, mayoría, contraste por categoría).
Si scope=question: te paso TODOS los charts de la slide que pertenecen a esa pregunta. Comparás entre breakdowns, identificás patrones cruzados de esa pregunta.
Si scope=slide: te paso TODOS los charts de la slide (de cualquier pregunta). Sintetizás insights cruzados entre charts y preguntas.

Idioma: español neutral. Longitud máxima: 4 oraciones.
"""


def _build_client() -> Optional[Anthropic]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    return Anthropic(api_key=key)


_client: Optional[Anthropic] = _build_client()


def generate_analysis(scope: str, context: dict) -> str:
    if _client is None:
        raise LLMError("ANTHROPIC_API_KEY no configurada. Agregá a .env y reiniciá el backend.")

    user_msg = f"""Sección: "{context.get('section_title', '')}"
Pregunta: "{context.get('question_text', '')}"
Opciones: {context.get('options', [])}
Breakdown: {context.get('breakdown_label', '')}
Datos: {json.dumps(context.get('data', {}), ensure_ascii=False)}
Scope: {scope}
"""

    try:
        msg = _client.messages.create(
            model=MODEL,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_msg}],
        )
    except APIStatusError as e:
        raise LLMError(f"LLM API error: {e}") from e
    except Exception as e:
        raise LLMError(f"LLM error: {e}") from e

    text = "".join(block.text for block in msg.content if hasattr(block, "text")).strip()
    if not text:
        return "[Análisis no disponible — editar manualmente]"
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH - 3] + "..."
    return text
```

- [ ] **Step 4: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_llm_client.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/llm_client.py backend/tests/test_llm_client.py
git commit -m "feat(backend): llm_client — Haiku 4.5 with prompt caching + error handling"
```

---

### Task 3: API — /api/generate-analysis endpoint

**Files:**
- Modify: `backend/aurum_encuestas/api.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Failing test**

Append to `backend/tests/test_api.py`:

```python
from unittest.mock import patch


@patch("aurum_encuestas.api.generate_analysis")
def test_generate_analysis_endpoint(mock_gen):
    mock_gen.return_value = "El 50% respondió Sí."
    payload = {
        "scope": "chart",
        "context": {
            "section_title": "X", "question_text": "?", "options": ["Sí", "No"],
            "breakdown_label": "General",
            "data": {"Total": {"Sí": {"count": 50, "pct": 0.5}}},
        },
    }
    r = client.post("/api/generate-analysis", json=payload)
    assert r.status_code == 200
    assert "Sí" in r.json()["text"]


@patch("aurum_encuestas.api.generate_analysis")
def test_generate_analysis_returns_fallback_on_error(mock_gen):
    from aurum_encuestas.errors import LLMError
    mock_gen.side_effect = LLMError("API down")
    payload = {"scope": "chart", "context": {"section_title": "x", "question_text": "y", "options": [], "breakdown_label": "z", "data": {}}}
    r = client.post("/api/generate-analysis", json=payload)
    assert r.status_code == 200
    assert "[Análisis no disponible" in r.json()["text"]
```

- [ ] **Step 2: Implement endpoint**

Append to `backend/aurum_encuestas/api.py`:

```python
from .llm_client import generate_analysis


class GenerateAnalysisRequest(BaseModel):
    scope: str
    context: dict


@app.post("/api/generate-analysis")
async def generate_analysis_endpoint(req: GenerateAnalysisRequest):
    try:
        text = generate_analysis(req.scope, req.context)
        return {"text": text, "fallback": False}
    except Exception:
        return {"text": "[Análisis no disponible — editar manualmente]", "fallback": True}
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_api.py -v -k "generate_analysis"`
Expected: 2 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/api.py backend/tests/test_api.py
git commit -m "feat(backend): /api/generate-analysis with LLM fallback"
```

---

### Task 4: training_extractor — parse PPT, extract layouts/styles

**Files:**
- Create: `backend/aurum_encuestas/training_extractor.py`
- Create: `backend/tests/test_training_extractor.py`
- Modify: `backend/aurum_encuestas/models.py` (add `LearnedLayout`, `LayoutBank`)
- Modify: `backend/tests/conftest.py` (add training fixture)

- [ ] **Step 1: Add models**

Append to `backend/aurum_encuestas/models.py`:

```python
class LayoutElement(BaseModel):
    role: str
    x: int
    y: int
    cx: int
    cy: int
    chart_type: Optional[ChartType] = None
    anchor_chart: Optional[int] = None


class LearnedLayout(BaseModel):
    id: str
    signature: str
    source: str
    free_area: dict
    elements: list[LayoutElement]
    chart_style: dict = {}
    text_style: dict = {}


class LayoutBank(BaseModel):
    extracted_at: Optional[str] = None
    source_pptxs: list[str] = []
    layouts: list[LearnedLayout] = []


class TrainingPPT(BaseModel):
    filename: str
    added_at: str
    layouts_extracted: int
    status: str = "ok"  # ok | error | pending
    error: Optional[str] = None
```

- [ ] **Step 2: Add training fixture in conftest**

Append to `backend/tests/conftest.py`:

```python
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE


@pytest.fixture
def training_pptx_path(tmp_path):
    """Synthesize a PPT with 1 chart slide for training extraction tests."""
    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    s = prs.slides.add_slide(blank)
    cd = CategoryChartData()
    cd.categories = ["Sí", "No"]
    cd.add_series("Total", [80, 20])
    s.shapes.add_chart(XL_CHART_TYPE.PIE, Inches(2), Inches(2), Inches(4), Inches(4), cd)
    tb = s.shapes.add_textbox(Inches(0.5), Inches(6.5), Inches(8), Inches(0.5))
    tb.text_frame.text = "Análisis: el 80% respondió Sí."

    out = tmp_path / "training.pptx"
    prs.save(out)
    return out
```

- [ ] **Step 3: Failing tests**

Create `backend/tests/test_training_extractor.py`:

```python
from aurum_encuestas.training_extractor import extract_layouts_from_pptx, signature_for_slide


def test_extract_at_least_one_layout(training_pptx_path):
    layouts = extract_layouts_from_pptx(str(training_pptx_path))
    assert len(layouts) >= 1
    lay = layouts[0]
    assert lay.signature  # non-empty
    assert any(el.role == "chart_0" for el in lay.elements)


def test_signature_encodes_chart_count_and_types():
    sig = signature_for_slide(n_charts=2, chart_types=["PIE", "BAR_CLUSTERED"], n_chart_an=1, n_q_an=0, has_slide_an=True)
    assert "2" in sig
    assert "PIE" in sig
    assert "BAR_CLUSTERED" in sig
```

- [ ] **Step 4: Implement training_extractor**

Create `backend/aurum_encuestas/training_extractor.py`:

```python
from datetime import UTC, datetime
from pathlib import Path

from pptx import Presentation

from .models import LayoutBank, LayoutElement, LearnedLayout


def signature_for_slide(n_charts: int, chart_types: list[str], n_chart_an: int, n_q_an: int, has_slide_an: bool) -> str:
    types = ",".join(sorted(chart_types))
    return f"{n_charts}|{types}|{n_chart_an}|{n_q_an}|{1 if has_slide_an else 0}"


def extract_layouts_from_pptx(pptx_path: str) -> list[LearnedLayout]:
    prs = Presentation(pptx_path)
    layouts: list[LearnedLayout] = []

    for slide_idx, slide in enumerate(prs.slides):
        charts = [sh for sh in slide.shapes if getattr(sh, "has_chart", False)]
        text_boxes = [sh for sh in slide.shapes if sh.has_text_frame and not getattr(sh, "has_chart", False)]
        if not charts:
            continue

        chart_types = []
        chart_els: list[LayoutElement] = []
        for i, ch in enumerate(charts):
            ct = _xl_to_app(ch.chart.chart_type) if hasattr(ch.chart, "chart_type") else "BAR"
            chart_types.append(ct)
            chart_els.append(LayoutElement(
                role=f"chart_{i}",
                x=ch.left or 0, y=ch.top or 0, cx=ch.width or 0, cy=ch.height or 0,
                chart_type=ct,
            ))

        # Classify text boxes by proximity to charts → chart_analysis, else slide_analysis
        text_els: list[LayoutElement] = []
        for tb in text_boxes:
            text = tb.text_frame.text or ""
            if "@" in text and "Titulo" in text or "Notas" in text:
                continue
            text_els.append(LayoutElement(
                role="slide_analysis" if _is_bottom(tb, prs.slide_height) else "chart_analysis_0",
                x=tb.left or 0, y=tb.top or 0, cx=tb.width or 0, cy=tb.height or 0,
            ))

        n_chart_an = sum(1 for e in text_els if e.role.startswith("chart_analysis"))
        n_slide_an = sum(1 for e in text_els if e.role == "slide_analysis")
        signature = signature_for_slide(len(charts), chart_types, n_chart_an, 0, n_slide_an > 0)

        free_area = {
            "x": min(e.x for e in chart_els),
            "y": min(e.y for e in chart_els),
            "cx": prs.slide_width,
            "cy": prs.slide_height,
        }

        layouts.append(LearnedLayout(
            id=f"lay_{slide_idx:03d}",
            signature=signature,
            source=f"{Path(pptx_path).name}#slide{slide_idx + 1}",
            free_area=free_area,
            elements=chart_els + text_els,
        ))

    return layouts


def _is_bottom(shape, slide_height: int) -> bool:
    top = shape.top or 0
    return top > slide_height * 0.7


_REVERSE_CHART_MAP = {
    5: "PIE", 4: "DOUGHNUT", 57: "BAR_CLUSTERED", 51: "COLUMN_CLUSTERED",
    58: "BAR_STACKED", 52: "COLUMN_STACKED", 4: "LINE", 1: "AREA", -4151: "RADAR",
}


def _xl_to_app(xl_type) -> str:
    try:
        v = int(xl_type)
    except (TypeError, ValueError):
        return "BAR"
    return _REVERSE_CHART_MAP.get(v, "BAR")


def build_bank_from_pptxs(pptx_paths: list[str]) -> LayoutBank:
    all_layouts: list[LearnedLayout] = []
    for p in pptx_paths:
        try:
            all_layouts.extend(extract_layouts_from_pptx(p))
        except Exception:
            continue
    return LayoutBank(
        extracted_at=datetime.now(UTC).isoformat(),
        source_pptxs=[Path(p).name for p in pptx_paths],
        layouts=all_layouts,
    )
```

- [ ] **Step 5: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_training_extractor.py -v`
Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/aurum_encuestas/training_extractor.py backend/tests/test_training_extractor.py backend/aurum_encuestas/models.py backend/tests/conftest.py
git commit -m "feat(backend): training_extractor — extract layouts + chart types from PPTs"
```

---

### Task 5: API — training endpoints (add/list/delete/reprocess/bank)

**Files:**
- Modify: `backend/aurum_encuestas/api.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_api.py`:

```python
def test_training_add_and_list(tmp_path, monkeypatch, training_pptx_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    with open(training_pptx_path, "rb") as f:
        r = client.post("/api/training/add", files={"file": ("t.pptx", f, "application/octet-stream")})
    assert r.status_code == 200
    assert r.json()["layouts_extracted"] >= 1

    r2 = client.get("/api/training/list")
    assert r2.status_code == 200
    assert len(r2.json()["pptxs"]) >= 1


def test_training_bank_returns_layouts(tmp_path, monkeypatch, training_pptx_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    with open(training_pptx_path, "rb") as f:
        client.post("/api/training/add", files={"file": ("t.pptx", f, "application/octet-stream")})
    r = client.get("/api/training/bank")
    assert r.status_code == 200
    bank = r.json()
    assert "layouts" in bank
    assert len(bank["layouts"]) >= 1


def test_training_delete(tmp_path, monkeypatch, training_pptx_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    with open(training_pptx_path, "rb") as f:
        client.post("/api/training/add", files={"file": ("removeme.pptx", f, "application/octet-stream")})
    r = client.post("/api/training/delete", json={"filename": "removeme.pptx"})
    assert r.status_code == 200
    r2 = client.get("/api/training/list")
    files = [p["filename"] for p in r2.json()["pptxs"]]
    assert "removeme.pptx" not in files
```

- [ ] **Step 2: Implement endpoints**

Append to `backend/aurum_encuestas/api.py`:

```python
import shutil
import json as _json

from .config import get_training_dir, get_layout_bank_path
from .training_extractor import build_bank_from_pptxs, extract_layouts_from_pptx
from datetime import UTC, datetime


def _save_bank() -> dict:
    pptxs = sorted([str(p) for p in get_training_dir().glob("*.pptx")])
    bank = build_bank_from_pptxs(pptxs)
    get_layout_bank_path().write_text(bank.model_dump_json(indent=2), encoding="utf-8")
    return bank.model_dump()


@app.post("/api/training/add")
async def training_add(file: UploadFile = File(...)):
    contents = await file.read()
    dest = get_training_dir() / file.filename
    dest.write_bytes(contents)
    layouts = extract_layouts_from_pptx(str(dest))
    _save_bank()
    return {"filename": file.filename, "layouts_extracted": len(layouts), "added_at": datetime.now(UTC).isoformat()}


@app.get("/api/training/list")
async def training_list():
    bank_path = get_layout_bank_path()
    bank = _json.loads(bank_path.read_text()) if bank_path.exists() else {"layouts": [], "source_pptxs": []}
    pptxs_info = []
    for p in sorted(get_training_dir().glob("*.pptx")):
        count = sum(1 for lay in bank.get("layouts", []) if lay.get("source", "").startswith(p.name + "#"))
        pptxs_info.append({"filename": p.name, "added_at": datetime.fromtimestamp(p.stat().st_mtime, UTC).isoformat(), "layouts_extracted": count, "status": "ok"})
    return {"pptxs": pptxs_info, "bank_size": len(bank.get("layouts", []))}


class DeleteTrainingRequest(BaseModel):
    filename: str


@app.post("/api/training/delete")
async def training_delete(req: DeleteTrainingRequest):
    p = get_training_dir() / req.filename
    if p.exists():
        p.unlink()
    _save_bank()
    return {"deleted": True}


@app.post("/api/training/reprocess")
async def training_reprocess():
    bank = _save_bank()
    return {"reprocessed": True, "bank_size": len(bank.get("layouts", []))}


@app.get("/api/training/bank")
async def training_bank():
    p = get_layout_bank_path()
    if not p.exists():
        return {"layouts": [], "source_pptxs": []}
    return _json.loads(p.read_text())
```

- [ ] **Step 3: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_api.py -v -k training`
Expected: 3 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/aurum_encuestas/api.py backend/tests/test_api.py
git commit -m "feat(backend): /api/training endpoints — add, list, delete, reprocess, bank"
```

---

### Task 6: Frontend — store actions for analyses

**Files:**
- Modify: `frontend/src/store/project.ts`
- Modify: `frontend/tests/store.test.ts`

- [ ] **Step 1: Failing tests**

Append to `frontend/tests/store.test.ts`:

```ts
describe("store analysis operations", () => {
  beforeEach(() => {
    useProjectStore.setState({ state: null })
    useProjectStore.getState().setNewProject({ name: "T", db_path: "./x", template_path: "./y" })
    useProjectStore.getState().addSeparator("Sec")
    useProjectStore.getState().addShell()
  })

  it("addAnalysis appends to slide.analyses", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addAnalysis(shellId, { scope: "slide", target_id: null, text: "Test", ai_generated: true, edited: false })
    expect(useProjectStore.getState().state!.slides[1].analyses.length).toBe(1)
  })

  it("removeAnalysis removes by id", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addAnalysis(shellId, { scope: "slide", target_id: null, text: "X", ai_generated: true, edited: false })
    const aid = useProjectStore.getState().state!.slides[1].analyses[0].id
    useProjectStore.getState().removeAnalysis(shellId, aid)
    expect(useProjectStore.getState().state!.slides[1].analyses.length).toBe(0)
  })

  it("updateAnalysisText changes text and marks edited", () => {
    const shellId = useProjectStore.getState().state!.slides[1].id
    useProjectStore.getState().addAnalysis(shellId, { scope: "slide", target_id: null, text: "X", ai_generated: true, edited: false })
    const aid = useProjectStore.getState().state!.slides[1].analyses[0].id
    useProjectStore.getState().updateAnalysisText(shellId, aid, "Nuevo")
    const a = useProjectStore.getState().state!.slides[1].analyses[0]
    expect(a.text).toBe("Nuevo")
    expect(a.edited).toBe(true)
  })
})
```

- [ ] **Step 2: Implement actions**

Append to `Store` interface in `frontend/src/store/project.ts`:

```ts
  addAnalysis(slideId: string, analysis: Omit<import("../types").Analysis, "id">): void
  removeAnalysis(slideId: string, analysisId: string): void
  updateAnalysisText(slideId: string, analysisId: string, text: string): void
```

Implementations inside temporal((set, get) => ({ ... })):

```ts
      addAnalysis(slideId, analysis) {
        const s = get().state
        if (!s) return
        const newAnalysis = { ...analysis, id: uid("an") }
        const slides = s.slides.map((sl) =>
          sl.id !== slideId ? sl : { ...sl, analyses: [...sl.analyses, newAnalysis] },
        )
        set({ state: { ...s, slides } })
      },

      removeAnalysis(slideId, analysisId) {
        const s = get().state
        if (!s) return
        const slides = s.slides.map((sl) =>
          sl.id !== slideId ? sl : { ...sl, analyses: sl.analyses.filter((a) => a.id !== analysisId) },
        )
        set({ state: { ...s, slides } })
      },

      updateAnalysisText(slideId, analysisId, text) {
        const s = get().state
        if (!s) return
        const slides = s.slides.map((sl) =>
          sl.id !== slideId ? sl : {
            ...sl,
            analyses: sl.analyses.map((a) => (a.id === analysisId ? { ...a, text, edited: true } : a)),
          },
        )
        set({ state: { ...s, slides } })
      },
```

- [ ] **Step 3: Run, verify pass**

Run: `cd frontend && npm test`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/store/project.ts frontend/tests/store.test.ts
git commit -m "feat(frontend): store actions — addAnalysis, removeAnalysis, updateAnalysisText"
```

---

### Task 7: API client — generateAnalysis + training wrappers

**Files:**
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/api/training.ts`

- [ ] **Step 1: Add generateAnalysis**

Append to `frontend/src/api/client.ts`:

```ts
export interface GenerateAnalysisContext {
  section_title: string
  question_text: string
  options: string[]
  breakdown_label: string
  data: Record<string, Record<string, { count: number; pct: number | null }>>
}

export async function generateAnalysis(scope: "slide" | "question" | "chart", context: GenerateAnalysisContext): Promise<{ text: string; fallback: boolean }> {
  return request("/generate-analysis", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scope, context }),
  })
}
```

- [ ] **Step 2: Create training api wrappers**

Create `frontend/src/api/training.ts`:

```ts
const BASE = "/api/training"

export interface TrainingPPT {
  filename: string
  added_at: string
  layouts_extracted: number
  status: string
}

export interface TrainingListResponse {
  pptxs: TrainingPPT[]
  bank_size: number
}

export async function addTraining(file: File): Promise<{ filename: string; layouts_extracted: number; added_at: string }> {
  const fd = new FormData()
  fd.append("file", file)
  const r = await fetch(`${BASE}/add`, { method: "POST", body: fd })
  if (!r.ok) throw await r.json()
  return r.json()
}

export async function listTraining(): Promise<TrainingListResponse> {
  const r = await fetch(`${BASE}/list`)
  if (!r.ok) throw await r.json()
  return r.json()
}

export async function deleteTraining(filename: string): Promise<void> {
  const r = await fetch(`${BASE}/delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename }),
  })
  if (!r.ok) throw await r.json()
}

export async function reprocessTraining(): Promise<void> {
  const r = await fetch(`${BASE}/reprocess`, { method: "POST" })
  if (!r.ok) throw await r.json()
}

export async function getBank(): Promise<{ layouts: unknown[]; source_pptxs: string[] }> {
  const r = await fetch(`${BASE}/bank`)
  if (!r.ok) throw await r.json()
  return r.json()
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/api/training.ts
git commit -m "feat(frontend): api wrappers — generateAnalysis + training endpoints"
```

---

### Task 8: AddAnalysisModal

**Files:**
- Create: `frontend/src/pages/Editor/modals/AddAnalysisModal.tsx`
- Create: `frontend/tests/AddAnalysisModal.test.tsx`

- [ ] **Step 1: Failing test**

Create `frontend/tests/AddAnalysisModal.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import AddAnalysisModal from "../src/pages/Editor/modals/AddAnalysisModal"
import type { Slide, ParsedDB } from "../src/types"

const DB: ParsedDB = {
  questions: [{ id: "q1", code: "P1", text: "?", options: ["a"], confidence: 1.0 }],
  breakdowns: [{ id: "general", label: "General", categories: ["Total"] }],
  sample_size: 500,
  data_blocks: { counts_cols: [], pct_row_cols: [], pct_col_cols: [] },
}
const SLIDE: Slide = {
  id: "sl1", type: "shell", title: "Sec",
  charts: [{ id: "c1", question_id: "q1", breakdown_id: "general", chart_type: "PIE", multi_series: false }],
  analyses: [], auto_notes: null,
}

describe("AddAnalysisModal", () => {
  it("renders scope radios", () => {
    render(<AddAnalysisModal open slide={SLIDE} db={DB} onClose={() => {}} onAdd={() => {}} />)
    expect(screen.getByLabelText(/Slide/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Pregunta/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Chart/i)).toBeInTheDocument()
  })

  it("generating calls api and shows text", async () => {
    const onAdd = vi.fn()
    vi.mock("../src/api/client", () => ({
      generateAnalysis: () => Promise.resolve({ text: "Generated text", fallback: false }),
    }))
    render(<AddAnalysisModal open slide={SLIDE} db={DB} onClose={() => {}} onAdd={onAdd} />)
    await userEvent.click(screen.getByRole("button", { name: /Generar/i }))
    // wait for textarea to fill
    await screen.findByDisplayValue(/Generated text/i)
  })
})
```

- [ ] **Step 2: Implement modal**

Create `frontend/src/pages/Editor/modals/AddAnalysisModal.tsx`:

```tsx
import { useState } from "react"
import Modal from "../../../components/Modal"
import * as api from "../../../api/client"
import type { Analysis, AnalysisScope, ParsedDB, Slide } from "../../../types"

interface Props {
  open: boolean
  slide: Slide | null
  db: ParsedDB | null
  onClose(): void
  onAdd(a: Omit<Analysis, "id">): void
}

export default function AddAnalysisModal({ open, slide, db, onClose, onAdd }: Props) {
  const [scope, setScope] = useState<AnalysisScope>("slide")
  const [targetId, setTargetId] = useState<string>("")
  const [text, setText] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!open || !slide || !db) return null

  const handleGenerate = async () => {
    setBusy(true); setError(null)
    try {
      const ctx = _buildContext(scope, targetId, slide, db)
      const r = await api.generateAnalysis(scope, ctx)
      setText(r.text)
    } catch (e) {
      setError((e as { message?: string }).message || "Error")
      setText("[Análisis no disponible — editar manualmente]")
    } finally {
      setBusy(false)
    }
  }

  const handleAccept = () => {
    if (!text.trim()) return
    onAdd({
      scope, target_id: scope === "slide" ? null : targetId,
      text, ai_generated: true, edited: false,
    })
    setText(""); setScope("slide"); setTargetId("")
    onClose()
  }

  return (
    <Modal open={open} onClose={onClose} title="Agregar análisis" footer={
      <>
        <button onClick={onClose} className="px-3 py-1.5 text-sm rounded bg-neutral-700">Cancelar</button>
        <button onClick={handleAccept} disabled={!text.trim()} className="px-3 py-1.5 text-sm rounded bg-accent text-neutral-900 font-semibold disabled:opacity-40">Aceptar</button>
      </>
    }>
      <div className="text-xs text-neutral-400 mb-1">Scope</div>
      <div className="flex gap-3 mb-3">
        {(["slide", "question", "chart"] as AnalysisScope[]).map((s) => (
          <label key={s} className="flex items-center gap-1 text-sm">
            <input type="radio" name="scope" checked={scope === s} onChange={() => { setScope(s); setTargetId("") }} aria-label={s} />
            {s}
          </label>
        ))}
      </div>

      {scope === "question" && (
        <>
          <label className="block text-xs text-neutral-400 mb-1">Pregunta</label>
          <select value={targetId} onChange={(e) => setTargetId(e.target.value)} className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm">
            <option value="">— Seleccionar —</option>
            {Array.from(new Set(slide.charts.map((c) => c.question_id))).map((qid) => {
              const q = db.questions.find((q) => q.id === qid)
              return <option key={qid} value={qid}>{q?.code}: {q?.text}</option>
            })}
          </select>
        </>
      )}

      {scope === "chart" && (
        <>
          <label className="block text-xs text-neutral-400 mb-1">Chart</label>
          <select value={targetId} onChange={(e) => setTargetId(e.target.value)} className="w-full mb-3 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm">
            <option value="">— Seleccionar —</option>
            {slide.charts.map((c) => {
              const q = db.questions.find((q) => q.id === c.question_id)
              const b = db.breakdowns.find((b) => b.id === c.breakdown_id)
              return <option key={c.id} value={c.id}>{q?.code} · {b?.label} · {c.chart_type}</option>
            })}
          </select>
        </>
      )}

      <button
        onClick={handleGenerate}
        disabled={busy || (scope !== "slide" && !targetId)}
        className="w-full mb-3 bg-purple-700 hover:bg-purple-600 text-white text-sm py-1.5 rounded disabled:opacity-40"
      >
        {busy ? "Generando..." : "✨ Generar con AI"}
      </button>

      <label className="block text-xs text-neutral-400 mb-1">Texto análisis (editable)</label>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={5}
        className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
        placeholder="Generá o escribí manualmente..."
      />
      {error && <p className="text-xs text-red-400 mt-2">{error}</p>}
    </Modal>
  )
}


function _buildContext(scope: AnalysisScope, targetId: string, slide: Slide, db: ParsedDB) {
  const charts = scope === "chart"
    ? slide.charts.filter((c) => c.id === targetId)
    : scope === "question"
      ? slide.charts.filter((c) => c.question_id === targetId)
      : slide.charts

  const firstChart = charts[0]
  const q = firstChart ? db.questions.find((q) => q.id === firstChart.question_id) : null
  const b = firstChart ? db.breakdowns.find((b) => b.id === firstChart.breakdown_id) : null

  return {
    section_title: slide.title || "",
    question_text: q?.text || "",
    options: q?.options || [],
    breakdown_label: b?.label || "",
    data: {},  // backend fills if needed; for MVP we send empty since extractor lives backend-side
  }
}
```

- [ ] **Step 3: Run tests**

Run: `cd frontend && npm test -- AddAnalysisModal`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Editor/modals/AddAnalysisModal.tsx frontend/tests/AddAnalysisModal.test.tsx
git commit -m "feat(frontend): AddAnalysisModal with scope picker + LLM generate + editable text"
```

---

### Task 9: Extend ConfigPanel with analyses section

**Files:**
- Modify: `frontend/src/pages/Editor/ConfigPanel.tsx`

- [ ] **Step 1: Add analyses section**

Edit `frontend/src/pages/Editor/ConfigPanel.tsx`. Add imports + state + section:

```tsx
// imports
import AddAnalysisModal from "./modals/AddAnalysisModal"

// inside component, after chart list:
const addAnalysis = useProjectStore((s) => s.addAnalysis)
const removeAnalysis = useProjectStore((s) => s.removeAnalysis)
const [analysisModalOpen, setAnalysisModalOpen] = useState(false)
```

Add JSX after chart list (still inside `!isSep` block, before closing fragment):

```tsx
          <h4 className="text-xs uppercase text-neutral-500 mt-4 mb-2">Análisis ({slide.analyses.length})</h4>
          {slide.analyses.map((a) => (
            <div key={a.id} className="bg-neutral-800 border border-neutral-700 rounded p-2 mb-2 flex items-start gap-2">
              <span className={`text-xs px-1.5 rounded font-semibold ${
                a.scope === "slide" ? "bg-accent text-neutral-900" :
                a.scope === "question" ? "bg-green-500 text-neutral-900" :
                "bg-blue-400 text-neutral-900"
              }`}>{a.scope.slice(0, 4).toUpperCase()}</span>
              <span className="text-xs flex-1 line-clamp-2">{a.text}</span>
              <button onClick={() => removeAnalysis(slide.id, a.id)} className="text-neutral-500 hover:text-red-400">
                <Trash2 size={12} />
              </button>
            </div>
          ))}
          <button
            onClick={() => setAnalysisModalOpen(true)}
            className="w-full text-xs bg-transparent border border-dashed border-neutral-600 rounded py-1.5 flex items-center justify-center gap-1 text-neutral-400 hover:text-neutral-200"
          >
            <Plus size={12} /> Análisis
          </button>

          <AddAnalysisModal
            open={analysisModalOpen}
            slide={slide}
            db={parsedDb}
            onClose={() => setAnalysisModalOpen(false)}
            onAdd={(a) => addAnalysis(slide.id, a)}
          />
```

- [ ] **Step 2: Verify build + test**

Run: `cd frontend && npm run build`
Run: `cd frontend && npm test`
Expected: build + all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Editor/ConfigPanel.tsx
git commit -m "feat(frontend): ConfigPanel — analyses section with add/remove + scope badges"
```

---

### Task 10: Training page (full implementation)

**Files:**
- Modify: `frontend/src/pages/Training/TrainingPage.tsx`
- Create: `frontend/tests/TrainingPage.test.tsx`

- [ ] **Step 1: Failing test**

Create `frontend/tests/TrainingPage.test.tsx`:

```tsx
import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import TrainingPage from "../src/pages/Training/TrainingPage"

vi.mock("../src/api/training", () => ({
  listTraining: vi.fn(() => Promise.resolve({ pptxs: [{ filename: "deck_a.pptx", added_at: "2026-06-16T20:00:00Z", layouts_extracted: 5, status: "ok" }], bank_size: 5 })),
  addTraining: vi.fn(),
  deleteTraining: vi.fn(),
  reprocessTraining: vi.fn(),
  getBank: vi.fn(() => Promise.resolve({ layouts: [], source_pptxs: [] })),
}))

describe("TrainingPage", () => {
  it("lists training pptxs", async () => {
    render(<TrainingPage />)
    await waitFor(() => expect(screen.getByText("deck_a.pptx")).toBeInTheDocument())
    expect(screen.getByText(/Banco: 5 layouts/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Implement TrainingPage**

Overwrite `frontend/src/pages/Training/TrainingPage.tsx`:

```tsx
import { useEffect, useRef, useState } from "react"
import { Plus, Trash2, RefreshCw } from "lucide-react"
import * as tapi from "../../api/training"

export default function TrainingPage() {
  const [pptxs, setPptxs] = useState<tapi.TrainingPPT[]>([])
  const [bankSize, setBankSize] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const refresh = async () => {
    setLoading(true); setError(null)
    try {
      const r = await tapi.listTraining()
      setPptxs(r.pptxs)
      setBankSize(r.bank_size)
    } catch (e) {
      setError((e as { message?: string }).message || "Error")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  const handleAdd = async (f: File) => {
    setLoading(true)
    try {
      await tapi.addTraining(f)
      await refresh()
    } catch (e) {
      setError((e as { message?: string }).message || "Error")
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (filename: string) => {
    if (!window.confirm(`Eliminar ${filename}?`)) return
    await tapi.deleteTraining(filename)
    await refresh()
  }

  const handleReprocess = async () => {
    setLoading(true)
    try {
      await tapi.reprocessTraining()
      await refresh()
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto text-neutral-100">
      <header className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold">Entrenamiento</h2>
          <p className="text-sm text-neutral-400">Banco: {bankSize} layouts de {pptxs.length} PPTs</p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleReprocess} disabled={loading} className="text-sm bg-neutral-700 hover:bg-neutral-600 px-3 py-1.5 rounded flex items-center gap-1 disabled:opacity-40">
            <RefreshCw size={14} /> Re-procesar
          </button>
          <button onClick={() => fileRef.current?.click()} disabled={loading} className="text-sm bg-accent text-neutral-900 font-semibold px-3 py-1.5 rounded flex items-center gap-1">
            <Plus size={14} /> Agregar PPT
          </button>
          <input ref={fileRef} type="file" accept=".pptx" className="hidden" onChange={(e) => e.target.files?.[0] && handleAdd(e.target.files[0])} />
        </div>
      </header>

      {error && <div className="bg-red-900/40 border border-red-900 text-red-300 px-3 py-2 rounded mb-4 text-sm">{error}</div>}

      <table className="w-full text-sm">
        <thead className="text-xs text-neutral-400 border-b border-neutral-700">
          <tr>
            <th className="text-left py-2 px-2">Archivo</th>
            <th className="text-left py-2 px-2">Agregado</th>
            <th className="text-left py-2 px-2">Layouts</th>
            <th className="text-left py-2 px-2">Status</th>
            <th className="py-2 px-2 w-12"></th>
          </tr>
        </thead>
        <tbody>
          {pptxs.length === 0 && !loading && (
            <tr><td colSpan={5} className="text-center text-neutral-500 py-6">Sin training PPTs aún. Agregá uno.</td></tr>
          )}
          {pptxs.map((p) => (
            <tr key={p.filename} className="border-b border-neutral-800">
              <td className="py-2 px-2">{p.filename}</td>
              <td className="py-2 px-2 text-neutral-400">{new Date(p.added_at).toLocaleString()}</td>
              <td className="py-2 px-2">{p.layouts_extracted}</td>
              <td className="py-2 px-2">{p.status === "ok" ? "✓" : "⚠"}</td>
              <td className="py-2 px-2">
                <button onClick={() => handleDelete(p.filename)} className="text-neutral-500 hover:text-red-400">
                  <Trash2 size={14} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 3: Run, verify pass**

Run: `cd frontend && npm test -- TrainingPage`
Expected: 1 PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Training/TrainingPage.tsx frontend/tests/TrainingPage.test.tsx
git commit -m "feat(frontend): TrainingPage — list/add/delete/reprocess training PPTs"
```

---

### Task 11: M4 wrap-up — full test suite + manual smoke + tag

**Files:** none

- [ ] **Step 1: Run all tests**

Run: `cd backend && .venv/bin/pytest -v`
Run: `cd frontend && npm test`
Expected: all PASS.

- [ ] **Step 2: Manual smoke**

Terminals: `make dev-backend` + `make dev-frontend`.

1. Set `ANTHROPIC_API_KEY=sk-ant-...` in `backend/.env`. Restart backend.
2. Open app → upload xlsx + template → confirm wizard → enter editor
3. Add Separador + Shell + 1 chart
4. Click + Análisis → scope=slide → Generar → verify text fills (AI response) → Aceptar
5. See analysis appear in ConfigPanel list
6. Click tab "Entrenamiento" → "+ Agregar PPT" → upload PPT con charts → verify it appears in list + bank size > 0
7. Click "Re-procesar" → verify still works
8. Delete a training PPT → verify removed

- [ ] **Step 3: Tag**

```bash
git tag m4-llm-training
git log --oneline | head -30
```

---

## M4 Done When

- LLM generates análisis on demand (3 scopes), editable before accept
- Análisis aparecen en panel derecho con scope badges
- Training tab funciona: agregar/listar/eliminar/reprocesar PPTs
- `~/.aurum/training/` se popula con PPTs + `layout_bank.json` actualizado
- Errores LLM (sin key, rate limit) → fallback `[Análisis no disponible — editar manualmente]`
- ~70 tests pasan
- Git tag `m4-llm-training`
