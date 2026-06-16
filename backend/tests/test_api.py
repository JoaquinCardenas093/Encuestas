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

        from aurum_encuestas.pptx_generator import build_pptx
        from aurum_encuestas.models import ProjectState, Slide
        import tempfile

        # Create a minimal project state
        state = ProjectState(
            version=1,
            project_name="Test",
            inputs={"db_path": str(valid_xlsx_path), "template_path": str(valid_template_path), "font_override": None},
            slides=[
                Slide(
                    id="slide_0",
                    type="separator",
                    title="Test Slide",
                )
            ],
        )

        # Build PPTX
        with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
            pptx_path = f.name
        build_pptx(state, pptx_path)

        # Test preview endpoint
        req = {
            "pptx_path": pptx_path,
            "slide_index": 0,
        }
        r = client.post("/api/preview-slide", json=req)
        assert r.status_code == 200
        body = r.json()
        assert "png_base64" in body
        # Should start with data URL prefix or just base64
        assert isinstance(body["png_base64"], str)
        assert len(body["png_base64"]) > 0

    def test_preview_slide_returns_placeholder_without_libreoffice(self):
        """preview-slide returns base64 placeholder PNG if LibreOffice unavailable."""
        import shutil
        if shutil.which("soffice"):
            import pytest
            pytest.skip("LibreOffice is installed")

        req = {
            "pptx_path": "/nonexistent.pptx",
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
            "out_path": out_path,
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
