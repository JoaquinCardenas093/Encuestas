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


class TestPreviewSlide:
    """Tests for /api/preview-slide endpoint"""

    def test_preview_slide_returns_base64_png(self, valid_template_path, valid_xlsx_path):
        """preview-slide endpoint returns base64-encoded PNG if LibreOffice available."""
        import shutil
        if not shutil.which("soffice"):
            import pytest
            pytest.skip("LibreOffice not installed")

        state_dict = {
            "version": 1,
            "project_name": "Test",
            "inputs": {"db_path": str(valid_xlsx_path), "template_path": str(valid_template_path), "font_override": None},
            "slides": [
                {
                    "id": "slide_0",
                    "type": "separator",
                    "title": "Test Slide",
                }
            ],
        }

        req = {
            "state": state_dict,
            "slide_index": 0,
        }
        r = client.post("/api/preview-slide", json=req)
        assert r.status_code == 200
        body = r.json()
        assert "png_base64" in body
        assert isinstance(body["png_base64"], str)
        assert len(body["png_base64"]) > 0

    def test_preview_slide_returns_placeholder_without_libreoffice(self, valid_template_path, valid_xlsx_path):
        """preview-slide returns base64 placeholder PNG if LibreOffice unavailable."""
        import shutil
        if shutil.which("soffice"):
            import pytest
            pytest.skip("LibreOffice is installed")

        state_dict = {
            "version": 1,
            "project_name": "Test",
            "inputs": {"db_path": str(valid_xlsx_path), "template_path": str(valid_template_path), "font_override": None},
            "slides": [],
        }

        req = {
            "state": state_dict,
            "slide_index": 0,
        }
        r = client.post("/api/preview-slide", json=req)
        assert r.status_code == 200
        body = r.json()
        assert "png_base64" in body
        assert isinstance(body["png_base64"], str)


class TestExportPptx:
    """Tests for /api/export-pptx endpoint"""

    def test_export_pptx_writes_file(self, valid_template_path, valid_xlsx_path, tmp_path):
        """export-pptx endpoint writes PPTX file to disk."""

        state_dict = {
            "version": 1,
            "project_name": "Export Test",
            "inputs": {"db_path": str(valid_xlsx_path), "template_path": str(valid_template_path), "font_override": None},
            "slides": [
                {
                    "id": "slide_0",
                    "type": "separator",
                    "title": "Export Test Slide",
                }
            ],
        }

        out_path = str(tmp_path / "exported.pptx")
        req = {
            "state": state_dict,
            "path": out_path,
        }
        r = client.post("/api/export-pptx", json=req)
        assert r.status_code == 200
        body = r.json()
        assert body["exported"] == True
        assert body["path"] == out_path

        # Verify file was written
        from pathlib import Path
        assert Path(out_path).exists()
        assert Path(out_path).stat().st_size > 0


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


# test_training_add_and_list, test_training_bank_returns_layouts, test_training_delete
# removed in M6.2 — M4/M5 training endpoints deleted; will be replaced by M6.8 corpus CRUD tests.

@patch("aurum_encuestas.api.suggest_layout")
def test_suggest_layout_endpoint(mock_sug):
    mock_sug.return_value = {"source": "ai", "elements": [{"role": "chart_0", "x": 100, "y": 100, "cx": 1000, "cy": 1000}]}
    payload = {
        "n_charts": 1, "chart_types": ["PIE"],
        "n_chart_an": 0, "n_q_an": 0, "has_slide_an": False,
        "free_area": {"x": 0, "y": 0, "cx": 12000000, "cy": 7000000},
    }
    r = client.post("/api/suggest-layout", json=payload)
    assert r.status_code == 200
    assert r.json()["source"] == "ai"


# ─── M6.7: AI analysis job endpoints ────────────────────────────────────────

def test_analyze_with_ai_returns_job_id():
    r = client.post("/api/training/analyze-with-ai")
    assert r.status_code == 200
    assert "job_id" in r.json()


def test_analysis_status_unknown_job():
    r = client.get("/api/training/analysis-status/nonexistent-job-id")
    assert r.status_code == 404


