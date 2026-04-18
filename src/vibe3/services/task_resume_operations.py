"""Task resume operations logic.

This module provides operations for resetting task scenes and
managing flow states during resume operations.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.environment.session_naming import get_manager_session_name
from vibe3.models.orchestration import IssueState
from vibe3.services.handoff_service import HandoffService
from vibe3.services.issue_failure_service import (
    resume_blocked_issue_to_ready,
    resume_failed_issue_to_ready,
)

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient
    from vibe3.models.flow import FlowStatusResponse
    from vibe3.services.flow_service import FlowService
    from vibe3.services.issue_flow_service import IssueFlowService
    from vibe3.services.label_service import LabelService


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
        """
        branch = getattr(flow, "branch", None) if flow else None
        previous_state = self.label_service.get_state(issue_number)

        # Determine target state based on label_state parameter
        if label_state is not None:
            # --label provided: restore to specified state without deleting worktree
            target_state = (
                IssueState.READY if label_state == "ready" else IssueState.HANDOFF
            )

            # --label: minimal cleanup only. The agent did work but the label
            # wasn't updated correctly, causing a block.  Clear the reason
            # fields so the next dispatch picks it up; the flow record, refs,
            # and worktree are all valid and should be preserved.
            if isinstance(branch, str):
                self._clear_flow_reasons(branch, resume_kind)

            # Restore issue to target state
            self.label_service.confirm_issue_state(
                issue_number,
                target_state,
                actor="human:resume",
                force=True,
            )

            # Add comment about label-based resume
            self._add_label_resume_comment(
                issue_number=issue_number,
                resume_kind=resume_kind,
                target_state=target_state,
                repo=repo,
                reason=reason,
            )

            # DO NOT call reset_task_scene (keep worktree)
        else:
            # Original logic: delete worktree/branch for full rebuild
            if resume_kind == "failed":
                resume_failed_issue_to_ready(
                    issue_number=issue_number,
                    repo=repo,
                    reason=reason,
                )
            elif resume_kind == "blocked":
                resume_blocked_issue_to_ready(
                    issue_number=issue_number,
                    repo=repo,
                    reason=reason,
                )
            else:
                self.label_service.confirm_issue_state(
                    issue_number,
                    IssueState.READY,
                    actor="human:resume",
                    force=True,
                )

            if isinstance(branch, str):
                try:
                    self.reset_task_scene(branch, worktree_path=worktree_path)
                except Exception as exc:
                    self.restore_issue_state(
                        issue_number=issue_number,
                        previous_state=previous_state,
                        repo=repo,
                        failure_reason=str(exc),
                    )
                    raise

    def reset_task_scene(self, branch: str, worktree_path: str | None = None) -> None:
        """Delete the stale task scene so the next run starts from scratch.

        Flow record deletion is guaranteed even if worktree/branch/handoff
        cleanup fails partially — a stale flow record is the root cause of
        phantom downstream dispatches (issue #301).
        """
        is_task = self.issue_flow_service.is_task_branch(branch)

        try:
            if is_task:
                self.terminate_task_sessions(branch)

                resolved_path = worktree_path
                if resolved_path is None:
                    found_path = self.git_client.find_worktree_path_for_branch(branch)
                    resolved_path = str(found_path) if found_path is not None else None
                logger.bind(
                    domain="resume",
                    action="reset_task_scene",
                    branch=branch,
                    worktree_path=resolved_path,
                ).info("Resetting task scene")
                if resolved_path is not None:
                    self.git_client.remove_worktree(resolved_path, force=True)
                if self.git_client.branch_exists(branch):
                    self.git_client.delete_branch(
                        branch,
                        force=True,
                        skip_if_worktree=True,
                    )
                HandoffService(
                    store=self.flow_service.store,
                    git_client=self.git_client,
                ).clear_handoff_for_branch(branch)
        except Exception as exc:
            logger.bind(
                domain="resume",
                action="reset_task_scene_partial",
                branch=branch,
            ).warning(
                f"Partial scene cleanup failed (flow will still be deleted): {exc}"
            )

        # Always delete the flow record — stale flows cause phantom dispatches
        self.flow_service.delete_flow(branch)

    def terminate_task_sessions(self, branch: str) -> None:
        """Kill lingering tmux sessions for a task issue before resume."""
        issue_number = self.issue_flow_service.parse_issue_number(branch)
        if issue_number is None:
            return

        prefixes = (
            get_manager_session_name(issue_number),
            f"vibe3-plan-issue-{issue_number}",
            f"vibe3-run-issue-{issue_number}",
            f"vibe3-review-issue-{issue_number}",
        )

        try:
            result = subprocess.run(
                ["tmux", "ls"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except FileNotFoundError:
            return
        except Exception as exc:
            logger.bind(
                domain="resume",
                action="terminate_task_sessions",
                branch=branch,
            ).warning(f"Failed to inspect tmux sessions: {exc}")
            return

        if result.returncode != 0:
            return

        active_sessions: list[str] = []
        for line in result.stdout.splitlines():
            session_name = line.split(":", 1)[0].strip()
            if any(
                session_name == prefix or session_name.startswith(f"{prefix}-")
                for prefix in prefixes
            ):
                active_sessions.append(session_name)

        for session_name in active_sessions:
            subprocess.run(
                ["tmux", "kill-session", "-t", session_name],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

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

    def _add_label_resume_comment(
        self,
        *,
        issue_number: int,
        resume_kind: str,
        target_state: IssueState,
        repo: str | None,
        reason: str,
    ) -> None:
        """Add comment about label-based resume.

        Args:
            issue_number: GitHub issue number
            resume_kind: Resume kind (failed, blocked, all)
            target_state: Target state (HANDOFF or READY)
            repo: Repository (owner/repo format, optional)
            reason: Resume reason
        """
        try:
            kind_label = {
                "failed": "state/failed",
                "blocked": "state/blocked",
                "all": "task scene",
            }.get(resume_kind, resume_kind)

            comment_body = (
                f"[resume] 已从 {kind_label} 恢复到 state/{target_state.value}。\n\n"
                f"已清除 blocked_reason/failed_reason，保留 worktree现场。\n"
                f"后续可在当前 worktree 继续推进。"
            )

            normalized_reason = reason.strip()
            if normalized_reason:
                comment_body += f"\n\n原因:{normalized_reason}"

            # Deduplicate: skip if latest comment matches
            issue_payload = self.github_client.view_issue(issue_number, repo=repo)
            if isinstance(issue_payload, dict) and self._latest_comment_matches(
                issue_payload, comment_body
            ):
                return

            self.github_client.add_comment(
                issue_number,
                comment_body,
                repo=repo,
            )
        except Exception as exc:
            # Non-blocking: comment failure should not affect resume
            logger.bind(
                domain="resume",
                action="add_label_resume_comment",
                issue_number=issue_number,
            ).warning(f"Failed to add label resume comment: {exc}")

    def _latest_comment_matches(
        self,
        issue_payload: dict[str, object],
        comment_body: str,
    ) -> bool:
        """Return True when the latest issue comment is the same comment."""
        comments = issue_payload.get("comments")
        if not isinstance(comments, list):
            return False
        normalized_comment = comment_body.strip()
        for comment in reversed(comments):
            if not isinstance(comment, dict):
                continue
            body = comment.get("body")
            return isinstance(body, str) and body.strip() == normalized_comment
        return False
