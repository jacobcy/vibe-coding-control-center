"""Individual check rules extracted from _check_branch.

Each rule receives a CheckContext with shared state and returns
CheckResult if it handled the branch (short-circuit), or None to
continue to the next rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from loguru import logger

from vibe3.models import IssueState, PRState
from vibe3.services.check.remote import is_empty_auto_scene
from vibe3.services.check.state_label_recovery import should_recover_missing_state_label

if TYPE_CHECKING:
    from vibe3.models import PRResponse
    from vibe3.services.check.service import CheckResult


@dataclass
class CheckContext:
    """Shared state passed to check rules."""

    branch: str
    flow_data: dict[str, Any]
    flow_status: str
    is_active_flow: bool
    task_issue: int | None
    task_issue_closed: bool
    orchestration_state: IssueState | None
    issue_payload: dict | None
    issue_labels: list[str]
    issue_labels_loaded: bool
    branch_missing: bool
    branch_pr: PRResponse | None = None
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def rule_pr_terminal_state(ctx: CheckContext, svc: Any) -> CheckResult | None:
    """Handle PR merged/closed -> mark flow aborted."""
    if not svc._sync_rules.local.pr_terminal_state.enabled:
        return None

    ctx.branch_pr = svc._branch_to_pr.get(ctx.branch)
    if ctx.branch_pr:
        handled, pr_issues, pr_warnings = (
            svc._check_pr_service.handle_pr_terminal_state(ctx.branch, ctx.branch_pr)
        )
        if handled:
            from vibe3.services.check.service import CheckResult

            return CheckResult(
                is_valid=len(pr_issues) == 0,
                issues=pr_issues,
                warnings=pr_warnings,
                branch=ctx.branch,
            )
    else:
        try:
            cached_or_remote_pr = svc._pr_service.get_branch_pr_status(ctx.branch)
            if cached_or_remote_pr:
                ctx.branch_pr = cached_or_remote_pr
                handled, pr_issues, pr_warnings = (
                    svc._check_pr_service.handle_pr_terminal_state(
                        ctx.branch, cached_or_remote_pr
                    )
                )
                if handled:
                    from vibe3.services.check.service import CheckResult

                    return CheckResult(
                        is_valid=len(pr_issues) == 0,
                        issues=pr_issues,
                        warnings=pr_warnings,
                        branch=ctx.branch,
                    )
                svc._branch_to_pr[ctx.branch] = cached_or_remote_pr
        except Exception as e:
            logger.bind(domain="check", branch=ctx.branch).warning(
                f"Failed to verify PR status from GitHub: {e}"
            )
            ctx.issues.append(f"Cannot verify PR status for branch '{ctx.branch}': {e}")
    return None


def rule_closed_issue_sync(ctx: CheckContext, svc: Any) -> CheckResult | None:
    """Handle closed task issue -> mark flow aborted."""
    if not ctx.task_issue_closed:
        return None
    if not svc._sync_rules.local.closed_issue_sync.enabled:
        return None
    if not ctx.is_active_flow:
        return None

    from vibe3.services.check.service import CheckResult

    if ctx.branch_pr and ctx.branch_pr.state == PRState.OPEN:
        return CheckResult(is_valid=True, branch=ctx.branch, issues=[])
    pr_detail = f"PR #{ctx.branch_pr.number} closed" if ctx.branch_pr else "no PR found"
    reason = f"Task issue #{ctx.task_issue} is CLOSED ({pr_detail})"
    svc._flow_status_service.mark_flow_aborted(ctx.branch, reason)
    return CheckResult(
        is_valid=True,
        branch=ctx.branch,
        issues=[],
        warnings=[reason],
    )


def rule_stale_blocked_sync(ctx: CheckContext, svc: Any) -> CheckResult | None:
    """Auto-resume flow when remote state/blocked label removed."""
    if not svc._sync_rules.local.stale_blocked_sync.enabled:
        return None
    if not (
        ctx.flow_status == "blocked"
        and ctx.task_issue
        and ctx.orchestration_state is not None
        and ctx.orchestration_state != IssueState.BLOCKED
    ):
        return None

    from vibe3.services.check.service import CheckResult

    try:
        result = svc.recovery_svc.recover(
            branch=ctx.branch,
            issue_number=ctx.task_issue,
            reason="Remote state/blocked label removed",
            auto=True,
            ensure_worktree=True,
        )
        logger.info(
            "Auto-resumed stale blocked flow",
            branch=ctx.branch,
            action=result.action.value,
            detail=result.detail,
        )
        return CheckResult(is_valid=True, branch=ctx.branch, issues=[])
    except Exception as e:
        logger.error(
            "Failed to auto-resume blocked flow",
            branch=ctx.branch,
            error=str(e),
        )
        ctx.issues.append(f"Blocked flow auto-resume failed: {e}")
        return None


def rule_blocked_label_sync(ctx: CheckContext, svc: Any) -> CheckResult | None:
    """Sync remote state/blocked label to local flow status."""
    if not svc._sync_rules.local.blocked_label_sync.enabled:
        return None
    if not (
        ctx.is_active_flow
        and ctx.task_issue
        and ctx.orchestration_state == IssueState.BLOCKED
        and ctx.flow_status != "blocked"
    ):
        return None

    from vibe3.services.check.service import CheckResult
    from vibe3.services.flow import BlockedStateService

    try:
        BlockedStateService(
            github_client=svc.github_client,
            store=svc.store,
        ).write_cache(
            branch=ctx.branch,
            reason="Remote state/blocked label detected",
            blocked_by_issue=None,
            actor="check:blocked_label_sync",
        )
        logger.info(
            "Synced blocked label to local flow status (cache-from-truth)",
            branch=ctx.branch,
        )
        return CheckResult(is_valid=True, branch=ctx.branch, issues=[])
    except Exception as e:
        logger.error(
            "Failed to sync blocked label to flow",
            branch=ctx.branch,
            error=str(e),
        )
        ctx.issues.append(f"Blocked label sync failed: {e}")
        return None


def rule_stale_ready_rebuild(ctx: CheckContext, svc: Any) -> CheckResult | None:
    """Rebuild stale ready flow from remote issue state."""
    if not svc._sync_rules.local.stale_ready_rebuild.enabled:
        return None
    if not (
        ctx.flow_status == "stale"
        and ctx.branch.startswith("task/issue-")
        and ctx.orchestration_state == IssueState.READY
        and svc._flow_status_service.rebuild_stale_ready_flow(
            ctx.branch, task_issue=ctx.task_issue, issue_payload=ctx.issue_payload
        )
    ):
        return None

    from vibe3.services.check.service import CheckResult

    return CheckResult(is_valid=True, branch=ctx.branch, issues=[])


def rule_missing_branch_cleanup(ctx: CheckContext, svc: Any) -> CheckResult | None:
    """Mark flow aborted when local branch deleted."""
    if not svc._sync_rules.local.missing_branch_cleanup.enabled:
        return None
    if not ctx.branch_missing:
        return None

    from vibe3.services.check.service import CheckResult

    svc._flow_status_service.mark_flow_aborted(
        ctx.branch, f"Branch '{ctx.branch}' no longer exists locally"
    )
    return CheckResult(
        is_valid=False,
        branch=ctx.branch,
        issues=[f"Branch '{ctx.branch}' no longer exists locally"],
    )


def rule_orphaned_flow_cleanup(ctx: CheckContext, svc: Any) -> CheckResult | None:
    """Mark orphaned active flows (>100 commits behind) as aborted."""
    if not svc._sync_rules.local.orphaned_flow_cleanup.enabled:
        return None
    if not (
        ctx.flow_status == "active"
        and not ctx.task_issue
        and not svc._has_worktree(ctx.branch)
    ):
        return None

    from vibe3.services.check.service import CheckResult

    try:
        behind_count = svc._count_commits_behind_main(ctx.branch)
        if behind_count and behind_count > svc.ORPHAN_FLOW_BEHIND_THRESHOLD:
            svc._flow_status_service.mark_flow_aborted(
                ctx.branch,
                f"Orphaned flow '{ctx.branch}' is {behind_count} "
                "commits behind main",
            )
            return CheckResult(
                is_valid=False,
                branch=ctx.branch,
                issues=[
                    f"Orphaned flow '{ctx.branch}' is {behind_count} "
                    "commits behind main"
                ],
            )
    except Exception as exc:
        logger.bind(domain="check", branch=ctx.branch).debug(
            f"Could not count commits behind main: {exc}"
        )
    return None


def rule_empty_ready_cleanup(ctx: CheckContext, svc: Any) -> CheckResult | None:
    """Mark empty ready flows as stale."""
    if not svc._sync_rules.local.empty_ready_cleanup.enabled:
        return None
    if not (
        ctx.flow_status == "active"
        and ctx.branch.startswith("task/issue-")
        and ctx.orchestration_state == IssueState.READY
        and is_empty_auto_scene(ctx.flow_data)
        and not svc._has_worktree(ctx.branch)
    ):
        return None

    from vibe3.services.check.service import CheckResult

    svc._flow_status_service.mark_flow_stale(
        ctx.branch,
        f"Issue #{ctx.task_issue} remains state/ready with no active scene",
    )
    return CheckResult(is_valid=True, branch=ctx.branch, issues=[])


def rule_flow_consistency_recovery(ctx: CheckContext, svc: Any) -> CheckResult | None:
    """Auto-recover inconsistent flow state."""
    if not svc._sync_rules.local.flow_consistency_recovery.enabled:
        return None
    if ctx.flow_status in svc.INACTIVE_FLOW_STATUSES:
        return None

    from vibe3.services.check.service import CheckResult
    from vibe3.services.flow.recovery import RecoveryAction

    action, consistency = svc.recovery_svc.classify(ctx.branch)
    if action == RecoveryAction.RESUME_ONLY:
        return None

    consistency_error = consistency.reason if consistency else "No flow record"
    try:
        result = svc.recovery_svc.recover(
            branch=ctx.branch,
            issue_number=ctx.task_issue or 0,
            reason="Health check auto-recover",
            auto=True,
            ensure_worktree=True,
        )
        logger.info(
            "Auto-recovered inconsistent flow",
            branch=ctx.branch,
            action=result.action.value,
            detail=result.detail,
        )
        return CheckResult(is_valid=True, branch=ctx.branch, issues=[])
    except Exception as e:
        logger.error(
            "Auto-recovery failed",
            branch=ctx.branch,
            error=str(e),
        )
        ctx.issues.append(
            f"{consistency_error}. "
            f"Auto-recovery failed: {e}. "
            f"Manual fix: vibe3 flow rebuild {ctx.task_issue} --yes"
        )
        return None


def rule_missing_state_label_recovery(
    ctx: CheckContext, svc: Any
) -> CheckResult | None:
    """Recover missing remote state label from local flow."""
    if not svc._sync_rules.local.missing_state_label_recovery.enabled:
        return None
    if not (
        ctx.task_issue
        and should_recover_missing_state_label(
            labels=ctx.issue_labels,
            flow_status=str(ctx.flow_status),
            issue_loaded=ctx.issue_payload is not None and ctx.issue_labels_loaded,
            task_issue_closed=ctx.task_issue_closed,
        )
    ):
        return None

    from vibe3.services.check.service import CheckResult

    try:
        result = svc.recovery_svc.recover(
            branch=ctx.branch,
            issue_number=ctx.task_issue,
            reason="Remote state label missing",
            auto=False,
            ensure_worktree=True,
        )
        logger.info(
            "Recovered missing remote state label",
            branch=ctx.branch,
            action=result.action.value,
            detail=result.detail,
        )
        return CheckResult(is_valid=True, branch=ctx.branch, issues=[])
    except Exception as e:
        logger.error(
            "Failed to recover missing remote state label",
            branch=ctx.branch,
            error=str(e),
        )
        ctx.issues.append(f"Missing state label auto-recovery failed: {e}")
        return None


# Ordered list of rules executed in _check_branch (priority order)
RULES = [
    rule_pr_terminal_state,
    rule_closed_issue_sync,
    rule_stale_blocked_sync,
    rule_blocked_label_sync,
    rule_stale_ready_rebuild,
    rule_missing_branch_cleanup,
    rule_orphaned_flow_cleanup,
    rule_empty_ready_cleanup,
    rule_flow_consistency_recovery,
    rule_missing_state_label_recovery,
]
