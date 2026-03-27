"""Unified codeagent execution service for plan/review/run commands."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

from loguru import logger
from typer import echo

from vibe3.config.settings import VibeConfig
from vibe3.models.review_runner import AgentOptions
from vibe3.services.execution_pipeline import ExecutionRequest, run_execution_pipeline

ExecutionRole = Literal["planner", "executor", "reviewer"]


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
    config: VibeConfig | None = None
    branch: str | None = None
    cli_args: list[str] | None = None


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


class CodeagentExecutionService:
    """Unified service for codeagent execution."""

    def __init__(self, config: VibeConfig | None = None) -> None:
        self.config = config or VibeConfig.get_defaults()

    def resolve_agent_options(
        self,
        section: Literal["plan", "run", "review"],
        agent: str | None = None,
        backend: str | None = None,
        model: str | None = None,
    ) -> AgentOptions:
        """Resolve agent options with CLI override support.

        Priority: CLI --agent > CLI --backend/--model > Config agent > Config backend
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
        """Execute codeagent synchronously."""
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
        """Execute codeagent asynchronously in background."""
        from vibe3.services.async_execution_service import AsyncExecutionService

        log = logger.bind(
            domain="codeagent",
            role=command.role,
            branch=branch,
        )

        cli_command = self._build_cli_command(command)

        async_svc = AsyncExecutionService()
        # Mark child so run_execution_pipeline skips lifecycle recording
        # (parent AsyncExecutionService owns lifecycle events).
        child_env = {**os.environ, "VIBE3_ASYNC_CHILD": "1"}
        pid = async_svc.start_async_execution(
            command.role, cli_command, branch, env=child_env
        )

        log.info("Started async execution", pid=pid)
        role_name = command.role.capitalize()
        echo(f"[green]✓[/] {role_name} started in background (PID: {pid})")
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
        """Execute codeagent with automatic mode selection."""
        if async_mode and not command.dry_run and command.branch:
            return self.execute_async(command, command.branch)
        return self.execute_sync(command)

    def _build_cli_command(self, command: CodeagentCommand) -> list[str]:
        """Build CLI command for async execution.

        Priority:
        1. Explicit CLI args from command builder
        2. Current process argv (strip --async)
        3. Fallback role-based defaults for non-CLI callers
        """
        if command.cli_args:
            return self.build_self_invocation(command.cli_args)

        current_argv = list(sys.argv[1:]) if len(sys.argv) > 1 else []
        if current_argv:
            return self.build_self_invocation(current_argv)

        return self._build_fallback_cli_command(command)

    @staticmethod
    def build_self_invocation(args: Sequence[str]) -> list[str]:
        """Build `uv run python src/vibe3/cli.py ...` invocation and strip --async."""
        cmd = ["uv", "run", "python", "src/vibe3/cli.py"]
        for arg in args:
            if arg == "--async":
                continue
            cmd.append(arg)
        return cmd

    @staticmethod
    def _build_fallback_cli_command(command: CodeagentCommand) -> list[str]:
        """Fallback async CLI command for non-CLI/internal call sites."""
        cmd = ["uv", "run", "python", "src/vibe3/cli.py"]

        role_default_args: dict[ExecutionRole, list[str]] = {
            "planner": ["plan", "task"],
            "executor": ["run"],
            "reviewer": ["review", "base"],
        }
        cmd.extend(role_default_args[command.role])

        if command.agent:
            cmd.extend(["--agent", command.agent])
        if command.backend:
            cmd.extend(["--backend", command.backend])
        if command.model:
            cmd.extend(["--model", command.model])
        if command.task:
            cmd.append(command.task)
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
    cli_args: list[str] | None = None,
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
        cli_args: Optional explicit CLI args used for async self-invocation

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
        cli_args=cli_args,
    )
