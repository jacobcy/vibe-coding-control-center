"""Issue failure and block side effects service.

This module handles failure/block transitions for issues when
executor or manager runs fail or make no progress.
"""

from __future__ import annotations

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestration import IssueState
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_flow_service import IssueFlowService
from vibe3.services.label_service import LabelService


def _ensure_flow_state_for_issue(
    issue_number: int,
    action: str,  # "block" or "fail"
    reason: str,
    actor: str,
) -> None:
    """Find flow for issue and write block/fail state.

    This helper ensures flow is the source of truth before GitHub sync.

    Args:
        issue_number: GitHub issue number
        action: "block" or "fail"
        reason: Block/fail reason text
        actor: Actor performing the action

    Behavior:
        - Find active flow for issue using IssueFlowService
        - If no flow found: create minimal flow (per Eng Review decision)
        - Call FlowService.block_flow() or fail_flow()
        - On flow write error: log and continue (Fallback strategy)

    Note:
        Flow write failures do not block GitHub sync. This ensures user
        visibility even when flow persistence fails.
    """
    try:
        issue_flow_service = IssueFlowService()
        flow_service = FlowService()

        # Find active flow for issue
        flow = issue_flow_service.find_active_flow(issue_number)

        if not flow:
            # Eng Review decision: create minimal flow if missing
            branch = issue_flow_service.canonical_branch_name(issue_number)
            logger.bind(
                domain="flow",
                action="create_minimal",
                issue_number=issue_number,
            ).info("Creating minimal flow for block/fail operation")
            flow_service.create_flow(
                slug=f"issue-{issue_number}",
                branch=branch,
                actor=actor,
            )
        else:
            branch = str(flow.get("branch") or "").strip()

        # Write flow state (source of truth)
        if action == "block":
            flow_service.block_flow(branch, reason=reason, actor=actor)
        elif action == "fail":
            flow_service.fail_flow(branch, reason=reason, actor=actor)
        else:
            logger.bind(
                domain="flow",
                action=action,
                issue_number=issue_number,
            ).warning(f"Unknown action: {action}")

    except Exception as e:
        # Fallback strategy: log error, continue with GitHub sync
        logger.bind(
            domain="flow",
            action="ensure_flow_state",
            issue_number=issue_number,
            error=str(e),
        ).error(
            f"Flow write failed for issue #{issue_number}, "
            f"continuing with GitHub sync (Fallback strategy)"
        )


def _transition_issue_state(
    *,
    issue_number: int,
    to_state: IssueState,
    actor: str,
    force: bool,
    comment: str | None = None,
    repo: str | None = None,
    dedupe_latest_comment: bool = False,
    dedupe_reason: str | None = None,
) -> None:
    """Apply optional comment side effect, then transition the issue state."""
    github = GitHubClient()
    if comment:
        if dedupe_latest_comment:
            _add_comment_if_missing(
                github=github,
                issue_number=issue_number,
                body=comment,
                repo=repo,
            )
        elif dedupe_reason is not None:
            issue_payload = github.view_issue(issue_number, repo=repo)
            if not (
                isinstance(issue_payload, dict)
                and _has_matching_block_comment(issue_payload, dedupe_reason)
            ):
                github.add_comment(issue_number, comment, repo=repo)
        else:
            github.add_comment(issue_number, comment, repo=repo)

    LabelService(repo=repo).confirm_issue_state(
        issue_number,
        to_state,
        actor=actor,
        force=force,
    )


def _build_failure_comment(role: str, reason: str) -> str:
    return f"[{role}] {_ROLE_FAILURE_COPY[role]}\n\n原因:{reason}"


def _build_missing_ref_comment(role: str, ref_name: str, reason: str) -> str:
    return (
        f"[{role}] {_ROLE_MISSING_REF_COPY[role]} {ref_name}，"
        "已切换为 state/blocked。\n\n"
        f"原因:{reason}"
    )


_ROLE_FAILURE_COPY = {
    "review": "审查执行报错,已切换为 state/failed。",
    "plan": "规划执行报错,已切换为 state/failed。",
    "run": "执行报错,已切换为 state/failed。",
    "manager": "管理执行报错,已切换为 state/failed。",
}

_ROLE_MISSING_REF_COPY = {
    "plan": "规划执行完成，但未登记 authoritative",
    "run": "执行完成，但未登记 authoritative",
    "review": "审查完成，但未登记 authoritative",
}


def fail_reviewer_issue(
    *,
    issue_number: int,
    reason: str,
    actor: str = "agent:review",
) -> None:
    """Fail a reviewer issue with comment and state transition.

    Args:
        issue_number: GitHub issue number
        reason: Failure reason to include in comment
        actor: Actor performing the transition (defaults to "agent:review")
    """
    # Write to flow (source of truth) before GitHub sync
    _ensure_flow_state_for_issue(issue_number, "fail", reason, actor)

    _transition_issue_state(
        issue_number=issue_number,
        to_state=IssueState.FAILED,
        actor=actor,
        force=True,
        comment=_build_failure_comment("review", reason),
    )


