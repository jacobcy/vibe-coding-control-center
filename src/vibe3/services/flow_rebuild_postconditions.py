"""Postcondition checks for destructive flow rebuilds."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def assert_rebuild_postconditions(
    *,
    branch: str,
    result: dict[str, Any] | None,
    ensure_worktree: bool,
    git_client: Any,
    store: Any,
) -> None:
    """Fail fast when rebuild did not produce a dispatchable scene."""
    failures: list[str] = []

    if not git_client.branch_exists(branch):
        failures.append(f"branch does not exist: {branch}")

    if ensure_worktree:
        worktree_path = git_client.find_worktree_path_for_branch(branch)
        if worktree_path is None:
            failures.append(f"git worktree not registered for branch: {branch}")
        else:
            resolved_path = Path(worktree_path)
            if not resolved_path.exists():
                failures.append(f"worktree path does not exist: {resolved_path}")

            result_path = (
                result.get("worktree_path") if isinstance(result, dict) else None
            )
            if result_path and Path(str(result_path)) != resolved_path:
                failures.append(
                    "bootstrap result worktree_path mismatch: "
                    f"{result_path} != {resolved_path}"
                )

            flow_state = store.get_flow_state(branch)
            recorded_path = (
                flow_state.get("worktree_path")
                if isinstance(flow_state, dict)
                else None
            )
            if recorded_path and Path(str(recorded_path)) != resolved_path:
                failures.append(
                    "flow_state worktree_path mismatch: "
                    f"{recorded_path} != {resolved_path}"
                )

    if failures:
        raise RuntimeError(
            f"Rebuild postcondition failed for {branch}: {'; '.join(failures)}"
        )
