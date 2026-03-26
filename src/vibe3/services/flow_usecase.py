"""Usecase layer for flow command orchestration."""

from typing import Literal

from vibe3.models.flow import CreateDecision, FlowState, IssueLink
from vibe3.services.flow_service import FlowService
from vibe3.services.handoff_service import HandoffService
from vibe3.services.task_service import TaskService


class FlowUsecaseError(RuntimeError):
    """Command-facing validation or orchestration error."""

    def __init__(self, message: str, guidance: str | None = None) -> None:
        super().__init__(message)
        self.guidance = guidance


class FlowUsecase:
    """Coordinate flow command side effects using reusable services."""

    def __init__(
        self,
        flow_service: FlowService | None = None,
        task_service: TaskService | None = None,
        handoff_service: HandoffService | None = None,
    ) -> None:
        self.flow_service = flow_service or FlowService()
        self.task_service = task_service or TaskService()
        self.handoff_service = handoff_service or HandoffService()

    def add_flow(
        self,
        name: str,
        task: str | None = None,
        spec: str | None = None,
    ) -> FlowState:
        """Create a flow on the current branch and apply optional bindings."""
        branch = self.flow_service.get_current_branch()
        existing_flow = self.flow_service.get_flow_status(branch)
        if existing_flow:
            raise FlowUsecaseError(
                f"Branch '{branch}' already has flow: {existing_flow.flow_slug}"
            )

        flow = self.flow_service.create_flow(slug=name, branch=branch)
        self._bind_optional_refs(branch, task, spec)
        self.handoff_service.ensure_current_handoff()
        return flow

    def create_flow(
        self,
        name: str,
        base: str = "main",
        task: str | None = None,
        spec: str | None = None,
    ) -> FlowState:
        """Create a branch-backed flow while enforcing worktree governance."""
        current_branch = self.flow_service.get_current_branch()
        decision = self.flow_service.can_create_from_current_worktree(current_branch)
        self._validate_create_request(base, decision)

        start_ref = self._resolve_start_ref(base, current_branch, decision)
        try:
            flow = self.flow_service.create_flow_with_branch(
                slug=name,
                start_ref=start_ref,
            )
        except RuntimeError as exc:
            guidance = None
            if "already exists" in str(exc):
                guidance = f"Hint: Use different name or 'vibe3 flow switch {name}'"
            raise FlowUsecaseError(str(exc), guidance) from exc

        branch = f"task/{name}"
        self._bind_optional_refs(branch, task, spec)
        self.handoff_service.ensure_current_handoff()
        return flow

    def bind_issue(
        self,
        issue: str,
        role: Literal["task", "related", "dependency"] = "task",
    ) -> IssueLink:
        """Bind an issue to the current flow."""
        branch = self.flow_service.get_current_branch()
        issue_number = self._parse_issue_number(issue)
        return self.task_service.link_issue(branch, issue_number, role)

    @staticmethod
    def _parse_issue_number(issue: str) -> int:
        digits = "".join(filter(str.isdigit, issue))
        if not digits:
            raise ValueError(f"Invalid issue format: {issue}")
        return int(digits)

    def _bind_optional_refs(
        self,
        branch: str,
        task: str | None,
        spec: str | None,
    ) -> None:
        if task:
            self.flow_service.bind_task(branch, task, "system")
        if spec:
            self.flow_service.bind_spec(branch, spec, "system")

    @staticmethod
    def _validate_create_request(base: str, decision: CreateDecision) -> None:
        if not decision.allowed:
            raise FlowUsecaseError(decision.reason, decision.guidance)

        if decision.requires_new_worktree:
            raise FlowUsecaseError(decision.guidance or decision.reason)

        if base == "current" and not decision.allow_base_current:
            raise FlowUsecaseError(
                "'--base current' is only allowed when current flow is blocked.",
                "For independent new features, use 'vibe3 wtnew <name>' first.",
            )

    @staticmethod
    def _resolve_start_ref(
        base: str,
        current_branch: str,
        decision: CreateDecision,
    ) -> str:
        if base == "main":
            return decision.start_ref or "origin/main"
        if base == "current":
            return current_branch
        return base
