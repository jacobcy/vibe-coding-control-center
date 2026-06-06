"""Tests for trace output models."""

from datetime import datetime

from vibe3.models.trace import ExecutionStep, TraceOutput, format_result_entries


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


def test_format_result_entries_dict() -> None:
    """Test format_result_entries with dict value."""
    result = {"pr": {"number": 200, "title": "Test PR"}}
    lines = format_result_entries(result)
    assert lines == ["  pr:", "    number: 200", "    title: Test PR"]


def test_format_result_entries_list() -> None:
    """Test format_result_entries with list value."""
    result = {"files": ["a.py", "b.py"]}
    lines = format_result_entries(result)
    assert lines == ["  files:", "    - a.py", "    - b.py"]


def test_format_result_entries_scalar() -> None:
    """Test format_result_entries with scalar value."""
    result = {"number": 200, "title": "Test PR"}
    lines = format_result_entries(result)
    assert lines == ["  number: 200", "  title: Test PR"]


def test_format_result_entries_empty() -> None:
    """Test format_result_entries with empty dict."""
    result = {}
    lines = format_result_entries(result)
    assert lines == []


def test_format_result_entries_custom_indent() -> None:
    """Test format_result_entries with custom indent."""
    result = {"pr": {"number": 200}}
    lines = format_result_entries(result, indent="")
    assert lines == ["pr:", "  number: 200"]


def test_trace_output_to_text_with_list() -> None:
    """Test to_text with list result."""
    trace = TraceOutput(
        command="pr list",
        status="completed",
        start_time=datetime(2026, 3, 18, 13, 13, 43),
        end_time=datetime(2026, 3, 18, 13, 13, 45),
        result={"files": ["a.py", "b.py"]},
    )

    text = trace.to_text()

    assert "▶ Result:" in text
    assert "  files:" in text
    assert "    - a.py" in text
    assert "    - b.py" in text


def test_trace_output_to_yaml_flat_structure() -> None:
    """Test to_yaml produces flat structure (not nested under trace:)."""
    trace = TraceOutput(
        command="pr show",
        status="completed",
        start_time=datetime(2026, 3, 18, 13, 13, 43),
        end_time=datetime(2026, 3, 18, 13, 13, 45),
        result={"number": 200},
    )

    yaml_str = trace.to_yaml()

    # Verify flat structure: these should be top-level keys, not nested under "trace:"
    assert "command: pr show" in yaml_str
    assert "status: completed" in yaml_str
    assert "start_time:" in yaml_str
    # Verify no "trace:" wrapper key at the top
    lines = yaml_str.split("\n")
    # Check that 'command:' is not indented (top-level key)
    assert any(line.startswith("command:") for line in lines)
