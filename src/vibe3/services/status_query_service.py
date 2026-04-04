"""Status query service - aggregates GitHub/Git data for status dashboard.

Handles all external data fetching so the status command remains
a thin rendering layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestration import IssueState

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
    return branch.startswith("task/issue-")


def is_canonical_task_branch(branch: str, task_issue_number: int | None) -> bool:
    """Check if branch matches the canonical task/issue-N pattern."""
    return task_issue_number is not None and branch == f"task/issue-{task_issue_number}"


class StatusQueryService:
    """Aggregates GitHub/Git data for the status dashboard.

    Fetches issues, builds worktree maps, and returns structured
    data ready for rendering by the command layer.
    """

    def __init__(
        self,
        github_client: GitHubClient | None = None,
        git_client: GitClient | None = None,
    ) -> None:
        self.github = github_client or GitHubClient()
        self.git = git_client or GitClient()

    def fetch_orchestrated_issues(
        self,
        flows: list[FlowStatusResponse],
        queued_set: set[int],
    ) -> list[dict[str, object]]:
        """Fetch GitHub issues and cross-reference with flow state.

        Args:
            flows: Active flow status responses
            queued_set: Set of issue numbers in the queue

        Returns:
            Sorted list of issue dicts with number, title, state, flow, queued
        """
        from typing import cast

        issue_to_flow = {f.task_issue_number: f for f in flows if f.task_issue_number}

        orchestrated_issues: list[dict[str, object]] = []
        try:
            raw_issues = self.github.list_issues(limit=100, state="open", assignee=None)
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
            orchestrated_issues.append(
                {
                    "number": number,
                    "title": str(item.get("title") or ""),
                    "state": state,
                    "flow": flow,
                    "queued": number in queued_set,
                }
            )

        orchestrated_issues.sort(
            key=lambda item: (
                *issue_priority(cast(IssueState, item["state"])),
                cast(int, item["number"]),
            )
        )
        return orchestrated_issues

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
