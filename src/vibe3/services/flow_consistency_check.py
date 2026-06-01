"""Shared flow/worktree/ref consistency checks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from vibe3.services.path_helpers import check_ref_exists


class FlowConsistencyCode(StrEnum):
    """Machine-readable consistency failure codes."""

    OK = "ok"
    MISSING_WORKTREE = "missing_worktree"
    MISSING_RECORDED_WORKTREE = "missing_recorded_worktree"
    MISSING_REF = "missing_ref"


@dataclass(frozen=True)
class FlowConsistencyResult:
    """Result of shared structural consistency detection."""

    needs_rebuild: bool
    code: FlowConsistencyCode = FlowConsistencyCode.OK
    reason: str = ""
    severity: str = ""
    auto_rebuild: bool = False
    ref_field: str | None = None
    ref_value: str | None = None


def check_flow_consistency(
    branch: str,
    flow_state: Mapping[str, Any],
    *,
    git_client: Any,
) -> FlowConsistencyResult:
    """Check whether a flow scene is structurally rebuild-worthy.

    This is intentionally limited to local scene consistency: physical worktree,
    recorded worktree path, and artifact refs. Remote issue/PR semantics remain
    in CheckService and QualifyGate.
    """
    worktree_path = git_client.find_worktree_path_for_branch(branch)
    if worktree_path is None:
        return FlowConsistencyResult(
            needs_rebuild=True,
            code=FlowConsistencyCode.MISSING_WORKTREE,
            reason=f"Worktree does not exist for branch '{branch}'",
            severity="critical",
            auto_rebuild=True,
        )

    if branch.startswith("task/issue-") and not flow_state.get("worktree_path"):
        return FlowConsistencyResult(
            needs_rebuild=True,
            code=FlowConsistencyCode.MISSING_RECORDED_WORKTREE,
            reason="Worktree exists but is not recorded in flow_state",
            severity="critical",
            auto_rebuild=False,
        )

    for ref_field in ("plan_ref", "report_ref", "audit_ref"):
        ref_value = flow_state.get(ref_field)
        if not ref_value:
            continue
        _display_path, exists = check_ref_exists(
            str(ref_value),
            branch,
            git_client=git_client,
        )
        if not exists:
            return FlowConsistencyResult(
                needs_rebuild=True,
                code=FlowConsistencyCode.MISSING_REF,
                reason=f"{ref_field} file not found: {ref_value}",
                severity="critical",
                auto_rebuild=False,
                ref_field=ref_field,
                ref_value=str(ref_value),
            )

    return FlowConsistencyResult(needs_rebuild=False)
