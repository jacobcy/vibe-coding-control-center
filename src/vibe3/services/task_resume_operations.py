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
    ) -> None:
        """Reset an issue to ready after clearing stale task scene state."""
        branch = getattr(flow, "branch", None) if flow else None
        previous_state = self.label_service.get_state(issue_number)

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
        """Delete the stale task scene so the next run starts from scratch."""
        if not self.issue_flow_service.is_task_branch(branch):
            return

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
