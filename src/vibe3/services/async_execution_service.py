"""Compatibility wrapper for async execution lifecycle persistence.

Async tmux/session/log mechanics now live in the codeagent wrapper adapter.
This service remains as a thin compatibility layer for callers/tests that
expect branch-scoped lifecycle persistence.
"""

import os
from typing import Literal

from loguru import logger

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.services.execution_lifecycle import (
    ExecutionLifecycleEvent,
    persist_execution_lifecycle_event,
)

ExecutionRole = Literal["planner", "executor", "reviewer"]
ExecutionStatus = Literal["pending", "running", "done", "crashed"]


class AsyncExecutionService:
    """Compatibility service for managing async execution lifecycle."""

    def __init__(
        self,
        store: SQLiteClient | None = None,
        backend: CodeagentBackend | None = None,
    ) -> None:
        self.store = store or SQLiteClient()
        self._backend = backend or CodeagentBackend()

    def start_async_execution(
        self,
        role: ExecutionRole,
        command: list[str],
        branch: str,
        env: dict[str, str] | None = None,
    ) -> int:
        """Start background execution via the lower-level wrapper adapter."""
        execution_name = f"vibe3-{role}-{branch}"
        handle = self._backend.start_async_command(
            command,
            execution_name=execution_name,
            env=env,
        )

        persist_execution_lifecycle_event(
            self.store,
            branch,
            role,
            "started",
            "system",
            detail=(
                f"Started async {role} in tmux session: {handle.tmux_session}\n"
                f"Log: {handle.log_path}"
            ),
            refs={
                "tmux_session": handle.tmux_session,
                "log_path": str(handle.log_path),
            },
        )

        logger.bind(
            domain="async_execution",
            role=role,
            branch=branch,
            session=handle.tmux_session,
            log_path=str(handle.log_path),
        ).info(f"Started async {role} in tmux")

        return 0

    def check_execution_status(self, pid: int) -> ExecutionStatus:
        try:
            os.kill(pid, 0)
            return "running"
        except OSError:
            return "done"

    def complete_execution(
        self,
        role: ExecutionRole,
        branch: str,
        success: bool = True,
    ) -> None:
        lifecycle: ExecutionLifecycleEvent = "completed" if success else "aborted"
        status: ExecutionStatus = "done" if success else "crashed"
        persist_execution_lifecycle_event(
            self.store,
            branch,
            role,
            lifecycle,
            "system",
            detail=f"{role} finished with status: {status}",
            refs={"status": status},
        )

        logger.bind(
            domain="async_execution",
            role=role,
            branch=branch,
            status=status,
        ).info(f"{role} completed")
