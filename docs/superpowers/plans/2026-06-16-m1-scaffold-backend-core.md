# M1 — Scaffold + Backend Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the AurumEncuestas repo skeleton, configure tooling, and implement the backend core (xlsx parser, pptx template validator, project store) with full TDD coverage.

**Architecture:** Monorepo with `backend/` (Python 3.11+ FastAPI) and `frontend/` (React+Vite, stub only in M1). Backend is stateless REST. Tests with pytest + fixtures.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, openpyxl, python-pptx, pydantic v2, pytest, pytest-asyncio, httpx (test client). Makefile orchestration.

---

## File Structure

**Create:**
- `Makefile` — `make dev / test / lint`
- `.env.example` — `ANTHROPIC_API_KEY=`
- `.gitignore` — already exists, extend
- `README.md` — minimal
- `backend/pyproject.toml` — deps + tool config
- `backend/aurum_encuestas/__init__.py` — package marker
- `backend/aurum_encuestas/api.py` — FastAPI app + endpoint stubs
- `backend/aurum_encuestas/models.py` — pydantic models (Question, Breakdown, ParsedDB, Slide, ProjectState, TemplateInfo)
- `backend/aurum_encuestas/xlsx_parser.py` — parse + heuristics
- `backend/aurum_encuestas/pptx_template.py` — validate + extract shell/separator/free_area
- `backend/aurum_encuestas/project_store.py` — `.aurum.json` I/O + path resolution
- `backend/aurum_encuestas/errors.py` — typed errors
- `backend/tests/conftest.py` — fixtures
- `backend/tests/fixtures/valid.xlsx` — synthesized via openpyxl in conftest
- `backend/tests/fixtures/valid_template.pptx` — synthesized via python-pptx in conftest
- `backend/tests/test_xlsx_parser.py`
- `backend/tests/test_pptx_template.py`
- `backend/tests/test_project_store.py`
- `backend/tests/test_api.py`

---

### Task 1: Repo bootstrap (Makefile, README, .gitignore extension)

**Files:**
- Modify: `.gitignore` (add Python/Node specific entries if missing)
- Create: `Makefile`
- Create: `README.md`
- Create: `.env.example`

- [ ] **Step 1: Verify .gitignore already covers Python/Node**

Run: `cat .gitignore | grep -E "(__pycache__|node_modules|\.env)"`
Expected: prints matching lines (already added in spec commit).

- [ ] **Step 2: Write Makefile**

Create `Makefile`:

```makefile
.PHONY: dev test lint backend-install frontend-install install

install: backend-install

backend-install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

dev-backend:
	cd backend && .venv/bin/uvicorn aurum_encuestas.api:app --reload --port 8000

test-backend:
	cd backend && .venv/bin/pytest -v

lint-backend:
	cd backend && .venv/bin/ruff check aurum_encuestas tests

dev: dev-backend

test: test-backend

lint: lint-backend
```

- [ ] **Step 3: Write README.md**

Create `README.md`:

```markdown
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
```

- [ ] **Step 4: Write .env.example**

Create `.env.example`:

```
ANTHROPIC_API_KEY=
```

- [ ] **Step 5: Commit bootstrap**

```bash
git add Makefile README.md .env.example
git commit -m "chore: bootstrap repo (Makefile, README, .env.example)"
```

---

