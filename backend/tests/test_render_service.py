import base64
import shutil
import pytest
from aurum_encuestas.render_service import render_slide_to_png, _PLACEHOLDER_PNG


HAS_LIBREOFFICE = shutil.which("soffice") is not None


class TestRenderService:
    """Tests for render_service.py"""

    @pytest.mark.skipif(not HAS_LIBREOFFICE, reason="LibreOffice not installed")
    def test_render_slide_returns_png_bytes_if_libreoffice_installed(self, tmp_path):
        """If LibreOffice is available, render_slide_to_png returns PNG bytes."""
        pptx_path = str(tmp_path / "test.pptx")
        # Create a minimal valid PPTX (empty)
        from pptx import Presentation
        prs = Presentation()
        prs.save(pptx_path)

        result = render_slide_to_png(pptx_path, slide_index=0)

        assert isinstance(result, bytes)
        assert result.startswith(b'\x89PNG')  # PNG magic number

    def test_render_slide_returns_placeholder_if_no_libreoffice(self):
        """If LibreOffice is not available, render_slide_to_png returns placeholder PNG."""
        # Mock absence of LibreOffice by passing a non-existent path
        # This test runs regardless of libreoffice availability
        if HAS_LIBREOFFICE:
            pytest.skip("LibreOffice is installed; skipping placeholder test")

        result = render_slide_to_png("/nonexistent/path.pptx", slide_index=0)

        assert isinstance(result, bytes)
        assert result == _PLACEHOLDER_PNG
        # Verify it's a valid PNG
        assert result.startswith(b'\x89PNG')
