"""Status query service - aggregates GitHub/Git data for status dashboard.

Handles all external data fetching so the status command remains
a thin rendering layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.queue_ordering import (
    resolve_priority,
    resolve_roadmap_rank,
    sort_ready_issues,
)

if TYPE_CHECKING:
    from vibe3.models.flow import FlowStatusResponse
    from vibe3.services.issue_title_cache_service import IssueTitleCacheService


def _state_from_labels(raw_labels: object) -> IssueState | None:
    """Extract orchestration state from GitHub label payload."""
    if not isinstance(raw_labels, list):
        return None
    for item in raw_labels:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str):
            continue
        parsed = IssueState.from_label(name)
        if parsed is not None:
            return parsed
    return None


def extract_issue_labels(raw_labels: object) -> list[str]:
    """Extract plain label names from GitHub issue payload."""
    if not isinstance(raw_labels, list):
        return []
    return [
        label.get("name", "")
        for label in raw_labels
        if isinstance(label, dict) and "name" in label
    ]


def extract_milestone_title(raw_milestone: object) -> str | None:
    """Extract milestone title from GitHub milestone payload."""
    if isinstance(raw_milestone, dict) and "title" in raw_milestone:
        title = raw_milestone["title"]
        if isinstance(title, str) and title.strip():
            return title
    return None


def extract_queue_metadata(
    raw_labels: object,
    raw_milestone: object,
) -> tuple[list[str], str | None, int, str | None]:
    """Extract shared queue metadata fields from GitHub payload."""
    labels = extract_issue_labels(raw_labels)
    milestone = extract_milestone_title(raw_milestone)
    priority = resolve_priority(labels)
    _, roadmap = resolve_roadmap_rank(labels)
    return labels, milestone, priority, roadmap


def issue_priority(state: IssueState) -> tuple[int, str]:
    """Sort orchestration issues by operational urgency."""
    if state in {
        IssueState.IN_PROGRESS,
        IssueState.REVIEW,
        IssueState.HANDOFF,
        IssueState.CLAIMED,
    }:
        return (0, state.value)
    if state == IssueState.READY:
        return (1, state.value)
    if state == IssueState.BLOCKED:
        return (2, state.value)
    return (3, state.value)


def is_auto_task_branch(branch: str) -> bool:
    """Check if branch follows auto-managed task naming convention.

    Pure string check without SQLite I/O side effects.
    """
    return branch.startswith("task/issue-")


def is_canonical_task_branch(branch: str, task_issue_number: int | None) -> bool:
    """Check if branch matches the canonical task/issue-N pattern.

    Pure string check without SQLite I/O side effects.
    """
    return task_issue_number is not None and branch == f"task/issue-{task_issue_number}"


def is_orchestra_managed_flow_branch(branch: str | None) -> bool:
    """Whether a flow branch belongs to orchestra-managed auto task scenes."""
    return isinstance(branch, str) and is_auto_task_branch(branch)


def extract_primary_assignee_login(raw_assignees: object) -> str | None:
    """Extract the primary manager assignee login from GitHub payload."""
    if not isinstance(raw_assignees, list):
        return None

    for assignee in raw_assignees:
        if not isinstance(assignee, dict):
            continue
        login = assignee.get("login")
        if isinstance(login, str) and login.strip():
            return login.strip()
    return None


def sort_ready_issue_dicts(
    ready_issues: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Sort READY issue dicts and attach queue ranks."""
    ready_issue_infos = [
        IssueInfo(
            number=cast(int, item["number"]),
            title=cast(str, item["title"]),
            state=cast(IssueState | None, item["state"]),
            labels=cast(list[str], item["labels"]),
            assignees=[cast(str, item["assignee"])] if item.get("assignee") else [],
            milestone=cast(str | None, item["milestone"]),
        )
        for item in ready_issues
    ]
    sorted_ready_infos = sort_ready_issues(ready_issue_infos)

    sorted_ready_issues: list[dict[str, object]] = []
    for rank, issue_info in enumerate(sorted_ready_infos, start=1):
        matching_item = next(
            (item for item in ready_issues if item["number"] == issue_info.number),
            None,
        )
        if matching_item:
            sorted_ready_issues.append({**matching_item, "queue_rank": rank})
    return sorted_ready_issues


