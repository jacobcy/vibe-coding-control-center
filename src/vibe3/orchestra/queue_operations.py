"""Queue operations for dispatch coordination."""

from __future__ import annotations

import importlib
import time
from typing import TYPE_CHECKING, Any, Callable, cast

from vibe3.config import get_manager_usernames
from vibe3.models import IssueInfo, IssueState, OrchestraConfig, QueueEntry
from vibe3.observability import append_orchestra_event
from vibe3.orchestra import get_flow_context, is_auto_task_branch, load_issue
from vibe3.utils import sort_ready_issues

if TYPE_CHECKING:
    from vibe3.clients import GitHubClient, SQLiteClient
    from vibe3.orchestra import FlowManagerProtocol
    from vibe3.orchestra.domain_types import (
        LabelServiceProtocol,
        QualifyGateServiceProtocol,
    )


# Cooldown mechanism for auto-resume circuit breaker
AUTO_RESUME_COOLDOWN_SECONDS = 300  # 5 minutes
_COOLDOWN_EVICTION_SECONDS = 86400  # 24 hours
_last_auto_resume_attempt: dict[int, float] = {}


def select_ready_issues_from_collected_issues(
    issues: list[IssueInfo],
    trigger_state: IssueState,
    config: OrchestraConfig,
    github: "GitHubClient",
    store: "SQLiteClient",
    flow_manager: "FlowManagerProtocol",
    qualify_gate: QualifyGateServiceProtocol,
    supervisor_label: str,
    *,
    role_resolver: Callable[[IssueState], object | None] | None = None,
    queue_filter: Callable[..., bool] | None = None,
    label_service: LabelServiceProtocol | None = None,
) -> list[IssueInfo]:
    """Select ready issues from already-collected IssueInfo objects."""
    selected: list[IssueInfo] = []
    if role_resolver is not None:
        role = role_resolver(trigger_state)
    else:
        # Fallback: lazy import for backward compatibility
        _finder = importlib.import_module("vibe3.domain")
        role = cast("Any", _finder.find_role_for_state)(trigger_state)  # type: ignore[attr-defined]
    if role is None:
        return selected

    for issue in issues:
        if issue.state != trigger_state:
            continue
        if queue_filter is not None and queue_filter(
            issue,
            supervisor_label=supervisor_label,
            manager_usernames=get_manager_usernames(config),
            require_manager_assignee=True,
        ):
            continue

        branch, flow_state = get_flow_context(
            issue.number, config, github, store, flow_manager
        )

        target = qualify_gate.run_qualify_gate(
            issue, branch, flow_state, issue.labels, trigger_state
        )
        if target is None or target != trigger_state:
            continue

        if role.trigger_name != "manager":  # type: ignore[attr-defined]
            if not branch or not is_auto_task_branch(branch):
                if issue.state not in {IssueState.READY, IssueState.BLOCKED}:
                    _auto_resume_to_ready(issue, config, label_service=label_service)
                continue

        selected.append(issue)

    return sort_ready_issues(selected)


def _auto_resume_to_ready(
    issue: IssueInfo,
    config: OrchestraConfig,
    label_service: LabelServiceProtocol | None = None,
) -> None:
    """Auto-resume orphaned issue without flow scene back to READY state."""
    now = time.time()

    stale = [
        k
        for k, t in _last_auto_resume_attempt.items()
        if now - t > _COOLDOWN_EVICTION_SECONDS
    ]
    for k in stale:
        del _last_auto_resume_attempt[k]

    last_attempt = _last_auto_resume_attempt.get(issue.number, 0)
    if now - last_attempt < AUTO_RESUME_COOLDOWN_SECONDS:
        return
    _last_auto_resume_attempt[issue.number] = now

    if issue.state is None:
        return

    if issue.state in {IssueState.READY, IssueState.BLOCKED}:
        return

    if label_service is None:
        return

    try:
        label_service.transition(
            issue.number,
            IssueState.READY,
            actor="orchestra:auto-resume",
            force=True,
        )
        append_orchestra_event(
            "dispatcher",
            f"auto-resume #{issue.number}: no flow scene, "
            f"state={issue.state.value}, recovered to ready",
        )
        _last_auto_resume_attempt.pop(issue.number, None)
    except Exception as exc:
        append_orchestra_event(
            "dispatcher",
            f"auto-resume #{issue.number} failed: {exc}",
        )


def promote_progressed_entries(
    frozen_queue: list[QueueEntry],
    config: OrchestraConfig,
    github: "GitHubClient",
    supervisor_label: str,
    load_issue_func: Callable[[int], IssueInfo | None] | None = None,
    *,
    queue_filter: Callable[..., bool] | None = None,
) -> tuple[list[QueueEntry], list[QueueEntry], list[QueueEntry]]:
    """Process frozen queue entries and categorize them."""
    promoted: list[QueueEntry] = []
    retained: list[QueueEntry] = []
    removed: list[QueueEntry] = []

    issue_loader = load_issue_func or (lambda num: load_issue(num, config, github))

    for entry in frozen_queue:
        if entry.waiting_state is None:
            retained.append(entry)
            continue

        issue = issue_loader(entry.issue_number)
        if issue is None or issue.state is None:
            continue

        if queue_filter is not None and queue_filter(
            issue,
            supervisor_label=supervisor_label,
            manager_usernames=get_manager_usernames(config),
            require_manager_assignee=True,
        ):
            removed.append(entry)
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: removed #{entry.issue_number} "
                "from queue (supervisor or assignee check failed)",
            )
            continue

        current_state = issue.state.value
        if current_state == entry.waiting_state:
            retained.append(entry)
            continue

        entry.waiting_state = None
        entry.collected_state = current_state
        promoted.append(entry)
        append_orchestra_event(
            "dispatcher",
            f"GlobalDispatchCoordinator: requeued #{entry.issue_number} "
            f"to front after state change to {current_state}",
        )

    return promoted, retained, removed
