"""Git client branch management operations."""

from loguru import logger


class GitBranchMixin:
    """Mixin for branch management operations."""

    def _run(self, args: list[str]) -> str:
        """Execute git command (implemented in main GitClient)."""
        raise NotImplementedError

    def create_branch(self, branch_name: str, start_ref: str = "origin/main") -> None:
        """Create a new branch from start_ref.

        Args:
            branch_name: Name of the new branch
            start_ref: Starting point for the new branch (default: origin/main)

        Raises:
            GitError: Branch creation failed
        """
        logger.bind(
            domain="git",
            action="create_branch",
            branch=branch_name,
            start_ref=start_ref,
        ).info("Creating branch")

        self._run(["checkout", "-b", branch_name, start_ref])

        logger.bind(branch=branch_name).success("Branch created successfully")

    def switch_branch(self, branch_name: str) -> None:
        """Switch to an existing branch.

        Args:
            branch_name: Name of the branch to switch to

        Raises:
            GitError: Branch switch failed
        """
        logger.bind(
            domain="git",
            action="switch_branch",
            branch=branch_name,
        ).info("Switching branch")

        self._run(["checkout", branch_name])

        logger.bind(branch=branch_name).success("Switched to branch successfully")

    def delete_branch(self, branch_name: str, force: bool = False) -> None:
        """Delete a local branch.

        Args:
            branch_name: Name of the branch to delete
            force: Force delete unmerged branches

        Raises:
            GitError: Branch deletion failed
        """
        logger.bind(
            domain="git",
            action="delete_branch",
            branch=branch_name,
            force=force,
        ).info("Deleting branch")

        args = ["branch", "-D" if force else "-d", branch_name]
        self._run(args)

        logger.bind(branch=branch_name).success("Branch deleted successfully")

    def delete_remote_branch(self, branch_name: str) -> None:
        """Delete a remote branch.

        Args:
            branch_name: Name of the remote branch to delete
                (without remote prefix)

        Raises:
            GitError: Remote branch deletion failed
        """
        logger.bind(
            domain="git",
            action="delete_remote_branch",
            branch=branch_name,
        ).info("Deleting remote branch")

        self._run(["push", "origin", "--delete", branch_name])

        logger.bind(branch=branch_name).success("Remote branch deleted successfully")
