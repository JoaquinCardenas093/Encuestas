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
