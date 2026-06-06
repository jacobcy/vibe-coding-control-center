"""Tests for output format utilities.

Merged from test_output_format_basic.py + test_output_format_result.py.
"""

from datetime import datetime

import pytest

from vibe3.commands.output_format import (
    _output_simple,
    add_execution_step,
    create_trace_output,
    output_result,
)

# ==============================================================================
# Core functions tests (from test_output_format_basic.py)
# ==============================================================================


def test_create_trace_output() -> None:
    """Test creating a trace output model."""
    start_time = datetime(2026, 3, 18, 13, 13, 43)
    trace_output = create_trace_output("pr show", start_time)

    assert trace_output.command == "pr show"
    assert trace_output.status == "running"
    assert trace_output.start_time == start_time


def test_add_execution_step() -> None:
    """Test adding an execution step to trace output."""
    trace_output = create_trace_output("pr show")

    add_execution_step(
        trace_output=trace_output,
        time="13:13:43",
        level="INFO",
        module="vibe3.commands.pr",
        function="show",
        line=99,
        message="Fetching PR details",
    )

    assert len(trace_output.execution) == 1
    assert trace_output.execution[0].message == "Fetching PR details"


def test_add_execution_step_none(capsys: pytest.CaptureFixture[str]) -> None:
    """Test adding execution step when trace_output is None."""
    add_execution_step(
        trace_output=None,
        time="13:13:43",
        level="INFO",
        module="test",
        function="test",
        line=1,
        message="test",
    )
    captured = capsys.readouterr()
    assert captured.out == ""


def test_output_simple_dict(capsys: pytest.CaptureFixture[str]) -> None:
    """Test simple output with nested dict."""
    result = {"pr": {"number": 200, "title": "Test PR"}}
    _output_simple(result)
    captured = capsys.readouterr()
    assert "pr:" in captured.out
    assert "number: 200" in captured.out
    assert "title: Test PR" in captured.out


def test_output_simple_list(capsys: pytest.CaptureFixture[str]) -> None:
    """Test simple output with list."""
    result = {"files": ["file1.py", "file2.py"]}
    _output_simple(result)
    captured = capsys.readouterr()
    assert "files:" in captured.out
    assert "- file1.py" in captured.out
    assert "- file2.py" in captured.out


# ==============================================================================
# Result output tests (from test_output_format_result.py)
# ==============================================================================


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


def test_output_simple_scalar(capsys: pytest.CaptureFixture[str]) -> None:
    """Test simple output with scalar values."""
    result = {"number": 200, "title": "Test PR"}
    _output_simple(result)
    captured = capsys.readouterr()
    assert "number: 200" in captured.out
    assert "title: Test PR" in captured.out


def test_output_simple_mixed(capsys: pytest.CaptureFixture[str]) -> None:
    """Test simple output with mixed types."""
    result = {
        "pr": {"number": 200, "title": "Test PR"},
        "files": ["a.py", "b.py"],
        "status": "completed",
    }
    _output_simple(result)
    captured = capsys.readouterr()
    # Verify dict value
    assert "pr:" in captured.out
    assert "  number: 200" in captured.out
    # Verify list value
    assert "files:" in captured.out
    assert "  - a.py" in captured.out
    # Verify scalar value
    assert "status: completed" in captured.out
