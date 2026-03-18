"""Tests for output format utilities - result output."""

import pytest

from vibe3.commands.output_format import create_trace_output, output_result


def test_output_trace_json(capsys: pytest.CaptureFixture[str]) -> None:
    """Test trace output in JSON format."""
    trace = create_trace_output("pr show")
    result = {"number": 200}
    output_result(result, trace, json_output=True, yaml_output=False)
    captured = capsys.readouterr()
    assert '"command": "pr show"' in captured.out


def test_output_trace_yaml(capsys: pytest.CaptureFixture[str]) -> None:
    """Test trace output in YAML format."""
    trace = create_trace_output("pr show")
    result = {"number": 200}
    output_result(result, trace, json_output=False, yaml_output=True)
    captured = capsys.readouterr()
    assert "command: pr show" in captured.out


def test_output_trace_text(capsys: pytest.CaptureFixture[str]) -> None:
    """Test trace output in text format."""
    trace = create_trace_output("pr show")
    result = {"number": 200}
    output_result(result, trace, json_output=False, yaml_output=False)
    captured = capsys.readouterr()
    assert "[TRACE] pr show" in captured.out


def test_output_no_trace_json(capsys: pytest.CaptureFixture[str]) -> None:
    """Test output without trace in JSON format."""
    result = {"number": 200}
    output_result(result, None, json_output=True, yaml_output=False)
    captured = capsys.readouterr()
    assert '"number": 200' in captured.out


def test_output_no_trace_yaml(capsys: pytest.CaptureFixture[str]) -> None:
    """Test output without trace in YAML format."""
    result = {"number": 200}
    output_result(result, None, json_output=False, yaml_output=True)
    captured = capsys.readouterr()
    assert "number: 200" in captured.out


def test_output_no_trace_text(capsys: pytest.CaptureFixture[str]) -> None:
    """Test output without trace in simple text format."""
    result = {"number": 200}
    output_result(result, None, json_output=False, yaml_output=False)
    captured = capsys.readouterr()
    assert "number: 200" in captured.out