"""Issue failure and block side effects service.

This module handles failure/block transitions for issues when
executor or manager runs fail or make no progress.
"""

from __future__ import annotations

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestration import IssueState
from vibe3.services.issue_flow_service import IssueFlowService
from vibe3.services.label_service import LabelService
from vibe3.utils.label_utils import normalize_labels


def _ensure_flow_state_for_issue(
    issue_number: int,
    action: str,  # "block" or "fail"
    reason: str,
    actor: str,
) -> None:
    """Record block/fail reason on the flow for observability."""
    try:
        issue_flow_service = IssueFlowService()
        store = issue_flow_service.store

        # Find any flow for this issue (active or otherwise)
        flows = store.get_flows_by_issue(issue_number, role="task")
        if not flows:
            return

        branch = str(flows[0].get("branch") or "").strip()
        if not branch:
            return

        # Write flow event for observability
        event_type = f"{action}ed"  # "blocked" or "failed"
        store.add_event(
            branch,
            event_type,
            actor,
            detail=reason,
            refs={"issue": str(issue_number), "action": action},
        )

        # Record reason as display-only field
        if action == "block":
            store.update_flow_state(branch, blocked_reason=reason, latest_actor=actor)
        elif action == "fail":
            store.update_flow_state(branch, failed_reason=reason, latest_actor=actor)
        else:
            logger.bind(
                domain="flow",
                action=action,
                issue_number=issue_number,
            ).warning(f"Unknown action: {action}")

    except Exception as e:
        logger.bind(
            domain="flow",
            action="ensure_flow_state",
            issue_number=issue_number,
            error=str(e),
        ).warning(f"Flow reason recording failed for issue #{issue_number}")


_TERMINAL_LABELS = {
    IssueState.FAILED.to_label(),
    IssueState.BLOCKED.to_label(),
}


def _issue_has_terminal_label(
    github: GitHubClient,
    issue_number: int,
    repo: str | None,
) -> bool:
    """Return True if issue already carries a terminal state label."""
    payload = github.view_issue(issue_number, repo=repo)
    if not isinstance(payload, dict):
        return False
    labels = normalize_labels(payload.get("labels"))
    return any(lb in _TERMINAL_LABELS for lb in labels)


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
    skip_if_terminal: bool = False,
) -> bool:
    """Apply optional comment side effect, then transition the issue state."""
    github = GitHubClient()
    if skip_if_terminal and _issue_has_terminal_label(github, issue_number, repo):
        logger.bind(
            domain="flow",
            action="transition_skipped",
            issue_number=issue_number,
            to_state=to_state.value,
        ).info(f"Skipping transition for #{issue_number}: terminal state")
        return False

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
    return True


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
    "review": "审查未产出可交接的 audit 结果，缺失 authoritative",
}

_ROLE_DEFAULT_ACTOR = {
    "review": "agent:review",
    "plan": "agent:plan",
    "run": "agent:run",
    "manager": "agent:manager",
}

_ROLE_MAP = {
    "executor": "run",
    "reviewer": "review",
    "planner": "plan",
}


def fail_issue(
    *,
    issue_number: int,
    reason: str,
    role: str,
    actor: str | None = None,
) -> None:
    """Generic fail issue handler."""
    # Normalize role names
    role = _ROLE_MAP.get(role, role)
    actor = actor or _ROLE_DEFAULT_ACTOR.get(role, f"agent:{role}")

    _ensure_flow_state_for_issue(issue_number, "fail", reason, actor)

    _transition_issue_state(
        issue_number=issue_number,
        to_state=IssueState.FAILED,
        actor=actor,
        force=True,
        comment=_build_failure_comment(role, reason),
        dedupe_latest_comment=True,
    )


def block_issue(
    *,
    issue_number: int,
    reason: str,
    role: str,
    actor: str | None = None,
    repo: str | None = None,
    is_noop: bool = False,
) -> None:
    """Generic block issue handler."""
    role = _ROLE_MAP.get(role, role)
    actor = actor or _ROLE_DEFAULT_ACTOR.get(role, f"agent:{role}")

    _ensure_flow_state_for_issue(issue_number, "block", reason, actor)

    if is_noop:
        ref_names = {"plan": "plan_ref", "run": "report_ref", "review": "audit_ref"}
        ref_name = ref_names.get(role)
        if ref_name:
            comment = _build_missing_ref_comment(role, ref_name, reason)
        else:
            comment = f"[{role}] 无法推进,已切换为 state/blocked。\n\n原因:{reason}"
    else:
        comment = f"[{role}] 已切换为 state/blocked。\n\n原因:{reason}"

    _transition_issue_state(
        issue_number=issue_number,
        to_state=IssueState.BLOCKED,
        actor=actor,
        force=True,
        repo=repo,
        dedupe_reason=reason if not is_noop else None,
        dedupe_latest_comment=is_noop,
        comment=comment,
        skip_if_terminal=True,
    )


