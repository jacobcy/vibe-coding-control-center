"""Status query service - aggregates GitHub/Git data for status dashboard.

Handles all external data fetching so the status command remains
a thin rendering layer.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, cast

from loguru import logger

from vibe3.clients import GitClient, GitHubClient, GitHubClientProtocol, SQLiteClient
from vibe3.models import IssueInfo, IssueState
from vibe3.utils import (
    resolve_priority,
    resolve_roadmap_rank,
    sort_ready_issues,
)

if TYPE_CHECKING:
    from vibe3.models import FlowStatusResponse


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


def issue_priority(state: IssueState | None) -> tuple[int, str]:
    """Sort orchestration issues by operational urgency."""
    if state is None:
        return (4, "")
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


def is_dev_collab_branch(branch: str | None) -> bool:
    """Check if branch follows the dev/issue-N human-collaboration pattern."""
    return isinstance(branch, str) and branch.startswith("dev/issue-")


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
        title_cache: object | None = None,
        store: SQLiteClient | None = None,
    ) -> None:
        self.github = github_client or GitHubClient()
        self.git = git_client or GitClient()
        self.repo = repo
        self.store = store or SQLiteClient()
        self._title_cache = title_cache

    @property
    def title_cache(self) -> object:
        """Lazy-initialized title cache service."""
        if self._title_cache is None:
            import importlib

            _mod = importlib.import_module("vibe3.services.issue.title_cache")
            self._title_cache = _mod.IssueTitleCacheService(self.store, self.github)
        return self._title_cache

    def fetch_orchestrated_issues(
        self,
        flows: list[FlowStatusResponse],
        queued_set: set[int],
        stale_flows: list[FlowStatusResponse] | None = None,
        manager_usernames: tuple[str, ...] | None = None,
        supervisor_label: str | None = None,
    ) -> list[dict[str, object]]:
        """Fetch GitHub issues and cross-reference with flow state.

        Args:
            flows: Active flow status responses
            queued_set: Set of issue numbers in the queue
            stale_flows: Stale flow status responses
            manager_usernames: Tuple of manager usernames for remote task detection
            supervisor_label: Supervisor label for dispatch exclusion reporting

        Returns:
            Sorted list of issue dicts with number, title, state, flow, queued, remote
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

        try:
            _collection_mod = importlib.import_module("vibe3.services.issue.collection")
            collected_issues = _collection_mod.IssueCollectionService(
                self.github,
                repo=self.repo,
            ).collect_open_issues(limit=100)
        except Exception as exc:
            logger.bind(domain="status").warning(f"Failed to fetch issues: {exc}")
            collected_issues = []

        _dispatch_mod = importlib.import_module("vibe3.services.issue.dispatch_policy")
        dispatch_policy = _dispatch_mod.IssueDispatchPolicy(
            supervisor_label=supervisor_label or "",
            manager_usernames=manager_usernames or (),
        )

        # Collect all branches from flows for cache lookup
        branches = [flow.branch for flow in flows if flow.branch]

        # Use cache service for titles (cache-first)
        branch_titles, _ = self.title_cache.get_titles_with_fallback(branches)  # type: ignore[attr-defined]

        # Batch fetch all open PRs through the shared PRService cache path.
        try:
            _pr_mod = importlib.import_module("vibe3.services.pr.service")
            branch_to_pr = _pr_mod.PRService(
                github_client=cast(GitHubClientProtocol, self.github),
                git_client=self.git,
                store=self.store,
            ).refresh_open_pr_cache()
        except Exception as exc:
            logger.bind(domain="status").warning(f"Failed to fetch PRs: {exc}")
            branch_to_pr = {}

        orchestrated_issues: list[dict[str, object]] = []
        for issue in collected_issues:
            number = issue.number
            state = issue.state
            # Note: IssueState.DONE is no longer skipped here.
            # It will be filtered at the UI layer or grouped into PR section.
            flow = issue_to_flow.get(number)
            if flow and not is_orchestra_managed_flow_branch(flow.branch):
                if not is_dev_collab_branch(flow.branch):
                    continue

            # Get blocked_by and blocked_reason from flow state
            blocked_by: tuple[int, ...] | None = None
            blocked_reason: str | None = None
            if state == IssueState.BLOCKED:
                if flow:
                    # Read from database instead of parsing issue body
                    blocked_by_issue = getattr(flow, "blocked_by_issue", None)
                    if blocked_by_issue:
                        blocked_by = (blocked_by_issue,)
                    blocked_reason = getattr(flow, "blocked_reason", None)
                elif issue.body:
                    # For remote BLOCKED issues, parse from issue body
                    _body_mod = importlib.import_module("vibe3.services.issue.body")
                    proj = _body_mod.parse_projection(issue.body)
                    if proj.blocked_by:
                        blocked_by = tuple(proj.blocked_by)
                    blocked_reason = proj.blocked_reason

            labels = list(issue.labels)
            milestone = issue.milestone
            priority = resolve_priority(labels)
            _, roadmap = resolve_roadmap_rank(labels)
            assignee = issue.assignees[0] if issue.assignees else None
            exclusion_reasons = dispatch_policy.exclusion_reasons(issue)
            exclusion_codes = [reason.code for reason in exclusion_reasons]
            exclusion_messages = [reason.message for reason in exclusion_reasons]

            # Get title from cache (using branch) or fall back to API title
            if flow:
                title = branch_titles.get(flow.branch) or issue.title
            else:
                # Fallback to the collected issue title
                title = issue.title

            # Get PR data from batch query
            pr_number = None
            pr_state = None
            if flow:
                pr = branch_to_pr.get(flow.branch)
                if pr:
                    pr_number = pr.number
                    pr_state = pr.state.value

            # Calculate remote flag: issue claimed by manager but no local flow
            # Blocked issues are not remote — they display in Blocked Issues section
            is_remote = (
                state
                in {
                    IssueState.CLAIMED,
                    IssueState.IN_PROGRESS,
                    IssueState.HANDOFF,
                    IssueState.REVIEW,
                    IssueState.MERGE_READY,
                }
                and assignee is not None
                and assignee in (manager_usernames or [])
                and flow is None
            )

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
                    "dispatch_exclusion_codes": exclusion_codes,
                    "dispatch_exclusion_messages": exclusion_messages,
                    # Remote task flag
                    "remote": is_remote,
                    # Issue body for dependency parsing
                    "body": issue.body,
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
                *issue_priority(cast(IssueState | None, item["state"])),
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
            and resume_kind ("failed", "blocked", or "aborted")
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
