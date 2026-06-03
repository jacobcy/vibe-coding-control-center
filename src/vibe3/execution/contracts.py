"""Execution contracts for unifying role execution."""

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

# Backward-compat re-exports — moved to models.execution_request
from vibe3.models.execution_request import (  # noqa: F401
    ExecutionLaunchResult,
    ExecutionRequest,
)
from vibe3.models.worktree import WorktreeRequirement  # noqa: F401

if TYPE_CHECKING:
    from vibe3.agents.backends.async_launcher import AsyncExecutionHandle


class AsyncLauncherProtocol(Protocol):
    """Protocol for async command launcher function."""

    def __call__(
        self,
        command: list[str],
        *,
        execution_name: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        keep_alive_seconds: int = 0,
    ) -> "AsyncExecutionHandle": ...


_StartAsyncFactory = AsyncLauncherProtocol
