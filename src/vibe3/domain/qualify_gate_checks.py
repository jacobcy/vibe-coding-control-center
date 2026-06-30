"""Worktree and dependency checks for qualify gate logic."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vibe3.domain.qualify_gate_support import _append_orchestra_event
from vibe3.services.flow import BlockedStateService
from vibe3.services.shared import LabelService

if TYPE_CHECKING:
    from vibe3.clients import GitHubClient, SQLiteClient
    from vibe3.models import CoordinationTruth, IssueInfo, OrchestraConfig


def check_worktree_health(
    *,
    issue: "IssueInfo",
    branch: str,
    truth: "CoordinationTruth",
    store: "SQLiteClient",
    github: "GitHubClient",
    config: "OrchestraConfig",
    path_cls: type[Path] = Path,
    subprocess_module: Any = subprocess,
    blocked_state_service_cls: type[Any] = BlockedStateService,
    label_service_cls: type[Any] = LabelService,
) -> bool:
    flow_state = store.get_flow_state(branch)
    if (
        flow_state
        and flow_state.get("flow_status") == "blocked"
        and not truth.worktree_path
    ):
        return True

    worktree_path = truth.worktree_path
    if not worktree_path or not isinstance(worktree_path, str):
        return True

    wt_path = path_cls(worktree_path)
    if not wt_path.exists():
        reason = f"Worktree path does not exist: {worktree_path}"
        blocked_state_service_cls(
            store=store,
            github_client=github,
            label_service=label_service_cls(repo=config.repo),
        ).set_block(
            branch=branch,
            reason=reason,
            actor="orchestra:dispatcher",
            issue_number=issue.number,
        )
        _append_orchestra_event(
            "dispatcher", f"qualify_gate skip #{issue.number}: {reason}"
        )
        return False

    try:
        result = subprocess_module.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(wt_path),
            capture_output=True,
            text=True,
            timeout=5,
        )
        actual_branch = result.stdout.strip()
        if actual_branch != branch:
            reason = f"Worktree branch mismatch: expected {branch}, got {actual_branch}"
            blocked_state_service_cls(
                store=store,
                github_client=github,
                label_service=label_service_cls(repo=config.repo),
            ).set_block(
                branch=branch,
                reason=reason,
                actor="orchestra:dispatcher",
                issue_number=issue.number,
            )
            _append_orchestra_event(
                "dispatcher", f"qualify_gate skip #{issue.number}: {reason}"
            )
            return False
    except Exception:
        pass
    return True
