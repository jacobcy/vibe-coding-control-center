"""Queue operations for dispatch coordination."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Callable

from vibe3.domain import QualifyGateService, find_role_for_state
from vibe3.models import IssueInfo, IssueState, OrchestraConfig, QueueEntry
from vibe3.observability import append_orchestra_event
from vibe3.orchestra import get_flow_context, is_auto_task_branch, load_issue
from vibe3.utils.queue_ordering import sort_ready_issues

if TYPE_CHECKING:
    from vibe3.clients import GitHubClient, SQLiteClient
    from vibe3.environment import SessionRegistryService
    from vibe3.orchestra import FlowManagerProtocol

# Cooldown mechanism for auto-resume circuit breaker
AUTO_RESUME_COOLDOWN_SECONDS = 300  # 5 minutes
_COOLDOWN_EVICTION_SECONDS = 86400  # 24 hours
_last_auto_resume_attempt: dict[int, float] = {}


def _get_manager_usernames_lazy(config: OrchestraConfig) -> tuple[str, ...]:
    """Lazy import wrapper for get_manager_usernames."""
    from vibe3.services import get_manager_usernames

    return get_manager_usernames(config)


def _should_skip_from_queue_lazy(
    issue: IssueInfo,
    supervisor_label: str,
    manager_usernames: tuple[str, ...],
    require_manager_assignee: bool,
) -> bool:
    """Lazy import wrapper for should_skip_from_queue."""
    from vibe3.services import should_skip_from_queue

    return should_skip_from_queue(
        issue,
        supervisor_label=supervisor_label,
        manager_usernames=manager_usernames,
        require_manager_assignee=require_manager_assignee,
    )


def select_ready_issues_from_collected_issues(
    issues: list[IssueInfo],
    trigger_state: IssueState,
    config: OrchestraConfig,
    github: "GitHubClient",
    store: "SQLiteClient",
    flow_manager: "FlowManagerProtocol",
    qualify_gate: QualifyGateService,
    supervisor_label: str,
) -> list[IssueInfo]:
    """Select ready issues from already-collected IssueInfo objects."""
    selected: list[IssueInfo] = []
    role = find_role_for_state(trigger_state)
    if role is None:
        return selected

    for issue in issues:
        if issue.state != trigger_state:
            continue
        # Verify assignee/supervisor filters
        # Always require manager assignee for all dispatch stages
        if _should_skip_from_queue_lazy(
            issue,
            supervisor_label=supervisor_label,
            manager_usernames=_get_manager_usernames_lazy(config),
            require_manager_assignee=True,
        ):
            continue

        # All roles go through Qualify Gate for body-truth alignment.
        # Blocked issues from label are re-evaluated against body truth
        # before retention, removal, or promotion.
        branch, flow_state = get_flow_context(
            issue.number, config, github, store, flow_manager
        )

        # Qualify Gate — returns target state or None if blocked
        target = qualify_gate.run_qualify_gate(
            issue, branch, flow_state, issue.labels, trigger_state
        )
        if target is None or target != trigger_state:
            continue

        # Role-specific branch existence requirements
        if role.trigger_name != "manager":
            if not branch or not is_auto_task_branch(branch):
                # Auto-resume orphaned issues without flow scene
                if issue.state not in {IssueState.READY, IssueState.BLOCKED}:
                    _auto_resume_to_ready(issue, config)
                continue
            if not flow_manager.git.branch_exists(branch):
                append_orchestra_event(
                    "dispatcher",
                    f"skip #{issue.number}: branch '{branch}' not found in git",
                )
                continue

        selected.append(issue)

    return sort_ready_issues(selected)


def _auto_resume_to_ready(
    issue: IssueInfo,
    config: OrchestraConfig,
) -> None:
    """Auto-resume orphaned issue without flow scene back to READY state.

    Used when an issue has no flow scene (branch=None) but is in a non-ready/blocked
    state. This recovers orphaned issues that got stuck due to missing branch/flow.

    Args:
        issue: Issue to auto-resume
        config: Orchestra configuration
    """
    from vibe3.services.label_service import LabelService

    # Cooldown guard: prevent repeated attempts within cooldown period
    now = time.time()

    # Evict stale entries older than eviction threshold to bound memory
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

    # Defensive guard: never auto-resume READY or BLOCKED issues
    # READY issues are already in target state
    # BLOCKED issues require human intervention per state machine invariant
    if issue.state in {IssueState.READY, IssueState.BLOCKED}:
        return

    try:
        label_service = LabelService(repo=config.repo)
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
        # Clear cooldown on success to allow immediate future resume
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
    registry: "SessionRegistryService | None",
    supervisor_label: str,
    load_issue_func: Callable[[int], IssueInfo | None] | None = None,
) -> tuple[list[QueueEntry], list[QueueEntry], list[QueueEntry]]:
    """Process frozen queue entries and categorize them.

    Args:
        frozen_queue: Current frozen queue entries
        config: Orchestra configuration
        github: GitHub client
        registry: Session registry (optional)
        supervisor_label: Supervisor label to check
        load_issue_func: Optional function to load issues (for backward compatibility)

    Returns:
        Tuple of (promoted, retained, removed) entries
    """

    promoted: list[QueueEntry] = []
    retained: list[QueueEntry] = []
    removed: list[QueueEntry] = []

    # Use provided loader or default
    issue_loader = load_issue_func or (lambda num: load_issue(num, config, github))

    for entry in frozen_queue:
        if entry.waiting_state is None:
            retained.append(entry)
            continue

        issue = issue_loader(entry.issue_number)
        if issue is None or issue.state is None:
            continue

        if _should_skip_from_queue_lazy(
            issue,
            supervisor_label=supervisor_label,
            manager_usernames=_get_manager_usernames_lazy(config),
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
            # State unchanged - retain entry for next tick
            retained.append(entry)
            continue

        # Progress detected (state changed to non-terminal) - promote to front
        entry.waiting_state = None
        entry.collected_state = current_state  # Sync with current state
        promoted.append(entry)
        append_orchestra_event(
            "dispatcher",
            f"GlobalDispatchCoordinator: requeued #{entry.issue_number} "
            f"to front after state change to {current_state}",
        )

    return promoted, retained, removed