def fail_planner_issue(
    *,
    issue_number: int,
    reason: str,
    actor: str = "agent:plan",
) -> None:
    """Fail a planner issue with comment and state transition.

    Args:
        issue_number: GitHub issue number
        reason: Failure reason to include in comment
        actor: Actor performing the transition (defaults to "agent:plan")
    """
    # Write to flow (source of truth) before GitHub sync
    _ensure_flow_state_for_issue(issue_number, "fail", reason, actor)

    _transition_issue_state(
        issue_number=issue_number,
        to_state=IssueState.FAILED,
        actor=actor,
        force=True,
        comment=_build_failure_comment("plan", reason),
    )


def fail_executor_issue(
    *,
    issue_number: int,
    reason: str,
    actor: str,
) -> None:
    """Fail an executor issue with comment and state transition.

    Args:
        issue_number: GitHub issue number
        reason: Failure reason to include in comment
        actor: Actor performing the transition (e.g., "agent:executor")
    """
    # Write to flow (source of truth) before GitHub sync
    _ensure_flow_state_for_issue(issue_number, "fail", reason, actor)

    _transition_issue_state(
        issue_number=issue_number,
        to_state=IssueState.FAILED,
        actor=actor,
        force=True,
        comment=_build_failure_comment("run", reason),
    )


def fail_manager_issue(
    *,
    issue_number: int,
    reason: str,
    actor: str = "agent:manager",
) -> None:
    """Fail a manager issue with comment and state transition.

    Args:
        issue_number: GitHub issue number
        reason: Failure reason to include in comment
        actor: Actor performing the transition (defaults to "agent:manager")
    """
    # Write to flow (source of truth) before GitHub sync
    _ensure_flow_state_for_issue(issue_number, "fail", reason, actor)

    _transition_issue_state(
        issue_number=issue_number,
        to_state=IssueState.FAILED,
        actor=actor,
        force=True,
        comment=_build_failure_comment("manager", reason),
    )


def resume_failed_issue_to_handoff(
    *,
    issue_number: int,
    repo: str | None,
    reason: str,
    actor: str = "human:resume",
) -> None:
    """Resume a failed issue back to handoff for manager triage.

    Args:
        issue_number: GitHub issue number
        repo: Repository (owner/repo format, optional)
        reason: Resume reason to include in comment
        actor: Actor performing the resume
    """
    _transition_issue_state(
        issue_number=issue_number,
        to_state=IssueState.HANDOFF,
        actor=actor,
        force=False,
        repo=repo,
        dedupe_latest_comment=True,
        comment=_build_resume_comment(
            header="[resume] 已从 state/failed 继续到 state/handoff。",
            detail="manager 将重新判断现场并决定下一步。",
            reason=reason,
        ),
    )


def resume_failed_issue_to_ready(
    *,
    issue_number: int,
    repo: str | None,
    reason: str,
    actor: str = "human:resume",
) -> None:
    """Resume a failed issue back to ready for fresh manager entry.

    Args:
        issue_number: GitHub issue number
        repo: Repository (owner/repo format, optional)
        reason: Resume reason to include in comment
        actor: Actor performing the resume
    """
    _transition_issue_state(
        issue_number=issue_number,
        to_state=IssueState.READY,
        actor=actor,
        force=True,
        repo=repo,
        dedupe_latest_comment=True,
        comment=_build_resume_comment(
            header="[resume] 已从 state/failed 继续到 state/ready。",
            detail="将重新进入 manager 标准入口。",
            reason=reason,
        ),
    )


def resume_blocked_issue_to_ready(
    *,
    issue_number: int,
    repo: str | None,
    reason: str,
    actor: str = "human:resume",
) -> None:
    """Resume a blocked issue back to ready after blockage resolved.

    Args:
        issue_number: GitHub issue number
        repo: Repository (owner/repo format, optional)
        reason: Resume reason to include in comment
        actor: Actor performing the resume
    """
    _transition_issue_state(
        issue_number=issue_number,
        to_state=IssueState.READY,
        actor=actor,
        force=True,
        repo=repo,
        dedupe_latest_comment=True,
        comment=_build_resume_comment(
            header="[resume] 已从 state/blocked 恢复到 state/ready。",
            detail="阻塞已解除,准备继续执行。",
            reason=reason,
        ),
    )


def block_manager_noop_issue(
    *,
    issue_number: int,
    repo: str | None,
    reason: str,
    actor: str,
) -> None:
    """Block a manager issue that made no progress.

    Adds block comment if not already present, and transitions
    issue to blocked state.

    Args:
        issue_number: GitHub issue number
        repo: Repository (owner/repo format, optional)
        reason: Block reason to include in comment
        actor: Actor performing the transition
    """
    # Write to flow (source of truth) before GitHub sync
    _ensure_flow_state_for_issue(issue_number, "block", reason, actor)

    _transition_issue_state(
        issue_number=issue_number,
        to_state=IssueState.BLOCKED,
        actor=actor,
        force=True,
        repo=repo,
        dedupe_reason=reason,
        comment=f"[manager] 无法推进,已切换为 state/blocked。\n\n原因:{reason}",
    )


