"""Remote label anomaly check for orchestra dispatch.

This module provides periodic remote label synchronization to ensure
GitHub issue labels stay in sync with local flow state.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from loguru import logger

from vibe3.clients import (
    GhIssueLabelPort,
    GitHubClient,
    LabelAnomaly,
    SQLiteClient,
    collect_label_anomalies,
    has_manager_assignee,
    load_sync_rules,
    normalize_assignees,
    normalize_labels,
)
from vibe3.config import get_convention, get_manager_usernames, load_orchestra_config


@dataclass
class RemoteCheckResult:
    """Result of remote label anomaly check."""

    checked_count: int
    anomaly_count: int
    removed_count: int
    added_count: int
    dry_run: bool
    anomalies: list[LabelAnomaly] = field(default_factory=list)


def run_remote_label_check(*, dry_run: bool = True) -> RemoteCheckResult:
    """Run remote label anomaly check.

    This function checks remote GitHub issues for label anomalies and
    optionally fixes them. It's called periodically by the dispatch
    coordinator to maintain label consistency.

    Args:
        dry_run: If True, only report anomalies without fixing them.

    Returns:
        RemoteCheckResult with check statistics and anomalies.
    """
    logger.bind(domain="orchestra", action="remote_check").info(
        "Starting remote label check", dry_run=dry_run
    )

    config = load_orchestra_config()
    convention = get_convention()
    manager_usernames = get_manager_usernames(config)
    sync_rules = load_sync_rules()
    github = GitHubClient()
    store = SQLiteClient()
    label_port = GhIssueLabelPort(repo=config.repo)

    all_issues = github.list_issues(
        state="open", fields=["number", "labels", "assignees"]
    )
    local_flow_issues = {
        issue_number
        for flow in store.get_all_flows()
        if (branch := str(flow.get("branch") or "").strip())
        if (issue_number := convention.branch.parse_issue_number(branch)) is not None
    }

    anomalies: list[LabelAnomaly] = []
    removed_count = added_count = 0

    for issue in all_issues:
        num = issue.get("number")
        if not isinstance(num, int):
            continue
        labels = normalize_labels(issue.get("labels", []))
        assignees = normalize_assignees(issue.get("assignees", []))
        found = collect_label_anomalies(
            labels,
            issue_number=num,
            has_local_flow=num in local_flow_issues,
            is_manager_issue=has_manager_assignee(assignees, manager_usernames),
            rules=sync_rules,
        )
        anomalies.extend(found)
        # Log matched anomalies with issue context
        for found_anomaly in found:
            if "governed_missing_state" in found_anomaly.rule:
                logger.bind(domain="orchestra", action="remote_check", issue=num).info(
                    "governed_missing_state: adding state/ready",
                    labels=labels,
                )
        if not dry_run and found:
            for a in found:
                for lb in a.removed:
                    try:
                        label_port.remove_issue_label(num, lb)
                        removed_count += 1
                    except Exception as exc:
                        logger.bind(domain="orchestra", action="remote_check").warning(
                            f"Failed to remove label {lb} from #{num}: {exc}"
                        )
                for lb in a.added:
                    try:
                        label_port.add_issue_label(num, lb)
                        added_count += 1
                    except Exception as exc:
                        logger.bind(domain="orchestra", action="remote_check").warning(
                            f"Failed to add label {lb} to #{num}: {exc}"
                        )

    logger.bind(domain="orchestra", action="remote_check").info(
        "Remote label check completed",
        checked=len(all_issues),
        anomalies=len(anomalies),
        removed=removed_count,
        added=added_count,
    )

    return RemoteCheckResult(
        checked_count=len(all_issues),
        anomaly_count=len(anomalies),
        removed_count=removed_count,
        added_count=added_count,
        dry_run=dry_run,
        anomalies=anomalies,
    )
