import base64
import logging
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import add_recent, load_recents
from .errors import AurumError
from .llm_client import generate_analysis, suggest_layout
from .models import ProjectState
from .pptx_generator import build_pptx
from .pptx_template import load_template
from .project_store import load_project, save_project
from .render_service import render_slide_to_png
from .style_guide import migrate_legacy_files
from .xlsx_parser import parse_xlsx

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


app = FastAPI(title="AurumEncuestas API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AurumError)
async def handle_aurum_error(request, exc: AurumError):
    return JSONResponse(status_code=exc.status, content={"code": exc.code, "message": str(exc)})


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    print(f"[VALIDATION 422] {request.method} {request.url.path}")
    print(f"  errors: {exc.errors()}")
    try:
        body = await request.body()
        snippet = body[:2000].decode("utf-8", errors="replace")
        print(f"  body[:2000]: {snippet}")
    except Exception as e:
        print(f"  body read failed: {e}")
    return JSONResponse(status_code=422, content={"code": "validation_error", "detail": exc.errors()})


@app.get("/api/health")
async def health():
    return {"status": "ok"}


async def _save_upload_tmp(file: UploadFile, suffix: str) -> str:
    contents = await file.read()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(contents)
    tmp.close()
    return tmp.name


def _persist_upload(file_bytes: bytes, original_name: str) -> str:
    """Save uploaded file to ~/.aurum/uploads/ keyed by filename. Returns absolute path."""
    from .config import get_aurum_dir
    uploads_dir = get_aurum_dir() / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(original_name).name  # strip any path component
    dest = uploads_dir / safe_name
    dest.write_bytes(file_bytes)
    return str(dest.resolve())


@app.post("/api/parse-xlsx")
async def parse_xlsx_endpoint(file: UploadFile = File(...)):
    contents = await file.read()
    persisted_path = _persist_upload(contents, file.filename or "uploaded.xlsx")
    db = parse_xlsx(persisted_path)
    result = db.model_dump()
    result["persisted_path"] = persisted_path
    return result


@app.post("/api/parse-template")
async def parse_template_endpoint(file: UploadFile = File(...)):
    contents = await file.read()
    persisted_path = _persist_upload(contents, file.filename or "template.pptx")
    info = load_template(persisted_path)
    result = info.model_dump()
    result["persisted_path"] = persisted_path
    return result


class SaveProjectRequest(BaseModel):
    path: str
    state: dict


@app.post("/api/save-project")
async def save_project_endpoint(req: SaveProjectRequest):
    state = ProjectState.model_validate(req.state)
    save_project(state, req.path)
    add_recent(req.path, state.project_name)
    return {"saved": True, "path": req.path}


class LoadProjectRequest(BaseModel):
    path: str


@app.post("/api/load-project")
async def load_project_endpoint(req: LoadProjectRequest):
    state = load_project(req.path)
    return state.model_dump()


class PreviewSlideRequest(BaseModel):
    state: dict
    slide_index: int = 0


@app.post("/api/preview-slide")
async def preview_slide_endpoint(req: PreviewSlideRequest):
    """Build pptx in-memory from project state, render specified slide as base64 PNG."""
    state = ProjectState.model_validate(req.state)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tmp:
        tmp_path = tmp.name
    try:
        build_pptx(state, tmp_path)
        png_bytes = render_slide_to_png(tmp_path, slide_index=req.slide_index)
        return {"png_base64": base64.b64encode(png_bytes).decode("utf-8")}
    finally:
        Path(tmp_path).unlink(missing_ok=True)


class ExportPptxRequest(BaseModel):
    state: dict
    path: str


@app.post("/api/export-pptx")
async def export_pptx_endpoint(req: ExportPptxRequest):
    """Build and export a PPTX file from ProjectState to the given path."""
    state = ProjectState.model_validate(req.state)
    expanded = str(Path(req.path).expanduser())
    Path(expanded).parent.mkdir(parents=True, exist_ok=True)
    build_pptx(state, expanded)
    size = Path(expanded).stat().st_size if Path(expanded).exists() else 0
    return {"exported": True, "path": expanded, "size": size}


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


# TODO M6.8: new training endpoints (corpus CRUD + AI analyze + style-guide GET/PUT)


class SuggestLayoutRequest(BaseModel):
    n_charts: int
    chart_types: list[str]
    n_chart_an: int = 0
    n_q_an: int = 0
    has_slide_an: bool = False
    free_area: dict


@app.post("/api/suggest-layout")
async def suggest_layout_endpoint(req: SuggestLayoutRequest):
    return suggest_layout(
        n_charts=req.n_charts,
        chart_types=req.chart_types,
        n_chart_an=req.n_chart_an,
        n_q_an=req.n_q_an,
        has_slide_an=req.has_slide_an,
        free_area=req.free_area,
    )


@app.get("/api/recents")
async def recents_endpoint():
    return {"recents": load_recents()}


# ────────────────────────────────────────────────────────────────────────────
# M6.7: Async AI analysis job endpoints
# ────────────────────────────────────────────────────────────────────────────

_analysis_jobs: dict[str, dict] = {}


@app.post("/api/training/analyze-with-ai")
async def analyze_with_ai(background_tasks: BackgroundTasks):
    """Start async AI analysis job. Returns job_id immediately."""
    job_id = str(uuid.uuid4())
    _analysis_jobs[job_id] = {"progress": 0, "status": "running", "message": "Iniciando..."}

    def _run():
        from .style_guide import load_active_style_guide
        from .style_guide_analyzer import run_full_analysis_pipeline
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
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    return job