def block_planner_noop_issue(
    *,
    issue_number: int,
    reason: str,
    actor: str = "agent:plan",
    repo: str | None = None,
) -> None:
    """Block a planner issue when no authoritative plan_ref was produced.

    Args:
        issue_number: GitHub issue number
        reason: Reason for blocking
        actor: Actor performing the block
        repo: Repository (owner/repo format, optional)
    """
    # Write to flow (source of truth) before GitHub sync
    _ensure_flow_state_for_issue(issue_number, "block", reason, actor)

    _transition_issue_state(
        issue_number=issue_number,
        to_state=IssueState.BLOCKED,
        actor=actor,
        force=True,
        repo=repo,
        dedupe_latest_comment=True,
        comment=_build_missing_ref_comment("plan", "plan_ref", reason),
    )


def block_executor_noop_issue(
    *,
    issue_number: int,
    reason: str,
    actor: str = "agent:run",
    repo: str | None = None,
) -> None:
    """Block an executor issue when no authoritative report_ref was produced.

    Args:
        issue_number: GitHub issue number
        reason: Reason for blocking
        actor: Actor performing the block
        repo: Repository (owner/repo format, optional)
    """
    # Write to flow (source of truth) before GitHub sync
    _ensure_flow_state_for_issue(issue_number, "block", reason, actor)

    _transition_issue_state(
        issue_number=issue_number,
        to_state=IssueState.BLOCKED,
        actor=actor,
        force=True,
        repo=repo,
        dedupe_latest_comment=True,
        comment=_build_missing_ref_comment("run", "report_ref", reason),
    )


def block_reviewer_noop_issue(
    *,
    issue_number: int,
    reason: str,
    actor: str = "agent:review",
    repo: str | None = None,
) -> None:
    """Block a reviewer issue when no authoritative audit_ref was produced.

    Args:
        issue_number: GitHub issue number
        reason: Reason for blocking
        actor: Actor performing the block
        repo: Repository (owner/repo format, optional)
    """
    # Write to flow (source of truth) before GitHub sync
    _ensure_flow_state_for_issue(issue_number, "block", reason, actor)

    _transition_issue_state(
        issue_number=issue_number,
        to_state=IssueState.BLOCKED,
        actor=actor,
        force=True,
        repo=repo,
        dedupe_latest_comment=True,
        comment=_build_missing_ref_comment("review", "audit_ref", reason),
    )


def confirm_role_handoff(
    *,
    issue_number: int,
    actor: str,
) -> str:
    """Transition issue to handoff after successful role execution.

    Called from success_handler in SYNC_SPEC to advance state → HANDOFF
    so the next stage can be dispatched.

    Args:
        issue_number: GitHub issue number
        actor: Actor performing the transition (e.g., "agent:plan")

    Returns:
        Transition result string (e.g., "advanced" or "blocked")
    """
    return LabelService().confirm_issue_state(
        issue_number,
        IssueState.HANDOFF,
        actor=actor,
    )


# Role-specific aliases for backward compatibility
confirm_plan_handoff = confirm_role_handoff
confirm_run_handoff = confirm_role_handoff
confirm_review_handoff = confirm_role_handoff


def _has_matching_block_comment(issue_payload: dict[str, object], reason: str) -> bool:
    """Check if issue already has a block comment with this reason.

    Args:
        issue_payload: GitHub issue payload
        reason: Reason string to search for

    Returns:
        True if matching block comment exists
    """
    comments = issue_payload.get("comments")
    if not isinstance(comments, list):
        return False
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        body = comment.get("body")
        if isinstance(body, str) and reason in body:
            return True
    return False


def _build_resume_comment(*, header: str, detail: str, reason: str) -> str:
    """Build a stable resume comment body.

    When reason is empty, omit the reason section so repeated manual retries can be
    deduplicated using the exact same comment body.
    """
    body = f"{header}\n\n{detail}"
    normalized_reason = reason.strip()
    if normalized_reason:
        body += f"\n\n原因:{normalized_reason}"
    return body


def _add_comment_if_missing(
    *,
    github: GitHubClient,
    issue_number: int,
    body: str,
    repo: str | None,
) -> None:
    """Add a GitHub comment unless the latest comment already has the same body."""
    issue_payload = github.view_issue(issue_number, repo=repo)
    if isinstance(issue_payload, dict) and _latest_comment_matches(issue_payload, body):
        return
    github.add_comment(issue_number, body, repo=repo)


def _latest_comment_matches(
    issue_payload: dict[str, object], comment_text: str
) -> bool:
    """Return True when the latest issue comment has the same body."""
    comments = issue_payload.get("comments")
    if not isinstance(comments, list):
        return False
    normalized_comment = comment_text.strip()
    for comment in reversed(comments):
        if not isinstance(comment, dict):
            continue
        body = comment.get("body")
        return isinstance(body, str) and body.strip() == normalized_comment
    return False
