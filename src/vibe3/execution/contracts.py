"""Execution contracts for unifying role execution."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Protocol

from vibe3.execution.role_contracts import WorktreeRequirement

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


@dataclass
class ExecutionRequest:
    """Request to launch a role execution."""

    role: str
    target_branch: str
    target_id: int
    execution_name: str
    cmd: Optional[List[str]] = None
    prompt: Optional[str] = None
    options: Optional[Any] = None
    cwd: Optional[str] = None
    repo_path: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    refs: Dict[str, str] = field(default_factory=dict)
    actor: str = "orchestra:system"
    mode: Literal["sync", "async"] = "async"
    dry_run: bool = False
    show_prompt: bool = False
    include_global_notice: bool = True
    fallback_prompt: Optional[str] = None
    fallback_include_global_notice: bool = True
    dry_run_summary: Dict[str, Any] = field(default_factory=dict)
    worktree_requirement: WorktreeRequirement = WorktreeRequirement.NONE
    tick_id: int = 0  # Heartbeat tick number for error tracking


@dataclass
class ExecutionLaunchResult:
    """Result of an execution launch attempt."""

    launched: bool
    skipped: bool = False
    session_id: Optional[str] = None
    tmux_session: Optional[str] = None
    log_path: Optional[str] = None
    stdout: Optional[str] = None  # Only populated for sync mode
    reason: Optional[str] = None
    reason_code: Optional[str] = None
    error_recorded: bool = False  # True if runner already recorded specific error
