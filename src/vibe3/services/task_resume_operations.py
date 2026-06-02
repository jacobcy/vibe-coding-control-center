"""Task resume operations.

`task resume` only clears blocked state and restores the issue label. Destructive
scene rebuild belongs to FlowRebuildUsecase.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from vibe3.exceptions import UserError
from vibe3.models.orchestration import IssueState

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient
    from vibe3.models.flow import FlowStatusResponse
    from vibe3.services.flow_service import FlowService
    from vibe3.services.issue_flow_service import IssueFlowService
    from vibe3.services.label_service import LabelService


ProgressCallback = Callable[[int, str | None, str, str], None]


class TaskResumeOperations:
    """Non-destructive blocked issue resume operations."""

    def __init__(
        self,
        git_client: GitClient,
        github_client: GitHubClient,
        flow_service: FlowService,
        label_service: LabelService,
        issue_flow_service: IssueFlowService,
    ) -> None:
        self.git_client = git_client
        self.github_client = github_client
        self.flow_service = flow_service
        self.label_service = label_service
        self.issue_flow_service = issue_flow_service

    def reset_issue_to_ready(
        self,
        *,
        issue_number: int,
        resume_kind: str,
        flow: FlowStatusResponse | None,
        repo: str | None,
        reason: str,
        label_state: str | None = "",
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Clear blocked state without deleting worktree, branch, or flow record."""
        branch = getattr(flow, "branch", None) if flow else None
        if label_state is None:
            raise UserError(
                "Task resume no longer supports destructive label_state=None. "
                "Use FlowRebuildUsecase for flow/worktree rebuild."
            )

        if isinstance(branch, str):
            flow_status = self.flow_service.get_flow_status(branch)
            if flow_status and flow_status.flow_status == "done":
                raise UserError(
                    f"Flow '{branch}' is done - cannot reset. "
                    "Use 'vibe check --clean-branch' to clean physical resources, "
                    "or close the linked issue manually if still open."
                )
            self._guard_no_live_sessions(branch)

        def emit_progress(step: str, status: str = "running") -> None:
            if progress_callback:
                progress_callback(issue_number, branch, step, status)

        emit_progress("checking consistency and recovering")

        # Delegate to unified recovery service (manual path: auto=False)
        from vibe3.services.flow_recovery_service import FlowRecoveryService

        recovery = FlowRecoveryService(
            store=self.flow_service.store,
            git_client=self.git_client,
            github_client=self.github_client,
        )
        recovery.recover(
            branch=branch or "",
            issue_number=issue_number,
            reason=f"Resumed from {resume_kind}: {reason}",
            auto=False,
        )
        emit_progress("recovery complete", status="done")

    def _guard_no_live_sessions(self, branch: str) -> None:
        from vibe3.agents import CodeagentBackend
        from vibe3.environment.session_registry import SessionRegistryService

        registry = SessionRegistryService(
            store=self.flow_service.store,
            backend=CodeagentBackend(),
        )
        live_sessions = registry.get_truly_live_sessions_for_branch(branch)
        if live_sessions:
            raise UserError(
                f"Flow '{branch}' still has a live runtime session; "
                "wait for the active automation run to finish before resume."
            )

    def _resolve_target_state(
        self,
        branch: str | None,
        label_state: str,
    ) -> IssueState:
        if not label_state:
            from vibe3.models.flow import FlowState
            from vibe3.services.flow_resume_resolver import infer_resume_label

            fs_dict = (
                self.flow_service.store.get_flow_state(branch)
                if isinstance(branch, str)
                else None
            )
            return (
                infer_resume_label(FlowState.model_validate(fs_dict))
                if fs_dict
                else IssueState.READY
            )

        valid_states = {
            "ready": IssueState.READY,
            "claimed": IssueState.CLAIMED,
            "in-progress": IssueState.IN_PROGRESS,
            "handoff": IssueState.HANDOFF,
            "review": IssueState.REVIEW,
            "merge-ready": IssueState.MERGE_READY,
        }
        return valid_states.get(label_state, IssueState.CLAIMED)
