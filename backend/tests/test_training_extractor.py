from aurum_encuestas.training_extractor import extract_layouts_from_pptx, signature_for_slide


def test_extract_at_least_one_layout(training_pptx_path):
    layouts = extract_layouts_from_pptx(str(training_pptx_path))
    assert len(layouts) >= 1
    lay = layouts[0]
    assert lay.signature  # non-empty
    assert any(el.role == "chart_0" for el in lay.elements)


def test_signature_encodes_chart_count_and_types():
    sig = signature_for_slide(n_charts=2, chart_types=["PIE", "BAR_CLUSTERED"], n_chart_an=1, n_q_an=0, has_slide_an=True)
    assert "2" in sig
    assert "PIE" in sig
    assert "BAR_CLUSTERED" in sig
