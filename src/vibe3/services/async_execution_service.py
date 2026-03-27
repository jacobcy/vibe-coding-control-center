"""Async execution service for plan/review/run commands.

This module provides functionality for running agent commands asynchronously
in background processes, with status tracking in flow state.
"""

import os
import subprocess
from typing import Literal

from loguru import logger

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.services.execution_lifecycle import (
    ExecutionLifecycleEvent,
    persist_execution_lifecycle_event,
)

ExecutionRole = Literal["planner", "executor", "reviewer"]
ExecutionStatus = Literal["pending", "running", "done", "crashed"]


class AsyncExecutionService:
    """Service for managing async execution of agent commands."""

    def __init__(self, store: SQLiteClient | None = None) -> None:
        """Initialize async execution service.

        Args:
            store: SQLiteClient instance for persistence
        """
        self.store = store or SQLiteClient()

    def start_async_execution(
        self,
        role: ExecutionRole,
        command: list[str],
        branch: str,
        env: dict[str, str] | None = None,
    ) -> int:
        """Start background execution of a command in a tmux session.

        Args:
            role: Execution role (planner/executor/reviewer)
            command: Command to execute
            branch: Current branch name
            env: Environment variables (ignored, tmux inherits parent env)

        Returns:
            Always returns 0 (tmux session name is the meaningful identifier).
        """
        session_name = f"vibe3-{role}-{branch}"[:50].replace("/", "-")

        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name, "--"] + command,
            check=True,
        )

        persist_execution_lifecycle_event(
            self.store,
            branch,
            role,
            "started",
            "system",
            detail=f"Started async {role} in tmux session: {session_name}",
        )

        logger.bind(
            domain="async_execution",
            role=role,
            branch=branch,
            session=session_name,
        ).info(f"Started async {role} in tmux")

        return 0

    def check_execution_status(self, pid: int) -> ExecutionStatus:
        """Check if a background process is still running.

        Args:
            pid: Process ID to check

        Returns:
            Execution status (running/done/crashed)
        """
        try:
            os.kill(pid, 0)
            return "running"
        except OSError:
            return "done"

    def cancel_execution(
        self,
        role: ExecutionRole,
        branch: str,
    ) -> bool:
        """Cancel a running async execution by killing its tmux session.

        Args:
            role: Execution role (planner/executor/reviewer)
            branch: Branch name

        Returns:
            True if session was killed, False if not found
        """
        session_name = f"vibe3-{role}-{branch}"[:50].replace("/", "-")

        try:
            subprocess.run(
                ["tmux", "kill-session", "-t", session_name],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            return False

        persist_execution_lifecycle_event(
            self.store,
            branch,
            role,
            "aborted",
            "system",
            detail=f"{role} cancelled (tmux session: {session_name})",
            refs={"reason": "cancelled"},
        )

        logger.bind(
            domain="async_execution",
            role=role,
            branch=branch,
            session=session_name,
        ).info(f"{role} cancelled")

        return True

    def complete_execution(
        self,
        role: ExecutionRole,
        branch: str,
        success: bool = True,
    ) -> None:
        """Mark execution as complete.

        Args:
            role: Execution role
            branch: Branch name
            success: Whether execution succeeded
        """
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