def resume_issue(
    *,
    issue_number: int,
    reason: str,
    from_state: str,  # "failed" or "blocked"
    repo: str | None = None,
    actor: str = "human:resume",
) -> None:
    """Generic resume issue handler."""
    # Write to flow (source of truth) before GitHub sync
    issue_flow_service = IssueFlowService()
    flows = issue_flow_service.store.get_flows_by_issue(issue_number, role="task")
    if flows:
        branch = str(flows[0].get("branch") or "").strip()
        if branch:
            issue_flow_service.store.add_event(
                branch,
                "resumed",
                actor,
                detail=f"Resumed from {from_state} to ready: {reason}",
                refs={
                    "issue": str(issue_number),
                    "from_state": from_state,
                    "to_state": "ready",
                },
            )

    action_text = "恢复" if from_state == "blocked" else "继续"
    header = f"[resume] 已从 state/{from_state} {action_text}到 state/ready。"
    detail = (
        "阻塞已解除,准备继续执行。"
        if from_state == "blocked"
        else "将重新进入 manager 标准入口。"
    )

    _transition_issue_state(
        issue_number=issue_number,
        to_state=IssueState.READY,
        actor=actor,
        force=True,
        repo=repo,
        dedupe_latest_comment=True,
        comment=_build_resume_comment(
            header=header,
            detail=detail,
            reason=reason,
        ),
    )


# Backward compatibility wrappers (can be removed later if all callers updated)
def fail_reviewer_issue(
    *, issue_number: int, reason: str, actor: str = "agent:review"
) -> None:
    fail_issue(issue_number=issue_number, reason=reason, role="review", actor=actor)


def fail_planner_issue(
    *, issue_number: int, reason: str, actor: str = "agent:plan"
) -> None:
    fail_issue(issue_number=issue_number, reason=reason, role="plan", actor=actor)


def fail_executor_issue(*, issue_number: int, reason: str, actor: str) -> None:
    fail_issue(issue_number=issue_number, reason=reason, role="run", actor=actor)


def fail_manager_issue(
    *, issue_number: int, reason: str, actor: str = "agent:manager"
) -> None:
    fail_issue(issue_number=issue_number, reason=reason, role="manager", actor=actor)


def block_manager_noop_issue(
    *, issue_number: int, repo: str | None, reason: str, actor: str
) -> None:
    block_issue(
        issue_number=issue_number,
        reason=reason,
        role="manager",
        actor=actor,
        repo=repo,
        is_noop=True,
    )


def block_planner_noop_issue(
    *,
    issue_number: int,
    reason: str,
    actor: str = "agent:plan",
    repo: str | None = None,
) -> None:
    block_issue(
        issue_number=issue_number,
        reason=reason,
        role="plan",
        actor=actor,
        repo=repo,
        is_noop=True,
    )


def block_executor_noop_issue(
    *, issue_number: int, reason: str, actor: str = "agent:run", repo: str | None = None
) -> None:
    block_issue(
        issue_number=issue_number,
        reason=reason,
        role="run",
        actor=actor,
        repo=repo,
        is_noop=True,
    )


def block_reviewer_noop_issue(
    *,
    issue_number: int,
    reason: str,
    actor: str = "agent:review",
    repo: str | None = None,
) -> None:
    block_issue(
        issue_number=issue_number,
        reason=reason,
        role="review",
        actor=actor,
        repo=repo,
        is_noop=True,
    )


def resume_failed_issue_to_ready(
    *, issue_number: int, repo: str | None, reason: str, actor: str = "human:resume"
) -> None:
    resume_issue(
        issue_number=issue_number,
        reason=reason,
        from_state="failed",
        repo=repo,
        actor=actor,
    )


def resume_blocked_issue_to_ready(
    *, issue_number: int, repo: str | None, reason: str, actor: str = "human:resume"
) -> None:
    resume_issue(
        issue_number=issue_number,
        reason=reason,
        from_state="blocked",
        repo=repo,
        actor=actor,
    )


def _has_matching_block_comment(issue_payload: dict[str, object], reason: str) -> bool:
    """Check if issue already has a block comment with this reason."""
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
    """Build a stable resume comment body."""
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
