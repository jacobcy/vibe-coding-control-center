"""Explicit flow rebuild usecase.

Rebuild is destructive: delete the old physical scene and flow record, then
bootstrap a fresh flow/worktree. Per #3289 a manual rebuild does NOT implicitly
clear the business blocked reason — ``label_resume`` defaults to a no-op so
the physical scene is repaired without touching blocked truth. Users who want
to clear the block separately invoke ``vibe3 task resume`` (manual_resume).
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


def _noop_label_resume(**_kwargs: Any) -> None:
    """Default post-rebuild hook: no-op.

    #3289: a rebuild restores the physical scene only; it must not clear the
    business blocked reason or advance the state label. Callers that need to
    resume a blocked flow do so explicitly via ``vibe3 task resume``.
    """


class FlowRebuildUsecase:
    """Hard rebuild a flow scene without touching business blocked truth."""

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
        self._label_resume = label_resume or _noop_label_resume

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
        """Hard-delete the old scene, recreate flow/worktree, append handoff.

        This performs a destructive rebuild of the flow scene. Per #3289 it
        does NOT clear the business blocked reason — ``label_resume`` defaults
        to a no-op. Blocked state, reason, dependency projection, and label
        survive the rebuild; callers that want to resume a blocked flow do so
        explicitly via ``vibe3 task resume``.

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

        # Record scene_rebuilt timeline event (must not claim cleared blocked)
        from vibe3.services.flow.timeline import FlowTimelineService
        from vibe3.services.issue.flow import IssueFlowService

        issue_number = IssueFlowService(self.store).resolve_task_issue_number(branch)
        if issue_number:
            FlowTimelineService(
                store=self.store,
                github_client=self.github_client,
            ).record_timeline_event(
                branch=branch,
                event_type="scene_rebuilt",
                actor="vibe3:flow_rebuild",
                detail=f"Scene rebuilt: {reason}",
                issue_number=issue_number,
            )

        # Post-rebuild hook (no-op by default per #3289)
        self._label_resume(
            issue_number=issue.number,
            branch=branch,
            reason=reason,
        )
        return result
