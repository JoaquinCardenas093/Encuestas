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
