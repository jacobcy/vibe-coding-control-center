"""Tests for trace output models."""

from datetime import datetime

import pytest

from vibe3.models.trace import ExecutionStep, TraceOutput


def test_execution_step_creation() -> None:
    """Test creating an execution step."""
    step = ExecutionStep(
        time="13:13:43",
        level="INFO",
        module="vibe3.commands.pr",
        function="show",
        line=99,
        message="Fetching PR details",
    )

    assert step.time == "13:13:43"
    assert step.level == "INFO"
    assert step.module == "vibe3.commands.pr"
    assert step.function == "show"
    assert step.line == 99
    assert step.message == "Fetching PR details"


def test_trace_output_creation() -> None:
    """Test creating a trace output."""
    start_time = datetime(2026, 3, 18, 13, 13, 43)
    end_time = datetime(2026, 3, 18, 13, 13, 45)

    trace = TraceOutput(
        command="pr show",
        status="completed",
        start_time=start_time,
        end_time=end_time,
    )

    assert trace.command == "pr show"
    assert trace.status == "completed"
    assert trace.start_time == start_time
    assert trace.end_time == end_time
    assert trace.execution == []
    assert trace.result == {}


def test_trace_output_with_steps() -> None:
    """Test trace output with execution steps."""
    step1 = ExecutionStep(
        time="13:13:43",
        level="INFO",
        module="vibe3.commands.pr",
        function="show",
        line=99,
        message="Fetching PR details",
    )

    step2 = ExecutionStep(
        time="13:13:44",
        level="DEBUG",
        module="vibe3.clients.sqlite_client",
        function="_init_db",
        line=124,
        message="Database schema initialized",
    )

    trace = TraceOutput(
        command="pr show",
        status="completed",
        start_time=datetime(2026, 3, 18, 13, 13, 43),
        end_time=datetime(2026, 3, 18, 13, 13, 45),
        execution=[step1, step2],
        result={"number": 200, "title": "feat: codex auto-review"},
    )

    assert len(trace.execution) == 2
    assert trace.execution[0].message == "Fetching PR details"
    assert trace.execution[1].message == "Database schema initialized"
    assert trace.result["number"] == 200


def test_trace_output_to_yaml() -> None:
    """Test converting trace output to YAML."""
    trace = TraceOutput(
        command="pr show",
        status="completed",
        start_time=datetime(2026, 3, 18, 13, 13, 43),
        end_time=datetime(2026, 3, 18, 13, 13, 45),
        result={"number": 200, "title": "feat: codex auto-review"},
    )

    yaml_str = trace.to_yaml()

    assert "command: pr show" in yaml_str
    assert "status: completed" in yaml_str
    assert "result:" in yaml_str
    assert "number: 200" in yaml_str


def test_trace_output_to_json() -> None:
    """Test converting trace output to JSON."""
    trace = TraceOutput(
        command="pr show",
        status="completed",
        start_time=datetime(2026, 3, 18, 13, 13, 43),
        result={"number": 200},
    )

    json_str = trace.to_json()

    assert '"command": "pr show"' in json_str
    assert '"status": "completed"' in json_str
    assert '"number": 200' in json_str


def test_trace_output_to_text() -> None:
    """Test converting trace output to human-readable text."""
    step = ExecutionStep(
        time="13:13:43",
        level="INFO",
        module="vibe3.commands.pr",
        function="show",
        line=99,
        message="Fetching PR details",
    )

    trace = TraceOutput(
        command="pr show",
        status="completed",
        start_time=datetime(2026, 3, 18, 13, 13, 43),
        end_time=datetime(2026, 3, 18, 13, 13, 45),
        execution=[step],
        result={"number": 200, "title": "feat: codex auto-review"},
    )

    text = trace.to_text()

    assert "[TRACE] pr show" in text
    assert "▶ Execution Flow:" in text
    assert "13:13:43 | INFO  | Fetching PR details" in text
    assert "▶ Result:" in text
    assert "number: 200" in text
    assert "completed ✅" in text


def test_trace_output_failed_status() -> None:
    """Test trace output with failed status."""
    trace = TraceOutput(
        command="pr show",
        status="failed",
        start_time=datetime(2026, 3, 18, 13, 13, 43),
    )

    text = trace.to_text()

    assert "failed ❌" in text
