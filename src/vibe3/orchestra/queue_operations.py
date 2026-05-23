"""Queue operations for dispatch coordination."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.issue_loader import (
    find_role_for_state,
    get_flow_context,
    is_auto_task_branch,
    load_issue,
)
from vibe3.orchestra.logging import append_orchestra_event
from vibe3.orchestra.queue_entry import QueueEntry
from vibe3.orchestra.queue_ordering import sort_ready_issues
from vibe3.services.label_utils import normalize_labels, should_skip_from_queue

if TYPE_CHECKING:
    from vibe3.clients.github_client import GitHubClient
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.orchestra.flow_dispatch import FlowManager


def collect_raw_issues_without_qualify(
    raw_issues: list[dict[str, object]],
) -> list[IssueInfo]:
    """Apply collection-time filters without running the qualify gate.

    Performs the shared 3-step filtering chain:
    1. normalize_labels
    2. state/ label presence check
    3. IssueInfo.from_github_payload

    Skips the qualify gate so callers can defer qualification (e.g. BLOCKED
    bypass path) or apply it selectively.

    Note: should_skip_from_queue is NOT applied here to preserve original
    behavior where issues flow through qualify gate first for side effects
    (blocked-label alignment, auto-resume).
    """
    selected: list[IssueInfo] = []
    for item in raw_issues:
        labels = normalize_labels(item.get("labels"))
        if not any(lbl.startswith("state/") for lbl in labels):
            continue
        issue = IssueInfo.from_github_payload(item)
        if issue is None:
            continue
        selected.append(issue)
    return selected


def select_ready_issues(
    raw_issues: list[dict[str, object]],
    trigger_state: IssueState,
    config: OrchestraConfig,
    github: "GitHubClient",
    store: "SQLiteClient",
    flow_manager: "FlowManager",
    qualify_gate: QualifyGateService,
    supervisor_label: str,
) -> list[IssueInfo]:
    """Select ready issues by filtering through qualify gate and other checks.

    Args:
        raw_issues: Raw issue payloads from GitHub
        trigger_state: The trigger state being collected
        config: Orchestra configuration
        github: GitHub client
        store: SQLite client
        flow_manager: Flow manager
        qualify_gate: Qualify gate service
        supervisor_label: Supervisor label to check

    Returns:
        Filtered and sorted ready issues
    """
    selected: list[IssueInfo] = []
    role = find_role_for_state(trigger_state)
    if role is None:
        return selected

    raw_selected = collect_raw_issues_without_qualify(raw_issues)

    for issue in raw_selected:
        # Verify assignee/supervisor filters
        # Always require manager assignee for all dispatch stages
        if should_skip_from_queue(
            issue,
            supervisor_label=supervisor_label,
            manager_usernames=config.get_manager_usernames(),
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
            manager_usernames=config.get_manager_usernames(),
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
