"""Sync codeagent execution utilities for command-mode role entrypoints."""

import os
from pathlib import Path
from typing import Literal

from loguru import logger
from typer import echo

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.agents.models import (
    CodeagentCommand,
    CodeagentResult,
    ExecutionRole,
    create_codeagent_command,
)
from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.execution.actor_support import format_agent_actor
from vibe3.execution.codeagent_support import resolve_command_agent_options
from vibe3.execution.execution_lifecycle import persist_execution_lifecycle_event
from vibe3.execution.session_service import load_session_id
from vibe3.services.handoff_recorder_unified import (
    HandoffRecord,
    record_handoff_unified,
)

__all__ = [
    "ExecutionRole",
    "CodeagentCommand",
    "CodeagentResult",
    "create_codeagent_command",
    "CodeagentExecutionService",
]


class CodeagentExecutionService:
    """Unified sync execution shell for command-mode codeagent runs."""

    def __init__(self, config: VibeConfig | None = None) -> None:
        self.config = config or VibeConfig.get_defaults()

    @staticmethod
    def _resolve_command_cwd(explicit_cwd: Path | None) -> Path:
        if explicit_cwd is not None:
            return explicit_cwd
        try:
            return Path(GitClient().get_worktree_root())
        except Exception:
            return Path.cwd()

    def execute_sync(self, command: CodeagentCommand) -> CodeagentResult:
        """Execute codeagent synchronously."""
        log = logger.bind(
            domain="codeagent",
            role=command.role,
            handoff_kind=command.handoff_kind,
        )

        role_to_section: dict[str, Literal["plan", "run", "review"]] = {
            "planner": "plan",
            "executor": "run",
            "reviewer": "review",
        }
        options = resolve_command_agent_options(
            config=self.config,
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
            except Exception as exc:  # pragma: no cover
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
