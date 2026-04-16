"""Execution contracts for unifying role execution."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from vibe3.execution.role_contracts import CompletionContract, WorktreeRequirement


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
    worktree_requirement: WorktreeRequirement = WorktreeRequirement.NONE
    completion_gate: Optional[CompletionContract] = None


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
