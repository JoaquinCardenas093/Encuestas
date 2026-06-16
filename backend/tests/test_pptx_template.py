from aurum_encuestas.pptx_template import load_template
from aurum_encuestas.errors import TemplateInvalidError
import pytest


def test_load_valid_template(valid_template_path):
    info = load_template(str(valid_template_path))
    assert info.shell_slide_index == 0
    assert info.separator_slide_index == 1
    assert "@Titulo" in info.placeholders


def test_load_template_with_notas_placeholder(valid_template_path):
    info = load_template(str(valid_template_path))
    assert "@Notas" in info.placeholders


def test_load_template_with_one_slide_raises(invalid_template_one_slide):
    with pytest.raises(TemplateInvalidError, match="2 slides"):
        load_template(str(invalid_template_one_slide))


def test_load_template_without_titulo_raises(invalid_template_no_titulo):
    with pytest.raises(TemplateInvalidError, match="@Titulo"):
        load_template(str(invalid_template_no_titulo))


def test_load_template_free_area_computed(valid_template_path):
    info = load_template(str(valid_template_path))
    fa = info.free_area
    assert fa["cx"] > 0
    assert fa["cy"] > 0
