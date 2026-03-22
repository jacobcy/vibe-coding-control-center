"""Git client utility operations."""

from vibe3.exceptions import GitError


class GitUtilityMixin:
    """Mixin for utility operations."""

    def _run(self, args: list[str]) -> str:
        """Execute git command (implemented in main GitClient)."""
        raise NotImplementedError

    def has_uncommitted_changes(self) -> bool:
        """Check if working directory has uncommitted changes.

        Returns:
            True if there are uncommitted changes, False otherwise
        """
        try:
            # Check for staged changes
            staged = self._run(["diff", "--quiet", "--cached"])
            if staged:  # Non-empty output means there are staged changes
                return True
        except GitError:
            # diff --quiet returns non-zero if there are differences
            return True

        try:
            # Check for unstaged changes
            unstaged = self._run(["diff", "--quiet"])
            if unstaged:  # Non-empty output means there are unstaged changes
                return True
        except GitError:
            # diff --quiet returns non-zero if there are differences
            return True

        return False

    def branch_exists(self, branch_name: str) -> bool:
        """Check if a branch exists (local or remote).

        Args:
            branch_name: Name of the branch to check

        Returns:
            True if branch exists, False otherwise
        """
        try:
            # Check local branches
            local_branches = self._run(["branch", "--list", branch_name])
            if branch_name in local_branches:
                return True

            # Check remote branches
            remote_branch = f"origin/{branch_name}"
            remote_branches = self._run(["branch", "-r", "--list", remote_branch])
            if remote_branch in remote_branches:
                return True

            return False
        except GitError:
            return False
