"""Task resume operations logic.

This module provides operations for resetting task scenes and
managing flow states during resume operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from loguru import logger

from vibe3.exceptions import UserError
from vibe3.models.orchestration import IssueState
from vibe3.services.flow_timeline_service import FlowTimelineService

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
        label_state: str | None = None,
        remote: bool = False,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Resume an issue after clearing stale blocked state.

        Public task resume callers pass label_state="" for auto inference.
        That path clears blocked cache/labels and preserves worktree/branch.

        label_state=None is legacy/internal destructive compatibility only.
        New destructive callers must prefer FlowRebuildUsecase.

        Args:
            issue_number: GitHub issue number
            resume_kind: Resume kind (blocked, all, aborted, pr_closed)
            flow: Flow status response
            repo: Repository (owner/repo format, optional)
            reason: Resume reason to include in comments
            label_state: Optional state to restore (None=full rebuild,
                empty/"handoff"=restore to handoff, "ready"=restore to ready)
            remote: If True, keep remote branch (use with --remote flag).
                If False, delete remote branch (default).
            progress_callback: Optional callback for progress updates.

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

        # Guard: block resume if branch has live runtime sessions
        if isinstance(branch, str):
            from vibe3.agents import CodeagentBackend
            from vibe3.environment.session_registry import SessionRegistryService

            backend = CodeagentBackend()
            registry = SessionRegistryService(
                store=self.flow_service.store, backend=backend
            )
            live_sessions = registry.get_truly_live_sessions_for_branch(branch)
            if live_sessions:
                raise UserError(
                    f"Flow '{branch}' still has a live runtime session; "
                    "wait for the active automation run to finish before resume."
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
                    # No flow → restore to READY (can be claimed by any agent)
                    # CLAIMED is wrong: implies claimed by actor, but no flow
                    # exists to provide execution context
                    target_state = IssueState.READY
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
            # wasn't updated correctly, causing a block.  Clear blocked state
            # and resume issue using unified BlockedStateService.
            from vibe3.services.blocked_state_service import BlockedStateService

            if isinstance(branch, str):
                emit_progress(f"clearing reasons for branch {branch}")
            else:
                emit_progress("clearing reasons (no branch)")

            service = BlockedStateService(
                github_client=self.github_client,
                label_service=self.label_service,
                store=self.flow_service.store,
            )

            service.unblock(
                branch=branch or "",  # Empty string if no branch
                target_state=target_state,
                issue_number=issue_number,
                detail=f"Resumed from {resume_kind} to {target_state.value}: {reason}",
            )

            emit_progress("label resume done", status="done")

            # DO NOT call reset_task_scene (keep worktree)
        else:
            # Legacy/internal destructive compatibility. Public CLI paths must
            # not reach this branch; use FlowRebuildUsecase for new rebuilds.
            emit_progress("full rebuild mode")

            from vibe3.services.blocked_state_service import BlockedStateService

            service = BlockedStateService(
                github_client=self.github_client,
                label_service=self.label_service,
                store=self.flow_service.store,
            )
            service.unblock(
                branch=branch or "",
                target_state=IssueState.READY,
                issue_number=issue_number,
                detail=f"Resumed from {resume_kind}: {reason}",
            )
            emit_progress("state unblocked", status="done")

            if isinstance(branch, str):
                try:
                    emit_progress(f"resetting task scene for branch {branch}")
                    self.reset_task_scene(
                        branch,
                        include_remote=not remote,
                    )
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

    def reset_task_scene(
        self,
        branch: str,
        include_remote: bool = True,
    ) -> None:
        """Hard delete flow + worktree so the next run starts from scratch.

        Always uses hard delete (force_delete=True) because task resume
        means complete rebuild — old events have no audit value.
        Soft delete is only for vibe3 check (issue closed / flow aborted).

        Args:
            branch: Branch name
            include_remote: If True, delete remote branch (default).
                If False, keep remote branch (for --remote mode).
        """
        from vibe3.services.flow_cleanup_service import FlowCleanupService

        logger.bind(
            domain="resume",
            action="reset_task_scene",
            branch=branch,
        ).info("Resetting task scene")

        cleanup_service = FlowCleanupService(
            git_client=self.git_client,
            store=self.flow_service.store,
            flow_service=self.flow_service,
            issue_flow_service=self.issue_flow_service,
        )

        results = cleanup_service.cleanup_flow_scene(
            branch,
            include_remote=include_remote,
            terminate_sessions=True,
            keep_flow_record=False,
            force_delete=True,
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

            # Add [flow] timeline comment via FlowTimelineService
            branch: str | None = None
            try:
                flows = self.flow_service.store.get_flows_by_issue(
                    issue_number, role="task"
                )
                if flows:
                    branch = str(flows[0].get("branch") or "").strip()
            except Exception:
                pass

            if branch:
                try:
                    timeline_service = FlowTimelineService(
                        store=self.flow_service.store
                    )
                    timeline_service.record_timeline_event(
                        branch=branch,
                        event_type="resumed",
                        actor="human:resume",
                        detail=(
                            f"Rollback to state/{previous_state.value} "
                            f"due to scene reset failure: {failure_reason}"
                        ),
                        issue_number=issue_number,
                    )
                except Exception as exc:
                    logger.bind(
                        domain="resume",
                        action="rollback_timeline",
                        issue_number=issue_number,
                    ).warning(f"Failed to add timeline comment: {exc}")
            else:
                # Fallback: flow record deleted, use direct GitHub comment
                try:
                    self.github_client.add_comment(
                        issue_number,
                        "[flow] Flow resumed\n\n"
                        f"Rollback to state/{previous_state.value} "
                        f"due to scene reset failure: {failure_reason}",
                        repo=repo,
                    )
                except Exception as exc:
                    logger.bind(
                        domain="resume",
                        action="rollback_comment",
                        issue_number=issue_number,
                    ).warning(f"Failed to add rollback comment: {exc}")
        except Exception as exc:
            logger.bind(
                domain="resume",
                action="rollback_issue_state",
                issue_number=issue_number,
                previous_state=previous_state.value,
            ).warning("Failed to rollback issue state after resume error: " f"{exc}")
