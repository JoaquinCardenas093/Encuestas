"""Render service: PPTX slide → PNG via libreoffice headless + pdftoppm."""
import base64
import shutil
import subprocess
import tempfile
from pathlib import Path

from .errors import RenderError

# Minimal 1x1 transparent PNG fallback (only when libreoffice itself missing)
_PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _find_soffice() -> str | None:
    p = shutil.which("soffice") or shutil.which("libreoffice")
    if p:
        return p
    candidate = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    if Path(candidate).exists():
        return candidate
    return None


def render_slide_to_png(pptx_path: str, slide_index: int = 0) -> bytes:
    """Render a specific slide as PNG. Uses pptx→pdf (libreoffice) → png (pdftoppm or pdf2image)."""
    soffice = _find_soffice()
    if not soffice:
        return _PLACEHOLDER_PNG

    with tempfile.TemporaryDirectory() as tmpdir:
        outdir = Path(tmpdir)

        # Step 1: pptx → pdf via libreoffice
        try:
            r = subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(outdir), pptx_path],
                capture_output=True, timeout=60, check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RenderError(f"libreoffice falló: stderr={e.stderr.decode('utf-8', errors='replace')[:500]}") from e
        except subprocess.TimeoutExpired as e:
            raise RenderError("libreoffice timeout (60s)") from e

        pdfs = list(outdir.glob("*.pdf"))
        if not pdfs:
            raise RenderError(f"libreoffice no produjo PDF. stdout={r.stdout.decode('utf-8', errors='replace')[:300]}")
        pdf_path = pdfs[0]

        # Step 2: pdf page → png via pdftoppm (preferred, native C)
        pdftoppm = shutil.which("pdftoppm")
        if pdftoppm:
            try:
                subprocess.run(
                    [
                        pdftoppm, "-png", "-r", "120",
                        "-f", str(slide_index + 1), "-l", str(slide_index + 1),
                        str(pdf_path), str(outdir / "page"),
                    ],
                    capture_output=True, timeout=30, check=True,
                )
            except subprocess.CalledProcessError as e:
                raise RenderError(f"pdftoppm falló: stderr={e.stderr.decode('utf-8', errors='replace')[:500]}") from e
            pngs = sorted(outdir.glob("page-*.png"))
            if pngs:
                return pngs[0].read_bytes()
            raise RenderError("pdftoppm corrió pero no generó PNG")

        # Fallback: pdf2image (PIL)
        try:
            from pdf2image import convert_from_path
            images = convert_from_path(str(pdf_path), dpi=120, first_page=slide_index + 1, last_page=slide_index + 1)
            if images:
                import io
                buf = io.BytesIO()
                images[0].save(buf, "PNG")
                return buf.getvalue()
        except Exception as e:
            raise RenderError(f"pdf2image falló: {e}") from e
        raise RenderError("Sin pdftoppm ni pdf2image disponibles")
