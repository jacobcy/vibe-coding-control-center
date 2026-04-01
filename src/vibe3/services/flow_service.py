"""Flow service implementation."""

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.config.settings import VibeConfig
from vibe3.models.flow import (
    FlowStatusResponse,
    MainBranchProtectedError,
)
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
        initiated_by: str | None = None,
    ) -> FlowStatusResponse:
        """Create a new flow.

        Args:
            slug: Flow name/slug
            branch: Git branch name
            actor: Optional actor name
            initiated_by: Optional initiator identifier

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
            initiated_by=initiated_by,
        ).info("Creating flow")
        # Flow state actor: only set when explicitly provided.
        # orchestra uses actor=None to signal "no agent has taken ownership yet".
        effective_actor = (
            SignatureService.resolve_actor(explicit_actor=actor)
            if actor is not None
            else None
        )
        # Event actor: audit log always needs attribution (NOT NULL in schema).
        # Falls back to worktree identity when no explicit actor — this is an
        # audit record, not an agent claim, so the distinction is fine.
        event_actor = effective_actor or SignatureService.get_worktree_actor()

        # Resolve initiator if not explicitly provided (e.g. manual CLI create)
        if initiated_by is None:
            initiated_by = SignatureService.resolve_initiator(branch)

        self.store.update_flow_state(
            branch,
            flow_slug=slug,
            latest_actor=effective_actor,
            initiated_by=initiated_by,
        )

        self.store.add_event(
            branch,
            "flow_created",
            event_actor,
            f"Flow '{slug}' created",
        )

        status = self.get_flow_status(branch)
        if not status:
            raise RuntimeError(f"Failed to create flow for branch {branch}")

        return status
