"""Flow query mixin for FlowService."""

from typing import TYPE_CHECKING, Literal

from loguru import logger
from pydantic import ValidationError

from vibe3.models.flow import FlowEvent, FlowState, FlowStatusResponse, IssueLink
from vibe3.services.signature_service import SignatureService

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.sqlite_client import SQLiteClient


class FlowQueryMixin:
    """Mixin for flow query operations."""

    store: "SQLiteClient"
    git_client: "GitClient"

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
        """Get flow status for branch."""
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
        try:
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
        except ValidationError as exc:
            logger.bind(domain="flow", branch=branch).warning(
                f"Flow status has invalid data: {exc}"
            )
            return None

    def list_flows(
        self,
        status: Literal["active", "blocked", "done", "stale"] | None = None,
    ) -> list[FlowState]:
        """List flows with optional status filter."""
        logger.bind(
            domain="flow",
            action="list",
            status=status,
        ).debug("Listing flows")
        flows_data = self.store.get_all_flows()
        if status:
            flows_data = [f for f in flows_data if f.get("flow_status") == status]
        flows: list[FlowState] = []
        for flow in flows_data:
            try:
                flows.append(FlowState(**flow))
            except ValidationError as exc:
                branch = flow.get("branch", "<unknown>")
                logger.bind(
                    domain="flow",
                    action="list",
                    branch=branch,
                ).warning(f"Skipping flow with invalid data: {exc}")
        return flows

    def get_flow_timeline(self, branch: str) -> dict:
        """Get flow state and recent events for timeline view."""
        state_data = self.store.get_flow_state(branch)
        if not state_data:
            return {"state": None, "events": []}
        events_data = self.store.get_events(branch, limit=100)
        events = [FlowEvent(**e) for e in events_data]
        try:
            state = FlowState(**state_data)
        except ValidationError as exc:
            logger.bind(
                domain="flow",
                action="get_timeline",
                branch=branch,
            ).warning(f"Flow has invalid data: {exc}")
            return {"state": None, "events": []}
        return {"state": state, "events": events}

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
