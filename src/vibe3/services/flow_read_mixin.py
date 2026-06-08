"""Flow read operations mixin."""

from typing import Literal, Self, cast

from loguru import logger
from pydantic import ValidationError

from vibe3.clients import GitHubClient, GitHubClientProtocol, SQLiteClient
from vibe3.models import FlowEvent, FlowState, FlowStatusResponse, IssueLink
from vibe3.services.git_path_client import GitPathProtocol, get_git_common_dir


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

        try:
            return FlowStatusResponse.from_state(
                flow_data,
                issues=issues,
                pr_number=pr_number,
                pr_ready=pr_ready,
                worktree_root=worktree_root,
            )
        except ValidationError as exc:
            logger.bind(domain="flow", branch=branch).warning(
                f"Flow status has invalid data: {exc}"
            )
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

                # Resolve worktree root context
                worktree_root = None
                try:
                    wt_path = self.git_client.find_worktree_path_for_branch(branch)
                    if wt_path:
                        worktree_root = str(wt_path)
                except Exception:
                    pass

                flows.append(
                    FlowStatusResponse.from_state(
                        flow, issues=issues, worktree_root=worktree_root
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
