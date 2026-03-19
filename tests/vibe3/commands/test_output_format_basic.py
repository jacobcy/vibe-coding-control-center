"""Tests for output format utilities - core functions."""

from datetime import datetime

import pytest

from vibe3.commands.output_format import (
    _output_simple,
    add_execution_step,
    create_trace_output,
)


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


def test_add_execution_step_none() -> None:
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


def test_output_simple_dict(capsys: pytest.CaptureFixture[str]) -> None:
    """Test simple output with nested dict."""
    result = {"pr": {"number": 200, "title": "Test PR"}}
    _output_simple(result)
    captured = capsys.readouterr()
    assert "pr:" in captured.out


def test_output_simple_list(capsys: pytest.CaptureFixture[str]) -> None:
    """Test simple output with list."""
    result = {"files": ["file1.py", "file2.py"]}
    _output_simple(result)
    captured = capsys.readouterr()
    assert "files:" in captured.out
