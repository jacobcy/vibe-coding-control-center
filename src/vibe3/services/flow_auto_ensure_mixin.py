"""Flow auto-ensure mixin for automatic flow creation."""

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.models.flow import FlowState, MainBranchProtectedError


class FlowAutoEnsureMixin:
    """Mixin for auto-ensuring flow existence."""

    store: SQLiteClient
    config: VibeConfig

    def _is_main_branch(self, branch: str) -> bool:
        """Check if branch is a protected main branch.

        Args:
            branch: Branch name to check

        Returns:
            True if branch is protected
        """
        # Check against configured protected branches
        protected = self.config.flow.protected_branches

        # Direct match
        if branch in protected:
            return True

        # Check for remote tracking branches (origin/main, etc.)
        for protected_branch in protected:
            if branch == f"origin/{protected_branch}":
                return True

        return False

    def ensure_flow_for_branch(self, branch: str, slug: str | None = None) -> FlowState:
        """Ensure flow exists for branch, creating if needed.

        Args:
            branch: Git branch name
            slug: Optional flow slug (defaults to derived from branch)

        Returns:
            Existing or newly created FlowState

        Raises:
            MainBranchProtectedError: If branch is main/master
        """
        # Import here to avoid circular dependency
        from vibe3.services.flow_service import FlowService

        # Ensure self is a FlowService instance
        if not isinstance(self, FlowService):
            raise TypeError("FlowAutoEnsureMixin must be used with FlowService")

        # Guard against main branch
        if self._is_main_branch(branch):
            raise MainBranchProtectedError(
                f"Cannot create flow on protected branch '{branch}'. "
                "Switch to a feature branch first."
            )

        # Check if flow already exists
        existing = self.get_flow_status(branch)
        if existing:
            logger.bind(
                domain="flow",
                action="ensure",
                branch=branch,
                existing=True,
            ).debug("Flow already exists")
            return FlowState(**existing.model_dump())

        # Generate slug from branch if not provided
        if not slug:
            # Extract branch name after slash (task/my-feature -> my_feature)
            parts = branch.split("/")
            branch_name = parts[-1] if len(parts) > 1 else branch
            slug = branch_name.replace("-", "_")

        # Create new flow
        logger.bind(
            domain="flow",
            action="ensure",
            branch=branch,
            slug=slug,
            existing=False,
        ).info("Creating flow via ensure")

        return self.create_flow(slug=slug, branch=branch)