def test_recents_add_and_list(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    # save a project (should auto-add to recents)
    proj = {"version": 1, "project_name": "P1", "inputs": {"db_path": "./x", "template_path": "./y", "font_override": None}, "slides": []}
    save_path = str(tmp_path / "p1.aurum.json")
    client.post("/api/save-project", json={"path": save_path, "state": proj})

    r = client.get("/api/recents")
    assert r.status_code == 200
    recs = r.json()["recents"]
    assert any(rec["path"] == save_path for rec in recs)


# ─── M6.8 T2: Corpus CRUD endpoints ─────────────────────────────────────────

import io


def test_corpus_add_pptx(tmp_path, monkeypatch, training_pptx_path):
    """POST /api/training/corpus/add saves PPT to corpus dir and returns metadata."""
    monkeypatch.setenv("HOME", str(tmp_path))
    with open(training_pptx_path, "rb") as f:
        r = client.post(
            "/api/training/corpus/add",
            files={"file": ("demo.pptx", f, "application/octet-stream")},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "demo.pptx"
    assert "slides_with_charts" in body
    assert "added_at" in body

    # Verify file actually saved
    corpus_dir = tmp_path / ".aurum" / "training" / "corpus"
    assert (corpus_dir / "demo.pptx").exists()


def test_corpus_add_rejects_non_pptx(tmp_path, monkeypatch):
    """Only .pptx files should be accepted."""
    monkeypatch.setenv("HOME", str(tmp_path))
    fake_csv = io.BytesIO(b"col1,col2\n1,2")
    r = client.post(
        "/api/training/corpus/add",
        files={"file": ("data.csv", fake_csv, "text/csv")},
    )
    assert r.status_code == 400
    assert "pptx" in r.json()["detail"].lower()


def test_corpus_list_returns_pptxs(tmp_path, monkeypatch, training_pptx_path):
    """GET /api/training/corpus/list returns list of corpus PPTs with metadata."""
    monkeypatch.setenv("HOME", str(tmp_path))
    corpus_dir = tmp_path / ".aurum" / "training" / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy(training_pptx_path, corpus_dir / "deck_a.pptx")
    shutil.copy(training_pptx_path, corpus_dir / "deck_b.pptx")

    r = client.get("/api/training/corpus/list")
    assert r.status_code == 200
    body = r.json()
    assert "pptxs" in body
    filenames = [p["filename"] for p in body["pptxs"]]
    assert "deck_a.pptx" in filenames
    assert "deck_b.pptx" in filenames
    # Each item should have filename, slides_with_charts, added_at
    for pptx_info in body["pptxs"]:
        assert "filename" in pptx_info
        assert "added_at" in pptx_info
        assert "slides_with_charts" in pptx_info


def test_corpus_list_empty_when_no_corpus(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    r = client.get("/api/training/corpus/list")
    assert r.status_code == 200
    assert r.json()["pptxs"] == []


def test_corpus_delete_removes_file(tmp_path, monkeypatch, training_pptx_path):
    """POST /api/training/corpus/delete removes file from corpus."""
    monkeypatch.setenv("HOME", str(tmp_path))
    corpus_dir = tmp_path / ".aurum" / "training" / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy(training_pptx_path, corpus_dir / "to_delete.pptx")

    r = client.post("/api/training/corpus/delete", json={"filename": "to_delete.pptx"})
    assert r.status_code == 200
    assert r.json()["deleted"] is True
    assert not (corpus_dir / "to_delete.pptx").exists()


def test_corpus_delete_missing_file_still_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    r = client.post("/api/training/corpus/delete", json={"filename": "nonexistent.pptx"})
    assert r.status_code == 200
    assert r.json()["deleted"] is False


# ─── M6.8 T3: Verify analyze-with-ai + analysis-status from M6.7 ─────────────

def test_analyze_with_ai_endpoint_returns_job_id():
    r = client.post("/api/training/analyze-with-ai")
    assert r.status_code == 200
    body = r.json()
    assert "job_id" in body
    assert isinstance(body["job_id"], str)


def test_analysis_status_returns_progress_for_valid_job():
    r = client.post("/api/training/analyze-with-ai")
    job_id = r.json()["job_id"]

    # Poll status immediately — job may still be running
    r2 = client.get(f"/api/training/analysis-status/{job_id}")
    assert r2.status_code == 200
    body = r2.json()
    assert "progress" in body
    assert "status" in body
    assert body["status"] in ("running", "done", "error")


def test_analysis_status_404_for_unknown_job():
    r = client.get("/api/training/analysis-status/nonexistent-job-id-xyz")
    assert r.status_code == 404
