"""Centralized branch naming and issue-to-flow mapping service."""

import re

from vibe3.clients.sqlite_client import SQLiteClient


class IssueFlowService:
    """Centralized service for task branch naming and issue-to-flow mapping.

    Provides consistent methods for:
    - Canonical branch name generation (task/issue-N)
    - Issue number parsing from branch names
    - Active flow lookup for issues

    This consolidates logic that was previously scattered across:
    - FlowManager._canonical_task_branch()
    - StatusQueryService.is_task_branch() / is_canonical_task_branch()
    - Various regex patterns in manager, orchestra, and services
    """

    CANONICAL_PATTERN = re.compile(r"^task/issue-(\d+)$")

    def __init__(self, store: SQLiteClient | None = None) -> None:
        """Initialize IssueFlowService.

        Args:
            store: SQLiteClient instance for flow queries
        """
        self.store = store or SQLiteClient()

    def canonical_branch_name(self, issue_number: int) -> str:
        """Return canonical task branch name.

        Args:
            issue_number: GitHub issue number

        Returns:
            Canonical branch name (task/issue-{issue_number})

        Example:
            >>> service.canonical_branch_name(372)
            "task/issue-372"
        """
        return f"task/issue-{issue_number}"

    def parse_issue_number(self, branch: str) -> int | None:
        """Extract issue number from canonical task branch.

        Args:
            branch: Git branch name

        Returns:
            Issue number if branch is canonical task branch, None otherwise

        Examples:
            >>> service.parse_issue_number("task/issue-372")
            372
            >>> service.parse_issue_number("dev/feature-123")
            None
            >>> service.parse_issue_number("task/issue-372-worktree")
            None
        """
        match = self.CANONICAL_PATTERN.fullmatch(branch)
        return int(match.group(1)) if match else None

    def is_task_branch(self, branch: str) -> bool:
        """Check if branch is a task branch (starts with task/issue-).

        Args:
            branch: Git branch name

        Returns:
            True if branch starts with 'task/issue-', False otherwise

        Example:
            >>> service.is_task_branch("task/issue-372")
            True
            >>> service.is_task_branch("task/issue-372-worktree")
            True
            >>> service.is_task_branch("dev/feature")
            False
        """
        return branch.startswith("task/issue-")

    def is_canonical_task_branch(
        self, branch: str, task_issue_number: int | None
    ) -> bool:
        """Check if branch is the canonical task branch for a given issue.

        Args:
            branch: Git branch name
            task_issue_number: Issue number to match against

        Returns:
            True if branch matches canonical pattern for the issue, False otherwise

        Example:
            >>> service.is_canonical_task_branch("task/issue-372", 372)
            True
            >>> service.is_canonical_task_branch("task/issue-372-worktree", 372)
            False
            >>> service.is_canonical_task_branch("task/issue-372", 999)
            False
        """
        return task_issue_number is not None and branch == self.canonical_branch_name(
            task_issue_number
        )

    def find_active_flow(self, issue_number: int) -> dict | None:
        """Find active flow for an issue with deterministic selection.

        Priority order:
        1. Active canonical flow (task/issue-N)
        2. Active non-canonical flow
        3. First available flow (fallback)

        Args:
            issue_number: GitHub issue number

        Returns:
            Flow state dict if found, None otherwise

        Note:
            This wraps SQLiteClient.get_flows_by_issue with priority logic.
        """
        flows = self.store.get_flows_by_issue(issue_number, role="task")
        if not flows:
            return None

        canonical_branch = self.canonical_branch_name(issue_number)

        # Priority 1: Active canonical flow
        for flow in flows:
            branch = str(flow.get("branch") or "").strip()
            status = str(flow.get("flow_status") or "active")
            if branch == canonical_branch and status == "active":
                return flow

        # Priority 2: Active non-canonical flow
        for flow in flows:
            status = str(flow.get("flow_status") or "active")
            if status == "active":
                return flow

        # Priority 3: First available (fallback)
        return flows[0]
