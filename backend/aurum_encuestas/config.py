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
