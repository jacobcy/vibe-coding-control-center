"""Flow service implementation."""

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.config.settings import VibeConfig
from vibe3.models.flow import (
    FlowStatusResponse,
    MainBranchProtectedError,
)
from vibe3.services.base_resolution_usecase import MAIN_BRANCH_REF
from vibe3.services.flow_lifecycle import FlowLifecycleMixin
from vibe3.services.flow_query_mixin import FlowQueryMixin
from vibe3.services.signature_service import SignatureService


class FlowService(FlowLifecycleMixin, FlowQueryMixin):
    """Service for managing flow state."""

    SAFE_BRANCH_PREFIX = "vibe/main-safe/"

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

    # ------------------------------------------------------------------
    # Main branch detection (from flow_auto_ensure_mixin.py)
    # ------------------------------------------------------------------

    def _is_main_branch(self, branch: str) -> bool:
        """Check if branch is a protected main branch.

        Protected branches include:
        - Configured protected_branches (e.g. main, master, develop)
        - Remote tracking variants (origin/main, etc.)
        - Safe branches created by flow close (vibe/main-safe/...)
        """
        # Strip remote prefix for safe branch check (origin/vibe/main-safe/...)
        local_name = branch.split("/", 1)[1] if branch.startswith("origin/") else branch
        if local_name.startswith(self.SAFE_BRANCH_PREFIX):
            return True

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

    def ensure_flow_for_branch(
        self, branch: str, slug: str | None = None
    ) -> FlowStatusResponse:
        """Ensure flow exists for branch, creating if needed.

        Args:
            branch: Git branch name
            slug: Optional flow slug (defaults to derived from branch)

        Returns:
            Existing or newly created FlowStatusResponse

        Raises:
            MainBranchProtectedError: If branch is main/master
        """
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
            return existing

        # Generate slug from branch if not provided
        if not slug:
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

    def resolve_flow_name(self, name: str | None = None) -> str:
        """Return explicit name or derive slug from current branch.

        Args:
            name: Explicit flow name. If None, derives from current branch.

        Returns:
            Flow name/slug

        Raises:
            ValueError: If cannot infer name from detached HEAD
        """
        if name:
            return name
        branch = self.get_current_branch()
        if branch == "HEAD":
            raise ValueError("Cannot infer flow name from detached HEAD")
        return branch.rsplit("/", 1)[-1] or branch

    def create_flow(
        self,
        slug: str,
        branch: str,
        actor: str | None = None,
    ) -> FlowStatusResponse:
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

        status = self.get_flow_status(branch)
        if not status:
            raise RuntimeError(f"Failed to create flow for branch {branch}")

        return status

    def create_flow_with_branch(
        self,
        slug: str,
        start_ref: str = MAIN_BRANCH_REF,
        actor: str | None = None,
    ) -> FlowStatusResponse:
        """Create a new flow and create branch.

        Args:
            slug: Flow name/slug
            start_ref: Starting reference for new branch
            actor: Actor creating the flow

        Returns:
            Created flow status

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

        has_changes = self.git_client.has_uncommitted_changes()
        if has_changes:
            raise RuntimeError(
                "Worktree has uncommitted changes. "
                "Please commit or stash them before flow create."
            )

        self.git_client.create_branch(branch, start_ref)

        flow = self.create_flow(slug, branch, actor=actor)

        return flow

    def switch_flow(self, target: str) -> FlowStatusResponse:
        """Switch to a different flow.

        Args:
            target: Flow name or branch name

        Returns:
            Flow status of the target flow

        Raises:
            RuntimeError: If flow not found
        """
        logger.bind(
            domain="flow",
            action="switch",
            target=target,
        ).info("Switching to flow")

        flows = self.list_flows()
        target_flow: FlowStatusResponse | None = None
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
