"""Queue operations for dispatch coordination."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.domain.role_resolver import find_role_for_state
from vibe3.models import IssueInfo, IssueState
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.queue_entry import QueueEntry
from vibe3.orchestra.issue_loader import (
    get_flow_context,
    is_auto_task_branch,
    load_issue,
)
from vibe3.orchestra.logging import append_orchestra_event
from vibe3.orchestra.queue_ordering import sort_ready_issues
from vibe3.services.shared.labels import should_skip_from_queue
from vibe3.services.shared.orchestra import get_manager_usernames

if TYPE_CHECKING:
    from vibe3.clients.github_client import GitHubClient
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.orchestra.protocols import FlowManagerProtocol


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
        if should_skip_from_queue(
            issue,
            supervisor_label=supervisor_label,
            manager_usernames=get_manager_usernames(config),
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
                continue
            if not flow_manager.git.branch_exists(branch):
                append_orchestra_event(
                    "dispatcher",
                    f"skip #{issue.number}: branch '{branch}' not found in git",
                )
                continue

        selected.append(issue)

    return sort_ready_issues(selected)


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

        if should_skip_from_queue(
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
