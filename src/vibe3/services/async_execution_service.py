"""Async execution service for plan/review/run commands.

This module provides functionality for running agent commands asynchronously
in background processes, with status tracking in flow state.
"""

import os
import subprocess
import threading
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
        """Start background execution of a command.

        Args:
            role: Execution role (planner/executor/reviewer)
            command: Command to execute
            branch: Current branch name
            env: Environment variables for the child process

        Returns:
            Process ID of the background process
        """
        process = subprocess.Popen(
            command,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.getcwd(),
            env=env,
        )

        persist_execution_lifecycle_event(
            self.store,
            branch,
            role,
            "started",
            "system",
            detail=f"Started async {role}",
            extra_state_updates={"execution_pid": process.pid},
        )

        self._start_completion_watcher(process, role, branch)

        logger.bind(
            domain="async_execution",
            role=role,
            branch=branch,
            pid=process.pid,
        ).info(f"Started async {role}")

        return process.pid

    def _start_completion_watcher(
        self,
        process: subprocess.Popen,
        role: ExecutionRole,
        branch: str,
    ) -> None:
        """Spawn background watcher to mark completion."""
        watcher = threading.Thread(
            target=self._wait_for_process,
            args=(process, role, branch),
            daemon=True,
        )
        watcher.start()

    def _wait_for_process(
        self,
        process: subprocess.Popen,
        role: ExecutionRole,
        branch: str,
    ) -> None:
        """Wait for process exit and mark completion."""
        try:
            exit_code = process.wait()
            success = exit_code == 0
        except Exception as exc:  # pragma: no cover - defensive path
            logger.bind(
                domain="async_execution",
                role=role,
                branch=branch,
            ).exception(f"Async {role} wait failed: {exc}")
            self.complete_execution(role, branch, success=False)
            return

        self.complete_execution(role, branch, success=success)

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
        """Cancel a running background execution.

        Args:
            role: Execution role (planner/executor/reviewer)
            branch: Branch name

        Returns:
            True if process was killed, False if not running
        """
        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            return False

        pid = flow_data.get("execution_pid")
        if not pid:
            return False

        current_status = flow_data.get(f"{role}_status")
        if current_status != "running":
            return False

        try:
            os.killpg(os.getpgid(pid), 15)
        except (OSError, ProcessLookupError):
            pass

        persist_execution_lifecycle_event(
            self.store,
            branch,
            role,
            "aborted",
            "system",
            detail=f"{role} was manually cancelled",
            refs={"reason": "cancelled"},
        )

        logger.bind(
            domain="async_execution",
            role=role,
            branch=branch,
            pid=pid,
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


def build_async_command(
    base_command: list[str],
    role: ExecutionRole,
    branch: str,
) -> list[str]:
    """Build command for async execution with completion callback.

    Args:
        base_command: Original command (e.g., ["vibe3", "review", "base"])
        role: Execution role
        branch: Branch name

    Returns:
        Full command including completion callback
    """
    async_flag = "--no-async"
    if async_flag not in base_command:
        base_command.append(async_flag)

    complete_cmd = [
        "python",
        "-m",
        "vibe3",
        "_complete_execution",
        role,
        branch,
    ]

    wrapped_command = base_command + ["&&"] + complete_cmd

    return wrapped_command
