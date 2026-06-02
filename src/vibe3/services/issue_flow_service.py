"""Centralized branch naming and issue-to-flow mapping service."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from vibe3.clients import SQLiteClient

if TYPE_CHECKING:
    from vibe3.services.convention_resolver import ConventionResolver


def _default_store() -> SQLiteClient:
    """Default factory for store."""
    return SQLiteClient()


def _default_resolver() -> "ConventionResolver":
    """Default factory for resolver."""
    from vibe3.services.convention_resolver import ConventionResolver

    return ConventionResolver.from_repo()


@dataclass
class IssueFlowService:
    """Centralized service for task branch naming and issue-to-flow mapping.

    Refactored to use ConventionResolver instead of hardcoded patterns.

    Provides consistent methods for:
    - Canonical branch name generation (via convention)
    - Issue number parsing from branch names (via convention)
    - Active flow lookup for issues

    This consolidates logic that was previously scattered across:
    - FlowManager._canonical_task_branch()
    - StatusQueryService.is_task_branch() / is_canonical_task_branch()
    - Various regex patterns in manager, orchestra, and services
    """

    store: SQLiteClient = field(default_factory=_default_store)
    resolver: "ConventionResolver" = field(default_factory=_default_resolver)

    def canonical_branch_name(self, issue_number: int) -> str:
        """Return canonical task branch name.

        Args:
            issue_number: GitHub issue number

        Returns:
            Canonical branch name according to convention

        Example:
            >>> service.canonical_branch_name(372)
            "task/issue-372"
        """
        convention = self.resolver.resolve()
        return convention.branch.canonical_branch(issue_number)

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
        convention = self.resolver.resolve()
        # For strict canonical matching, check if it matches task prefix exactly
        task_prefix = convention.branch.task_prefix
        if not branch.startswith(task_prefix):
            return None
        # Delegate to convention's parsing
        return convention.branch.parse_issue_number(branch)

    def parse_issue_number_any(self, branch: str) -> int | None:
        """Extract issue number from task or dev issue branch.

        Supports both:
        - task/issue-N (canonical task branch)
        - dev/issue-N (development branch)

        Args:
            branch: Git branch name

        Returns:
            Issue number if branch matches pattern, None otherwise

        Examples:
            >>> service.parse_issue_number_any("task/issue-436")
            436
            >>> service.parse_issue_number_any("dev/issue-328")
            328
            >>> service.parse_issue_number_any("feature/my-feature")
            None
        """
        convention = self.resolver.resolve()
        return convention.branch.parse_issue_number(branch)

    def is_issue_branch(self, branch: str) -> bool:
        """Check if branch is an issue branch (task/issue-N or dev/issue-N).

        Args:
            branch: Git branch name

        Returns:
            True if branch matches issue pattern, False otherwise

        Example:
            >>> service.is_issue_branch("task/issue-372")
            True
            >>> service.is_issue_branch("dev/issue-328")
            True
            >>> service.is_issue_branch("feature/my-feature")
            False
        """
        convention = self.resolver.resolve()
        return convention.branch.parse_issue_number(branch) is not None

    def is_task_branch(self, branch: str) -> bool:
        """Check if branch is a task branch (starts with task prefix).

        Args:
            branch: Git branch name

        Returns:
            True if branch starts with task prefix, False otherwise

        Example:
            >>> service.is_task_branch("task/issue-372")
            True
            >>> service.is_task_branch("task/issue-372-worktree")
            True
            >>> service.is_task_branch("dev/feature")
            False
        """
        convention = self.resolver.resolve()
        return branch.startswith(convention.branch.task_prefix)

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

    def resolve_task_issue_number(self, branch: str) -> int | None:
        """Resolve task issue number from branch using unified two-tier logic.

        Resolution order:
        1. DB flow_issue_links table (via store.get_task_issue_number)
        2. Branch name parsing (via parse_issue_number_any)

        Args:
            branch: Git branch name

        Returns:
            Issue number if found, None otherwise

        Example:
            >>> service.resolve_task_issue_number("task/issue-372")
            372
            >>> service.resolve_task_issue_number("dev/issue-123")
            123
            >>> service.resolve_task_issue_number("feature/my-branch")
            None
        """
        # Tier 1: Try DB links first (most reliable)
        issue_num = self.store.get_task_issue_number(branch)
        if issue_num is not None:
            return issue_num

        # Tier 2: Fallback to branch name parsing
        return self.parse_issue_number_any(branch)
