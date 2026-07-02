"""Explicit flow rebuild usecase.

Rebuild is destructive: delete the old physical scene and flow record, then
bootstrap a fresh flow/worktree and clear blocked labels through the standard
label-auto resume path.
"""

from __future__ import annotations

from typing import Any, Callable

from vibe3.clients import GitClient, GitHubClient, SQLiteClient
from vibe3.config import load_orchestra_config
from vibe3.models import IssueInfo
from vibe3.services.flow.cleanup import FlowCleanupService
from vibe3.services.flow.rebuild_postconditions import assert_rebuild_postconditions
from vibe3.services.protocols.flow_protocols import FlowBootstrapProtocol

LabelResume = Callable[..., None]


class FlowRebuildUsecase:
    """Hard rebuild a flow scene and restore issue state through label-auto."""

    def __init__(
        self,
        *,
        store: SQLiteClient | None = None,
        git_client: GitClient | None = None,
        github_client: GitHubClient | None = None,
        orchestrator: FlowBootstrapProtocol | None = None,
        label_resume: LabelResume | None = None,
    ) -> None:
        self.store = store or SQLiteClient()
        self.git_client = git_client or GitClient()
        self.github_client = github_client or GitHubClient()
        if orchestrator is not None:
            self.orchestrator = orchestrator
        else:
            try:
                from vibe3.services.orchestra.orchestrator import (
                    FlowOrchestratorService,
                )

                config = load_orchestra_config()
                self.orchestrator = FlowOrchestratorService(
                    config,
                    store=self.store,
                    git=self.git_client,
                    github=self.github_client,
                )
            except ImportError as e:
                raise SystemError(
                    f"Failed to import FlowOrchestratorService: {e}. "
                    "Provide orchestrator parameter explicitly."
                ) from e
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
        assert_rebuild_postconditions(
            branch=branch,
            result=result,
            ensure_worktree=ensure_worktree,
            git_client=self.git_client,
            store=self.store,
        )
        self.store.reset_transition_epoch(branch)

        # Record flow_rebuild timeline event
        from vibe3.services.flow.timeline import FlowTimelineService
        from vibe3.services.issue.flow import IssueFlowService

        issue_number = IssueFlowService(self.store).resolve_task_issue_number(branch)
        if issue_number:
            FlowTimelineService(
                store=self.store,
                github_client=self.github_client,
            ).record_timeline_event(
                branch=branch,
                event_type="flow_rebuild",
                actor="vibe3:flow_rebuild",
                detail=f"Flow rebuilt: {reason}",
                issue_number=issue_number,
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
        """Clear blocked markers after rebuild.

        Post-rebuild: consistency is guaranteed (we just rebuilt), so we
        skip the classify step and go straight to clearing blocked state.
        """
        from loguru import logger

        from vibe3.services.flow.blocked_state_service import BlockedStateService

        target = BlockedStateService(
            github_client=self.github_client,
            store=self.store,
        ).reconcile_blocked(
            issue_number=issue_number,
            branch=branch,
            clear_reason=True,
            actor="vibe3:flow_rebuild",
        )

        if target is None:
            logger.bind(
                domain="recovery",
                branch=branch,
                issue_number=issue_number,
            ).error(
                f"Label not cleared after rebuild for #{issue_number}. "
                f"Manual fix: gh issue edit {issue_number} --remove-label state/blocked"
            )
