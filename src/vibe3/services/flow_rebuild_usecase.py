"""Explicit flow rebuild usecase.

Rebuild is destructive: delete the old physical scene and flow record, then
bootstrap a fresh flow/worktree and clear blocked labels through the standard
label-auto resume path.
"""

from __future__ import annotations

from typing import Any, Callable

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.models.orchestration import IssueInfo
from vibe3.services.flow_cleanup_service import FlowCleanupService
from vibe3.services.flow_orchestrator_service import FlowOrchestratorService
from vibe3.services.handoff_service import HandoffService

LabelResume = Callable[..., None]


class FlowRebuildUsecase:
    """Hard rebuild a flow scene and restore issue state through label-auto."""

    def __init__(
        self,
        *,
        store: SQLiteClient | None = None,
        git_client: GitClient | None = None,
        github_client: GitHubClient | None = None,
        orchestrator: FlowOrchestratorService | None = None,
        label_resume: LabelResume | None = None,
    ) -> None:
        self.store = store or SQLiteClient()
        self.git_client = git_client or GitClient()
        self.github_client = github_client or GitHubClient()
        config = load_orchestra_config()
        self.orchestrator = orchestrator or FlowOrchestratorService(
            config,
            store=self.store,
            git=self.git_client,
            github=self.github_client,
        )
        self._label_resume = label_resume or self._default_label_resume

    def rebuild_issue_flow(
        self,
        *,
        issue: IssueInfo,
        branch: str,
        reason: str,
        slug: str | None = None,
        source: str = "flow:rebuild",
        include_remote: bool = True,
        ensure_worktree: bool = True,
    ) -> dict[str, Any] | None:
        """Hard-delete the old scene, recreate flow/worktree, append handoff, resume.

        This performs a destructive rebuild of the flow scene.

        Raises:
            RuntimeError: If cleanup fails (prevents bootstrap on dirty state)
        """
        cleanup_results = FlowCleanupService(
            git_client=self.git_client,
            store=self.store,
        ).cleanup_flow_scene(
            branch,
            include_remote=include_remote,
            terminate_sessions=True,
            keep_flow_record=False,
            force_delete=True,
        )

        # Check cleanup results before proceeding
        failed_steps = [
            step for step, success in cleanup_results.items() if not success
        ]
        if failed_steps:
            raise RuntimeError(
                f"Flow cleanup failed for steps: {', '.join(failed_steps)}. "
                f"Cannot rebuild flow in dirty state."
            )

        result = self.orchestrator.bootstrap_issue_flow(
            issue,
            branch=branch,
            slug=slug or f"issue-{issue.number}",
            source=source,
            initiated_by=source,
            ensure_worktree=ensure_worktree,
            reactivate_existing=False,
        )

        HandoffService(
            store=self.store,
            git_client=self.git_client,
            github_client=self.github_client,
        ).append_current_handoff(
            message=f"Flow rebuilt: {reason}",
            actor="vibe3:flow_rebuild",
            kind="milestone",
            branch=branch,
        )

        self._label_resume(
            issue_number=issue.number,
            branch=branch,
            reason=reason,
        )
        return result

    def _default_label_resume(
        self,
        *,
        issue_number: int,
        branch: str,
        reason: str,
    ) -> None:
        from vibe3.models.flow import FlowStatusResponse
        from vibe3.services.flow_service import FlowService
        from vibe3.services.issue_flow_service import IssueFlowService
        from vibe3.services.label_service import LabelService
        from vibe3.services.task_resume_operations import TaskResumeOperations

        flow = FlowStatusResponse(
            branch=branch,
            flow_slug=branch,
            flow_status="active",
            latest_actor="vibe3:flow_rebuild",
            task_issue_number=issue_number,
        )
        operations = TaskResumeOperations(
            git_client=self.git_client,
            github_client=self.github_client,
            flow_service=FlowService(store=self.store),
            label_service=LabelService(),
            issue_flow_service=IssueFlowService(store=self.store),
        )
        operations.reset_issue_to_ready(
            issue_number=issue_number,
            resume_kind="rebuild",
            flow=flow,
            repo=None,
            reason=reason,
            label_state="",
        )
