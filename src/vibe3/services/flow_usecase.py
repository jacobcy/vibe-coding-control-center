"""Usecase layer for flow command orchestration."""

from collections.abc import Sequence
from typing import Literal

from vibe3.exceptions import UserError
from vibe3.models.flow import CreateDecision, FlowStatusResponse, IssueLink
from vibe3.services.base_resolution_usecase import BaseResolutionUsecase
from vibe3.services.flow_service import FlowService
from vibe3.services.handoff_service import HandoffService
from vibe3.services.signature_service import SignatureService
from vibe3.services.spec_ref_service import SpecRefService
from vibe3.services.task_service import TaskService
from vibe3.utils.issue_ref import (
    infer_task_issue_from_flow_name,
    parse_issue_number,
)


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
        base_resolver: BaseResolutionUsecase | None = None,
        spec_ref_service: SpecRefService | None = None,
    ) -> None:
        self.flow_service = flow_service or FlowService()
        self.task_service = task_service or TaskService()
        self.handoff_service = handoff_service or HandoffService()
        self.base_resolver = base_resolver or BaseResolutionUsecase()
        self.spec_ref_service = spec_ref_service or SpecRefService()

    @classmethod
    def create(
        cls,
        flow_service: FlowService | None = None,
        task_service: TaskService | None = None,
        handoff_service: HandoffService | None = None,
    ) -> "FlowUsecase":
        """Create FlowUsecase with default dependencies."""
        return cls(
            flow_service=flow_service or FlowService(),
            task_service=task_service or TaskService(),
            handoff_service=handoff_service or HandoffService(),
        )

    def add_flow(
        self,
        name: str,
        task: str | Sequence[str] | None = None,
        spec: str | None = None,
        actor: str | None = None,
    ) -> FlowStatusResponse:
        """Create a flow on the current branch and apply optional bindings."""
        branch = self.flow_service.get_current_branch()
        existing_flow = self.flow_service.get_flow_status(branch)
        if existing_flow:
            self._confirm_existing_flow(
                branch=branch,
                existing_flow=existing_flow,
                task=task,
                spec=spec,
                actor=actor,
            )
            confirmed = self.flow_service.get_flow_status(branch)
            if confirmed is not None:
                return confirmed
            return existing_flow

        flow = self.flow_service.create_flow(slug=name, branch=branch, actor=actor)
        self._apply_initial_bindings(branch, task, spec, actor=actor)
        self.handoff_service.ensure_current_handoff()
        return flow

    def _confirm_existing_flow(
        self,
        branch: str,
        existing_flow: FlowStatusResponse,
        task: str | Sequence[str] | None,
        spec: str | None,
        actor: str | None,
    ) -> None:
        """Idempotent add behavior for existing flow.

        - `--actor` updates default flow signature (latest_actor)
        - `--task` appends task links but does not overwrite primary task
        - `--spec` confirms/updates spec binding with minimum action
        """
        effective_actor = SignatureService.resolve_actor(
            explicit_actor=actor,
            flow_actor=existing_flow.latest_actor,
        )
        self.flow_service.store.update_flow_state(branch, latest_actor=effective_actor)

        task_refs = self._normalize_task_refs(task)
        original_primary = existing_flow.task_issue_number
        if task_refs:
            for task_ref in task_refs:
                self._link_issue(branch, task_ref, "task", actor=effective_actor)
            if original_primary is not None:
                # Preserve primary task truth in flow_issue_links(task) and flow_state.
                self._link_issue(
                    branch,
                    str(original_primary),
                    "task",
                    actor=effective_actor,
                )
        if spec:
            self.flow_service.bind_spec(branch, spec, effective_actor)

    def create_flow(
        self,
        name: str,
        base: str | None = None,
        task: str | Sequence[str] | None = None,
        spec: str | None = None,
        actor: str | None = None,
    ) -> FlowStatusResponse:
        """Create a branch-backed flow while enforcing worktree governance."""
        current_branch = self.flow_service.get_current_branch()
        decision = self.flow_service.can_create_from_current_worktree(current_branch)
        if not decision.allowed and self._try_auto_close_done_eligible_flow(
            current_branch, actor=actor
        ):
            current_branch = self.flow_service.get_current_branch()
            decision = self.flow_service.can_create_from_current_worktree(
                current_branch
            )
        self._validate_create_request(base, decision)
        task_refs = self._normalize_task_refs(task)
        if not task_refs:
            inferred_issue = infer_task_issue_from_flow_name(name)
            if inferred_issue is not None:
                task_refs = [str(inferred_issue)]
        self._validate_issue_refs(task_refs)

        default_policy: Literal["current", "main"] = (
            "current" if decision.start_ref == current_branch else "main"
        )
        start_ref = self.base_resolver.resolve_flow_create_base(
            requested_base=base,
            current_branch=current_branch,
            default_policy=default_policy,
        )
        try:
            flow = self.flow_service.create_flow_with_branch(
                slug=name,
                start_ref=start_ref,
                actor=actor,
            )
        except RuntimeError as exc:
            guidance = None
            if "already exists" in str(exc):
                guidance = f"Hint: Use different name or 'vibe3 flow switch {name}'"
            raise FlowUsecaseError(str(exc), guidance) from exc

        branch = f"task/{name}"
        self._apply_initial_bindings(branch, task_refs, spec, actor=actor)
        self.handoff_service.ensure_current_handoff()
        return flow

    def _try_auto_close_done_eligible_flow(
        self,
        branch: str,
        actor: str | None = None,
    ) -> bool:
        """Auto-close current active flow when PR merge guard allows it."""
        flow_status = self.flow_service.get_flow_status(branch)
        if flow_status is None or flow_status.flow_status != "active":
            return False

        try:
            if actor is None:
                self.flow_service.close_flow(branch, check_pr=True)
            else:
                self.flow_service.close_flow(branch, check_pr=True, actor=actor)
        except UserError:
            return False
        return True

    def bind_issue(
        self,
        issue: str,
        role: Literal["task", "related", "dependency"] = "task",
        actor: str | None = None,
    ) -> IssueLink:
        """Bind an issue to the current flow."""
        branch = self.flow_service.get_current_branch()
        return self._link_issue(branch, issue, role, actor=actor)

    def _apply_initial_bindings(
        self,
        branch: str,
        task: str | Sequence[str] | None,
        spec: str | None,
        actor: str | None = None,
    ) -> None:
        task_refs = self._normalize_task_refs(task)
        if task_refs:
            for task_ref in task_refs:
                self._link_issue(branch, task_ref, "task", actor=actor)
            if not spec:
                self._bind_task_as_spec_ref(branch, task_refs[0], actor=actor)
        if spec:
            self.flow_service.bind_spec(branch, spec, actor)

    def _link_issue(
        self,
        branch: str,
        issue_ref: str,
        role: Literal["task", "related", "dependency"],
        actor: str | None = None,
    ) -> IssueLink:
        issue_number = parse_issue_number(issue_ref)
        return self.task_service.link_issue(branch, issue_number, role, actor=actor)

    def _bind_task_as_spec_ref(
        self, branch: str, task: str, actor: str | None = None
    ) -> None:
        """Derive spec_ref from bound task issue for issue-first workflows."""
        issue_number = parse_issue_number(task)
        spec_info = self.spec_ref_service.parse_spec_ref(str(issue_number))
        if spec_info.display:
            self.flow_service.bind_spec(branch, spec_info.display, actor)

    @staticmethod
    def _normalize_task_refs(task: str | Sequence[str] | None) -> list[str]:
        if task is None:
            return []
        if isinstance(task, str):
            return [task]
        return [ref for ref in task if ref]

    def _validate_issue_refs(self, refs: Sequence[str]) -> None:
        for ref in refs:
            parse_issue_number(ref)

    @staticmethod
    def validate_issue_refs(
        primary: str | None,
        tail: list[str] | None,
        *,
        primary_hint: str,
    ) -> str | list[str] | None:
        """Validate and merge issue refs from command arguments."""
        tail = tail or []
        if not tail:
            return primary
        if primary is None:
            raise ValueError(f"Additional issue refs require '{primary_hint}' prefix.")
        return [primary, *tail]

    @staticmethod
    def _validate_create_request(base: str | None, decision: CreateDecision) -> None:
        if not decision.allowed:
            raise FlowUsecaseError(decision.reason, decision.guidance)

        if decision.requires_new_worktree:
            raise FlowUsecaseError(decision.guidance or decision.reason)

        if base == "current" and not decision.allow_base_current:
            raise FlowUsecaseError(
                "'--base current' is only allowed when current flow is blocked.",
                "For independent new features, use 'vibe3 wtnew <name>' first.",
            )
