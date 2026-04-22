"""Data models and factory for codeagent execution commands.

Migrated from vibe3.services.codeagent_models.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from vibe3.config.settings import VibeConfig

ExecutionRole = Literal["planner", "executor", "reviewer", "manager"]


@dataclass
class CodeagentCommand:
    """Configuration for a codeagent command execution."""

    role: ExecutionRole
    context_builder: Callable[[], str]
    task: str | None = None
    dry_run: bool = False
    handoff_kind: str = "run"
    handoff_metadata: dict[str, Any] | None = None
    agent: str | None = None
    backend: str | None = None
    model: str | None = None
    cwd: Path | None = None
    config: VibeConfig | None = None
    branch: str | None = None
    issue_number: int | None = None
    pre_gate_callback: Callable[..., None] | None = None
    cli_args: list[str] | None = None
    resolved_options: Any | None = None
    actor: str | None = None
    session_id: str | None = None


@dataclass
class CodeagentResult:
    """Result of codeagent execution."""

    success: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    handoff_file: Path | None = None
    session_id: str | None = None
    pid: int | None = None
    tmux_session: str | None = None
    log_path: Path | None = None


def create_codeagent_command(
    role: ExecutionRole,
    context_builder: Callable[[], str],
    task: str | None = None,
    dry_run: bool = False,
    handoff_kind: str | None = None,
    handoff_metadata: dict[str, Any] | None = None,
    agent: str | None = None,
    backend: str | None = None,
    model: str | None = None,
    cwd: Path | None = None,
    config: VibeConfig | None = None,
    branch: str | None = None,
    issue_number: int | None = None,
    pre_gate_callback: Callable[..., None] | None = None,
    cli_args: list[str] | None = None,
    resolved_options: Any | None = None,
    actor: str | None = None,
    session_id: str | None = None,
) -> CodeagentCommand:
    """Factory function to create CodeagentCommand.

    Args:
        role: Execution role (planner/executor/reviewer)
        context_builder: Function that builds prompt context
        task: Optional task message
        dry_run: Dry run mode
        handoff_kind: Kind for handoff recording
        handoff_metadata: Additional metadata for handoff
        agent: Agent preset override
        backend: Backend override
        model: Model override
        cwd: Explicit working directory for agent execution
        config: VibeConfig instance
        branch: Current branch (for async execution)
        issue_number: GitHub issue number (for no-op gate)
        pre_gate_callback: Optional callback invoked after agent completes
            but before the no-op gate fires. Receives (issue_number, branch,
            actor, stdout). Used by reviewer to write audit_ref from stdout.
        cli_args: Optional explicit CLI args used for async self-invocation
        resolved_options: Pre-resolved agent options for shared execution paths
        actor: Explicit actor override for shared execution paths
        session_id: Explicit session id override for resumed executions

    Returns:
        CodeagentCommand instance
    """
    kind_map: dict[ExecutionRole, str] = {
        "planner": "plan",
        "executor": "run",
        "reviewer": "review",
        "manager": "indicate",
    }

    return CodeagentCommand(
        role=role,
        context_builder=context_builder,
        task=task,
        dry_run=dry_run,
        handoff_kind=handoff_kind or kind_map.get(role, "run"),
        handoff_metadata=handoff_metadata,
        agent=agent,
        backend=backend,
        model=model,
        cwd=cwd,
        config=config,
        branch=branch,
        issue_number=issue_number,
        pre_gate_callback=pre_gate_callback,
        cli_args=cli_args,
        resolved_options=resolved_options,
        actor=actor,
        session_id=session_id,
    )
