
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
