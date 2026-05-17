"""Branch naming convention models for profile-based configuration.

Implements the portability design by replacing hardcoded branch patterns
with configurable conventions that can vary by project profile.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class BranchConvention:
    """Branch naming convention for a project profile.

    Immutable configuration that defines how issue branches are named
    and parsed. Replaces hardcoded patterns like "task/issue-N" with
    profile-configurable conventions.

    Examples:
        >>> convention = BranchConvention.vibe_center()
        >>> convention.canonical_branch(123)
        'task/issue-123'
        >>> convention.parse_issue_number('dev/issue-456')
        456
    """

    task_prefix: str
    dev_prefix: str

    def canonical_branch(self, issue_number: int) -> str:
        """Return canonical task branch name.

        Args:
            issue_number: GitHub issue number

        Returns:
            Canonical branch name for this convention
        """
        return f"{self.task_prefix}{issue_number}"

    def dev_branch(self, issue_number: int) -> str:
        """Return development branch name.

        Args:
            issue_number: GitHub issue number

        Returns:
            Development branch name for this convention
        """
        return f"{self.dev_prefix}{issue_number}"

    def parse_issue_number(self, branch: str) -> int | None:
        """Extract issue number from task or dev branch.

        Args:
            branch: Git branch name

        Returns:
            Issue number if branch matches convention, None otherwise
        """
        pattern = (
            rf"^(?:{re.escape(self.task_prefix)}|{re.escape(self.dev_prefix)})(\d+)$"
        )
        match = re.fullmatch(pattern, branch)
        return int(match.group(1)) if match else None

    @classmethod
    def vibe_center(cls) -> "BranchConvention":
        """Vibe Center default convention.

        Used by the vibe-center profile with task/dev distinction.
        """
        return cls(task_prefix="task/issue-", dev_prefix="dev/issue-")

    @classmethod
    def minimal(cls) -> "BranchConvention":
        """Minimal convention for generic repos.

        Used by minimal/github-flow profiles without task/dev distinction.
        """
        return cls(task_prefix="issue-", dev_prefix="issue-")
