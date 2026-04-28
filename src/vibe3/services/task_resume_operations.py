"""Task resume operations logic.

This module provides operations for resetting task scenes and
managing flow states during resume operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from loguru import logger

from vibe3.exceptions import UserError
from vibe3.models.orchestration import IssueState
from vibe3.services.issue_failure_service import (
    resume_blocked_issue_to_ready,
    resume_failed_issue_to_ready,
    resume_issue,
)

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient
    from vibe3.models.flow import FlowStatusResponse
    from vibe3.services.flow_service import FlowService
    from vibe3.services.issue_flow_service import IssueFlowService
    from vibe3.services.label_service import LabelService


# Type alias for progress callback: (issue_number, branch, step, status) -> None
ProgressCallback = Callable[[int, str | None, str, str], None]


class TaskResumeOperations:
    """Operations for task resume actions."""

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
        worktree_path: str | None = None,
        label_state: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Reset an issue to ready after clearing stale task scene state.

        Args:
            issue_number: GitHub issue number
            resume_kind: Resume kind (failed, blocked, all)
            flow: Flow status response
            repo: Repository (owner/repo format, optional)
            reason: Resume reason to include in comments
            worktree_path: Optional worktree path (for optimization)
            label_state: Optional state to restore (None=delete worktree,
                empty/"handoff"=restore to handoff, "ready"=restore to ready)
            progress_callback: Optional callback for progress updates.
                Signature: (issue_number: int, branch: str | None, step: str,
                    status: str) -> None

        Raises:
            UserError: If flow has status "done" (completed flows cannot be reset
                through task resume)
        """
        branch = getattr(flow, "branch", None) if flow else None
        previous_state = self.label_service.get_state(issue_number)

        # Guard: done flows must not be reset — their issue should already
        # be closed and the flow record preserved as audit history.
        if isinstance(branch, str):
            flow_status = self.flow_service.get_flow_status(branch)
            if flow_status and flow_status.flow_status == "done":
                raise UserError(
                    f"Flow '{branch}' is done — cannot reset. "
                    "Use 'vibe check --clean-branch' to clean physical resources, "
                    "or close the linked issue manually if still open."
                )

        def emit_progress(step: str, status: str = "running") -> None:
            if progress_callback:
                progress_callback(issue_number, branch, step, status)

        # Determine target state based on label_state parameter
        if label_state is not None:
            # --label provided: restore to specified state without deleting worktree
            # Convert string state to IssueState enum
            if not label_state:
                from vibe3.models.flow import FlowState
                from vibe3.services.flow_resume_resolver import infer_resume_label

                fs_dict = (
                    self.flow_service.store.get_flow_state(branch)
                    if isinstance(branch, str)
                    else None
                )
                if fs_dict:
                    target_state = infer_resume_label(FlowState.model_validate(fs_dict))
                else:
                    target_state = IssueState.CLAIMED
            else:
                valid_states = {
                    "ready": IssueState.READY,
                    "claimed": IssueState.CLAIMED,
                    "in-progress": IssueState.IN_PROGRESS,
                    "handoff": IssueState.HANDOFF,
                    "review": IssueState.REVIEW,
                    "merge-ready": IssueState.MERGE_READY,
                }
                target_state = valid_states.get(label_state, IssueState.CLAIMED)

            # --label: minimal cleanup only. The agent did work but the label
            # wasn't updated correctly, causing a block.  Clear the reason
            # fields so the next dispatch picks it up; the flow record, refs,
            # and worktree are all valid and should be preserved.
            if isinstance(branch, str):
                emit_progress(f"clearing reasons for branch {branch}")
                self._clear_flow_reasons(branch, resume_kind)

            # Use unified resume_issue for event registration and state transition
            emit_progress(f"resuming via unified handler to {target_state.value}")
            resume_issue(
                issue_number=issue_number,
                reason=reason,
                from_state=resume_kind,
                to_state=target_state,
                repo=repo,
            )
            emit_progress("label resume done", status="done")

            # DO NOT call reset_task_scene (keep worktree)
        else:
            # Original logic: delete worktree/branch for full rebuild
            emit_progress("full rebuild mode")
            if resume_kind == "failed":
                emit_progress("clearing failed state")
                resume_failed_issue_to_ready(
                    issue_number=issue_number,
                    repo=repo,
                    reason=reason,
                )
            elif resume_kind == "blocked":
                emit_progress("clearing blocked state")
                resume_blocked_issue_to_ready(
                    issue_number=issue_number,
                    repo=repo,
                    reason=reason,
                )
            else:
                emit_progress("setting issue state to ready")
                self.label_service.confirm_issue_state(
                    issue_number,
                    IssueState.READY,
                    actor="human:resume",
                    force=True,
                )

            if isinstance(branch, str):
                try:
                    emit_progress(f"resetting task scene for branch {branch}")
                    self.reset_task_scene(branch, worktree_path=worktree_path)
                    emit_progress("task scene reset done", status="done")
                except Exception as exc:
                    emit_progress(f"scene reset failed: {exc}", status="failed")
                    self.restore_issue_state(
                        issue_number=issue_number,
                        previous_state=previous_state,
                        repo=repo,
                        failure_reason=str(exc),
                    )
                    raise
            else:
                emit_progress("no branch to reset, done", status="done")

    def reset_task_scene(self, branch: str, worktree_path: str | None = None) -> None:
        """Delete the stale task scene so the next run starts from scratch.

        Flow record deletion is guaranteed even if worktree/branch/handoff
        cleanup fails partially — a stale flow record is the root cause of
        phantom downstream dispatches (issue #301).

        This method uses FlowCleanupService for consistent cleanup behavior
        across `task resume` and `check --clean-branch`.

        Note: Always deletes flow record (keep_flow_record=False) because
        the purpose of `task resume` is to restart the flow from scratch.
        """
        from vibe3.services.flow_cleanup_service import FlowCleanupService

        logger.bind(
            domain="resume",
            action="reset_task_scene",
            branch=branch,
            worktree_path=worktree_path,
        ).info("Resetting task scene")

        cleanup_service = FlowCleanupService(
            git_client=self.git_client,
            store=self.flow_service.store,
            flow_service=self.flow_service,
            issue_flow_service=self.issue_flow_service,
        )

        results = cleanup_service.cleanup_flow_scene(
            branch,
            include_remote=True,  # Delete remote branch for clean restart
            terminate_sessions=True,
            keep_flow_record=False,  # Delete flow record to allow fresh start
        )

        # Log if any step failed
        failed_steps = [k for k, v in results.items() if not v]
        if failed_steps:
            logger.bind(
                domain="resume",
                action="reset_task_scene_partial",
                branch=branch,
            ).warning(f"Some cleanup steps failed: {', '.join(failed_steps)}")

    def restore_issue_state(
        self,
        *,
        issue_number: int,
        previous_state: IssueState | None,
        repo: str | None,
        failure_reason: str,
    ) -> None:
        """Best-effort rollback when scene reset fails after issue transition."""
        if previous_state is None or previous_state == IssueState.READY:
            return
        try:
            self.label_service.confirm_issue_state(
                issue_number,
                previous_state,
                actor="human:resume",
                force=True,
            )
            self.github_client.add_comment(
                issue_number,
                "[resume] task scene 重置失败，已恢复为 "
                f"state/{previous_state.value}。\n\n"
                f"原因:{failure_reason}",
                repo=repo,
            )
        except Exception as exc:
            logger.bind(
                domain="resume",
                action="rollback_issue_state",
                issue_number=issue_number,
                previous_state=previous_state.value,
            ).warning("Failed to rollback issue state after resume error: " f"{exc}")

    def cleanup_stale_flow(self, branch: str) -> None:
        """Clean up stale flow metadata after blocked resume.

        Args:
            branch: Branch name for the flow to clean up
        """
        try:
            logger.bind(
                domain="resume",
                action="cleanup_stale_flow",
                branch=branch,
            ).info("Cleaning up stale flow")

            # Reactivate the stale flow (change status from "stale" to "active")
            self.flow_service.reactivate_flow(branch)
        except Exception as exc:
            # Log but don't fail the resume operation
            logger.bind(
                domain="resume",
                action="cleanup_stale_flow",
                branch=branch,
            ).warning(f"Failed to clean up stale flow: {exc}")

    def reactivate_aborted_flow(self, branch: str) -> None:
        """Reactivate an aborted flow.

        Args:
            branch: Branch name for the aborted flow
        """
        try:
            logger.bind(
                domain="resume",
                action="reactivate_aborted",
                branch=branch,
            ).info("Reactivating aborted flow")

            # Reactivate the aborted flow (change status from "aborted" to "active")
            self.flow_service.reactivate_flow(branch)
        except Exception as exc:
            logger.bind(
                domain="resume",
                action="reactivate_aborted",
                branch=branch,
            ).warning(f"Failed to reactivate aborted flow: {exc}")
            raise

    def _clear_flow_reasons(self, branch: str, resume_kind: str) -> None:
        """Clear blocked_reason/failed_reason from FlowState.

        Args:
            branch: Branch name
            resume_kind: Resume kind (failed, blocked, all)
        """
        try:
            logger.bind(
                domain="resume",
                action="clear_flow_reasons",
                branch=branch,
                resume_kind=resume_kind,
            ).info("Clearing flow reason fields")

            # Clear both blocked_reason and failed_reason
            # (issue may have been in multiple blocked/failed states)
            self.flow_service.store.update_flow_state(
                branch,
                blocked_reason=None,
                failed_reason=None,
                latest_actor="human:resume",
            )
        except Exception as exc:
            # Non-blocking: reason clearing failure should not affect resume
            logger.bind(
                domain="resume",
                action="clear_flow_reasons",
                branch=branch,
            ).warning(f"Failed to clear flow reasons: {exc}")
