"""Output format utilities.

This module provides utilities for handling multiple output formats
(YAML, JSON, text) for trace and command outputs.

Reference: docs/v3/design/trace-inspect-output-format.md
"""

from datetime import datetime
from typing import Any

import typer

from vibe3.models.trace import ExecutionStep, TraceOutput


def output_result(
    result: dict[str, Any],
    trace_output: TraceOutput | None,
    json_output: bool,
    yaml_output: bool,
) -> None:
    """Output result in the requested format.

    Args:
        result: Command result data
        trace_output: Trace output model (if --trace enabled)
        json_output: Whether to output JSON format
        yaml_output: Whether to output YAML format
    """
    if trace_output:
        # --trace enabled: use TraceOutput model
        trace_output.result = result
        trace_output.status = "completed"
        if trace_output.end_time is None:
            trace_output.end_time = datetime.now()

        if json_output:
            typer.echo(trace_output.to_json())
        elif yaml_output:
            typer.echo(trace_output.to_yaml())
        else:
            typer.echo(trace_output.to_text())
    else:
        # No trace: simple output
        if json_output:
            import json

            typer.echo(json.dumps(result, indent=2, default=str))
        elif yaml_output:
            import yaml

            typer.echo(yaml.dump(result, default_flow_style=False, allow_unicode=True))
        else:
            # Default: simple key-value output
            _output_simple(result)


def _output_simple(result: dict[str, Any]) -> None:
    """Output simple key-value format.

    Args:
        result: Result dictionary
    """
    for key, value in result.items():
        if isinstance(value, dict):
            typer.echo(f"{key}:")
            for k, v in value.items():
                typer.echo(f"  {k}: {v}")
        elif isinstance(value, list):
            typer.echo(f"{key}:")
            for item in value:
                typer.echo(f"  - {item}")
        else:
            typer.echo(f"{key}: {value}")


def create_trace_output(
    command: str, start_time: datetime | None = None
) -> TraceOutput:
    """Create a new trace output model.

    Args:
        command: Command name
        start_time: Start time (defaults to now)

    Returns:
        TraceOutput model
    """
    return TraceOutput(
        command=command,
        status="running",
        start_time=start_time or datetime.now(),
        end_time=None,
    )


def add_execution_step(
    trace_output: TraceOutput | None,
    time: str,
    level: str,
    module: str,
    function: str,
    line: int,
    message: str,
) -> None:
    """Add an execution step to trace output.

    Args:
        trace_output: Trace output model (can be None)
        time: Timestamp string
        level: Log level
        module: Module name
        function: Function name
        line: Line number
        message: Step message
    """
    if trace_output is None:
        return

    step = ExecutionStep(
        time=time,
        level=level,
        module=module,
        function=function,
        line=line,
        message=message,
    )
    trace_output.execution.append(step)
