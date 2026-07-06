"""Shared flow/worktree/ref consistency checks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from vibe3.services.shared.paths import check_ref_exists


class FlowConsistencyCode(StrEnum):
    """Machine-readable consistency failure codes."""

    OK = "ok"
    MISSING_WORKTREE = "missing_worktree"
    MISSING_RECORDED_WORKTREE = "missing_recorded_worktree"
    # A recorded spec/plan/report/audit whose file disappeared while the
    # worktree stayed healthy. This is a repair blocker (FR-011), NOT
    # physical scene damage — the flow waits for explicit rebind/regeneration
    # and is never auto-rebuilt (spec 012 US2, SC-002).
    MISSING_ARTIFACT = "missing_artifact"
    MISSING_REF = "missing_ref"


@dataclass(frozen=True)
class FlowConsistencyResult:
    """Result of shared structural consistency detection.

    Classification:
    - needs_rebuild: physical scene must be destroyed and recreated
    - fix_action: cheap local fix (e.g. backfill DB field), no rebuild needed
    - both False: scene is consistent
    """

    needs_rebuild: bool
    code: FlowConsistencyCode = FlowConsistencyCode.OK
    reason: str = ""
    severity: str = ""
    ref_field: str | None = None
    ref_value: str | None = None
    fix_action: str | None = None
    worktree_path: str | None = None


def check_flow_consistency(
    branch: str,
    flow_state: Mapping[str, Any],
    *,
    git_client: Any,
) -> FlowConsistencyResult:
    """Check whether a flow scene is structurally consistent.

    Classification:
    - MISSING_WORKTREE: physical worktree gone -> needs full rebuild
    - MISSING_RECORDED_WORKTREE: worktree exists but DB out of sync -> cheap fix
    - MISSING_ARTIFACT: a recorded spec/plan/report/audit file disappeared in
      an otherwise healthy worktree -> artifact repair blocker (NOT rebuild)
    - OK: scene is consistent
    """
    worktree_path = git_client.find_worktree_path_for_branch(branch)
    if worktree_path is None:
        # Placeholder flow: blocked + no git branch is a legal state
        if flow_state.get("flow_status") == "blocked" and not git_client.branch_exists(
            branch
        ):
            return FlowConsistencyResult(needs_rebuild=False)
        return FlowConsistencyResult(
            needs_rebuild=True,
            code=FlowConsistencyCode.MISSING_WORKTREE,
            reason=f"Worktree does not exist for branch '{branch}'",
            severity="critical",
        )

    if branch.startswith("task/issue-") and not flow_state.get("worktree_path"):
        # Worktree physically exists but DB doesn't know about it.
        # This is a cheap fix: just backfill the DB field.
        return FlowConsistencyResult(
            needs_rebuild=False,
            code=FlowConsistencyCode.MISSING_RECORDED_WORKTREE,
            reason="Worktree exists but is not recorded in flow_state",
            severity="low",
            fix_action="backfill_worktree_path",
            worktree_path=str(worktree_path),
        )

    # FR-010: spec_ref shares one resolution contract with plan/report/audit
    # (no special-casing). Order matters only for the reported ref_field.
    for ref_field in ("spec_ref", "plan_ref", "report_ref", "audit_ref"):
        ref_value = flow_state.get(ref_field)
        if not ref_value:
            continue
        _, exists = check_ref_exists(
            str(ref_value),
            branch,
            git_client=git_client,
        )
        if not exists:
            # The worktree is healthy (verified above); a missing recorded
            # artifact is a repair blocker, NOT physical scene damage. The
            # flow waits for explicit rebind/regeneration (FR-011, SC-002).
            return FlowConsistencyResult(
                needs_rebuild=False,
                code=FlowConsistencyCode.MISSING_ARTIFACT,
                reason=f"{ref_field} file not found: {ref_value}",
                severity="high",
                ref_field=ref_field,
                ref_value=str(ref_value),
            )

    return FlowConsistencyResult(needs_rebuild=False)


def apply_consistency_fix(
    result: FlowConsistencyResult,
    branch: str,
    *,
    store: Any,
) -> bool:
    """Apply a cheap fix identified by check_flow_consistency.

    Returns True if fix was applied, False if no fix applicable.
    """
    if result.fix_action == "backfill_worktree_path" and result.worktree_path:
        store.update_flow_state(branch, worktree_path=result.worktree_path)
        return True
    return False
