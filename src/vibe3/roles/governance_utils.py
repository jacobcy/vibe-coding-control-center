"""Utility functions for governance role."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.services.label_utils import normalize_assignees, normalize_labels
from vibe3.services.orchestra_helpers import get_manager_usernames
from vibe3.services.orchestra_status_service import (
    IssueStatusEntry,
    format_issue_runtime_line,
    format_issue_summary_line,
    is_running_issue,
)


def build_issue_context(
    active_entries: tuple[Any, ...],
    *,
    server_running: bool,
    active_flows: int,
    active_worktrees: int,
    queued_issues: tuple[int, ...],
    circuit_breaker_state: str,
    circuit_breaker_failures: int,
    issue_scope_name: str,
    scope_note: str,
) -> dict[str, Any]:
    """Build issue context dictionary for governance prompts."""
    active_count = len(active_entries)
    running_entries = tuple(
        entry for entry in active_entries if is_running_issue(entry)
    )
    suggested_entries = tuple(
        entry for entry in active_entries if not is_running_issue(entry)
    )
    issue_list = (
        "\n".join(format_issue_summary_line(entry) for entry in active_entries[:20])
        or "(无活跃 issue)"
    )
    running_issue_details = (
        "\n".join(format_issue_runtime_line(entry) for entry in running_entries[:20])
        or "(无 running issues)"
    )
    suggested_issue_details = (
        "\n".join(format_issue_runtime_line(entry) for entry in suggested_entries[:20])
        or "(无建议 issue)"
    )
    truncated_note = (
        f"\n(已截断，仅显示前 20 条 / 共 {active_count} 条活跃 issue)"
        if active_count > 20
        else ""
    )
    return {
        "issue_scope_name": issue_scope_name,
        "scope_note": scope_note,
        "server_status": "running" if server_running else "stopped",
        "active_count": active_count,
        "active_flows": active_flows,
        "active_worktrees": active_worktrees,
        "running_issue_count": len(running_entries),
        "queued_issue_count": len(queued_issues),
        "suggested_issue_count": len(suggested_entries),
        "circuit_breaker_state": circuit_breaker_state,
        "circuit_breaker_failures": circuit_breaker_failures,
        "issue_list": issue_list,
        "running_issue_details": running_issue_details,
        "suggested_issue_details": suggested_issue_details,
        "truncated_note": truncated_note,
    }


def is_doc_candidate(title: str, body: str, labels: list[str]) -> bool:
    """Check if an issue is a documentation candidate."""
    if any(label in {"type/docs", "scope/documentation"} for label in labels):
        return True
    normalized_title = title.lower()
    keywords = ("doc", "docs", "documentation", "readme", "文档", "说明")
    return any(keyword in normalized_title for keyword in keywords)


def build_broader_repo_entries(
    config: OrchestraConfig,
    *,
    current_material: str,
    github: GitHubClient | None = None,
) -> tuple[Any, ...]:
    """Build issue entries from broader repo for governance scan."""
    github = github or GitHubClient()
    raw_issues = github.list_issues(
        limit=100,
        state="open",
        assignee=None,
        repo=config.repo,
    )
    material_name = Path(current_material).name
    entries: list[Any] = []
    for item in raw_issues:
        number = item.get("number")
        title = item.get("title")
        if not isinstance(number, int) or not isinstance(title, str):
            continue

        labels = normalize_labels(item.get("labels"))
        # Three-layer governance filter + legacy compat:
        # - orchestra-scanned: intake skipped (self-closure)
        # - orchestra-governed: pool decided (defensive filter, e.g. close/rfc
        #   after assignee removed)
        # - orchestra (legacy umbrella): kept as compatibility alias because
        #   sync-labels.sh is non-destructive and historical issues may still
        #   carry it
        if (
            "supervisor" in labels
            or "orchestra-scanned" in labels
            or "orchestra-governed" in labels
            or "orchestra" in labels
        ):
            continue

        assignees = normalize_assignees(item.get("assignees"))
        is_assignee_issue = any(
            assignee in get_manager_usernames(config) for assignee in assignees
        )

        if material_name == "roadmap-intake.md" and is_assignee_issue:
            continue

        body = str(item.get("body") or "")
        if material_name == "cron-supervisor.md":
            if is_assignee_issue or not is_doc_candidate(title, body, labels):
                continue

        issue = IssueStatusEntry(
            number=number,
            title=title,
            state=None,
            assignee=assignees[0] if assignees else None,
            has_flow=False,
            flow_branch=None,
            has_worktree=False,
            worktree_path=None,
            has_pr=False,
            pr_number=None,
            blocked_by=(),
        )
        entries.append(issue)
    return tuple(entries)


def get_governed_issue_numbers(
    github: GitHubClient, config: OrchestraConfig
) -> set[int]:
    """Fetch issue numbers that have the orchestra-governed label.

    The orchestra-governed label marks issues that have been decided by the
    assignee-pool layer and should be skipped in future pool scans.

    Args:
        github: GitHubClient instance for API calls
        config: OrchestraConfig with repo information

    Returns:
        Set of issue numbers that have orchestra-governed label
    """
    governed_issues = github.list_issues(
        label="orchestra-governed",
        state="open",
        repo=config.repo,
        limit=5000,  # Fetch all governed issues to avoid truncation
    )
    numbers: set[int] = set()
    for item in governed_issues:
        number = item.get("number")
        if isinstance(number, int):
            numbers.add(number)
    return numbers


def normalize_material_name(material_name: str) -> str:
    """Normalize material name to canonical form for comparison.

    Converts various input formats to canonical form:
    - "roadmap-intake" → "roadmap-intake"
    - "roadmap-intake.md" → "roadmap-intake"
    - "supervisor/governance/roadmap-intake" → "roadmap-intake"
    - "supervisor/governance/roadmap-intake.md" → "roadmap-intake"
    """
    path = Path(material_name)
    # Get the filename without directory
    stem = path.stem if path.suffix == ".md" else path.name
    # If stem still has .md suffix, remove it
    if stem.endswith(".md"):
        stem = stem[:-3]
    return stem


def find_material_in_catalog(
    catalog: tuple[Any, ...], material_override: str
) -> Any | None:
    """Find material in catalog using flexible matching.

    Attempts multiple matching strategies:
    1. Exact name match (for advanced users who provide full path)
    2. Normalized match (handles partial names, missing suffixes, etc.)
    """
    # Strategy 1: Exact match
    for material in catalog:
        if material.name == material_override:
            return material

    # Strategy 2: Normalized match
    normalized_target = normalize_material_name(material_override)
    for material in catalog:
        normalized_catalog_name = normalize_material_name(material.name)
        if normalized_catalog_name == normalized_target:
            return material

    return None
