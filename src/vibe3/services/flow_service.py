"""Flow service implementation."""

from typing import Literal

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.config.settings import VibeConfig
from vibe3.models.flow import (
    FlowEvent,
    FlowState,
    FlowStatusResponse,
    IssueLink,
    MainBranchProtectedError,
)
from vibe3.services.base_resolution_usecase import MAIN_BRANCH_REF
from vibe3.services.flow_auto_ensure_mixin import FlowAutoEnsureMixin
from vibe3.services.flow_lifecycle import FlowLifecycleMixin
from vibe3.services.flow_query_mixin import FlowQueryMixin


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

        self.store.update_flow_state(
            branch,
            flow_slug=slug,
        )

        self.store.add_event(
            branch,
            "flow_created",
            "system",
            f"Flow '{slug}' created",
        )

        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise RuntimeError(f"Failed to create flow for branch {branch}")

        return FlowState(**flow_data)

    def create_flow_with_branch(
        self,
        slug: str,
        start_ref: str = MAIN_BRANCH_REF,
        save_unstash: bool = False,
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

        flow = self.create_flow(slug, branch)

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
            raise RuntimeError(f"Branch '{target_flow.branch}' does not exist")

        stash_ref = None
        if self.git_client.has_uncommitted_changes():
            stash_ref = self.git_client.stash_push(message=f"vibe flow switch {target}")

        self.git_client.switch_branch(target_flow.branch)

        if stash_ref:
            self.git_client.stash_apply(stash_ref)

        return target_flow

    def get_flow_status(self, branch: str) -> FlowStatusResponse | None:
        """Get flow status.

        Args:
            branch: Git branch name

        Returns:
            Flow status response or None if not found
        """
        logger.bind(
            domain="flow",
            action="get_status",
            branch=branch,
        ).debug("Getting flow status")

        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            return None

        issue_links = self.store.get_issue_links(branch)
        issues = [IssueLink(**link) for link in issue_links]

        return FlowStatusResponse(
            branch=flow_data["branch"],
            flow_slug=flow_data["flow_slug"],
            flow_status=flow_data["flow_status"],
            task_issue_number=flow_data.get("task_issue_number"),
            pr_number=flow_data.get("pr_number"),
            pr_ready_for_review=flow_data.get("pr_ready_for_review", False),
            spec_ref=flow_data.get("spec_ref"),
            plan_ref=flow_data.get("plan_ref"),
            report_ref=flow_data.get("report_ref"),
            audit_ref=flow_data.get("audit_ref"),
            planner_actor=flow_data.get("planner_actor"),
            planner_session_id=flow_data.get("planner_session_id"),
            executor_actor=flow_data.get("executor_actor"),
            executor_session_id=flow_data.get("executor_session_id"),
            reviewer_actor=flow_data.get("reviewer_actor"),
            reviewer_session_id=flow_data.get("reviewer_session_id"),
            latest_actor=flow_data.get("latest_actor"),
            blocked_by=flow_data.get("blocked_by"),
            next_step=flow_data.get("next_step"),
            issues=issues,
            planner_status=flow_data.get("planner_status"),
            executor_status=flow_data.get("executor_status"),
            reviewer_status=flow_data.get("reviewer_status"),
            execution_pid=flow_data.get("execution_pid"),
            execution_started_at=flow_data.get("execution_started_at"),
            execution_completed_at=flow_data.get("execution_completed_at"),
        )

    def list_flows(
        self,
        status: Literal["active", "blocked", "done", "stale"] | None = None,
    ) -> list[FlowState]:
        """List flows.

        Args:
            status: Optional status filter

        Returns:
            List of flow states
        """
        logger.bind(
            domain="flow",
            action="list",
            status=status,
        ).debug("Listing flows")

        flows_data = self.store.get_all_flows()

        if status:
            flows_data = [f for f in flows_data if f.get("flow_status") == status]

        return [FlowState(**flow) for flow in flows_data]

    def get_flow_timeline(self, branch: str) -> dict:
        state_data = self.store.get_flow_state(branch)
        if not state_data:
            return {"state": None, "events": []}
        events_data = self.store.get_events(branch, limit=100)
        events = [FlowEvent(**e) for e in events_data]
        return {"state": FlowState(**state_data), "events": events}
