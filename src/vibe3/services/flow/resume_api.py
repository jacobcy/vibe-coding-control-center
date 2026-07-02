"""Manual and auto resume APIs for blocked flows.

This module provides type-safe APIs for resuming blocked flows:
- manual_resume: Human-authorized clearance with actor and reason tracking
- evaluate_auto_resume: Observer-only eligibility check (no mutations)
- apply_auto_resume: Apply eligibility decision to unblock flow
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients import GitHubClient
from vibe3.models import FlowStateProjection, IssueState
from vibe3.services.flow.blocked_state_io import BlockedStateIO
from vibe3.services.flow.transition_recorder import TransitionRecorder
from vibe3.services.shared import DependencyResolutionService
from vibe3.services.shared.label_service import LabelService

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient


class ResumeSource(StrEnum):
    """Source of resume operation."""

    MANUAL_COMMAND = "manual_command"
    AUTO_EVALUATOR = "auto_evaluator"


class AutoResumeRejectedCode(StrEnum):
    """Reason why auto-resume is not eligible."""

    HUMAN_REASON_PRESENT = "human_reason_present"
    DEPENDENCY_OPEN = "dependency_open"
    TRUTH_UNREADABLE = "truth_unreadable"
    NOT_BLOCKED = "not_blocked"


@dataclass(frozen=True)
class AutoResumeDecision:
    """Result of auto-resume eligibility evaluation.

    This is a snapshot decision - it must be applied immediately or re-evaluated.
    """

    eligible: bool
    issue_number: int
    branch: str
    rejected_code: AutoResumeRejectedCode | None = None
    closed_dependency_ids: tuple[int, ...] = ()
    truth_snapshot: str = ""  # MD5 hash of issue body at evaluation time
    reason_detail: str = ""


@dataclass(frozen=True)
class ResumeResult:
    """Result of a resume operation (manual or auto)."""

    target_state: IssueState | None
    success: bool
    detail: str


def manual_resume(
    issue_number: int,
    branch: str,
    target_state: IssueState,
    actor: str,
    reason: str,
    *,
    github_client: GitHubClient | None = None,
    label_service: LabelService | None = None,
    store: SQLiteClient | None = None,
) -> ResumeResult:
    """Manually resume a blocked flow with human authorization.

    This function:
    1. Reads GitHub issue body and state label truth
    2. Checks ALL blocked_by deps (fail-closed if unreadable/unresolved)
    3. Sets blocked_reason = None in body projection
    4. Writes label to target_state with transition_recorder
    5. Emits ManualResumeRequested and ManualBlockedReasonCleared events

    Note: --force parameter is not part of this scope (future issue).
    """
    from vibe3.observability import DegradedModeReason, get_degraded_manager
    from vibe3.services.issue.body import parse_projection

    # Initialize IO
    io = BlockedStateIO(
        github_client=github_client,
        label_service=label_service,
        store=store,
    )
    transition_recorder = TransitionRecorder(store) if store else None

    # 1. Read Remote Truth
    try:
        body = io.github.get_issue_body(issue_number)
        if body is None:
            return ResumeResult(
                target_state=None,
                success=False,
                detail=f"Issue #{issue_number} body is None",
            )
        truth = parse_projection(body)
        get_degraded_manager().exit_degraded_mode()
    except Exception as exc:
        get_degraded_manager().enter_degraded_mode(DegradedModeReason.GITHUB_API_ERROR)
        logger.bind(
            domain="resume_api",
            action="manual_resume",
            issue_number=issue_number,
            error=str(exc),
        ).error("Failed to read GitHub truth")
        return ResumeResult(
            target_state=None,
            success=False,
            detail=f"GitHub API error: {exc}",
        )

    # 2. Check if currently blocked
    current_state = io.read_issue_state(issue_number)
    if current_state != IssueState.BLOCKED:
        return ResumeResult(
            target_state=None,
            success=False,
            detail=f"Issue is not blocked (current state: {current_state})",
        )

    # 3. Check dependencies (fail-closed)
    open_tasks: list[int] = []
    for task in truth.blocked_by:
        res = DependencyResolutionService.is_dependency_resolved(
            task,
            github_client=io.github,
        )
        if not res.resolved:
            open_tasks.append(task)

    if open_tasks:
        return ResumeResult(
            target_state=None,
            success=False,
            detail=f"Open dependencies remain: {open_tasks}",
        )

    # 4. Check transition budget
    if (
        branch
        and transition_recorder is not None
        and transition_recorder.would_exceed(
            branch,
            IssueState.BLOCKED.to_label(),
            target_state.to_label(),
        )
    ):
        return ResumeResult(
            target_state=None,
            success=False,
            detail="Transition budget exceeded",
        )

    # 5. Clear blocked_reason and write target label
    new_proj = FlowStateProjection(
        state="active",
        blocked_by=[],
        blocked_reason=None,
    )
    io.write_projection(issue_number, new_proj)

    write_result = io.write_label_state(
        issue_number,
        target_state,
        actor=actor,
        force=True,
        normalize=True,
    )

    if write_result not in {"advanced", "normalized"}:
        return ResumeResult(
            target_state=None,
            success=False,
            detail=f"Label write failed: {write_result}",
        )

    # 6. Record transition
    if branch and transition_recorder is not None:
        transition_recorder.record_confirmed(
            branch=branch,
            from_state=IssueState.BLOCKED.to_label(),
            to_state=target_state.to_label(),
            actor=actor,
            issue_number=issue_number,
        )

    # 7. Rebuild cache
    if branch and store:
        store.update_flow_state(
            branch,
            flow_status="active",
            blocked_reason=None,
            blocked_by_issue=None,
            latest_actor=actor,
        )
        # Clear dependency links
        current_deps = store.get_dependency_links(branch)
        for dep in current_deps:
            store.remove_issue_link(branch, dep, "dependency")

    # 8. Emit events
    logger.bind(
        domain="resume_api",
        action="manual_resume",
        issue_number=issue_number,
        branch=branch,
        target_state=target_state.value,
        actor=actor,
    ).info("Manual resume completed")

    return ResumeResult(
        target_state=target_state,
        success=True,
        detail=f"Resumed to {target_state.value}",
    )


def evaluate_auto_resume(
    issue_number: int,
    branch: str,
    *,
    github_client: GitHubClient | None = None,
) -> AutoResumeDecision:
    """Evaluate if a blocked flow is eligible for auto-resume.

    This function is OBSERVER-ONLY:
    - Never mutates state
    - Never writes to GitHub or DB
    - Returns a snapshot decision with truth hash

    Eligibility criteria:
    1. Issue must be in blocked state
    2. blocked_reason must be empty (no human reason)
    3. ALL blocked_by dependencies must be closed/resolved
    """
    from vibe3.observability import DegradedModeReason, get_degraded_manager
    from vibe3.services.issue.body import parse_projection

    # Initialize IO (read-only)
    io = BlockedStateIO(
        github_client=github_client,
        label_service=None,
        store=None,
    )

    # 1. Read Remote Truth (fail-closed)
    try:
        body = io.github.get_issue_body(issue_number)
        if body is None:
            return AutoResumeDecision(
                eligible=False,
                issue_number=issue_number,
                branch=branch,
                rejected_code=AutoResumeRejectedCode.TRUTH_UNREADABLE,
                reason_detail=f"Issue #{issue_number} body is None",
            )
        truth = parse_projection(body)
        get_degraded_manager().exit_degraded_mode()
    except Exception as exc:
        get_degraded_manager().enter_degraded_mode(DegradedModeReason.GITHUB_API_ERROR)
        logger.bind(
            domain="resume_api",
            action="evaluate_auto_resume",
            issue_number=issue_number,
            error=str(exc),
        ).warning("GitHub read failed")
        return AutoResumeDecision(
            eligible=False,
            issue_number=issue_number,
            branch=branch,
            rejected_code=AutoResumeRejectedCode.TRUTH_UNREADABLE,
            reason_detail=f"GitHub API error: {exc}",
        )

    # 2. Check if currently blocked
    current_state = io.read_issue_state(issue_number)
    if current_state != IssueState.BLOCKED:
        return AutoResumeDecision(
            eligible=False,
            issue_number=issue_number,
            branch=branch,
            rejected_code=AutoResumeRejectedCode.NOT_BLOCKED,
            reason_detail=f"Current state: {current_state}",
        )

    # 3. Check for human reason
    if truth.blocked_reason:
        return AutoResumeDecision(
            eligible=False,
            issue_number=issue_number,
            branch=branch,
            rejected_code=AutoResumeRejectedCode.HUMAN_REASON_PRESENT,
            reason_detail=f"Human reason present: {truth.blocked_reason}",
        )

    # 4. Check dependencies
    open_tasks: list[int] = []
    closed_tasks: list[int] = []
    for task in truth.blocked_by:
        res = DependencyResolutionService.is_dependency_resolved(
            task,
            github_client=io.github,
        )
        if res.resolved:
            closed_tasks.append(task)
        else:
            open_tasks.append(task)

    if open_tasks:
        return AutoResumeDecision(
            eligible=False,
            issue_number=issue_number,
            branch=branch,
            rejected_code=AutoResumeRejectedCode.DEPENDENCY_OPEN,
            reason_detail=f"Open dependencies: {open_tasks}",
        )

    # 5. All checks passed - eligible
    # Create truth snapshot (MD5 hash)
    truth_hash = hashlib.md5(body.encode()).hexdigest()

    return AutoResumeDecision(
        eligible=True,
        issue_number=issue_number,
        branch=branch,
        closed_dependency_ids=tuple(closed_tasks),
        truth_snapshot=truth_hash,
        reason_detail="All dependencies closed, no human reason",
    )


def apply_auto_resume(
    decision: AutoResumeDecision,
    *,
    github_client: GitHubClient | None = None,
    label_service: LabelService | None = None,
    store: SQLiteClient | None = None,
) -> ResumeResult:
    """Apply an auto-resume eligibility decision.

    This function:
    1. Verifies truth_snapshot still matches current body (reject if stale)
    2. Determines target state (handoff for existing flow, ready otherwise)
    3. Writes projection with cleared blocked_by + active state
    4. Writes target label with transition_recorder
    5. Emits AutoResumeEligible event

    Note: Does NOT set blocked_reason (it should already be None per eligibility).
    """

    if not decision.eligible:
        return ResumeResult(
            target_state=None,
            success=False,
            detail="Decision is not eligible",
        )

    # Initialize IO
    io = BlockedStateIO(
        github_client=github_client,
        label_service=label_service,
        store=store,
    )
    transition_recorder = TransitionRecorder(store) if store else None

    # 1. Verify truth snapshot
    try:
        body = io.github.get_issue_body(decision.issue_number)
        if body is None:
            return ResumeResult(
                target_state=None,
                success=False,
                detail=f"Issue #{decision.issue_number} body is None",
            )
        current_hash = hashlib.md5(body.encode()).hexdigest()
        if current_hash != decision.truth_snapshot:
            return ResumeResult(
                target_state=None,
                success=False,
                detail="Truth snapshot is stale - body has changed",
            )
    except Exception as exc:
        logger.bind(
            domain="resume_api",
            action="apply_auto_resume",
            issue_number=decision.issue_number,
            error=str(exc),
        ).error("Failed to verify truth snapshot")
        return ResumeResult(
            target_state=None,
            success=False,
            detail=f"GitHub API error: {exc}",
        )

    # 2. Determine target state
    # Use existing flow → handoff, otherwise → ready
    target_state = IssueState.READY
    if decision.branch and store:
        fs_dict = store.get_flow_state(decision.branch)
        if fs_dict:
            # Has existing flow scene → handoff
            target_state = IssueState.HANDOFF

    # 3. Check transition budget
    if (
        decision.branch
        and transition_recorder is not None
        and transition_recorder.would_exceed(
            decision.branch,
            IssueState.BLOCKED.to_label(),
            target_state.to_label(),
        )
    ):
        return ResumeResult(
            target_state=None,
            success=False,
            detail="Transition budget exceeded",
        )

    # 4. Write projection and label
    new_proj = FlowStateProjection(
        state="active",
        blocked_by=[],
        blocked_reason=None,  # Should already be None per eligibility
    )
    io.write_projection(decision.issue_number, new_proj)

    write_result = io.write_label_state(
        decision.issue_number,
        target_state,
        actor="system:auto-resume",
        force=True,
        normalize=True,
    )

    if write_result not in {"advanced", "normalized"}:
        return ResumeResult(
            target_state=None,
            success=False,
            detail=f"Label write failed: {write_result}",
        )

    # 5. Record transition
    if decision.branch and transition_recorder is not None:
        transition_recorder.record_confirmed(
            branch=decision.branch,
            from_state=IssueState.BLOCKED.to_label(),
            to_state=target_state.to_label(),
            actor="system:auto-resume",
            issue_number=decision.issue_number,
        )

    # 6. Rebuild cache
    if decision.branch and store:
        store.update_flow_state(
            decision.branch,
            flow_status="active",
            blocked_reason=None,
            blocked_by_issue=None,
            latest_actor="system:auto-resume",
        )
        # Clear dependency links
        current_deps = store.get_dependency_links(decision.branch)
        for dep in current_deps:
            store.remove_issue_link(decision.branch, dep, "dependency")

    # 7. Emit event
    logger.bind(
        domain="resume_api",
        action="apply_auto_resume",
        issue_number=decision.issue_number,
        branch=decision.branch,
        target_state=target_state.value,
    ).info("Auto resume applied")

    return ResumeResult(
        target_state=target_state,
        success=True,
        detail=f"Auto-resumed to {target_state.value}",
    )
