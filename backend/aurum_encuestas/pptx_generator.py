import json as _json
import re
from copy import deepcopy

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Emu

from .config import get_layout_bank_path
from .data_extractor import extract_chart_data
from .layout_matcher import match_layout
from .models import Chart, LayoutBank, ProjectState, Slide

CHART_TYPE_MAP = {
    "PIE": XL_CHART_TYPE.PIE,
    "DONUT": XL_CHART_TYPE.DOUGHNUT,
    "BAR": XL_CHART_TYPE.BAR_CLUSTERED,
    "COLUMN": XL_CHART_TYPE.COLUMN_CLUSTERED,
    "BAR_STACKED": XL_CHART_TYPE.BAR_STACKED,
    "COLUMN_STACKED": XL_CHART_TYPE.COLUMN_STACKED,
    "LINE": XL_CHART_TYPE.LINE,
    "AREA": XL_CHART_TYPE.AREA,
    "RADAR": XL_CHART_TYPE.RADAR,
}


def _load_bank() -> LayoutBank:
    p = get_layout_bank_path()
    if not p.exists():
        return LayoutBank()
    try:
        return LayoutBank.model_validate(_json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return LayoutBank()

PLACEHOLDER_RE = re.compile(r"@(\w+)")


def _slide_has_placeholder(slide, marker: str) -> bool:
    for sh in slide.shapes:
        if sh.has_text_frame and marker in (sh.text_frame.text or ""):
            return True
    return False


def _detect_shell_separator_indices(prs) -> tuple[int, int]:
    """Heuristic: shell = slide with @Notas placeholder. Separator = the other one.
    Fallback to (0, 1) if both/neither has @Notas."""
    slides_list = list(prs.slides)
    if len(slides_list) < 2:
        return 0, 1
    has_notas_0 = _slide_has_placeholder(slides_list[0], "@Notas")
    has_notas_1 = _slide_has_placeholder(slides_list[1], "@Notas")
    if has_notas_0 and not has_notas_1:
        return 0, 1
    if has_notas_1 and not has_notas_0:
        return 1, 0
    return 0, 1


def _duplicate_slide(prs, src_slide):
    """Add a new slide at end of presentation, cloning all shapes AND rels from src_slide.
    Preserves images (pic elements need their image rels copied too)."""
    new_slide = prs.slides.add_slide(src_slide.slide_layout)
    # remove placeholders created by layout
    for sp in list(new_slide.shapes):
        sp._element.getparent().remove(sp._element)
    # copy each shape XML
    for shape in src_slide.shapes:
        new_el = deepcopy(shape._element)
        new_slide.shapes._spTree.append(new_el)
    # copy rels (images, charts, etc.) — except notesSlide
    for rel in src_slide.part.rels.values():
        if "notesSlide" in rel.reltype:
            continue
        if rel.is_external:
            new_slide.part.rels.get_or_add_ext_rel(rel.reltype, rel.target_ref)
        else:
            new_slide.part.relate_to(rel.target_part, rel.reltype)
    return new_slide


def build_pptx(state: ProjectState, out_path: str) -> None:
    """Build final pptx. Open template, detect which slide is shell vs separator by @Notas
    placeholder, duplicate appropriate source per user slide (preserving image rels),
    substitute placeholders, insert charts, then remove the template originals."""
    template_path = state.inputs.template_path
    prs = Presentation(template_path)

    shell_idx, sep_idx = _detect_shell_separator_indices(prs)
    shell_src = prs.slides[shell_idx]
    separator_src = prs.slides[sep_idx]

    # Compute free_area from shell src before any mutation
    from .pptx_template import _compute_free_area
    free_area = _compute_free_area(shell_src, prs.slide_width, prs.slide_height)

    sep_counter = 0
    for slide_def in state.slides:
        if slide_def.type == "separator":
            sep_counter += 1
            new_slide = _duplicate_slide(prs, separator_src)
            _substitute_placeholders(new_slide, {"@Titulo": f"{sep_counter}. {slide_def.title or ''}", "@Notas": ""})
        else:
            new_slide = _duplicate_slide(prs, shell_src)
            notes_text = slide_def.auto_notes or f"Respuesta única. Número de observaciones: {state.parsed_db.sample_size if state.parsed_db else 500}."
            _substitute_placeholders(new_slide, {"@Titulo": slide_def.title or "", "@Notas": notes_text})
            _add_slide_content(new_slide, slide_def, state, free_area)

    # Remove the 2 template source slides (they're at positions 0 and 1)
    xml_slides = prs.slides._sldIdLst
    to_remove = [xml_slides[0], xml_slides[1]] if len(xml_slides) >= 2 else list(xml_slides)
    for sld in to_remove:
        rId = sld.rId
        try:
            prs.part.drop_rel(rId)
        except Exception:
            pass
        xml_slides.remove(sld)

    prs.save(out_path)


def _add_slide_content(slide, slide_def: Slide, state: ProjectState, free_area: dict) -> None:
    """Add charts + analyses to a shell slide per layout matcher."""
    n_chart_an = sum(1 for a in slide_def.analyses if a.scope == "chart")
    n_q_an = sum(1 for a in slide_def.analyses if a.scope == "question")
    has_slide_an = any(a.scope == "slide" for a in slide_def.analyses)

    layout_result = match_layout(
        bank=_load_bank(),
        n_charts=len(slide_def.charts),
        chart_types=[c.chart_type for c in slide_def.charts],
        n_chart_an=n_chart_an,
        n_q_an=n_q_an,
        has_slide_an=has_slide_an,
        free_area=free_area,
    )
    layout = {"elements": layout_result["elements"]}

    # Insert charts and analysis textboxes per layout elements
    for el in layout["elements"]:
        role = el["role"]
        if role.startswith("chart_") and not role.startswith("chart_analysis"):
            i = int(role.split("_")[1])
            chart_def = slide_def.charts[i]
            _add_chart(slide, chart_def, state, el)
        elif role.startswith("chart_analysis_"):
            i = int(role.split("_")[2])
            chart_analyses = [a for a in slide_def.analyses if a.scope == "chart"]
            if i < len(chart_analyses):
                _add_textbox(slide, chart_analyses[i].text, el, state.inputs.font_override)
        elif role.startswith("question_analysis_"):
            i = int(role.split("_")[2])
            q_analyses = [a for a in slide_def.analyses if a.scope == "question"]
            if i < len(q_analyses):
                _add_textbox(slide, q_analyses[i].text, el, state.inputs.font_override)
        elif role == "slide_analysis":
            slide_an = next((a for a in slide_def.analyses if a.scope == "slide"), None)
            if slide_an:
                _add_textbox(slide, slide_an.text, el, state.inputs.font_override)


def _add_chart(slide, chart_def: Chart, state: ProjectState, el: dict) -> None:
    data = extract_chart_data(state.inputs.db_path, _find_question(state, chart_def.question_id),
                              chart_def.breakdown_id, state.parsed_db.data_blocks if state.parsed_db else {})
    cd = CategoryChartData()
    # Categories = options, Series = breakdown categories (or single "Total" if general)
    options = _find_question(state, chart_def.question_id).options
    cd.categories = options

    if not chart_def.multi_series:
        # Sum across breakdown cats → single series "Total"
        series = []
        for opt in options:
            total = sum((data[cat].get(opt, {}).get("count", 0) or 0) for cat in data)
            series.append(total)
        cd.add_series("Total", series)
    else:
        for cat in data:
            values = [data[cat].get(opt, {}).get("count", 0) or 0 for opt in options]
            cd.add_series(cat, values)

    chart_type_xl = CHART_TYPE_MAP.get(chart_def.chart_type, XL_CHART_TYPE.BAR_CLUSTERED)
    slide.shapes.add_chart(chart_type_xl, Emu(el["x"]), Emu(el["y"]), Emu(el["cx"]), Emu(el["cy"]), cd)


def _add_textbox(slide, text: str, el: dict, font_name: str | None = None) -> None:
    tb = slide.shapes.add_textbox(Emu(el["x"]), Emu(el["y"]), Emu(el["cx"]), Emu(el["cy"]))
    tf = tb.text_frame
    tf.text = text
    tf.word_wrap = True
    if font_name:
        for para in tf.paragraphs:
            for run in para.runs:
                run.font.name = font_name


def _substitute_placeholders(slide, mapping: dict[str, str]) -> None:
    for sh in slide.shapes:
        if not sh.has_text_frame:
            continue
        for para in sh.text_frame.paragraphs:
            full_text = "".join(run.text or "" for run in para.runs)
            for key, val in mapping.items():
                if key in full_text:
                    new_text = full_text.replace(key, val)
                    # rewrite the paragraph as a single run
                    for run in list(para.runs):
                        run.text = ""
                    if para.runs:
                        para.runs[0].text = new_text
                    else:
                        para.add_run().text = new_text


def _find_question(state: ProjectState, qid: str):
    return next(q for q in state.parsed_db.questions if q.id == qid)
