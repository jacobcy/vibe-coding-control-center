"""Unified codeagent execution service.

This service provides a unified interface for executing codeagent commands
(plan/review/run) with support for both synchronous and asynchronous execution.

Design principles:
- Single source of truth for codeagent execution
- Support sync/async modes uniformly
- Reusable across plan/review/run commands
- Easy to extend for new commands
"""

import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal

from loguru import logger
from typer import echo

from vibe3.config.settings import VibeConfig
from vibe3.models.review_runner import AgentOptions
from vibe3.services.execution_pipeline import ExecutionRequest, run_execution_pipeline
from vibe3.services.handoff_recorder_unified import (
    HandoffRecord,
    record_handoff_unified,
)

ExecutionRole = Literal["planner", "executor", "reviewer"]


@dataclass
class CodeagentCommand:
    """Configuration for a codeagent command execution.

    This is the unified input for all codeagent-based commands.
    """

    role: ExecutionRole
    context_builder: Callable[[], str]
    task: str | None = None
    dry_run: bool = False
    handoff_kind: str = "run"
    handoff_metadata: dict[str, Any] | None = None
    agent: str | None = None
    backend: str | None = None
    model: str | None = None
    config: VibeConfig | None = None
    branch: str | None = None


@dataclass
class CodeagentResult:
    """Result of codeagent execution."""

    success: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    handoff_file: Path | None = None
    session_id: str | None = None
    pid: int | None = None  # For async execution


class CodeagentExecutionService:
    """Unified service for codeagent execution.

    This service handles:
    1. Agent options resolution (config + CLI overrides)
    2. Synchronous execution
    3. Asynchronous execution with status tracking
    4. Handoff recording
    5. Flow state updates for async execution
    """

    def __init__(self, config: VibeConfig | None = None) -> None:
        """Initialize service.

        Args:
            config: VibeConfig instance (defaults to VibeConfig.get_defaults())
        """
        self.config = config or VibeConfig.get_defaults()

    def resolve_agent_options(
        self,
        section: Literal["plan", "run", "review"],
        agent: str | None = None,
        backend: str | None = None,
        model: str | None = None,
    ) -> AgentOptions:
        """Resolve agent options with CLI override support.

        Priority:
        1. CLI --agent: use agent preset (ignore config backend/model)
        2. CLI --backend/--model: use backend/model directly
        3. Config: use config backend/model if set, else agent preset

        Args:
            section: Config section (plan/run/review)
            agent: CLI --agent override
            backend: CLI --backend override
            model: CLI --model override

        Returns:
            Resolved AgentOptions

        Raises:
            ValueError: If no configuration found
        """
        target_config = getattr(self.config, section, None)
        config_agent = None
        config_backend = None
        config_model = None

        if target_config and hasattr(target_config, "agent_config"):
            ac = target_config.agent_config
            config_agent = getattr(ac, "agent", None)
            config_backend = getattr(ac, "backend", None)
            config_model = getattr(ac, "model", None)

        if agent:
            return AgentOptions(agent=agent, backend=None, model=None)

        if backend:
            return AgentOptions(
                agent=None, backend=backend, model=model or config_model
            )

        if config_agent:
            return AgentOptions(agent=config_agent, backend=None, model=None)

        if config_backend:
            return AgentOptions(agent=None, backend=config_backend, model=config_model)

        raise ValueError(
            f"No agent configuration found for '{section}' command. "
            f"Configure agent_config in settings.yaml or use CLI options."
        )

    def execute_sync(self, command: CodeagentCommand) -> CodeagentResult:
        """Execute codeagent synchronously.

        Args:
            command: Execution configuration

        Returns:
            CodeagentResult with execution output
        """
        log = logger.bind(
            domain="codeagent",
            role=command.role,
            handoff_kind=command.handoff_kind,
        )

        role_to_section: dict[ExecutionRole, Literal["plan", "run", "review"]] = {
            "planner": "plan",
            "executor": "run",
            "reviewer": "review",
        }
        options = self.resolve_agent_options(
            section=role_to_section[command.role],
            agent=command.agent,
            backend=command.backend,
            model=command.model,
        )

        request = ExecutionRequest(
            role=command.role,
            context_builder=command.context_builder,
            options_builder=lambda: options,
            task=command.task,
            dry_run=command.dry_run,
            handoff_kind=command.handoff_kind,
            handoff_metadata=command.handoff_metadata,
        )

        log.info("Starting sync execution")
        echo(f"-> Executing with {options.agent or options.backend}...")

        result = run_execution_pipeline(request)

        return CodeagentResult(
            success=result.agent_result.is_success(),
            exit_code=result.agent_result.exit_code,
            stdout=result.agent_result.stdout,
            stderr=result.agent_result.stderr,
            handoff_file=result.handoff_file,
            session_id=result.session_id,
        )

    def execute_async(
        self,
        command: CodeagentCommand,
        branch: str,
    ) -> CodeagentResult:
        """Execute codeagent asynchronously in background.

        Args:
            command: Execution configuration
            branch: Current branch for status tracking

        Returns:
            CodeagentResult with background process PID
        """
        from vibe3.services.async_execution_service import AsyncExecutionService

        log = logger.bind(
            domain="codeagent",
            role=command.role,
            branch=branch,
        )

        cli_command = self._build_cli_command(command)

        async_svc = AsyncExecutionService()
        pid = async_svc.start_async_execution(command.role, cli_command, branch)

        log.info("Started async execution", pid=pid)
        echo(
            f"[green]✓[/] {command.role.capitalize()} started in background (PID: {pid})"
        )
        echo("Use 'vibe3 flow show' to check status")

        return CodeagentResult(
            success=True,
            pid=pid,
        )

    def execute(
        self,
        command: CodeagentCommand,
        async_mode: bool = False,
    ) -> CodeagentResult:
        """Execute codeagent with automatic mode selection.

        Args:
            command: Execution configuration
            async_mode: Whether to run asynchronously

        Returns:
            CodeagentResult
        """
        if async_mode and not command.dry_run and command.branch:
            return self.execute_async(command, command.branch)
        return self.execute_sync(command)

    def _build_cli_command(self, command: CodeagentCommand) -> list[str]:
        """Build CLI command for async execution.

        Args:
            command: Execution configuration

        Returns:
            CLI command as list of strings
        """
        cmd = ["python", "-m", "vibe3"]

        if command.role == "planner":
            cmd.extend(["plan", "task"])
        elif command.role == "executor":
            cmd.append("run")
        elif command.role == "reviewer":
            cmd.extend(["review", "base"])

        if command.agent:
            cmd.extend(["--agent", command.agent])
        if command.backend:
            cmd.extend(["--backend", command.backend])
        if command.model:
            cmd.extend(["--model", command.model])
        if command.task:
            cmd.append(command.task)

        cmd.append("--no-async")
        return cmd


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
    config: VibeConfig | None = None,
    branch: str | None = None,
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
        config: VibeConfig instance
        branch: Current branch (for async execution)

    Returns:
        CodeagentCommand instance
    """
    kind_map: dict[ExecutionRole, str] = {
        "planner": "plan",
        "executor": "run",
        "reviewer": "review",
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
        config=config,
        branch=branch,
    )
