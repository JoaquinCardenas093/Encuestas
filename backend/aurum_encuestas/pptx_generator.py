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


def build_pptx(state: ProjectState, out_path: str) -> None:
    """Build final pptx. Opens template, removes its 2 slides, then for each slide in state
    clones the appropriate source slide (shell or separator), substitutes placeholders, inserts shapes."""
    template_path = state.inputs.template_path
    prs = Presentation(template_path)

    # Cache source XMLs
    shell_src_xml = etree.tostring(prs.slides[0]._element)
    separator_src_xml = etree.tostring(prs.slides[1]._element)
    shell_rels = list(prs.slides[0].part.rels.values())

    # Remove template's 2 slides properly (drop rels so parts don't dupe-write to zip)
    xml_slides = prs.slides._sldIdLst
    slides_to_remove = list(xml_slides)
    for sld in slides_to_remove:
        rId = sld.rId
        try:
            prs.part.drop_rel(rId)
        except Exception:
            pass
        xml_slides.remove(sld)

    # Compute free_area from original shell slide (before remove)
    from .pptx_template import _compute_free_area
    free_area = _compute_free_area(
        Presentation(template_path).slides[0],
        prs.slide_width, prs.slide_height,
    )

    sep_counter = 0
    for idx, slide_def in enumerate(state.slides):
        if slide_def.type == "separator":
            sep_counter += 1
            _append_separator(prs, separator_src_xml, slide_def.title, sep_counter)
        else:
            _append_shell(prs, shell_src_xml, slide_def, state, free_area)

    prs.save(out_path)


def _append_separator(prs, src_xml: bytes, title: str | None, counter: int) -> None:
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)
    # Clear default placeholders
    for sp in list(slide.shapes):
        sp_el = sp._element
        sp_el.getparent().remove(sp_el)
    # Append shapes from src
    src_tree = etree.fromstring(src_xml)
    src_spTree = src_tree.find(".//{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}spTree") or \
                  src_tree.find(".//{http://schemas.openxmlformats.org/presentationml/2006/main}spTree")
    if src_spTree is None:
        # Try generic
        for child in src_tree.iter():
            if child.tag.endswith("}spTree"):
                src_spTree = child
                break
    if src_spTree is not None:
        for child in list(src_spTree):
            if child.tag.endswith("}sp") or child.tag.endswith("}pic") or child.tag.endswith("}cxnSp"):
                slide.shapes._spTree.append(deepcopy(child))

    _substitute_placeholders(slide, {"@Titulo": f"{counter}. {title or ''}", "@Notas": ""})


def _append_shell(prs, src_xml: bytes, slide_def: Slide, state: ProjectState, free_area: dict) -> None:
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)
    for sp in list(slide.shapes):
        sp_el = sp._element
        sp_el.getparent().remove(sp_el)

    src_tree = etree.fromstring(src_xml)
    src_spTree = None
    for child in src_tree.iter():
        if child.tag.endswith("}spTree"):
            src_spTree = child
            break
    if src_spTree is not None:
        for child in list(src_spTree):
            if child.tag.endswith("}sp") or child.tag.endswith("}pic") or child.tag.endswith("}cxnSp"):
                slide.shapes._spTree.append(deepcopy(child))

    notes_text = slide_def.auto_notes or f"Respuesta única. Número de observaciones: {state.parsed_db.sample_size if state.parsed_db else 500}."
    _substitute_placeholders(slide, {"@Titulo": slide_def.title or "", "@Notas": notes_text})

    # Compute layout for this slide
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
