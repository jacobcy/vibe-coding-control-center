"""Flow service implementation."""

from loguru import logger
from pydantic import ValidationError

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.config.settings import VibeConfig
from vibe3.models.flow import (
    FlowState,
    MainBranchProtectedError,
)
from vibe3.services.base_resolution_usecase import MAIN_BRANCH_REF
from vibe3.services.flow_auto_ensure_mixin import FlowAutoEnsureMixin
from vibe3.services.flow_lifecycle import FlowLifecycleMixin
from vibe3.services.flow_query_mixin import FlowQueryMixin
from vibe3.services.signature_service import SignatureService


class FlowService(FlowAutoEnsureMixin, FlowLifecycleMixin, FlowQueryMixin):
    """Service for managing flow state."""

    store: SQLiteClient
    git_client: GitClient
    config: VibeConfig

    def __init__(
        self,
        store: SQLiteClient | None = None,
        git_client: GitClient | None = None,
        config: VibeConfig | None = None,
    ) -> None:
        """Initialize flow service.

        Args:
            store: SQLiteClient instance for persistence
            git_client: GitClient instance for git operations
            config: VibeConfig instance for configuration
        """
        self.store = store or SQLiteClient()
        self.git_client = git_client or GitClient()
        self.config = config or VibeConfig.get_defaults()

    def get_current_branch(self) -> str:
        """Get current git branch.

        Returns:
            Current branch name
        """
        return self.git_client.get_current_branch()

    def create_flow(
        self,
        slug: str,
        branch: str,
        actor: str | None = None,
    ) -> FlowState:
        """Create a new flow.

        Args:
            slug: Flow name/slug
            branch: Git branch name

        Returns:
            Created flow state

        Raises:
            MainBranchProtectedError: If branch is main/master
        """
        if self._is_main_branch(branch):
            raise MainBranchProtectedError(
                f"Cannot create flow on protected branch '{branch}'. "
                "Switch to a feature branch first."
            )

        logger.bind(
            domain="flow",
            action="create",
            slug=slug,
            branch=branch,
        ).info("Creating flow")
        effective_actor = SignatureService.resolve_actor(explicit_actor=actor)

        self.store.update_flow_state(
            branch,
            flow_slug=slug,
            latest_actor=effective_actor,
        )

        self.store.add_event(
            branch,
            "flow_created",
            effective_actor,
            f"Flow '{slug}' created",
        )

        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise RuntimeError(f"Failed to create flow for branch {branch}")

        try:
            return FlowState(**flow_data)
        except ValidationError as exc:
            raise RuntimeError(
                f"Created flow has invalid data for branch {branch}: {exc}"
            ) from exc

    def create_flow_with_branch(
        self,
        slug: str,
        start_ref: str = MAIN_BRANCH_REF,
        save_unstash: bool = False,
        actor: str | None = None,
    ) -> FlowState:
        """Create a new flow and create branch.

        Args:
            slug: Flow name/slug
            start_ref: Starting reference for new branch
            save_unstash: Whether to stash and restore current changes

        Returns:
            Created flow state

        Raises:
            RuntimeError: If branch already exists or worktree is dirty
        """
        branch = f"task/{slug}"

        logger.bind(
            domain="flow",
            action="create_with_branch",
            slug=slug,
            branch=branch,
            start_ref=start_ref,
        ).info("Creating flow with branch")

        if self.git_client.branch_exists(branch):
            raise RuntimeError(f"Branch '{branch}' already exists")

        if self.git_client.has_uncommitted_changes() and not save_unstash:
            raise RuntimeError(
                "Worktree has uncommitted changes. "
                "Use --save-unstash to stash them automatically."
            )

        stash_ref = None
        if save_unstash and self.git_client.has_uncommitted_changes():
            stash_ref = self.git_client.stash_push(message=f"vibe flow new {slug}")

        self.git_client.create_branch(branch, start_ref)

        flow = self.create_flow(slug, branch, actor=actor)

        if stash_ref:
            self.git_client.stash_apply(stash_ref)

        return flow

    def switch_flow(
        self,
        target: str,
    ) -> FlowState:
        """Switch to existing flow.

        Args:
            target: Flow slug or branch name to switch to

        Returns:
            Flow state of the target flow

        Raises:
            RuntimeError: If flow not found
        """
        logger.bind(
            domain="flow",
            action="switch",
            target=target,
        ).info("Switching to flow")

        flows = self.list_flows()
        target_flow = None
        for flow in flows:
            if flow.flow_slug == target or flow.branch == target:
                target_flow = flow
                break

        if not target_flow:
            raise RuntimeError(f"Flow '{target}' not found")

        if not self.git_client.branch_exists(target_flow.branch):
            raise RuntimeError(f"Branch '{target_flow.branch}' not found")

        stash_ref = None
        if self.git_client.has_uncommitted_changes():
            stash_ref = self.git_client.stash_push(message=f"vibe flow switch {target}")

        self.git_client.switch_branch(target_flow.branch)

        if stash_ref:
            self.git_client.stash_apply(stash_ref)

        return target_flow
