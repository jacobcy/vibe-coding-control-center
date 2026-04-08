"""Flow service implementation."""

from typing import TYPE_CHECKING, Literal

from loguru import logger
from pydantic import ValidationError

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.config.settings import VibeConfig
from vibe3.models.flow import (
    FlowEvent,
    FlowState,
    FlowStatusResponse,
    IssueLink,
    MainBranchProtectedError,
)
from vibe3.services.flow_lifecycle import FlowLifecycleMixin
from vibe3.services.signature_service import SignatureService

if TYPE_CHECKING:
    pass


class FlowService(FlowLifecycleMixin):
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
        self.store = SQLiteClient() if store is None else store
        self.git_client = GitClient() if git_client is None else git_client
        self.config = VibeConfig.get_defaults() if config is None else config

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

        flow = self.create_flow(slug=slug, branch=branch)

        # Initialize issue flow context cache if this is an issue branch
        self._initialize_issue_flow_context(branch)

        return flow

    def _initialize_issue_flow_context(self, branch: str) -> None:
        """Initialize issue flow context cache for issue branches.

        This method is called after flow creation to populate the context cache
        for branches that match task/issue-N or dev/issue-N patterns.

        Args:
            branch: Git branch name
        """
        from vibe3.clients.github_client import GitHubClient
        from vibe3.services.issue_flow_service import IssueFlowService

        issue_service = IssueFlowService(store=self.store)
        issue_number = issue_service.parse_issue_number_any(branch)

        if issue_number is None:
            # Not an issue branch, skip cache initialization
            return

        logger.bind(
            domain="flow",
            action="init_issue_context",
            branch=branch,
            issue_number=issue_number,
        ).debug("Initializing issue flow context cache")

        # Check if there's an existing task issue link
        issue_links = self.store.get_issue_links(branch)
        task_issues = [
            link["issue_number"] for link in issue_links if link["issue_role"] == "task"
        ]
        effective_issue_number = task_issues[0] if task_issues else issue_number

        # Try to fetch issue title from GitHub
        issue_title = None
        try:
            gh = GitHubClient()
            issue_data = gh.view_issue(effective_issue_number)
            if isinstance(issue_data, dict):
                issue_title = issue_data.get("title")
        except Exception as e:
            logger.bind(
                domain="flow",
                action="init_issue_context",
                branch=branch,
                issue_number=effective_issue_number,
                error=str(e),
            ).warning("Failed to fetch issue title from GitHub")

        # Initialize cache with issue number and title (if available)
        self.store.upsert_flow_context_cache(
            branch=branch,
            task_issue_number=effective_issue_number,
            issue_title=issue_title,  # May be None if GitHub failed
            pr_number=None,
            pr_title=None,
        )

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

    def update_flow_metadata(self, branch: str, **updates: object) -> None:
        """Update flow metadata fields (slug, actor, etc.).

        Encapsulates store.update_flow_state so commands don't need
        direct store access.

        Args:
            branch: Flow branch name
            **updates: Keyword args passed to store.update_flow_state
        """
        self.store.update_flow_state(branch, **updates)

    def delete_flow(self, branch: str) -> None:
        """Delete all persisted flow truth for a branch.

        This is the hard-reset counterpart to ``reactivate_flow()``.
        It removes authoritative database state so any future manager/planner
        pass must recreate the flow scene from scratch instead of inheriting
        stale refs, events, issue links, or runtime session registry entries.
        """
        logger.bind(
            domain="flow",
            action="delete",
            branch=branch,
        ).info("Deleting flow")
        self.store.delete_flow(branch)

    def reactivate_flow(
        self,
        branch: str,
        *,
        flow_slug: str | None = None,
        initiator: str | None = None,
    ) -> FlowStatusResponse:
        """Reactivate a flow, recording a 'flow_reactivated' event.

        Used when a canonical task flow is being reused for a new issue
        iteration. Resets all agent session IDs and clears execution state
        while preserving the branch and flow structure.

        Args:
            branch: Flow branch to reactivate
            flow_slug: Optional new slug (defaults to existing)
            initiator: Who initiated reactivation (defaults to worktree identity)

        Returns:
            Updated flow state

        Raises:
            RuntimeError: If flow state cannot be retrieved after reactivation
        """
        logger.bind(
            domain="flow",
            action="reactivate",
            branch=branch,
            flow_slug=flow_slug,
            initiator=initiator,
        ).info("Reactivating flow")

        # Verify flow exists before reactivation
        existing_state = self.store.get_flow_state(branch)
        if not existing_state:
            raise RuntimeError(f"Flow not found for branch {branch}")

        # Resolve flow_slug: use explicit value or extract from existing state
        if flow_slug is None:
            flow_slug = existing_state.get("flow_slug")
            if not flow_slug:
                raise RuntimeError(f"Flow for branch {branch} has no flow_slug set")
        else:
            # Validate provided flow_slug matches existing state
            existing_slug = existing_state.get("flow_slug")
            if existing_slug and flow_slug != existing_slug:
                logger.bind(
                    domain="flow",
                    action="reactivate",
                    branch=branch,
                    provided_slug=flow_slug,
                    existing_slug=existing_slug,
                ).warning("flow_slug mismatch, using provided value")

        # Resolve initiator if not explicitly provided
        if initiator is None:
            initiator = SignatureService.resolve_initiator(branch)

        # Event actor: audit log requires attribution
        event_actor = SignatureService.get_worktree_actor()

        # Reset all agent sessions and execution state
        # Note: session_id fields are no longer written (registry is source of truth)
        self.store.update_flow_state(
            branch,
            flow_slug=flow_slug,
            flow_status="active",
            latest_actor=None,
            planner_actor=None,
            executor_actor=None,
            reviewer_actor=None,
            plan_ref=None,
            report_ref=None,
            audit_ref=None,
            planner_status=None,
            executor_status=None,
            reviewer_status=None,
            execution_pid=None,
            execution_started_at=None,
            execution_completed_at=None,
            blocked_by=None,
            next_step=None,
            initiated_by=initiator,
        )

        # Clear cached issue/PR metadata (will be re-initialized for new issue)
        self.store.delete_flow_context_cache(branch)

        self.store.add_event(
            branch,
            "flow_reactivated",
            event_actor,
            "Flow reactivated",
        )

        status = self.get_flow_status(branch)
        if not status:
            raise RuntimeError(f"Failed to reactivate flow for branch {branch}")

        return status

    # ========================================================================
    # Flow Query Methods (migrated from FlowQueryMixin)
    # ========================================================================

    def get_handoff_events(
        self, branch: str, event_type_prefix: str = "handoff_", limit: int | None = None
    ) -> list[FlowEvent]:
        """Get handoff events for branch.

        Args:
            branch: Branch name
            event_type_prefix: Event type filter prefix
            limit: Maximum number of events

        Returns:
            List of FlowEvent objects
        """
        events_data = self.store.get_events(
            branch, event_type_prefix=event_type_prefix, limit=limit
        )
        return [FlowEvent(**e) for e in events_data]

    def get_flow_state(self, branch: str) -> FlowState | None:
        """Get flow state for branch.

        Args:
            branch: Branch name

        Returns:
            FlowState or None if not found
        """
        state_data = self.store.get_flow_state(branch)
        if not state_data:
            return None
        try:
            return FlowState(**state_data)
        except ValidationError as exc:
            logger.bind(domain="flow", branch=branch).warning(
                f"Flow has invalid data: {exc}"
            )
            return None

    def get_flow_status(self, branch: str) -> FlowStatusResponse | None:
        """Get flow status for branch.

        Reads bridge fields from SQLite and hydrates PR info from GitHub.
        """
        logger.bind(
            domain="flow",
            action="get_status",
            branch=branch,
        ).debug("Getting flow status")
        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            return None

        # Fetch PR info from GitHub (truth)
        # TODO: Optimize with cache service when implemented
        gh = GitHubClient()
        pr_number, pr_ready = None, False  # Default values

        try:
            # Query PR by branch (pr_number not cached in flow_state yet)
            pr = gh.get_pr(None, branch)
            if pr:
                pr_number = pr.number
                pr_ready = pr.is_ready
        except Exception as e:
            logger.bind(domain="flow", branch=branch).warning(
                f"Failed to hydrate PR status from GitHub: {e}"
            )

        issue_links = self.store.get_issue_links(branch)
        issues = [IssueLink(**link) for link in issue_links]

        try:
            return FlowStatusResponse.from_state(
                flow_data,
                issues=issues,
                pr_number=pr_number,
                pr_ready=pr_ready,
            )
        except ValidationError as exc:
            logger.bind(domain="flow", branch=branch).warning(
                f"Flow status has invalid data: {exc}"
            )
            return None

    def list_flows(
        self,
        status: Literal["active", "blocked", "done", "stale"] | None = None,
    ) -> list[FlowStatusResponse]:
        """List flows with optional status filter."""
        logger.bind(
            domain="flow",
            action="list",
            status=status,
        ).debug("Listing flows")
        flows_data = self.store.get_all_flows()
        if status:
            flows_data = [f for f in flows_data if f.get("flow_status") == status]

        flows: list[FlowStatusResponse] = []
        for flow in flows_data:
            branch = flow.get("branch", "<unknown>")
            try:
                # Basic hydration: task_issue_number from issue_links (local truth)
                issue_links = self.store.get_issue_links(branch)
                issues = [IssueLink(**link) for link in issue_links]

                flows.append(FlowStatusResponse.from_state(flow, issues=issues))
            except (ValidationError, KeyError) as exc:
                logger.bind(
                    domain="flow",
                    action="list",
                    branch=branch,
                ).warning(f"Skipping flow with invalid data: {exc}")
        return flows

    def get_flow_timeline(self, branch: str) -> dict:
        """Get flow state and recent events for timeline view."""
        # Use hydrated status instead of raw flow_state to get truth fields
        status = self.get_flow_status(branch)
        if not status:
            return {"state": None, "events": []}

        events_data = self.store.get_events(branch, limit=100)
        events = [FlowEvent(**e) for e in events_data]

        return {"state": status, "events": events}

    def get_git_common_dir(self) -> str:
        """Get git common directory path.

        Returns:
            Path to git common directory
        """
        return self.git_client.get_git_common_dir()

    def bind_spec(
        self,
        branch: str,
        spec_ref: str,
        actor: str | None = None,
    ) -> None:
        """Bind a spec to a flow.

        Args:
            branch: Branch name
            spec_ref: Spec file reference
            actor: Actor performing the bind
        """
        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            branch,
            explicit_actor=actor,
        )
        self.store.update_flow_state(
            branch, spec_ref=spec_ref, latest_actor=effective_actor
        )
        self.store.add_event(
            branch, "spec_bound", effective_actor, detail=f"Spec bound: {spec_ref}"
        )
        logger.bind(branch=branch, spec=spec_ref).info("Spec bound to flow")
