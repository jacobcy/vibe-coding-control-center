"""Flow service lifecycle operations."""

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.exceptions import UserError
from vibe3.models.flow import FlowState

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient


class FlowLifecycleService:
    """Service for flow lifecycle operations."""

    def __init__(
        self,
        store: SQLiteClient,
        git_client: "GitClient",
    ) -> None:
        """Initialize flow lifecycle service.

        Args:
            store: SQLiteClient instance
            git_client: GitClient instance
        """
        self.store = store
        self.git = git_client

    def create_flow_with_branch(
        self,
        slug: str,
        start_ref: str = "origin/main",
        save_unstash: bool = False,
    ) -> FlowState:
        """Create a new flow with a new branch.

        Args:
            slug: Flow name/slug
            start_ref: Starting point for the new branch
                (default: origin/main)
            save_unstash: If True, stash current changes and restore them
                after branch creation

        Returns:
            Created flow state

        Raises:
            UserError: Branch already exists or dirty worktree without save_unstash
        """
        logger.bind(
            domain="flow",
            action="create_with_branch",
            slug=slug,
            start_ref=start_ref,
            save_unstash=save_unstash,
        ).info("Creating flow with branch")

        # Generate branch name from slug
        branch_name = f"task/{slug}"

        # Check if branch already exists
        if self.git.branch_exists(branch_name):
            raise UserError(
                message=f"Branch '{branch_name}' already exists. "
                "Use 'flow switch' to switch to an existing flow."
            )

        # Check for uncommitted changes
        has_changes = self.git.has_uncommitted_changes()
        stash_ref = None

        if has_changes and not save_unstash:
            raise UserError(
                message="Working directory has uncommitted changes. "
                "Use --save-unstash to stash and restore them."
            )

        # Stash changes if requested
        if save_unstash and has_changes:
            stash_ref = self.git.stash_push(
                message=f"Auto-stash before creating {branch_name}"
            )

        try:
            # Create branch
            self.git.create_branch(branch_name, start_ref)

            # Create flow in database
            self.store.update_flow_state(branch_name, flow_slug=slug)
            self.store.add_event(
                branch_name,
                "flow_created",
                "system",
                f"Flow '{slug}' created",
            )

            # Restore stashed changes
            if stash_ref:
                self.git.stash_apply(stash_ref)

            logger.bind(branch=branch_name).success(
                "Flow with branch created successfully"
            )

            flow_data = self.store.get_flow_state(branch_name)
            if not flow_data:
                raise RuntimeError(f"Failed to create flow for branch {branch_name}")
            return FlowState(**flow_data)

        except Exception:
            # Restore stash on failure
            if stash_ref:
                try:
                    self.git.stash_apply(stash_ref)
                except Exception:
                    logger.error("Failed to restore stash after error")

            raise

    def switch_flow(self, target: str) -> FlowState:
        """Switch to an existing flow.

        Args:
            target: Branch name or flow slug

        Returns:
            Target flow state

        Raises:
            UserError: Target flow/branch not found
        """
        logger.bind(
            domain="flow",
            action="switch",
            target=target,
        ).info("Switching flow")

        # Resolve branch name
        branch_name = target
        if not target.startswith("task/"):
            branch_name = f"task/{target}"

        # Check if branch exists
        if not self.git.branch_exists(branch_name):
            raise UserError(
                message=f"Branch '{branch_name}' does not exist. "
                "Use 'flow new' to create a new flow."
            )

        # Check if flow exists in database
        flow_data = self.store.get_flow_state(branch_name)
        if not flow_data:
            raise UserError(
                message=f"Flow for branch '{branch_name}' not found in database. "
                "The branch exists but the flow is not tracked."
            )

        # Stash current changes
        stash_ref = None
        if self.git.has_uncommitted_changes():
            stash_ref = self.git.stash_push(
                message=f"Auto-stash before switching to {branch_name}"
            )

        try:
            # Switch branch
            self.git.switch_branch(branch_name)

            # Restore stashed changes
            if stash_ref:
                self.git.stash_apply(stash_ref)

            logger.bind(branch=branch_name).success("Switched to flow successfully")
            return FlowState(**flow_data)

        except Exception:
            # Restore stash on failure
            if stash_ref:
                try:
                    self.git.stash_apply(stash_ref)
                except Exception:
                    logger.error("Failed to restore stash after error")

            raise
