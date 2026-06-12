"""Flow read operations mixin."""

from pathlib import Path
from typing import Any, Literal, Self, cast

from loguru import logger
from pydantic import ValidationError

from vibe3.clients import GitClient, GitHubClient, GitHubClientProtocol, SQLiteClient
from vibe3.models import FlowEvent, FlowState, FlowStatusResponse, IssueLink
from vibe3.services.shared.paths import GitPathProtocol, get_git_common_dir


class FlowReadMixin:
    """Mixin providing flow read operations."""

    store: SQLiteClient
    git_client: GitPathProtocol
    github_client: GitHubClient | None = None

    def get_flow_state(self: Self, branch: str) -> FlowState | None:
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

    def get_flow_status(self: Self, branch: str) -> FlowStatusResponse | None:
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

        # Cache-first: derive pr_number from local pr_ref if available
        pr_ref = flow_data.get("pr_ref")
        if isinstance(pr_ref, str) and pr_ref:
            try:
                pr_number = int(pr_ref.rsplit("/", 1)[-1])
                pr_ready = False  # Draft status unavailable from cache
            except (ValueError, IndexError) as e:
                # Malformed pr_ref: fall through to PRService fallback
                logger.bind(domain="flow", branch=branch).warning(
                    f"Malformed pr_ref '{pr_ref}': {e}"
                )
                pr_number, pr_ready = None, False
                # Continue to PRService fallback below
                pr_ref = None  # Clear to trigger fallback path
        else:
            pr_number, pr_ready = None, False

        if not pr_ref:
            # Fallback: hydrate from GitHub via PRService
            try:
                from vibe3.services.pr.service import PRService

                gh = getattr(self, "github_client", None) or GitHubClient()
                pr = PRService(
                    github_client=cast(GitHubClientProtocol, gh),
                    store=self.store,
                ).get_branch_pr_status(branch)
                if pr:
                    pr_number = pr.number
                    pr_ready = pr.is_ready
            except Exception as e:
                logger.bind(domain="flow", branch=branch).warning(
                    f"Failed to hydrate PR status from GitHub: {e}"
                )

        issue_links = self.store.get_issue_links(branch)
        issues = [IssueLink(**link) for link in issue_links]

        # Resolve worktree root for this branch (Execution Directory context)
        worktree_root = None
        try:
            wt_path = self.git_client.find_worktree_path_for_branch(branch)
            if wt_path:
                worktree_root = str(wt_path)
        except Exception:
            pass

        has_branch, has_worktree, is_placeholder = self._compute_scene_completeness(
            branch, flow_data
        )

        try:
            return FlowStatusResponse.from_state(
                flow_data,
                issues=issues,
                pr_number=pr_number,
                pr_ready=pr_ready,
                worktree_root=worktree_root,
                has_branch=has_branch,
                has_worktree=has_worktree,
                is_placeholder=is_placeholder,
            )
        except ValidationError as exc:
            logger.bind(domain="flow", branch=branch).warning(
                f"Flow status has invalid data: {exc}"
            )
            return None

    def _compute_scene_completeness(
        self: Self, branch: str, flow_data: dict[str, Any]
    ) -> tuple[bool, bool, bool]:
        """Compute scene completeness flags for a flow.

        Args:
            branch: Branch name
            flow_data: Raw flow state dict from store

        Returns:
            Tuple of (has_branch, has_worktree, is_placeholder)
        """
        has_branch = False
        try:
            # Runtime: git_client is actually a GitClient instance
            # Type: declared as GitPathProtocol for minimal interface
            if isinstance(self.git_client, GitClient):
                has_branch = self.git_client.branch_exists(branch)
        except Exception:
            pass

        # Check worktree existence (if recorded in DB)
        has_worktree = False
        worktree_path = flow_data.get("worktree_path")
        if worktree_path:
            has_worktree = Path(worktree_path).exists()

        # Placeholder flow: DB record exists but no git branch
        is_placeholder = not has_branch

        return has_branch, has_worktree, is_placeholder

    def get_flow_for_issue(self: Self, issue_number: int) -> dict[str, Any] | None:
        """Get flow data for an issue number.

        Args:
            issue_number: Issue number to search for

        Returns:
            Flow data dict or None if not found
        """
        # Query all flows and find one with matching task_issue_number
        flows = self.list_flows(status=None)
        for flow in flows:
            if flow.task_issue_number == issue_number:
                flow_data = self.store.get_flow_state(flow.branch)
                if flow_data:
                    return flow_data
        return None

    def list_flows(
        self: Self,
        status: Literal["active", "blocked", "done", "stale"] | None = None,
    ) -> list[FlowStatusResponse]:
        """List flows with optional status filter."""
        logger.bind(
            domain="flow",
            action="list",
            status=status,
        ).debug("Listing flows")
        if status:
            flows_data = self.store.get_flows_by_status(status)
        else:
            flows_data = self.store.get_all_flows()

        flows: list[FlowStatusResponse] = []
        for flow in flows_data:
            branch = flow.get("branch", "<unknown>")
            try:
                # Basic hydration: task_issue_number from issue_links (local truth)
                issue_links = self.store.get_issue_links(branch)
                issues = [IssueLink(**link) for link in issue_links]

                # Resolve worktree root context
                worktree_root = None
                try:
                    wt_path = self.git_client.find_worktree_path_for_branch(branch)
                    if wt_path:
                        worktree_root = str(wt_path)
                except Exception:
                    pass

                has_branch, has_worktree, is_placeholder = (
                    self._compute_scene_completeness(branch, flow)
                )

                flows.append(
                    FlowStatusResponse.from_state(
                        flow,
                        issues=issues,
                        worktree_root=worktree_root,
                        has_branch=has_branch,
                        has_worktree=has_worktree,
                        is_placeholder=is_placeholder,
                    )
                )
            except (ValidationError, KeyError) as exc:
                logger.bind(
                    domain="flow",
                    action="list",
                    branch=branch,
                ).warning(f"Skipping flow with invalid data: {exc}")
        return flows

    def get_flow_timeline(self: Self, branch: str) -> dict:
        """Get flow state and recent events for timeline view."""
        # Use hydrated status instead of raw flow_state to get truth fields
        status = self.get_flow_status(branch)
        if not status:
            return {"state": None, "events": []}

        events_data = self.store.get_events(branch, limit=100)
        events = [FlowEvent(**e) for e in events_data]

        return {"state": status, "events": events}

    def get_git_common_dir(self: Self) -> str:
        """Get git common directory path."""
        return get_git_common_dir(self.git_client)
