"""Sync codeagent execution utilities for plan/review/run commands."""

import os
from pathlib import Path
from typing import Literal, Sequence

from loguru import logger
from typer import echo

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.agents.execution_lifecycle import persist_execution_lifecycle_event
from vibe3.agents.models import (
    CodeagentCommand,
    CodeagentResult,
    ExecutionRole,
    create_codeagent_command,
)
from vibe3.agents.review_runner import format_agent_actor
from vibe3.agents.session_service import load_session_id
from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.models.review_runner import AgentOptions
from vibe3.services.handoff_recorder_unified import (
    HandoffRecord,
    record_handoff_unified,
)

# Re-export models for backward compatibility.
__all__ = [
    "ExecutionRole",
    "CodeagentCommand",
    "CodeagentResult",
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
        session_id = load_session_id(command.role)
        actor = format_agent_actor(options)
        is_async_child = os.environ.get("VIBE3_ASYNC_CHILD") == "1"
        branch = command.branch
        store = None
        if not command.dry_run and branch:
            try:
                store = SQLiteClient()
            except Exception as exc:  # pragma: no cover - defensive
                log.warning(f"Failed to initialize lifecycle store: {exc}")

        if branch and store and not is_async_child:
            persist_execution_lifecycle_event(
                store,
                branch,
                command.role,
                "started",
                actor,
                f"{command.role.capitalize()} started (status: running)",
                session_id=session_id,
            )

        log.info("Starting sync execution")
        prompt_content = command.context_builder()
        execution_cwd = self._resolve_command_cwd(command.cwd)
        echo(f"-> Executing with {options.agent or options.backend}...")

        try:
            agent_result = CodeagentBackend().run(
                prompt=prompt_content,
                options=options,
                task=command.task,
                dry_run=command.dry_run,
                session_id=session_id,
                cwd=execution_cwd,
            )
            if command.dry_run:
                return CodeagentResult(
                    success=True,
                    exit_code=agent_result.exit_code,
                    stdout=agent_result.stdout,
                    stderr=agent_result.stderr,
                    session_id=agent_result.session_id or session_id,
                )

            effective_session_id = agent_result.session_id or session_id
            handoff_file = record_handoff_unified(
                HandoffRecord(
                    kind=command.handoff_kind,  # type: ignore[arg-type]
                    content=agent_result.stdout,
                    options=options,
                    session_id=effective_session_id,
                    metadata=command.handoff_metadata,
                    branch=command.branch,
                )
            )
            if handoff_file:
                echo(f"-> {command.handoff_kind.capitalize()} saved: {handoff_file}")

            if branch and store and not is_async_child:
                persist_execution_lifecycle_event(
                    store,
                    branch,
                    command.role,
                    "completed",
                    actor,
                    f"{command.role.capitalize()} completed (status: done)",
                    session_id=effective_session_id,
                    refs={"status": "completed"},
                )

            return CodeagentResult(
                success=agent_result.is_success(),
                exit_code=agent_result.exit_code,
                stdout=agent_result.stdout,
                stderr=agent_result.stderr,
                handoff_file=handoff_file,
                session_id=effective_session_id,
            )
        except BaseException as exc:
            if branch and store and not is_async_child:
                abort_msg = (
                    f"{command.role.capitalize()} aborted "
                    f"(status: aborted, reason: {exc})"
                )
                persist_execution_lifecycle_event(
                    store,
                    branch,
                    command.role,
                    "aborted",
                    actor,
                    abort_msg,
                    session_id=session_id,
                    refs={"reason": str(exc), "status": "aborted"},
                )
            raise

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
        saw_no_async_flag = False
        for arg in args:
            if arg == "--async":
                continue
            if arg == "--no-async":
                saw_no_async_flag = True
            cmd.append(arg)
        if not saw_no_async_flag:
            cmd.append("--no-async")
        return cmd
