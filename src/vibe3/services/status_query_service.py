"""Status query service - aggregates GitHub/Git data for status dashboard.

Handles all external data fetching so the status command remains
a thin rendering layer.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestration import IssueState
from vibe3.orchestra.queue_ordering import (
    resolve_priority,
    resolve_roadmap_rank,
)

if TYPE_CHECKING:
    from vibe3.models.flow import FlowStatusResponse


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
    if state == IssueState.FAILED:
        return (3, state.value)
    return (4, state.value)


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
    ) -> None:
        self.github = github_client or GitHubClient()
        self.git = git_client or GitClient()
        self.repo = repo

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

        for item in raw_issues:
            number = item.get("number")
            if not isinstance(number, int):
                continue
            state = _state_from_labels(item.get("labels"))
            if state is None:
                continue
            if state == IssueState.DONE:
                continue
            flow = issue_to_flow.get(number)
            if flow and not is_orchestra_managed_flow_branch(flow.branch):
                continue
            failed_reason = (
                self._extract_failed_reason(number)
                if state == IssueState.FAILED
                else None
            )

            # Parse queue metadata from labels
            labels = [
                label.get("name", "")
                for label in item.get("labels", [])
                if isinstance(label, dict) and "name" in label
            ]

            # Extract milestone from GitHub milestone field
            milestone = None
            milestone_data = item.get("milestone")
            if isinstance(milestone_data, dict) and "title" in milestone_data:
                milestone = milestone_data["title"]

            # Resolve priority and roadmap
            priority = resolve_priority(labels)
            _, roadmap = resolve_roadmap_rank(labels)

            orchestrated_issues.append(
                {
                    "number": number,
                    "title": str(item.get("title") or ""),
                    "state": state,
                    "flow": flow,
                    "queued": number in queued_set,
                    "failed_reason": failed_reason,
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
            from vibe3.models.orchestration import IssueInfo
            from vibe3.orchestra.queue_ordering import sort_ready_issues

            ready_issue_infos = [
                IssueInfo(
                    number=cast(int, item["number"]),
                    title=cast(str, item["title"]),
                    state=cast(IssueState | None, item["state"]),
                    labels=cast(list[str], item["labels"]),
                    assignees=[],
                    milestone=cast(str | None, item["milestone"]),
                )
                for item in ready_issues
            ]
            sorted_ready_infos = sort_ready_issues(ready_issue_infos)

            # Build sorted ready issues with real queue ranks
            sorted_ready_issues = []
            for rank, issue_info in enumerate(sorted_ready_infos, start=1):
                matching_item = next(
                    (
                        item
                        for item in ready_issues
                        if item["number"] == issue_info.number
                    ),
                    None,
                )
                if matching_item:
                    matching_item["queue_rank"] = rank
                    sorted_ready_issues.append(matching_item)

            ready_issues = sorted_ready_issues

        # Sort other issues by operational urgency
        other_issues.sort(
            key=lambda item: (
                *issue_priority(cast(IssueState, item["state"])),
                cast(int, item["number"]),
            )
        )

        # Combine: ready issues first (sorted with real ranks), then others
        return ready_issues + other_issues

    def _extract_failed_reason(self, issue_number: int) -> str | None:
        """Extract a compact failure reason from issue comments."""
        issue = self.github.view_issue(issue_number, repo=self.repo)
        if not isinstance(issue, dict):
            return None

        comments = issue.get("comments")
        if not isinstance(comments, list):
            return None

        for comment in reversed(comments):
            if not isinstance(comment, dict):
                continue
            body = comment.get("body")
            if not isinstance(body, str):
                continue

            body_lower = body.lower()
            if (
                "[resume]" in body_lower
                or "[recovery]" in body_lower
                or "继续到 state/handoff" in body
                or "恢复到 state/handoff" in body
            ):
                continue

            match = re.search(r"(?:原因|reason)[:：\s]+(.*)", body, re.IGNORECASE)
            if match:
                reason = match.group(1).strip()
                if reason:
                    return reason.split("\n")[0].strip()

            if "failed" in body_lower or "error" in body_lower:
                return body.strip().split("\n")[0][:100]

        return None

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

            if state == IssueState.FAILED:
                # Failed issues are always resumable
                resumable.append({**issue, "resume_kind": "failed"})
            elif state == IssueState.BLOCKED:
                # Blocked issues are resumable only if flow is stale
                if flow is not None and hasattr(flow, "flow_status"):
                    if flow.flow_status == "stale":
                        resumable.append({**issue, "resume_kind": "blocked"})
            else:
                # For other states (READY, HANDOFF), check if flow is aborted
                if flow is not None and hasattr(flow, "flow_status"):
                    if flow.flow_status == "aborted":
                        resumable.append({**issue, "resume_kind": "aborted"})

        return resumable
