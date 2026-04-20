"""Dependency wake-up event handler.

Handles DependencySatisfied events to wake up waiting flows.
"""

import sqlite3
from typing import Callable

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_labels import GhIssueLabelPort
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.domain.events.flow_lifecycle import DependencySatisfied, DomainEvent


def handle_dependency_satisfied(event: DependencySatisfied) -> None:
    """Wake up flows waiting on this dependency.

    When a PR is created for a dependency flow, this handler finds all flows
    that are waiting on this issue and checks if all their dependencies are
    now satisfied. If so, it wakes them up from waiting to active.

    Args:
        event: The DependencySatisfied event containing issue_number, branch,
               and pr_number
    """
    logger.bind(
        domain="dependency_handler",
        satisfied_issue=event.issue_number,
        pr_number=event.pr_number,
    ).info("Dependency satisfied, checking dependents")

    store = SQLiteClient()
    gh = GitHubClient()

    # Find all flows waiting on this issue
    waiting_flows = _find_waiting_flows(store, event.issue_number)

    for flow in waiting_flows:
        branch = str(flow.get("branch") or "").strip()
        if not branch:
            continue

        # Check if ALL dependencies are now satisfied
        all_deps = _get_all_dependencies(store, branch)
        all_satisfied = all(_is_issue_satisfied(gh, dep) for dep in all_deps)

        if all_satisfied:
            # Wake up this flow
            _wake_up_flow(store, gh, branch, event.pr_number)


def _find_waiting_flows(store: SQLiteClient, dep_issue_number: int) -> list[dict]:
    """Find flows that depend on this specific issue.

    Args:
        store: SQLite client
        dep_issue_number: The dependency issue number

    Returns:
        List of flow_state records that are waiting and depend on this issue
    """
    with sqlite3.connect(store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # Query all waiting flows, then filter by dependency link
        cursor.execute(
            "SELECT * FROM flow_state WHERE flow_status = 'waiting'",
        )
        waiting_flows = [dict(row) for row in cursor.fetchall()]

        # Filter by checking if they have dependency on this issue
        result = []
        for flow in waiting_flows:
            branch = str(flow.get("branch") or "").strip()
            if not branch:
                continue

            # Check if this branch has dependency on dep_issue_number
            cursor.execute(
                "SELECT COUNT(*) FROM flow_issue_links "
                "WHERE branch = ? AND issue_number = ? AND issue_role = 'dependency'",
                (branch, dep_issue_number),
            )
            count = cursor.fetchone()[0]
            if count > 0:
                result.append(flow)

        return result


def _get_all_dependencies(store: SQLiteClient, branch: str) -> list[int]:
    """Get all dependency issue numbers for this branch.

    Args:
        store: SQLite client
        branch: The branch to check for dependencies

    Returns:
        List of dependency issue numbers
    """
    with sqlite3.connect(store.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT issue_number FROM flow_issue_links "
            "WHERE branch = ? AND issue_role = 'dependency'",
            (branch,),
        )
        return [row[0] for row in cursor.fetchall()]


def _is_issue_satisfied(gh: GitHubClient, issue_number: int) -> bool:
    """Check if issue is completed (PR created/closed).

    A dependency is satisfied when:
    - Local flow has a PR ref (primary truth source)
    - Issue is closed
    - Issue has state/done or state/merged label
    - Issue body mentions PR reference

    Args:
        gh: GitHub client
        issue_number: The issue number to check

    Returns:
        True if dependency is satisfied, False otherwise
    """
    from vibe3.orchestra.services.state_label_dispatch import _normalize_labels

    # Check local flow state first — this is the primary truth source.
    # Covers scenarios: (a) PR already exists, flow enters waiting later;
    # (b) service restart missed events.
    store = SQLiteClient()
    dep_flows = store.get_flows_by_issue(issue_number, role="task")
    for dep_flow in dep_flows:
        pr_ref = dep_flow.get("pr_ref")
        if pr_ref and str(pr_ref).strip():
            return True
        pr_number = dep_flow.get("pr_number")
        if pr_number:
            return True

    payload = gh.view_issue(issue_number)

    if not isinstance(payload, dict):
        return False

    # Check issue state
    state = payload.get("state")
    if state == "closed":
        return True  # Issue closed → dependency satisfied

    # Check for PR reference (completion marker)
    labels = _normalize_labels(payload.get("labels"))
    if "state/done" in labels or "state/merged" in labels:
        return True  # Task completed with PR

    # Check for PR in issue body
    body = payload.get("body", "")
    if isinstance(body, str):
        if "pull request" in body.lower() or "pr #" in body.lower():
            return True  # PR mentioned → likely completed

    return False  # Dependency not yet satisfied


def _wake_up_flow(
    store: SQLiteClient,
    gh: GitHubClient,
    branch: str,
    source_pr_number: int,
) -> None:
    """Wake up waiting flow and create branch from dependency PR.

    Args:
        store: SQLite client
        gh: GitHub client
        branch: The branch to wake up
        source_pr_number: The PR number that triggered the wake-up
    """
    # 1. Update flow status
    store.update_flow_state(
        branch,
        flow_status="active",
        blocked_by_issue=None,
        blocked_reason=None,
    )

    # 2. Add wake-up event
    store.add_event(
        branch,
        "dependency_wake_up",
        "orchestra:dependency_handler",
        detail="Dependencies satisfied, ready to proceed",
        refs={"source_pr": str(source_pr_number)},
    )

    # 3. Sync GitHub labels
    links = store.get_issue_links(branch)
    task_issue = next(
        (link for link in links if link.get("issue_role") == "task"), None
    )

    if task_issue:
        issue_number = task_issue.get("issue_number")
        if issue_number:
            try:
                label_port = GhIssueLabelPort()
                label_port.remove_issue_label(issue_number, "state/blocked")
                label_port.add_issue_label(issue_number, "state/ready")
            except Exception as exc:
                logger.bind(
                    domain="dependency_handler",
                    branch=branch,
                    issue=issue_number,
                ).warning(f"Failed to update GitHub labels: {exc}")

    logger.bind(
        domain="dependency_handler",
        branch=branch,
        source_pr=source_pr_number,
    ).info("Flow woken up from waiting")


def register_dependency_wake_up_handlers() -> None:
    """Register dependency wake-up event handlers."""
    from typing import cast

    from vibe3.domain.publisher import subscribe

    subscribe(
        "DependencySatisfied",
        cast(Callable[[DomainEvent], None], handle_dependency_satisfied),
    )

    logger.bind(domain="events").info("Dependency wake-up event handlers registered")
