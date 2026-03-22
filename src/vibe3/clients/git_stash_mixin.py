"""Git client stash operations."""

from loguru import logger

from vibe3.exceptions import GitError


class GitStashMixin:
    """Mixin for stash operations."""

    def _run(self, args: list[str]) -> str:
        """Execute git command (implemented in main GitClient)."""
        raise NotImplementedError

    def stash_push(self, message: str | None = None) -> str:
        """Stash current changes.

        Args:
            message: Optional message for the stash

        Returns:
            Stash reference (e.g., "stash@{0}")

        Raises:
            GitError: Stash operation failed
        """
        logger.bind(
            domain="git",
            action="stash_push",
            message=message,
        ).info("Stashing changes")

        args = ["stash", "push"]
        if message:
            args.extend(["-m", message])

        self._run(args)

        # Get the stash reference (most recent stash)
        stash_list = self._run(["stash", "list"])
        if not stash_list:
            raise GitError("stash_push", "No stash created")

        stash_ref = stash_list.splitlines()[0].split(":")[0]
        logger.bind(stash_ref=stash_ref).success("Changes stashed successfully")
        return stash_ref

    def stash_apply(self, stash_ref: str) -> None:
        """Apply and drop a stash.

        Args:
            stash_ref: Stash reference (e.g., "stash@{0}")

        Raises:
            GitError: Stash apply failed
        """
        logger.bind(
            domain="git",
            action="stash_apply",
            stash_ref=stash_ref,
        ).info("Applying stash")

        self._run(["stash", "apply", stash_ref])
        self._run(["stash", "drop", stash_ref])

        logger.bind(stash_ref=stash_ref).success(
            "Stash applied and dropped successfully"
        )
