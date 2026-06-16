"""
Render service for converting PPTX slides to PNG images via LibreOffice.
"""
import base64
import shutil
import subprocess
import tempfile
from pathlib import Path


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

    If LibreOffice is not installed, returns a placeholder PNG.

    Args:
        pptx_path: Path to the PPTX file
        slide_index: 0-based index of the slide to render (currently only 0 supported)

    Returns:
        PNG image as bytes
    """
    soffice = _find_soffice()
    if not soffice:
        return _PLACEHOLDER_PNG

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Convert PPTX to PNG via LibreOffice
            # --headless: no GUI
            # --convert-to: target format
            # --outdir: output directory
            subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--convert-to",
                    "png",
                    "--outdir",
                    tmpdir,
                    pptx_path,
                ],
                check=True,
                capture_output=True,
            )

            # LibreOffice outputs files like "filename_1.png", "filename_2.png", etc.
            # For slide_index=0, we need the first slide output
            png_pattern = Path(tmpdir).glob("*.png")
            png_files = sorted(png_pattern)

            if not png_files:
                return _PLACEHOLDER_PNG

            # Use the first PNG (corresponds to first slide)
            png_path = png_files[0]
            return png_path.read_bytes()

    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return _PLACEHOLDER_PNG
