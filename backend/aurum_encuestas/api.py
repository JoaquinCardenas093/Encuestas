import base64
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .errors import AurumError
from .models import ProjectState
from .pptx_generator import build_pptx
from .pptx_template import load_template
from .project_store import load_project, save_project
from .render_service import render_slide_to_png
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


class PreviewSlideRequest(BaseModel):
    pptx_path: str
    slide_index: int = 0


@app.post("/api/preview-slide")
async def preview_slide_endpoint(req: PreviewSlideRequest):
    """Render a PPTX slide to PNG and return as base64."""
    png_bytes = render_slide_to_png(req.pptx_path, req.slide_index)
    png_base64 = base64.b64encode(png_bytes).decode("utf-8")
    return {"png_base64": png_base64}


class ExportPptxRequest(BaseModel):
    state: dict
    out_path: str


@app.post("/api/export-pptx")
async def export_pptx_endpoint(req: ExportPptxRequest):
    """Build and export a PPTX file from ProjectState."""
    state = ProjectState.model_validate(req.state)
    build_pptx(state, req.out_path)
    return {"exported": True, "path": req.out_path}


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


from .llm_client import suggest_layout


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
