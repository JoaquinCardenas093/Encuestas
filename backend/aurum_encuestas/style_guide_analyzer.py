"""M6 Style Guide Analyzer — Claude Sonnet 4.6 vision wrapper.

Analyzes training corpus PPTs and synthesizes a unified StyleGuide JSON.
Full implementation in M6.7. This stub provides the public interface
so other modules can import without errors.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .style_guide import StyleGuide


def analyze_corpus(corpus_pptx_paths: list[str], existing_style_guide=None) -> "StyleGuide":
    """Stub: analyze training corpus with AI vision.

    Returns BUILTIN_STYLE_GUIDE until M6.7 implements the real pipeline.
    """
    from .style_guide import load_active
    return load_active()


def get_render_cache_path(pptx_hash: str, slide_idx: int) -> str:
    """Return the expected PNG cache path for a slide render."""
    from .config import get_render_cache_dir
    return str(get_render_cache_dir() / f"{pptx_hash}_{slide_idx}.png")
