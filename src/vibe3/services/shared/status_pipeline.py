"""Shared issue status aggregation pipeline.

Provides IssueStatusAggregator for cross-package reuse of the 6-step
Issue -> IssueStatusEntry pipeline (fetch issues -> match flow -> batch PR
lookup -> worktree map -> sort -> enrich).

This module is a leaf of the services DAG. It does not import from any
business subpackage (services/pr, flow, issue, task, orchestra); the PR
cache dependency is abstracted by services/protocols.PRCachePort.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from loguru import logger

from vibe3.clients import (
    FlowReader,
    GitClient,
    GitHubClient,
    parse_blocked_by,
)
from vibe3.models import IssueState
from vibe3.services.shared.status_query import (
    extract_primary_assignee_login,
    extract_queue_metadata,
    is_orchestra_managed_flow_branch,
    issue_priority,
    sort_ready_issue_dicts,
)

if TYPE_CHECKING:
    from vibe3.services.protocols import PRCachePort


@dataclass(frozen=True)
class IssueStatusEntry:
    """Aggregated status for a single issue."""

    number: int
    title: str
    state: IssueState | None
    assignee: str | None
    has_flow: bool
    flow_branch: str | None
    has_worktree: bool
    worktree_path: str | None
    has_pr: bool
    pr_number: int | None
    blocked_by: tuple[int, ...] = ()
    # Queue metadata fields
    milestone: str | None = None
    roadmap: str | None = None
    priority: int = 0
    queue_rank: int | None = None


def _extract_state_from_labels(labels: list) -> IssueState | None:
    """Extract state from issue labels without API call.

    Args:
        labels: List of label dicts from GitHub issue response

    Returns:
        IssueState if state/* label found, None otherwise
    """
    for label in labels:
        name = label.get("name", "") if isinstance(label, dict) else str(label)
        state = IssueState.from_label(name)
        if state:
            return state
    return None


class IssueStatusAggregator:
    """Aggregates issue status from GitHub, Git, and Flow data sources.

    Encapsulates the 6-step pipeline:
    1. Fetch Issues (provided by caller)
    2. Match Flow (is_orchestra_managed_flow_branch, flow-lookup)
    3. Batch PR lookup (PRService.refresh_recent_pr_cache)
    4. Worktree map (GitClient.list_worktrees)
    5. Sort ready/other (sort_ready_issue_dicts, issue_priority)
    6. Data enrichment (labels, milestone, priority, roadmap, assignee, blocked_by)
    """

    def __init__(
        self,
        github: GitHubClient,
        git: GitClient,
        pr_service_factory: Callable[[], PRCachePort],
        worktree_map_provider: Callable[[], dict[str, str]] | None = None,
        orchestrator: FlowReader | None = None,
    ) -> None:
        """Initialize aggregator with data source clients.

        Args:
            github: GitHub client for issue/PR data
            git: Git client for worktree operations
            pr_service_factory: Factory returning a PRCachePort (typically a
                PRService instance). Typed against the protocol so the shared
                layer has no static dependency on services.pr.
            worktree_map_provider: Optional provider for worktree map
                (default: build from git)
            orchestrator: Optional flow reader for flow matching
        """
        self._github = github
        self._git = git
        self._pr_service_factory = pr_service_factory
        self._worktree_map_provider = worktree_map_provider or self.fetch_worktree_map
        self._orchestrator = orchestrator

    def fetch_worktree_map(self) -> dict[str, str]:
        """Build branch→path worktree mapping from GitClient.

        Uses GitClient.list_worktrees() and strips refs/heads/ prefix.

        Returns:
            Dict mapping branch names to worktree paths
        """
        try:
            worktrees = self._git.list_worktrees()
            return {
                branch.removeprefix("refs/heads/"): path for path, branch in worktrees
            }
        except Exception as exc:
            logger.bind(domain="orchestra").warning(f"Failed to list worktrees: {exc}")
            return {}

    def aggregate(
        self,
        issues: list[dict],
        queued: set[int] | None = None,
        sync_context_cache: bool = True,
    ) -> tuple[IssueStatusEntry, ...]:
        """Aggregate issues into sorted IssueStatusEntry tuples.

        Args:
            issues: List of GitHub issue dicts (already filtered by caller)
            queued: Set of queued issue numbers (for queue_rank assignment)
            sync_context_cache: Whether to sync PR cache to context cache
                (default: True)

        Returns:
            Tuple of IssueStatusEntry, sorted by state priority and queue rules
        """
        log = logger.bind(domain="orchestra", action="status_pipeline_aggregate")
        log.debug(f"Aggregating {len(issues)} issues")

        queued = queued or set()
        worktrees = self._worktree_map_provider()

        # First pass: collect issue rows and flow branches for batch PR lookup
        issue_rows: list[dict[str, Any]] = []
        flow_branches: set[str] = set()
        active_flows = 0

        for issue in issues:
            number = issue.get("number")
            if not number:
                continue

            title = issue.get("title", "")
            assignee = extract_primary_assignee_login(issue.get("assignees"))

            # Get state from issue labels (avoid N+1 API calls)
            state = _extract_state_from_labels(issue.get("labels", []))

            # Check flow
            flow = None
            if self._orchestrator:
                flow = self._orchestrator.get_flow_for_issue(number)
                if flow and not is_orchestra_managed_flow_branch(flow.get("branch")):
                    continue

            has_flow = flow is not None
            flow_branch = flow.get("branch") if flow else None
            if has_flow:
                active_flows += 1
                if flow_branch:
                    flow_branches.add(flow_branch)

            # Check worktree
            branch_name = flow_branch or f"task/issue-{number}"
            worktree_path = worktrees.get(branch_name)
            has_worktree = worktree_path is not None

            # Parse blocked_by from issue body
            blocked_by_list = parse_blocked_by(issue.get("body") or "")

            labels, milestone, priority, roadmap = extract_queue_metadata(
                issue.get("labels"),
                issue.get("milestone"),
            )

            # Skip supervisor issues - orchestra manages task issues only
            if "supervisor" in labels:
                continue

            issue_rows.append(
                {
                    "number": number,
                    "title": title,
                    "state": state,
                    "assignee": assignee,
                    "has_flow": has_flow,
                    "flow_branch": flow_branch,
                    "has_worktree": has_worktree,
                    "worktree_path": worktree_path,
                    "flow": flow,
                    "blocked_by": tuple(blocked_by_list),
                    "milestone": milestone,
                    "roadmap": roadmap,
                    "priority": priority,
                    "labels": labels,
                }
            )

        # Batch PR lookup
        branch_to_pr: dict[str, Any] = {}
        if flow_branches:
            try:
                pr_service = self._pr_service_factory()
                all_prs = pr_service.refresh_recent_pr_cache(
                    sync_context_cache=sync_context_cache
                )
                branch_to_pr = {
                    b: pr for b, pr in all_prs.items() if b in flow_branches
                }
            except Exception as exc:
                log.warning(f"Failed to batch hydrate PR status: {exc}")

        # Second pass: build issue data with PR info
        ready_issues_data: list[dict[str, Any]] = []
        other_issues_data: list[dict[str, Any]] = []

        for row in issue_rows:
            flow_branch = row["flow_branch"]
            flow = row["flow"]

            # Determine PR number from batch cache or stored flow value
            pr_number = None
            if row["has_flow"] and flow_branch:
                cached_pr = branch_to_pr.get(flow_branch)
                pr_number_raw = flow.get("pr_number") if flow else None
                pr_number = cached_pr.number if cached_pr else None
                if pr_number is None and pr_number_raw:
                    try:
                        pr_number = int(pr_number_raw)
                    except (ValueError, TypeError):
                        pass

            issue_data = {
                "number": row["number"],
                "title": row["title"],
                "state": row["state"],
                "assignee": row["assignee"],
                "has_flow": row["has_flow"],
                "flow_branch": row["flow_branch"],
                "has_worktree": row["has_worktree"],
                "worktree_path": row["worktree_path"],
                "has_pr": pr_number is not None,
                "pr_number": pr_number,
                "blocked_by": row["blocked_by"],
                "milestone": row["milestone"],
                "roadmap": row["roadmap"],
                "priority": row["priority"],
                "labels": row["labels"],
            }

            if row["state"] == IssueState.READY:
                ready_issues_data.append(issue_data)
            else:
                other_issues_data.append(issue_data)

        # Sort ready issues and assign queue ranks
        sorted_ready_data = sort_ready_issue_dicts(ready_issues_data)

        other_issues_data.sort(
            key=lambda item: (
                *(
                    issue_priority(item["state"])
                    if isinstance(item["state"], IssueState)
                    else (4, "unknown")
                ),
                item["number"],
            )
        )

        # Combine: ready issues first, then others
        all_issues_data = sorted_ready_data + other_issues_data

        # Build final entries
        entries: list[IssueStatusEntry] = []
        for data in all_issues_data:
            entries.append(
                IssueStatusEntry(
                    number=data["number"],
                    title=data["title"],
                    state=data["state"],
                    assignee=data["assignee"],
                    has_flow=data["has_flow"],
                    flow_branch=data["flow_branch"],
                    has_worktree=data["has_worktree"],
                    worktree_path=data["worktree_path"],
                    has_pr=data["has_pr"],
                    pr_number=data["pr_number"],
                    blocked_by=data["blocked_by"],
                    milestone=data["milestone"],
                    roadmap=data["roadmap"],
                    priority=data["priority"],
                    queue_rank=data.get("queue_rank"),
                )
            )

        log.debug(f"Aggregated {len(entries)} entries, {active_flows} active flows")
        return tuple(entries)
