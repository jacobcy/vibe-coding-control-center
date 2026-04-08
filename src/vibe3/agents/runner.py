"""Unified codeagent execution service for plan/review/run commands.

Migrated from vibe3.services.codeagent_execution_service.
"""

import os
import sys
from pathlib import Path
from typing import Callable, Literal, Sequence

from loguru import logger
from typer import echo

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.agents.models import (
    AgentSpec,
    CodeagentCommand,
    CodeagentResult,
    ExecutionRole,
    create_codeagent_command,
)
from vibe3.agents.pipeline import ExecutionRequest, run_execution_pipeline
from vibe3.agents.review_runner import format_agent_actor
from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.models.review_runner import AgentOptions
from vibe3.services.execution_lifecycle import persist_execution_lifecycle_event

# Re-export models for backward compatibility.
__all__ = [
    "ExecutionRole",
    "CodeagentCommand",
    "CodeagentResult",
    "AgentSpec",
    "create_codeagent_command",
    "CodeagentExecutionService",
]


class CodeagentExecutionService:
    """Unified service for codeagent execution."""

    def __init__(self, config: VibeConfig | None = None) -> None:
        self.config = config or VibeConfig.get_defaults()

    @staticmethod
    def _resolve_command_cwd(explicit_cwd: Path | None) -> Path:
        """Resolve command cwd to the current worktree root unless overridden."""
        if explicit_cwd is not None:
            return explicit_cwd
        try:
            return Path(GitClient().get_worktree_root())
        except Exception:
            return Path.cwd()

    def resolve_agent_options(
        self,
        section: Literal["plan", "run", "review"],
        agent: str | None = None,
        backend: str | None = None,
        model: str | None = None,
    ) -> AgentOptions:
        """Resolve agent options with CLI override support.

        ``agent`` and ``backend`` are both supported configuration entry points.
        If both are present, ``agent`` wins.

        - agent mode  : pass ``--agent <preset>`` to codeagent-wrapper.
                        The preset's backend/model are defined in models.json.
                        ``model`` is irrelevant and ignored in this mode.
        - backend mode: pass ``--backend <name>`` [``--model <name>``].
                        ``model`` is optional — omitting it lets the backend
                        use its own default from models.json.

        Resolution priority (first match wins):

        1. CLI ``--agent``   → agent mode,   model ignored
        2. CLI ``--backend`` → backend mode, CLI ``--model`` used if given
                               (config model is NOT inherited — be explicit)
                3. Config ``agent``  → agent mode,   model ignored
                4. Config ``backend``→ backend mode, config ``model`` used if present

                Important:
                - Backend-only configuration is valid.
                - ``model`` only matters when ``backend`` is configured.
                - When config contains both ``agent`` and ``backend/model``, this method
                    intentionally keeps ``agent`` as the execution source of truth.
        """
        target_config = getattr(self.config, section, None)
        config_agent = None
        config_backend = None
        config_model = None
        config_timeout = 1800

        if target_config and hasattr(target_config, "agent_config"):
            ac = target_config.agent_config
            config_agent = getattr(ac, "agent", None)
            config_backend = getattr(ac, "backend", None)
            config_model = getattr(ac, "model", None)
            config_timeout = getattr(ac, "timeout_seconds", 1800)

        # 1. CLI --agent: preset mode, model is managed by the preset itself
        if agent:
            return AgentOptions(
                agent=agent,
                timeout_seconds=config_timeout,
            )

        # 2. CLI --backend: backend mode, use CLI --model only (no config fallback)
        #    Rationale: user explicitly chose a backend override; if they wanted
        #    a specific model they would have passed --model too.
        if backend:
            return AgentOptions(
                backend=backend,
                model=model,
                timeout_seconds=config_timeout,
            )

        # 3. Config agent: preset mode
        if config_agent:
            return AgentOptions(
                agent=config_agent,
                timeout_seconds=config_timeout,
            )

        # 4. Config backend: backend mode, apply config model as the intended default
        if config_backend:
            return AgentOptions(
                backend=config_backend,
                model=config_model,
                timeout_seconds=config_timeout,
            )

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
            cwd=self._resolve_command_cwd(command.cwd),
            branch=command.branch,
        )

        log.info("Starting sync execution")

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
        log = logger.bind(
            domain="codeagent",
            role=command.role,
            branch=branch,
        )

        role_to_section: dict[ExecutionRole, Literal["plan", "run", "review"]] = {
            "planner": "plan",
            "executor": "run",
            "reviewer": "review",
        }
        backend = CodeagentBackend()
        options = self.resolve_agent_options(
            section=role_to_section[command.role],
            agent=command.agent,
            backend=command.backend,
            model=command.model,
        )
        cli_command = self._build_cli_command(command)
        execution_cwd = self._resolve_command_cwd(command.cwd)
        handle = backend.start_async_command(
            cli_command,
            execution_name=f"vibe3-{command.role}-{branch}",
            cwd=execution_cwd,
            env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
        )

        store = SQLiteClient()
        persist_execution_lifecycle_event(
            store,
            branch,
            command.role,
            "started",
            format_agent_actor(options),
            detail=(
                f"Started async {command.role} in tmux session: {handle.tmux_session}\n"
                f"Log: {handle.log_path}"
            ),
            refs={
                "tmux_session": handle.tmux_session,
                "log_path": str(handle.log_path),
            },
        )

        log.info(
            "Started async execution",
            tmux_session=handle.tmux_session,
            log_path=str(handle.log_path),
        )
        role_name = command.role.capitalize()
        echo(f"[green]✓[/] {role_name} started in background (PID: 0)")
        echo(f"Tmux session: {handle.tmux_session}")
        echo(f"Session log: {handle.log_path}")
        echo("Use 'vibe3 flow show' to check status")

        return CodeagentResult(
            success=True,
            pid=0,
            tmux_session=handle.tmux_session,
            log_path=handle.log_path,
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

    def execute_with_callbacks(
        self,
        command: CodeagentCommand,
        on_success: Callable[[CodeagentResult], None],
        on_failure: Callable[[Exception], None],
        async_mode: bool = False,
    ) -> CodeagentResult:
        """带回调的执行方法。

        执行 Agent 并在成功或失败时调用回调函数。回调异常会被捕获并记录，
        不会中断主流程。

        Args:
            command: 执行命令配置
            on_success: 成功回调（result.success == True）
            on_failure: 失败回调（异常或 result.success == False）
            async_mode: 是否异步执行

        Returns:
            执行结果

        Raises:
            Exception: 执行过程中的异常（on_failure 已处理后重新抛出）
        """
        try:
            result = self.execute(command, async_mode=async_mode)
            if result.success:
                try:
                    on_success(result)
                except Exception as e:
                    logger.error(f"on_success callback failed: {e}")
            else:
                try:
                    on_failure(Exception(result.stderr or "Execution failed"))
                except Exception as e:
                    logger.error(f"on_failure callback failed: {e}")
            return result
        except Exception as e:
            try:
                on_failure(e)
            except Exception as callback_error:
                logger.error(f"on_failure callback failed: {callback_error}")
            raise

    def _build_cli_command(self, command: CodeagentCommand) -> list[str]:
        """Build CLI command for async execution.

        Priority:
        1. Explicit CLI args from command builder
        2. Current process argv (strip --async)
        3. Fallback role-based defaults for non-CLI callers
        """
        if command.cli_args:
            return self.build_self_invocation(command.cli_args)

        if len(sys.argv) > 1:
            # sys.argv[0] must be cli.py or vibe3 (installed script)
            # to be safe for self-invocation.
            executable = sys.argv[0]
            if not (executable.endswith("cli.py") or executable.endswith("vibe3")):
                from vibe3.exceptions import UserError

                raise UserError(
                    f"Cannot safely build self-invocation from current executable: "
                    f"{executable}. Async execution requires running "
                    "via 'vibe3' or 'cli.py'."
                )
            return self.build_self_invocation(list(sys.argv[1:]))

        return self._build_fallback_cli_command(command)

    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

    @classmethod
    def _cli_entry(cls) -> str:
        return str(cls._repo_root() / "src" / "vibe3" / "cli.py")

    @classmethod
    def build_self_invocation(cls, args: Sequence[str]) -> list[str]:
        """Build baseline-project self-invocation for tmux child.

        The child process must execute synchronously inside tmux; otherwise
        default-async command modes would recursively try to spawn more tmux
        sessions.
        """
        cmd = [
            "uv",
            "run",
            "--project",
            str(cls._repo_root()),
            "python",
            cls._cli_entry(),
        ]
        saw_sync_flag = False
        for arg in args:
            if arg == "--async":
                continue
            if arg == "--sync":
                saw_sync_flag = True
            cmd.append(arg)
        if not saw_sync_flag:
            cmd.append("--sync")
        return cmd

    @classmethod
    def _build_fallback_cli_command(cls, command: CodeagentCommand) -> list[str]:
        """Fallback async CLI command for non-CLI/internal call sites."""
        cmd = [
            "uv",
            "run",
            "--project",
            str(cls._repo_root()),
            "python",
            cls._cli_entry(),
        ]

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
        cmd.append("--sync")
        return cmd