### Task 2: Backend Python package setup

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/aurum_encuestas/__init__.py`
- Create: `backend/.gitignore`

- [ ] **Step 1: Write pyproject.toml**

Create `backend/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "aurum-encuestas"
version = "0.1.0"
description = "Generador de presentaciones PPT desde encuestas tabuladas"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.110",
  "uvicorn[standard]>=0.27",
  "openpyxl>=3.1",
  "python-pptx>=0.6.23",
  "pydantic>=2.6",
  "python-multipart>=0.0.9",
  "anthropic>=0.40",
  "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
  "httpx>=0.27",
  "ruff>=0.4",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["aurum_encuestas*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 120
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP"]
ignore = ["E501"]
```

- [ ] **Step 2: Create package marker**

Create `backend/aurum_encuestas/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Backend .gitignore**

Create `backend/.gitignore`:

```
.venv/
*.egg-info/
.pytest_cache/
__pycache__/
*.pyc
.env
```

- [ ] **Step 4: Install + verify**

Run: `make backend-install`
Expected: creates `backend/.venv/`, installs deps without error.

Verify: `cd backend && .venv/bin/python -c "import aurum_encuestas; print(aurum_encuestas.__version__)"`
Expected: `0.1.0`

- [ ] **Step 5: Commit backend setup**

```bash
git add backend/pyproject.toml backend/aurum_encuestas/__init__.py backend/.gitignore
git commit -m "chore(backend): pyproject + package skeleton"
```

---

### Task 3: Pydantic models

**Files:**
- Create: `backend/aurum_encuestas/models.py`
- Create: `backend/tests/test_models.py`
- Create: `backend/tests/__init__.py`

- [ ] **Step 1: Write failing test for Question model**

Create `backend/tests/__init__.py` (empty).

Create `backend/tests/test_models.py`:

```python
from aurum_encuestas.models import Question, Breakdown, ParsedDB, Slide, Chart, Analysis, ProjectState


def test_question_basic():
    q = Question(id="q1", code="P1", text="¿Recuerda?", options=["Sí", "No"], confidence=1.0)
    assert q.id == "q1"
    assert q.confidence == 1.0


def test_breakdown_basic():
    b = Breakdown(id="sexo", label="Sexo", categories=["Hombre", "Mujer"])
    assert b.categories == ["Hombre", "Mujer"]


def test_parsed_db_basic():
    db = ParsedDB(
        questions=[Question(id="q1", code="P1", text="?", options=["a"], confidence=1.0)],
        breakdowns=[Breakdown(id="general", label="General", categories=["Total"])],
        sample_size=500,
        data_blocks={"counts_cols": [3, 17], "pct_row_cols": [21, 35], "pct_col_cols": [41, 55]},
    )
    assert db.sample_size == 500


def test_slide_separator():
    s = Slide(id="s1", type="separator", title="Sección 1")
    assert s.type == "separator"
    assert s.charts == []
    assert s.analyses == []


def test_slide_shell_with_chart():
    chart = Chart(id="c1", question_id="q1", breakdown_id="sexo", chart_type="PIE", multi_series=False)
    s = Slide(id="s2", type="shell", charts=[chart])
    assert len(s.charts) == 1
    assert s.charts[0].chart_type == "PIE"


def test_analysis_scopes():
    for scope in ("slide", "question", "chart"):
        a = Analysis(id="a1", scope=scope, target_id=None, text="x", ai_generated=True, edited=False)
        assert a.scope == scope


def test_project_state_roundtrip():
    state = ProjectState(
        version=1,
        project_name="Test",
        inputs={"db_path": "./x.xlsx", "template_path": "./t.pptx", "font_override": None},
        slides=[Slide(id="s1", type="separator", title="A")],
    )
    dumped = state.model_dump()
    restored = ProjectState.model_validate(dumped)
    assert restored.project_name == "Test"
```

- [ ] **Step 2: Run test to see it fails**

Run: `cd backend && .venv/bin/pytest tests/test_models.py -v`
Expected: ImportError on `aurum_encuestas.models`.

- [ ] **Step 3: Implement models.py**

Create `backend/aurum_encuestas/models.py`:

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field

ChartType = Literal[
    "PIE", "DONUT", "BAR", "COLUMN",
    "BAR_STACKED", "COLUMN_STACKED",
    "LINE", "AREA", "RADAR",
]

AnalysisScope = Literal["slide", "question", "chart"]
SlideType = Literal["separator", "shell"]


class Question(BaseModel):
    id: str
    code: str
    text: str
    options: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class Breakdown(BaseModel):
    id: str
    label: str
    categories: list[str]


class DataBlocks(BaseModel):
    counts_cols: list[int]
    pct_row_cols: list[int]
    pct_col_cols: list[int]


class ParsedDB(BaseModel):
    questions: list[Question]
    breakdowns: list[Breakdown]
    sample_size: int
    data_blocks: dict


class Chart(BaseModel):
    id: str
    question_id: str
    breakdown_id: str
    chart_type: ChartType
    multi_series: bool = False


class Analysis(BaseModel):
    id: str
    scope: AnalysisScope
    target_id: Optional[str] = None
    text: str
    ai_generated: bool = False
    edited: bool = False


class Slide(BaseModel):
    id: str
    type: SlideType
    title: Optional[str] = None
    charts: list[Chart] = []
    analyses: list[Analysis] = []
    auto_notes: Optional[str] = None


class ProjectInputs(BaseModel):
    db_path: str
    template_path: str
    font_override: Optional[str] = None


class ProjectState(BaseModel):
    version: int = 1
    app_name: str = "AurumEncuestas"
    project_name: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    inputs: ProjectInputs
    parsed_db: Optional[ParsedDB] = None
    slides: list[Slide] = []
    history: dict = Field(default_factory=lambda: {"past": [], "future": []})


class TemplateInfo(BaseModel):
    shell_slide_index: int
    separator_slide_index: int
    free_area: dict  # {x, y, cx, cy} EMU
    placeholders: list[str]  # ["@Titulo", "@Notas", ...]
    default_font: Optional[str] = None
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_models.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/models.py backend/tests/test_models.py backend/tests/__init__.py
git commit -m "feat(backend): pydantic models for project state, slides, charts, analyses"
```

---

### Task 4: Test fixtures (synthesized xlsx + pptx)

**Files:**
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/fixtures/__init__.py`

- [ ] **Step 1: Write conftest with fixtures generating xlsx + pptx in tmp_path**

Create `backend/tests/__init__.py` (already created).
Create `backend/tests/fixtures/__init__.py` (empty).

Create `backend/tests/conftest.py`:

```python
"""Test fixtures. Generates valid xlsx and pptx files on the fly per-test using tmp_path."""

import pytest
from openpyxl import Workbook
from pptx import Presentation
from pptx.util import Inches, Pt, Emu


@pytest.fixture
def valid_xlsx_path(tmp_path):
    """Synthesize an xlsx matching the BD Aurora schema (2 questions, 5 breakdowns, 3 blocks)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "BD - Análisis"

    # Row 1: breakdown group headers (cols 4-5 edad, 6-7 sexo, 8-12 nse, 13-17 punto)
    ws.cell(1, 4, "Rango de edad")
    ws.cell(1, 6, "Sexo")
    ws.cell(1, 8, "NSE")
    ws.cell(1, 13, "Punto")
    # Repeat at cols 22, 24, 26, 31 (block 2 starts at col 20)
    ws.cell(1, 22, "Rango de edad")
    ws.cell(1, 24, "Sexo")
    ws.cell(1, 26, "NSE")
    ws.cell(1, 31, "Punto")

    # Row 2: subcategories
    ws.cell(2, 3, "General")
    ws.cell(2, 4, "De 18 a 39 años")
    ws.cell(2, 5, "de 40 a 59 años")
    ws.cell(2, 6, "Hombre")
    ws.cell(2, 7, "Mujer")
    ws.cell(2, 8, "Alto")
    ws.cell(2, 9, "Medio")
    ws.cell(2, 10, "Bajo superior")
    ws.cell(2, 11, "Bajo inferior")
    ws.cell(2, 12, "Marginal")
    ws.cell(2, 13, "Paradero")
    ws.cell(2, 14, "Mall")
    ws.cell(2, 15, "CC")
    ws.cell(2, 16, "Plaza")
    ws.cell(2, 17, "Open Plaza")
    ws.cell(2, 21, "General")  # block 2 start

    # Row 3: totals (Total = 500, distribution per breakdown)
    ws.cell(3, 2, "Total")
    ws.cell(3, 3, 500)
    for col, val in enumerate([250, 250, 250, 250, 38, 120, 276, 52, 14, 100, 100, 100, 100, 100], start=4):
        ws.cell(3, col, val)

    # Demographic distribution rows (Sexo)
    ws.cell(4, 1, "Sexo")
    ws.cell(4, 2, "Hombre")
    ws.cell(4, 3, 250)
    ws.cell(5, 2, "Mujer")
    ws.cell(5, 3, 250)

    # Question 1: $p1.label with 2 options Sí/No
    ws.cell(18, 1, "$p1.recordacion")
    ws.cell(18, 2, "Sí")
    ws.cell(18, 3, 458)
    for col, val in enumerate([230, 228, 229, 229, 35, 112, 245, 52, 14, 100, 86, 91, 90, 91], start=4):
        ws.cell(18, col, val)
    ws.cell(19, 2, "No")
    ws.cell(19, 3, 42)

    # Block 2 (percentages) — col 21 repeats General header in row 2
    ws.cell(18, 19, "$p1.recordacion")
    ws.cell(18, 20, "Sí")
    ws.cell(18, 21, 0.916)
    ws.cell(19, 20, "No")
    ws.cell(19, 21, 0.084)

    out = tmp_path / "valid.xlsx"
    wb.save(out)
    return out


@pytest.fixture
def valid_template_path(tmp_path):
    """Synthesize a 2-slide template: shell + separator, both with @Titulo placeholders."""
    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)

    blank_layout = prs.slide_layouts[6]  # blank

    # Slide 1: SHELL with @Titulo top-left + @Notas bottom-left
    shell = prs.slides.add_slide(blank_layout)
    tb_title = shell.shapes.add_textbox(Inches(0.4), Inches(0.2), Inches(6), Inches(0.5))
    tb_title.text_frame.text = "@Titulo"
    tb_notes = shell.shapes.add_textbox(Inches(0.4), Inches(6.7), Inches(8), Inches(0.6))
    tb_notes.text_frame.text = "@Notas"

    # Slide 2: SEPARATOR with @Titulo middle
    sep = prs.slides.add_slide(blank_layout)
    tb_sep = sep.shapes.add_textbox(Inches(0.4), Inches(3.5), Inches(10), Inches(0.6))
    tb_sep.text_frame.text = "Análisis de resultados\n@Titulo"

    out = tmp_path / "valid_template.pptx"
    prs.save(out)
    return out


@pytest.fixture
def invalid_template_one_slide(tmp_path):
    """Template with only 1 slide → should fail validation."""
    prs = Presentation()
    blank_layout = prs.slide_layouts[6]
    s = prs.slides.add_slide(blank_layout)
    tb = s.shapes.add_textbox(Inches(0.4), Inches(0.2), Inches(6), Inches(0.5))
    tb.text_frame.text = "@Titulo"
    out = tmp_path / "invalid_one_slide.pptx"
    prs.save(out)
    return out


@pytest.fixture
def invalid_template_no_titulo(tmp_path):
    """Template with 2 slides but missing @Titulo placeholder."""
    prs = Presentation()
    blank_layout = prs.slide_layouts[6]
    for _ in range(2):
        s = prs.slides.add_slide(blank_layout)
        tb = s.shapes.add_textbox(Inches(0.4), Inches(0.2), Inches(6), Inches(0.5))
        tb.text_frame.text = "Sin marker"
    out = tmp_path / "invalid_no_titulo.pptx"
    prs.save(out)
    return out
```

- [ ] **Step 2: Verify fixtures load**

Run: `cd backend && .venv/bin/pytest tests/conftest.py --collect-only -v`
Expected: no errors collecting (fixtures defined, no tests yet).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/conftest.py backend/tests/fixtures/__init__.py
git commit -m "test(backend): conftest with synthesized xlsx + pptx fixtures"
```

---

### Task 5: Errors module

**Files:**
- Create: `backend/aurum_encuestas/errors.py`

- [ ] **Step 1: Write errors.py**

Create `backend/aurum_encuestas/errors.py`:

```python
class AurumError(Exception):
    """Base for typed app errors."""
    code: str = "internal_error"
    status: int = 500


class XlsxParseError(AurumError):
    code = "xlsx_parse_error"
    status = 400


class TemplateInvalidError(AurumError):
    code = "template_invalid"
    status = 400


class ProjectIOError(AurumError):
    code = "project_io_error"
    status = 500


class LLMError(AurumError):
    code = "llm_error"
    status = 502


class RenderError(AurumError):
    code = "render_error"
    status = 500
```

- [ ] **Step 2: Commit**

```bash
git add backend/aurum_encuestas/errors.py
git commit -m "feat(backend): typed error hierarchy"
```

---

### Task 6: xlsx parser — detect breakdowns + sample_size

**Files:**
- Create: `backend/aurum_encuestas/xlsx_parser.py`
- Create: `backend/tests/test_xlsx_parser.py`

- [ ] **Step 1: Write failing test for breakdown detection**

Create `backend/tests/test_xlsx_parser.py`:

```python
from aurum_encuestas.xlsx_parser import parse_xlsx
from aurum_encuestas.errors import XlsxParseError
import pytest


def test_parse_detects_sample_size(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    assert db.sample_size == 500


def test_parse_detects_breakdowns(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    ids = [b.id for b in db.breakdowns]
    assert "general" in ids
    assert "sexo" in ids
    assert "edad" in ids
    assert "nse" in ids
    assert "punto" in ids


def test_parse_breakdown_sexo_categories(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    sexo = next(b for b in db.breakdowns if b.id == "sexo")
    assert "Hombre" in sexo.categories
    assert "Mujer" in sexo.categories


def test_parse_invalid_file_raises(tmp_path):
    bad = tmp_path / "bad.xlsx"
    bad.write_bytes(b"not an xlsx")
    with pytest.raises(XlsxParseError):
        parse_xlsx(str(bad))
```

- [ ] **Step 2: Run failing test**

Run: `cd backend && .venv/bin/pytest tests/test_xlsx_parser.py -v`
Expected: ImportError on `xlsx_parser`.

- [ ] **Step 3: Implement parser skeleton**

Create `backend/aurum_encuestas/xlsx_parser.py`:

```python
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from .errors import XlsxParseError
from .models import ParsedDB, Breakdown, Question


BREAKDOWN_ID_MAP = {
    "rango de edad": "edad",
    "sexo": "sexo",
    "nse": "nse",
    "punto": "punto",
}


def _slug(text: str) -> str:
    return text.strip().lower()


def parse_xlsx(path: str) -> ParsedDB:
    try:
        wb = load_workbook(path, data_only=True)
    except (InvalidFileException, OSError, KeyError) as e:
        raise XlsxParseError(f"No se pudo abrir el archivo: {e}") from e

    ws = wb.worksheets[0]

    breakdowns = _detect_breakdowns(ws)
    sample_size = _detect_sample_size(ws)
    questions = _detect_questions(ws)
    data_blocks = _detect_data_blocks(ws)

    return ParsedDB(
        questions=questions,
        breakdowns=breakdowns,
        sample_size=sample_size,
        data_blocks=data_blocks,
    )


def _detect_breakdowns(ws) -> list[Breakdown]:
    """Row 1 has breakdown group names in scattered cells. Row 2 has sub-categories below each group."""
    # Detect groups in row 1 (block 1 only — first occurrence)
    row1 = {c.column: (c.value or "") for c in ws[1]}
    row2 = {c.column: (c.value or "") for c in ws[2]}

    # Find "General" column (block 1 anchor)
    general_col = None
    for col, val in sorted(row2.items()):
        if str(val).strip() == "General":
            general_col = col
            break

    breakdowns = [Breakdown(id="general", label="General", categories=["Total"])]

    # Identify breakdown groups in row 1 (only block 1: cols 1 to general_col + range)
    block1_max = general_col + 30 if general_col else 50
    seen_labels = set()
    group_starts = []
    for col in sorted(row1.keys()):
        if col <= general_col or col > block1_max:
            continue
        label = str(row1[col]).strip()
        if not label or label in seen_labels:
            continue
        slug_key = _slug(label)
        if slug_key in BREAKDOWN_ID_MAP:
            seen_labels.add(label)
            group_starts.append((col, label, BREAKDOWN_ID_MAP[slug_key]))

    # For each group, categories are row2 cells from col to next group's col - 1
    sorted_groups = sorted(group_starts)
    for i, (col, label, gid) in enumerate(sorted_groups):
        end_col = sorted_groups[i + 1][0] if i + 1 < len(sorted_groups) else col + 6
        categories = []
        for c in range(col, end_col):
            v = row2.get(c)
            if v and str(v).strip() and str(v).strip() not in ("General",):
                categories.append(str(v).strip())
        if categories:
            breakdowns.append(Breakdown(id=gid, label=label, categories=categories))

    return breakdowns


def _detect_sample_size(ws) -> int:
    """Row 3 col 3 typically has Total = sample_size."""
    val = ws.cell(3, 3).value
    if val is None:
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def _detect_questions(ws) -> list[Question]:
    return []  # implemented in next task


def _detect_data_blocks(ws) -> dict:
    return {"counts_cols": [], "pct_row_cols": [], "pct_col_cols": []}  # next task
```

- [ ] **Step 4: Run tests, verify breakdown/sample tests pass, question test still empty**

Run: `cd backend && .venv/bin/pytest tests/test_xlsx_parser.py -v`
Expected: 3 PASS (sample_size, breakdowns, sexo), 1 PASS (invalid_file).

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/xlsx_parser.py backend/tests/test_xlsx_parser.py
git commit -m "feat(backend): xlsx parser — detect breakdowns + sample_size + invalid file error"
```

---

### Task 7: xlsx parser — detect questions

**Files:**
- Modify: `backend/aurum_encuestas/xlsx_parser.py`
- Modify: `backend/tests/test_xlsx_parser.py`

- [ ] **Step 1: Add failing tests for question detection**

Append to `backend/tests/test_xlsx_parser.py`:

```python
def test_parse_detects_questions(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    assert len(db.questions) >= 1
    q1 = db.questions[0]
    assert q1.code == "P1"
    assert q1.text  # non-empty
    assert "Sí" in q1.options
    assert "No" in q1.options


def test_parse_question_confidence(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    q1 = db.questions[0]
    assert q1.confidence >= 0.9  # $pN.label marker = high confidence
```

- [ ] **Step 2: Run, see failing**

Run: `cd backend && .venv/bin/pytest tests/test_xlsx_parser.py::test_parse_detects_questions -v`
Expected: AssertionError (questions list empty).

- [ ] **Step 3: Implement `_detect_questions`**

Replace `_detect_questions` in `backend/aurum_encuestas/xlsx_parser.py`:

```python
import re

QMARKER_RE = re.compile(r"^\$p(\d+)\.(\w+)")


def _detect_questions(ws) -> list[Question]:
    """Scan col A for question markers ($pN.label or text ending in ?). Following rows = options."""
    questions = []
    current_q = None
    current_options = []
    next_qid = 1

    for row in range(3, ws.max_row + 1):
        a_val = ws.cell(row, 1).value
        b_val = ws.cell(row, 2).value

        if a_val is not None and str(a_val).strip():
            # New question row
            if current_q is not None and current_options:
                current_q.options = current_options
                questions.append(current_q)

            a_str = str(a_val).strip()
            m = QMARKER_RE.match(a_str)
            if m:
                code = f"P{m.group(1)}"
                text = m.group(0)
                confidence = 1.0
            elif a_str.endswith("?"):
                code = f"P{next_qid}"
                text = a_str
                confidence = 0.9
            else:
                # Could be a demographic row (Sexo, Rango de edad, NSE, Punto)
                if a_str.lower() in ("sexo", "rango de edad", "nse", "punto", "nse_a"):
                    current_q = None
                    current_options = []
                    continue
                # Treat as low-confidence question
                code = f"P{next_qid}"
                text = a_str
                confidence = 0.5

            next_qid += 1
            current_q = Question(id=f"q{next_qid - 1}", code=code, text=text, options=[], confidence=confidence)
            current_options = []
            if b_val is not None and str(b_val).strip():
                current_options.append(str(b_val).strip())
        elif current_q is not None and b_val is not None and str(b_val).strip():
            current_options.append(str(b_val).strip())

    if current_q is not None and current_options:
        current_q.options = current_options
        questions.append(current_q)

    return questions
```

- [ ] **Step 4: Run all xlsx parser tests, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_xlsx_parser.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/xlsx_parser.py backend/tests/test_xlsx_parser.py
git commit -m "feat(backend): xlsx parser — detect questions with confidence"
```

---

### Task 8: xlsx parser — detect 3 column blocks (counts / %row / %col)

**Files:**
- Modify: `backend/aurum_encuestas/xlsx_parser.py`
- Modify: `backend/tests/test_xlsx_parser.py`

- [ ] **Step 1: Add failing test**

Append to `backend/tests/test_xlsx_parser.py`:

```python
def test_parse_detects_three_column_blocks(valid_xlsx_path):
    db = parse_xlsx(str(valid_xlsx_path))
    blocks = db.data_blocks
    assert "counts_cols" in blocks
    assert "pct_row_cols" in blocks
    # counts block starts at col 3
    assert blocks["counts_cols"][0] == 3
    # second block detected
    assert blocks["pct_row_cols"][0] >= 19
```

- [ ] **Step 2: Run, see failing**

Run: `cd backend && .venv/bin/pytest tests/test_xlsx_parser.py::test_parse_detects_three_column_blocks -v`
Expected: AssertionError (empty lists).

- [ ] **Step 3: Implement `_detect_data_blocks`**

Replace `_detect_data_blocks` in `xlsx_parser.py`:

```python
def _detect_data_blocks(ws) -> dict:
    """Find up to 3 column blocks. Each block starts at a column where row2 == 'General' and row3 has Total counts.

    Block 1: counts (integer values > 1)
    Block 2: %row (values 0-1)
    Block 3: %col (values 0-1)
    """
    row2 = {c.column: (c.value or "") for c in ws[2]}
    general_cols = [col for col, v in sorted(row2.items()) if str(v).strip() == "General"]

    blocks = []
    for i, start_col in enumerate(general_cols):
        end_col = general_cols[i + 1] - 3 if i + 1 < len(general_cols) else start_col + 14
        blocks.append((start_col, end_col))

    counts = blocks[0] if len(blocks) >= 1 else (3, 17)
    pct_row = blocks[1] if len(blocks) >= 2 else (counts[1] + 4, counts[1] + 18)
    pct_col = blocks[2] if len(blocks) >= 3 else (pct_row[1] + 4, pct_row[1] + 18)

    return {
        "counts_cols": [counts[0], counts[1]],
        "pct_row_cols": [pct_row[0], pct_row[1]],
        "pct_col_cols": [pct_col[0], pct_col[1]],
    }
```

- [ ] **Step 4: Run all xlsx tests, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_xlsx_parser.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/xlsx_parser.py backend/tests/test_xlsx_parser.py
git commit -m "feat(backend): xlsx parser — detect 3 column blocks (counts/%row/%col)"
```

---

### Task 9: pptx_template — validate + extract shell/separator/placeholders

**Files:**
- Create: `backend/aurum_encuestas/pptx_template.py`
- Create: `backend/tests/test_pptx_template.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_pptx_template.py`:

```python
from aurum_encuestas.pptx_template import load_template
from aurum_encuestas.errors import TemplateInvalidError
import pytest


def test_load_valid_template(valid_template_path):
    info = load_template(str(valid_template_path))
    assert info.shell_slide_index == 0
    assert info.separator_slide_index == 1
    assert "@Titulo" in info.placeholders


def test_load_template_with_notas_placeholder(valid_template_path):
    info = load_template(str(valid_template_path))
    assert "@Notas" in info.placeholders


def test_load_template_with_one_slide_raises(invalid_template_one_slide):
    with pytest.raises(TemplateInvalidError, match="2 slides"):
        load_template(str(invalid_template_one_slide))


def test_load_template_without_titulo_raises(invalid_template_no_titulo):
    with pytest.raises(TemplateInvalidError, match="@Titulo"):
        load_template(str(invalid_template_no_titulo))


def test_load_template_free_area_computed(valid_template_path):
    info = load_template(str(valid_template_path))
    fa = info.free_area
    assert fa["cx"] > 0
    assert fa["cy"] > 0
```

- [ ] **Step 2: Run, see failing**

Run: `cd backend && .venv/bin/pytest tests/test_pptx_template.py -v`
Expected: ImportError on `pptx_template`.

- [ ] **Step 3: Implement template loader**

Create `backend/aurum_encuestas/pptx_template.py`:

```python
import re
from pathlib import Path

from pptx import Presentation

from .errors import TemplateInvalidError
from .models import TemplateInfo


PLACEHOLDER_RE = re.compile(r"@\w+")


def load_template(path: str) -> TemplateInfo:
    p = Path(path)
    if not p.exists():
        raise TemplateInvalidError(f"Archivo no encontrado: {path}")
    try:
        prs = Presentation(path)
    except Exception as e:
        raise TemplateInvalidError(f"No se pudo abrir el pptx: {e}") from e

    if len(prs.slides) != 2:
        raise TemplateInvalidError(
            f"Template requiere exactamente 2 slides (shell + separador), tiene {len(prs.slides)}"
        )

    placeholders_by_slide = []
    for idx, slide in enumerate(prs.slides):
        found = set()
        for sh in slide.shapes:
            if sh.has_text_frame:
                for para in sh.text_frame.paragraphs:
                    for run in para.runs:
                        for m in PLACEHOLDER_RE.findall(run.text or ""):
                            found.add(m)
                    for m in PLACEHOLDER_RE.findall(para.text or ""):
                        found.add(m)
        if "@Titulo" not in found:
            raise TemplateInvalidError(f"Slide {idx + 1} no tiene placeholder @Titulo")
        placeholders_by_slide.append(found)

    all_placeholders = sorted(placeholders_by_slide[0] | placeholders_by_slide[1])
    free_area = _compute_free_area(prs.slides[0], prs.slide_width, prs.slide_height)
    default_font = _detect_default_font(prs.slides[0])

    return TemplateInfo(
        shell_slide_index=0,
        separator_slide_index=1,
        free_area=free_area,
        placeholders=all_placeholders,
        default_font=default_font,
    )


def _compute_free_area(slide, slide_w_emu: int, slide_h_emu: int) -> dict:
    """Largest contiguous rect not covered by any shape. Approximation: bbox below all shapes' bottom and above their top."""
    if not slide.shapes:
        return {"x": 0, "y": 0, "cx": slide_w_emu, "cy": slide_h_emu}

    shapes_bottom = max((sh.top or 0) + (sh.height or 0) for sh in slide.shapes if sh.top is not None)
    shapes_top = min(sh.top for sh in slide.shapes if sh.top is not None)

    # heuristic: free area is between top-most shape's bottom and bottom-most shape's top
    # if multiple shapes: use the middle gap
    tops_bottoms = []
    for sh in slide.shapes:
        if sh.top is None or sh.height is None:
            continue
        tops_bottoms.append((sh.top, sh.top + sh.height))
    tops_bottoms.sort()

    # find largest vertical gap
    cursor = 0
    best_y = 0
    best_h = 0
    for top, bot in tops_bottoms:
        if top - cursor > best_h:
            best_y = cursor
            best_h = top - cursor
        cursor = max(cursor, bot)
    if slide_h_emu - cursor > best_h:
        best_y = cursor
        best_h = slide_h_emu - cursor

    margin = int(slide_w_emu * 0.03)  # 3% margin
    return {
        "x": margin,
        "y": best_y + margin,
        "cx": slide_w_emu - 2 * margin,
        "cy": max(0, best_h - 2 * margin),
    }


def _detect_default_font(slide) -> str | None:
    for sh in slide.shapes:
        if sh.has_text_frame:
            for para in sh.text_frame.paragraphs:
                for run in para.runs:
                    if run.font and run.font.name:
                        return run.font.name
    return None
```

- [ ] **Step 4: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_pptx_template.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/pptx_template.py backend/tests/test_pptx_template.py
git commit -m "feat(backend): pptx template loader — validate 2 slides + @Titulo + extract free_area"
```

---

### Task 10: project_store — load/save .aurum.json + path resolution

**Files:**
- Create: `backend/aurum_encuestas/project_store.py`
- Create: `backend/tests/test_project_store.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_project_store.py`:

```python
import json
from pathlib import Path

import pytest

from aurum_encuestas.errors import ProjectIOError
from aurum_encuestas.models import ProjectInputs, ProjectState
from aurum_encuestas.project_store import load_project, resolve_input_paths, save_project


def test_save_and_load_roundtrip(tmp_path):
    state = ProjectState(
        version=1,
        project_name="Test",
        inputs=ProjectInputs(db_path="./db.xlsx", template_path="./tpl.pptx"),
    )
    out = tmp_path / "p.aurum.json"
    save_project(state, str(out))
    loaded = load_project(str(out))
    assert loaded.project_name == "Test"
    assert loaded.inputs.db_path == "./db.xlsx"


def test_resolve_input_paths_relative(tmp_path):
    (tmp_path / "db.xlsx").write_bytes(b"x")
    (tmp_path / "tpl.pptx").write_bytes(b"y")
    state = ProjectState(
        version=1,
        project_name="Test",
        inputs=ProjectInputs(db_path="./db.xlsx", template_path="./tpl.pptx"),
    )
    proj_path = tmp_path / "p.aurum.json"
    save_project(state, str(proj_path))
    resolved = resolve_input_paths(str(proj_path))
    assert resolved["db_path"] == str(tmp_path / "db.xlsx")
    assert resolved["template_path"] == str(tmp_path / "tpl.pptx")


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(ProjectIOError):
        load_project(str(tmp_path / "nonexistent.aurum.json"))


def test_load_malformed_json_raises(tmp_path):
    p = tmp_path / "bad.aurum.json"
    p.write_text("{not valid json")
    with pytest.raises(ProjectIOError):
        load_project(str(p))


def test_save_creates_parent_dir(tmp_path):
    state = ProjectState(
        version=1,
        project_name="Test",
        inputs=ProjectInputs(db_path="./x", template_path="./y"),
    )
    nested = tmp_path / "subdir" / "p.aurum.json"
    save_project(state, str(nested))
    assert nested.exists()
```

- [ ] **Step 2: Run failing**

Run: `cd backend && .venv/bin/pytest tests/test_project_store.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement project_store**

Create `backend/aurum_encuestas/project_store.py`:

```python
import json
from datetime import UTC, datetime
from pathlib import Path

from .errors import ProjectIOError
from .models import ProjectState


def save_project(state: ProjectState, path: str) -> None:
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        state.updated_at = datetime.now(UTC).isoformat()
        if state.created_at is None:
            state.created_at = state.updated_at
        p.write_text(json.dumps(state.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        raise ProjectIOError(f"No se pudo guardar el proyecto: {e}") from e


def load_project(path: str) -> ProjectState:
    p = Path(path)
    if not p.exists():
        raise ProjectIOError(f"Archivo no existe: {path}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return ProjectState.model_validate(data)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        raise ProjectIOError(f"No se pudo cargar el proyecto: {e}") from e


def resolve_input_paths(project_path: str) -> dict:
    """Resolve relative db_path/template_path against project file dir."""
    state = load_project(project_path)
    base = Path(project_path).parent
    return {
        "db_path": str((base / state.inputs.db_path).resolve()),
        "template_path": str((base / state.inputs.template_path).resolve()),
    }
```

- [ ] **Step 4: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_project_store.py -v`
Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/aurum_encuestas/project_store.py backend/tests/test_project_store.py
git commit -m "feat(backend): project_store — load/save .aurum.json + relative path resolution"
```

---

### Task 11: FastAPI app + endpoints (parse-xlsx, parse-template, project save/load)

**Files:**
- Create: `backend/aurum_encuestas/api.py`
- Create: `backend/tests/test_api.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_api.py`:

```python
from fastapi.testclient import TestClient

from aurum_encuestas.api import app


client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_parse_xlsx_endpoint(valid_xlsx_path):
    with open(valid_xlsx_path, "rb") as f:
        r = client.post("/api/parse-xlsx", files={"file": ("v.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 200
    body = r.json()
    assert body["sample_size"] == 500
    assert any(b["id"] == "sexo" for b in body["breakdowns"])


def test_parse_xlsx_invalid_returns_400(tmp_path):
    bad = tmp_path / "bad.xlsx"
    bad.write_bytes(b"junk")
    with open(bad, "rb") as f:
        r = client.post("/api/parse-xlsx", files={"file": ("bad.xlsx", f, "application/octet-stream")})
    assert r.status_code == 400
    assert r.json()["code"] == "xlsx_parse_error"


def test_parse_template_endpoint(valid_template_path):
    with open(valid_template_path, "rb") as f:
        r = client.post("/api/parse-template", files={"file": ("t.pptx", f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")})
    assert r.status_code == 200
    body = r.json()
    assert body["shell_slide_index"] == 0
    assert "@Titulo" in body["placeholders"]


def test_parse_template_invalid_returns_400(invalid_template_one_slide):
    with open(invalid_template_one_slide, "rb") as f:
        r = client.post("/api/parse-template", files={"file": ("t.pptx", f, "application/octet-stream")})
    assert r.status_code == 400
    assert r.json()["code"] == "template_invalid"


def test_save_load_project_endpoints(tmp_path):
    proj = {
        "version": 1,
        "project_name": "Test",
        "inputs": {"db_path": "./x.xlsx", "template_path": "./t.pptx", "font_override": None},
        "slides": [],
    }
    out = str(tmp_path / "p.aurum.json")
    r = client.post("/api/save-project", json={"path": out, "state": proj})
    assert r.status_code == 200
    r2 = client.post("/api/load-project", json={"path": out})
    assert r2.status_code == 200
    assert r2.json()["project_name"] == "Test"
```

- [ ] **Step 2: Run failing**

Run: `cd backend && .venv/bin/pytest tests/test_api.py -v`
Expected: ImportError on `api`.

- [ ] **Step 3: Implement api.py**

Create `backend/aurum_encuestas/api.py`:

```python
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .errors import AurumError, ProjectIOError, TemplateInvalidError, XlsxParseError
from .models import ProjectState
from .pptx_template import load_template
from .project_store import load_project, save_project
from .xlsx_parser import parse_xlsx


app = FastAPI(title="AurumEncuestas API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AurumError)
async def handle_aurum_error(request, exc: AurumError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=exc.status, content={"code": exc.code, "message": str(exc)})


@app.get("/api/health")
async def health():
    return {"status": "ok"}


async def _save_upload_tmp(file: UploadFile, suffix: str) -> str:
    contents = await file.read()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(contents)
    tmp.close()
    return tmp.name


@app.post("/api/parse-xlsx")
async def parse_xlsx_endpoint(file: UploadFile = File(...)):
    path = await _save_upload_tmp(file, ".xlsx")
    try:
        db = parse_xlsx(path)
        return db.model_dump()
    finally:
        Path(path).unlink(missing_ok=True)


@app.post("/api/parse-template")
async def parse_template_endpoint(file: UploadFile = File(...)):
    path = await _save_upload_tmp(file, ".pptx")
    try:
        info = load_template(path)
        return info.model_dump()
    finally:
        Path(path).unlink(missing_ok=True)


class SaveProjectRequest(BaseModel):
    path: str
    state: dict


@app.post("/api/save-project")
async def save_project_endpoint(req: SaveProjectRequest):
    state = ProjectState.model_validate(req.state)
    save_project(state, req.path)
    return {"saved": True, "path": req.path}


class LoadProjectRequest(BaseModel):
    path: str


@app.post("/api/load-project")
async def load_project_endpoint(req: LoadProjectRequest):
    state = load_project(req.path)
    return state.model_dump()
```

- [ ] **Step 4: Run, verify pass**

Run: `cd backend && .venv/bin/pytest tests/test_api.py -v`
Expected: all 6 PASS.

- [ ] **Step 5: Smoke-test the server manually**

Run: `cd backend && .venv/bin/uvicorn aurum_encuestas.api:app --port 8000 &`
Then: `curl http://localhost:8000/api/health`
Expected: `{"status":"ok"}`

Kill: `pkill -f "uvicorn aurum_encuestas"`

- [ ] **Step 6: Commit**

```bash
git add backend/aurum_encuestas/api.py backend/tests/test_api.py
git commit -m "feat(backend): FastAPI app with parse-xlsx, parse-template, save/load-project endpoints"
```

---

### Task 12: M1 wrap-up — full test suite + lint

**Files:** none

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && .venv/bin/pytest -v`
Expected: all tests PASS (sum: ~25 tests across 5 test files).

- [ ] **Step 2: Run lint**

Run: `cd backend && .venv/bin/ruff check aurum_encuestas tests`
Expected: no errors. Fix any reported issues.

- [ ] **Step 3: Manual end-to-end smoke**

Run: `make dev-backend &`
Wait 2s. Then:

```bash
curl -X POST http://localhost:8000/api/parse-xlsx -F "file=@/Users/joaquincardenas/Downloads/BD Aurora ejemplo.xlsx" | head -c 500
```

Expected: JSON with `breakdowns`, `questions`, `sample_size`.

Kill: `pkill -f uvicorn`

- [ ] **Step 4: Tag milestone commit**

```bash
git tag m1-backend-core
git log --oneline | head -15
```

---

## M1 Done When

- All ~25 backend tests pass
- `make dev-backend` boots without error
- `curl /api/parse-xlsx` with real BD Aurora xlsx returns valid JSON
- `curl /api/parse-template` with real template returns valid JSON
- Project save/load roundtrip works
- Lint passes
- Git tag `m1-backend-core`