def _select_preferred_issue_flow(
    existing: FlowStatusResponse | None,
    candidate: FlowStatusResponse,
) -> FlowStatusResponse:
    """Choose the preferred flow for issue aggregation.

    Priority order:
    1. Orchestra-managed flow over manual flow
    2. Active flow over stale/done flow
    3. Keep existing on ties to preserve first-seen stability
    """
    if existing is None:
        return candidate

    existing_managed = is_orchestra_managed_flow_branch(existing.branch)
    candidate_managed = is_orchestra_managed_flow_branch(candidate.branch)
    if candidate_managed != existing_managed:
        return candidate if candidate_managed else existing

    existing_active = existing.flow_status == "active"
    candidate_active = candidate.flow_status == "active"
    if candidate_active != existing_active:
        return candidate if candidate_active else existing

    return existing


class StatusQueryService:
    """Aggregates GitHub/Git data for the status dashboard.

    Fetches issues, builds worktree maps, and returns structured
    data ready for rendering by the command layer.
    """

    def __init__(
        self,
        github_client: GitHubClient | None = None,
        git_client: GitClient | None = None,
        repo: str | None = None,
        title_cache: IssueTitleCacheService | None = None,
        store: SQLiteClient | None = None,
    ) -> None:
        self.github = github_client or GitHubClient()
        self.git = git_client or GitClient()
        self.repo = repo
        self.store = store or SQLiteClient()
        self._title_cache = title_cache

    @property
    def title_cache(self) -> IssueTitleCacheService:
        """Lazy-initialized title cache service."""
        if self._title_cache is None:
            from vibe3.services.issue_title_cache_service import IssueTitleCacheService

            self._title_cache = IssueTitleCacheService(self.store, self.github)
        return self._title_cache

    def fetch_orchestrated_issues(
        self,
        flows: list[FlowStatusResponse],
        queued_set: set[int],
        stale_flows: list[FlowStatusResponse] | None = None,
    ) -> list[dict[str, object]]:
        """Fetch GitHub issues and cross-reference with flow state.

        Args:
            flows: Active flow status responses
            queued_set: Set of issue numbers in the queue
            stale_flows: Stale flow status responses

        Returns:
            Sorted list of issue dicts with number, title, state, flow, queued
        """

        # stale flows first, active flows overwrite (active priority)
        issue_to_flow: dict[int, FlowStatusResponse] = {}
        for f in stale_flows or []:
            if f.task_issue_number:
                issue_to_flow[f.task_issue_number] = _select_preferred_issue_flow(
                    issue_to_flow.get(f.task_issue_number),
                    f,
                )
        for f in flows:
            if f.task_issue_number:
                issue_to_flow[f.task_issue_number] = _select_preferred_issue_flow(
                    issue_to_flow.get(f.task_issue_number),
                    f,
                )

        orchestrated_issues: list[dict[str, object]] = []
        try:
            raw_issues = self.github.list_issues(
                limit=100,
                state="open",
                assignee=None,
                repo=self.repo,
            )
        except Exception as exc:
            logger.bind(domain="status").warning(f"Failed to fetch issues: {exc}")
            raw_issues = []

        # Collect all branches from flows for cache lookup
        branches = [flow.branch for flow in flows if flow.branch]

        # Use cache service for titles (cache-first)
        branch_titles, _ = self.title_cache.get_titles_with_fallback(branches)

        # Batch fetch all PRs (optimization: 1 call instead of N)
        try:
            all_prs = self.github.list_all_prs(state="open")
            branch_to_pr = {pr.head_branch: pr for pr in all_prs}
        except Exception as exc:
            logger.bind(domain="status").warning(f"Failed to fetch PRs: {exc}")
            branch_to_pr = {}

        for item in raw_issues:
            number = item.get("number")
            if not isinstance(number, int):
                continue
            state = _state_from_labels(item.get("labels"))
            if state is None:
                continue
            # Note: IssueState.DONE is no longer skipped here.
            # It will be filtered at the UI layer or grouped into PR section.
            flow = issue_to_flow.get(number)
            if flow and not is_orchestra_managed_flow_branch(flow.branch):
                continue

            # Get blocked_by and blocked_reason from flow state
            # (Note: failed_reason is deprecated, now unified to blocked_reason)
            blocked_by = None
            blocked_reason = None
            if state == IssueState.BLOCKED and flow:
                # Read from database instead of parsing issue body
                blocked_by_issue = getattr(flow, "blocked_by_issue", None)
                if blocked_by_issue:
                    blocked_by = (blocked_by_issue,)
                blocked_reason = getattr(flow, "blocked_reason", None)

            labels, milestone, priority, roadmap = extract_queue_metadata(
                item.get("labels"),
                item.get("milestone"),
            )
            assignee = extract_primary_assignee_login(item.get("assignees"))

            # Get title from cache (using branch) or fall back to API title
            if flow:
                title = branch_titles.get(flow.branch) or str(item.get("title") or "")
            else:
                # Fallback to API title
                title = str(item.get("title") or "")

            # Get PR data from batch query
            pr_number = None
            pr_state = None
            if flow:
                pr = branch_to_pr.get(flow.branch)
                if pr:
                    pr_number = pr.number
                    pr_state = pr.state.value

            orchestrated_issues.append(
                {
                    "number": number,
                    "title": title,
                    "state": state,
                    "assignee": assignee,
                    "flow": flow,
                    "queued": number in queued_set,
                    "blocked_by": blocked_by,
                    "blocked_reason": blocked_reason,
                    # PR data
                    "pr_number": pr_number,
                    "pr_state": pr_state,
                    # Queue metadata
                    "milestone": milestone,
                    "roadmap": roadmap,
                    "priority": priority,
                    "labels": labels,
                }
            )

        # Sort issues: READY issues use queue ordering, others use issue_priority
        ready_issues = [
            item for item in orchestrated_issues if item["state"] == IssueState.READY
        ]
        other_issues = [
            item for item in orchestrated_issues if item["state"] != IssueState.READY
        ]

        # Sort ready issues using queue ordering rules and assign real queue ranks
        if ready_issues:
            ready_issues = sort_ready_issue_dicts(ready_issues)

        # Sort other issues by operational urgency
        other_issues.sort(
            key=lambda item: (
                *issue_priority(cast(IssueState, item["state"])),
                cast(int, item["number"]),
            )
        )

        # Combine: ready issues first (sorted with real ranks), then others
        return ready_issues + other_issues

    def fetch_worktree_map(self) -> dict[str, str]:
        """Get worktree branch-to-directory mapping.

        Returns:
            Dict mapping branch names to worktree directory names
        """
        worktree_map: dict[str, str] = {}
        try:
            worktree_output = self.git._run(["worktree", "list", "--porcelain"])
            current_worktree = ""
            for line in worktree_output.splitlines():
                line = line.strip()
                if line.startswith("worktree "):
                    current_worktree = line.split(" ", 1)[1]
                elif line.startswith("branch ") and current_worktree:
                    branch_ref = line.split(" ", 1)[1]
                    branch = branch_ref.removeprefix("refs/heads/")
                    worktree_map[branch] = current_worktree.split("/")[-1]
        except Exception:
            pass
        return worktree_map

    def fetch_resume_candidates(
        self,
        flows: list[FlowStatusResponse],
        stale_flows: list[FlowStatusResponse] | None = None,
    ) -> list[dict[str, object]]:
        """Fetch resumable issue candidates (failed + stale blocked + aborted).

        Reuses fetch_orchestrated_issues() and filters for resumable states.
        Adds resume_kind field to distinguish failed vs blocked vs aborted recovery.

        Args:
            flows: Active flow status responses to cross-reference
            stale_flows: Stale flow status responses for blocked recovery

        Returns:
            List of resumable issue dicts with number, title, state, flow,
            failed_reason (if applicable), and resume_kind ("failed",
            "blocked", or "aborted")
        """
        all_issues = self.fetch_orchestrated_issues(
            flows, queued_set=set(), stale_flows=stale_flows
        )

        resumable: list[dict[str, object]] = []
        for issue in all_issues:
            state = issue.get("state")
            flow = issue.get("flow")

            if state == IssueState.BLOCKED:
                # Blocked issues are resumable only if flow is stale or aborted
                if flow is not None and hasattr(flow, "flow_status"):
                    if flow.flow_status in ("stale", "aborted"):
                        resumable.append({**issue, "resume_kind": "blocked"})
            else:
                # For other states (READY, HANDOFF), check if flow is aborted
                if flow is not None and hasattr(flow, "flow_status"):
                    if flow.flow_status == "aborted":
                        resumable.append({**issue, "resume_kind": "aborted"})

        return resumable
