"""Status query service - aggregates GitHub/Git data for status dashboard.

Handles all external data fetching so the status command remains
a thin rendering layer.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestration import IssueState
from vibe3.services.issue_flow_service import IssueFlowService

if TYPE_CHECKING:
    from vibe3.services.flow_service import FlowStatusResponse


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
    """Check if branch follows auto-managed task naming convention."""
    return IssueFlowService().is_task_branch(branch)


def is_canonical_task_branch(branch: str, task_issue_number: int | None) -> bool:
    """Check if branch matches the canonical task/issue-N pattern."""
    return IssueFlowService().is_canonical_task_branch(branch, task_issue_number)


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
        from typing import cast

        # stale flows first, active flows overwrite (active priority)
        issue_to_flow: dict[int, FlowStatusResponse] = {}
        for f in stale_flows or []:
            if f.task_issue_number:
                issue_to_flow[f.task_issue_number] = f
        for f in flows:
            if f.task_issue_number:
                issue_to_flow[f.task_issue_number] = f

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
            failed_reason = (
                self._extract_failed_reason(number)
                if state == IssueState.FAILED
                else None
            )
            orchestrated_issues.append(
                {
                    "number": number,
                    "title": str(item.get("title") or ""),
                    "state": state,
                    "flow": flow,
                    "queued": number in queued_set,
                    "failed_reason": failed_reason,
                }
            )

        orchestrated_issues.sort(
            key=lambda item: (
                *issue_priority(cast(IssueState, item["state"])),
                cast(int, item["number"]),
            )
        )
        return orchestrated_issues

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
            if "[recovery]" in body_lower or "恢复到 state/handoff" in body:
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
