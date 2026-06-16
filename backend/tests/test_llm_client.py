from unittest.mock import MagicMock, patch

import pytest

from aurum_encuestas.llm_client import generate_analysis
from aurum_encuestas.errors import LLMError


@patch("aurum_encuestas.llm_client._client")
def test_generate_analysis_chart_scope(mock_client):
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="El 50% respondió Sí.")]
    fake_msg.usage = MagicMock(input_tokens=200, output_tokens=20, cache_read_input_tokens=170)
    mock_client.messages.create.return_value = fake_msg

    text = generate_analysis(
        scope="chart",
        context={
            "section_title": "Test",
            "question_text": "?",
            "options": ["Sí", "No"],
            "breakdown_label": "General",
            "data": {"Total": {"Sí": {"count": 50, "pct": 0.5}, "No": {"count": 50, "pct": 0.5}}},
        },
    )
    assert "Sí" in text
    args, kwargs = mock_client.messages.create.call_args
    assert kwargs["model"] == "claude-haiku-4-5-20251001"
    system = kwargs["system"]
    assert isinstance(system, list)
    assert system[0]["cache_control"]["type"] == "ephemeral"


@patch("aurum_encuestas.llm_client._client", None)
def test_generate_analysis_no_api_key_raises():
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
        generate_analysis(scope="chart", context={"section_title": "x", "question_text": "y", "options": [], "breakdown_label": "z", "data": {}})


@patch("aurum_encuestas.llm_client._client")
def test_generate_analysis_truncates_long_response(mock_client):
    long_text = "x" * 1000
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text=long_text)]
    fake_msg.usage = MagicMock(input_tokens=200, output_tokens=20, cache_read_input_tokens=0)
    mock_client.messages.create.return_value = fake_msg

    text = generate_analysis(scope="chart", context={"section_title": "x", "question_text": "y", "options": [], "breakdown_label": "z", "data": {}})
    assert len(text) <= 500


@patch("aurum_encuestas.llm_client._client")
def test_generate_analysis_handles_api_error(mock_client):
    from anthropic import APIStatusError
    err = APIStatusError("rate limit", response=MagicMock(status_code=429), body=None)
    mock_client.messages.create.side_effect = err

    with pytest.raises(LLMError):
        generate_analysis(scope="chart", context={"section_title": "x", "question_text": "y", "options": [], "breakdown_label": "z", "data": {}})


@patch("aurum_encuestas.llm_client._client")
def test_suggest_layout_returns_validated_json(mock_client):
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text='{"elements":[{"role":"chart_0","x":1000,"y":1000,"cx":5000,"cy":4000}]}')]
    fake_msg.usage = MagicMock(input_tokens=200, output_tokens=80, cache_read_input_tokens=170)
    mock_client.messages.create.return_value = fake_msg

    from aurum_encuestas.llm_client import suggest_layout
    res = suggest_layout(
        n_charts=1, chart_types=["PIE"], n_chart_an=0, n_q_an=0, has_slide_an=False,
        free_area={"x": 0, "y": 0, "cx": 12000000, "cy": 7000000},
    )
    assert "elements" in res
    assert len(res["elements"]) == 1


@patch("aurum_encuestas.llm_client._client")
def test_suggest_layout_invalid_json_falls_back(mock_client):
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="not json")]
    fake_msg.usage = MagicMock(input_tokens=200, output_tokens=20, cache_read_input_tokens=0)
    mock_client.messages.create.return_value = fake_msg

    from aurum_encuestas.llm_client import suggest_layout
    res = suggest_layout(n_charts=1, chart_types=["PIE"], n_chart_an=0, n_q_an=0, has_slide_an=False, free_area={"x": 0, "y": 0, "cx": 12000000, "cy": 7000000})
    # falls back to heuristic
    assert res["source"] in ("heuristic", "ai_fallback")
