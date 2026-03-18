"""Trace output data models.

This module provides data models for structured trace output,
supporting multiple output formats (YAML, JSON, human-readable text).

Reference: docs/v3/design/trace-inspect-output-format.md
"""

from datetime import datetime
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field


class ExecutionStep(BaseModel):
    """A single execution step in the trace.

    Attributes:
        time: Timestamp of the step
        level: Log level (INFO, DEBUG, WARNING, ERROR)
        module: Module name where the step occurred
        function: Function name where the step occurred
        line: Line number in the source code
        message: Step message
    """

    time: str = Field(..., description="Timestamp of the step")
    level: str = Field(..., description="Log level (INFO, DEBUG, WARNING, ERROR)")
    module: str = Field(..., description="Module name")
    function: str = Field(..., description="Function name")
    line: int = Field(..., description="Line number")
    message: str = Field(..., description="Step message")


class TraceOutput(BaseModel):
    """Trace output model for structured trace data.

    Attributes:
        command: Command name (e.g., "pr show")
        status: Execution status (running, completed, failed)
        start_time: Start timestamp
        end_time: End timestamp (if completed)
        execution: List of execution steps
        result: Command result data
    """

    command: str = Field(..., description="Command name")
    status: str = Field(..., description="Execution status")
    start_time: datetime = Field(..., description="Start timestamp")
    end_time: Optional[datetime] = Field(None, description="End timestamp")
    execution: list[ExecutionStep] = Field(
        default_factory=list, description="Execution steps"
    )
    result: dict[str, Any] = Field(default_factory=dict, description="Command result")

    def to_yaml(self) -> str:
        """Convert to YAML string.

        Returns:
            YAML formatted string

        Example:
            >>> trace = TraceOutput(command="pr show", status="completed", ...)
            >>> print(trace.to_yaml())
            trace:
              command: pr show
              status: completed
        """
        data = {
            "trace": {
                "command": self.command,
                "status": self.status,
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat() if self.end_time else None,
            },
            "execution": [
                {
                    "time": step.time,
                    "level": step.level,
                    "module": step.module,
                    "function": step.function,
                    "line": step.line,
                    "message": step.message,
                }
                for step in self.execution
            ],
            "result": self.result,
        }
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)

    def to_json(self) -> str:
        """Convert to JSON string.

        Returns:
            JSON formatted string

        Example:
            >>> trace = TraceOutput(command="pr show", status="completed", ...)
            >>> print(trace.to_json())
            {"trace": {"command": "pr show", ...}}
        """
        return self.model_dump_json(indent=2)

    def to_text(self) -> str:
        """Convert to human-readable text.

        Returns:
            Human-readable text with clear sections

        Example:
            >>> trace = TraceOutput(command="pr show", status="completed", ...)
            >>> print(trace.to_text())
            [TRACE] pr show
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            ▶ Execution Flow:
              13:13:43 | INFO  | Fetching PR details
            ...
            ▶ Result:
              PR #200: feat: codex auto-review
            ...
        """
        lines = [
            f"[TRACE] {self.command}",
            "━" * 50,
            "",
            "▶ Execution Flow:",
        ]

        # Add execution steps
        for step in self.execution:
            lines.append(f"  {step.time} | {step.level:5} | {step.message}")

        # Add result section
        if self.result:
            lines.append("")
            lines.append("▶ Result:")
            for key, value in self.result.items():
                if isinstance(value, dict):
                    lines.append(f"  {key}:")
                    for k, v in value.items():
                        lines.append(f"    {k}: {v}")
                else:
                    lines.append(f"  {key}: {value}")

        # Add footer
        lines.append("")
        lines.append("━" * 50)
        status_icon = "✅" if self.status == "completed" else "❌"
        time_str = self.end_time.strftime("[%H:%M:%S]") if self.end_time else ""
        lines.append(f"{time_str} {self.status} {status_icon}")

        return "\n".join(lines)
