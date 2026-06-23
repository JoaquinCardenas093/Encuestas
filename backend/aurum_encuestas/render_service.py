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


def _crop_to_content(png_bytes: bytes, margin: int = 8, white_thresh: int = 245) -> bytes:
    """Crop PNG to non-white bounding box plus a small margin. Returns cropped PNG."""
    try:
        import io
        from PIL import Image, ImageChops
        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        # White background subtract → bbox of non-white pixels
        bg = Image.new("RGB", img.size, (255, 255, 255))
        diff = ImageChops.difference(img, bg)
        # Threshold: anything within white_thresh of pure white treated as bg
        diff_l = diff.convert("L").point(lambda p: 0 if p < (255 - white_thresh) else 255)
        bbox = diff_l.getbbox()
        if not bbox:
            return png_bytes
        x0, y0, x1, y1 = bbox
        x0 = max(0, x0 - margin)
        y0 = max(0, y0 - margin)
        x1 = min(img.size[0], x1 + margin)
        y1 = min(img.size[1], y1 + margin)
        cropped = img.crop((x0, y0, x1, y1))
        out = io.BytesIO()
        cropped.save(out, "PNG")
        return out.getvalue()
    except Exception:
        return png_bytes


def render_xlsx_to_png(xlsx_bytes: bytes, dpi: int = 200) -> bytes | None:
    """Render xlsx → PNG via libreoffice headless, cropped to content bbox.
    None if soffice missing or fails. Used for OLE placeholder PNG."""
    soffice = _find_soffice()
    if not soffice:
        return None
    with tempfile.TemporaryDirectory() as tmpdir:
        outdir = Path(tmpdir)
        xlsx_path = outdir / "in.xlsx"
        xlsx_path.write_bytes(xlsx_bytes)

        # xlsx → pdf (libreoffice handles native xlsx render with DataBar, fonts, etc.)
        try:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(outdir), str(xlsx_path)],
                capture_output=True, timeout=60, check=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None
        pdfs = list(outdir.glob("*.pdf"))
        if not pdfs:
            return None
        pdf_path = pdfs[0]

        # pdf → png via pdftoppm
        pdftoppm = shutil.which("pdftoppm")
        if pdftoppm:
            try:
                subprocess.run(
                    [pdftoppm, "-png", "-r", str(dpi),
                     "-f", "1", "-l", "1",
                     str(pdf_path), str(outdir / "page")],
                    capture_output=True, timeout=30, check=True,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                return None
            pngs = sorted(outdir.glob("page-*.png"))
            if pngs:
                return _crop_to_content(pngs[0].read_bytes())
        # Fallback pdf2image
        try:
            from pdf2image import convert_from_path
            images = convert_from_path(str(pdf_path), dpi=dpi, first_page=1, last_page=1)
            if images:
                import io
                buf = io.BytesIO()
                images[0].save(buf, "PNG")
                return _crop_to_content(buf.getvalue())
        except Exception:
            return None
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
