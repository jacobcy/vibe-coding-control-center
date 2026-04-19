"""Flow transition operations mixin.

Inherits from FlowWriteMixin to access:
- _is_main_branch (protected branch check)
- create_flow (flow creation)
- get_flow_status (flow status query)
- SAFE_BRANCH_PREFIX constant
"""

from typing import Self, cast

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.config.settings import VibeConfig
from vibe3.models.flow import FlowStatusResponse, MainBranchProtectedError
from vibe3.services.flow_write_mixin import FlowWriteMixin
from vibe3.services.issue_flow_service import IssueFlowService
from vibe3.services.signature_service import SignatureService


class FlowTransitionMixin(FlowWriteMixin):
    """Mixin providing flow transition operations.

    Inherits FlowWriteMixin and FlowReadMixin for:
    - _is_main_branch (protected branch check)
    - create_flow (flow creation)
    - get_flow_status (flow status query)
    - SAFE_BRANCH_PREFIX constant
    """

    store: SQLiteClient
    git_client: GitClient
    config: VibeConfig

    def ensure_flow_for_branch(
        self: Self,
        branch: str,
        slug: str | None = None,
        *,
        source: str = "cli",
    ) -> FlowStatusResponse:
        """Ensure flow exists for branch, creating if needed.

        Args:
            branch: Git branch name
            slug: Optional flow slug (defaults to derived from branch)
            source: Caller identity for audit logging
                (e.g. "dispatch", "cli", "agent").

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
                source=source,
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
            source=source,
        ).info("Creating flow via ensure")

        flow = self.create_flow(slug=slug, branch=branch, source=source)

        # Initialize issue flow context cache if this is an issue branch
        self._initialize_issue_flow_context(branch)

        return flow

    def _initialize_issue_flow_context(self: Self, branch: str) -> None:
        """Initialize issue flow context cache for issue branches.

        This method is called after flow creation to populate the context cache
        for branches that match task/issue-N or dev/issue-N patterns.

        Args:
            branch: Git branch name
        """
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

    def resolve_flow_name(self: Self, name: str | None = None) -> str:
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
        branch = cast(str, self.git_client.get_current_branch())
        if branch == "HEAD":
            raise ValueError("Cannot infer flow name from detached HEAD")
        return branch.rsplit("/", 1)[-1] or branch

    def reactivate_flow(
        self: Self,
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
