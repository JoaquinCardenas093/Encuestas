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


def get_session_dir() -> Path:
    """Per-session dir (uploads/config/projects). Falls back to the global aurum dir."""
    from .session import get_session
    sid = get_session()
    base = get_aurum_dir()
    return base / "sessions" / sid if sid else base


def get_training_dir() -> Path:
    d = get_aurum_dir() / "training"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_config_path() -> Path:
    return get_session_dir() / "config.json"


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


# Alias used by style_guide_analyzer
def get_analysis_logs_dir() -> Path:
    """Alias for get_ai_logs_dir."""
    return get_ai_logs_dir()


RENDER_CACHE_MAX_BYTES = 500 * 1024 * 1024  # 500 MB
