"""
Render service for converting PPTX slides to PNG images via LibreOffice.
"""
import base64
import shutil
import subprocess
import tempfile
from pathlib import Path

try:
    from pdf2image import convert_from_path
    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False


# Minimal 1x1 transparent PNG as placeholder (when LibreOffice unavailable)
_PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _find_soffice() -> str | None:
    """Find the path to LibreOffice soffice executable."""
    return shutil.which("soffice")


def render_slide_to_png(pptx_path: str, slide_index: int = 0) -> bytes:
    """
    Render a specific slide from a PPTX file to PNG bytes.

    Uses PPTX→PDF→PNG conversion for multi-slide support.
    If LibreOffice is not installed, returns a placeholder PNG.

    Args:
        pptx_path: Path to the PPTX file
        slide_index: 0-based index of the slide to render

    Returns:
        PNG image as bytes
    """
    soffice = _find_soffice()
    if not soffice:
        return _PLACEHOLDER_PNG

    if not HAS_PDF2IMAGE:
        return _PLACEHOLDER_PNG

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Step 1: Convert PPTX to PDF using LibreOffice
            pdf_path = tmpdir_path / "output.pdf"
            subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(tmpdir_path),
                    pptx_path,
                ],
                check=True,
                capture_output=True,
            )

            if not pdf_path.exists():
                return _PLACEHOLDER_PNG

            # Step 2: Convert specific PDF page to PNG using pdf2image
            # pdf2image returns a list of PIL Image objects (one per page)
            images = convert_from_path(str(pdf_path), first_page=slide_index + 1, last_page=slide_index + 1)

            if not images:
                return _PLACEHOLDER_PNG

            # Convert PIL Image to PNG bytes
            img = images[0]
            png_bytes = tempfile.TemporaryDirectory()
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                img.save(f.name, "PNG")
                return Path(f.name).read_bytes()

    except (subprocess.CalledProcessError, FileNotFoundError, OSError, Exception):
        return _PLACEHOLDER_PNG
