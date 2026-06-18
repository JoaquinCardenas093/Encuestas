
from aurum_encuestas.config import (
    add_recent,
    get_aurum_dir,
    get_layout_bank_path,
    get_training_dir,
    load_recents,
    get_corpus_dir,
    get_style_guide_path,
    get_render_cache_dir,
    get_ai_logs_dir,
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
