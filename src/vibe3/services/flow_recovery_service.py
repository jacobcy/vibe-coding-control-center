"""Unified flow recovery service.

Single entry point for all recovery paths: health check auto-recover,
PR-closed reset, manual task resume, and manual flow rebuild.

Decision tree:
  consistency OK           --> resume only (clear label + body + DB)
  MISSING_RECORDED_WORKTREE --> fix (backfill DB) + resume
  MISSING_WORKTREE          --> rebuild (delete + bootstrap) + resume
  MISSING_REF               --> manual: guide user; auto: rebuild + resume
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.exceptions import UserError
from vibe3.services.flow_consistency_check import (
    FlowConsistencyCode,
    FlowConsistencyResult,
    apply_consistency_fix,
    check_flow_consistency,
)

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient
    from vibe3.clients.sqlite_client import SQLiteClient


class RecoveryAction(StrEnum):
    """What kind of recovery is needed."""

    RESUME_ONLY = "resume_only"
    FIX_AND_RESUME = "fix_and_resume"
    REBUILD = "rebuild"


@dataclass
class RecoveryResult:
    """Outcome of a recovery attempt."""

    action: RecoveryAction
    success: bool
    detail: str = ""


class FlowRecoveryService:
    """Unified recovery: classify inconsistency, act, resume.

    All recovery paths (health check, PR closed, manual resume, manual
    rebuild) call into this service so the logic is never duplicated.
    """

    def __init__(
        self,
        *,
        store: SQLiteClient,
        git_client: GitClient,
        github_client: GitHubClient,
    ) -> None:
        self.store = store
        self.git_client = git_client
        self.github_client = github_client

    def classify(
        self, branch: str
    ) -> tuple[RecoveryAction, FlowConsistencyResult | None]:
        """Classify what recovery action a branch needs.

        Returns:
            Tuple of (action, consistency_result):
            - RESUME_ONLY: scene consistent, just clear blocked markers
            - FIX_AND_RESUME: cheap DB fix + clear blocked markers
            - REBUILD: full scene rebuild + clear blocked markers
            - consistency_result: reusable check result (None if no flow_state)
        """
        flow_state = self.store.get_flow_state(branch)
        if flow_state is None:
            return (RecoveryAction.REBUILD, None)

        consistency = check_flow_consistency(
            branch, flow_state, git_client=self.git_client
        )

        if consistency.code == FlowConsistencyCode.OK:
            return (RecoveryAction.RESUME_ONLY, consistency)
        if consistency.fix_action:
            return (RecoveryAction.FIX_AND_RESUME, consistency)
        if consistency.needs_rebuild:
            return (RecoveryAction.REBUILD, consistency)
        return (RecoveryAction.RESUME_ONLY, consistency)

    def recover(
        self,
        *,
        branch: str,
        issue_number: int,
        reason: str,
        auto: bool,
        ensure_worktree: bool = True,
        include_remote: bool = False,
    ) -> RecoveryResult:
        """Execute the full recovery: classify -> act -> resume.

        Args:
            branch: Flow branch name (empty string if no flow)
            issue_number: GitHub issue number
            reason: Human-readable reason for recovery
            auto: True for orchestra/health-check paths (auto-rebuild);
                  False for manual paths (guide user instead of rebuilding)
            ensure_worktree: Whether rebuild should create worktree
            include_remote: Whether rebuild should delete remote branch
        """
        # Special case: no branch (issue with no flow) -> just clear label
        if not branch:
            self._do_resume(branch, issue_number, reason)
            return RecoveryResult(
                action=RecoveryAction.RESUME_ONLY,
                success=True,
                detail="No flow branch; cleared blocked markers",
            )

        flow_state = self.store.get_flow_state(branch)

        # Short-circuit: no flow record -> rebuild (consistent with classify())
        if flow_state is None:
            if not auto:
                raise UserError(
                    f"No flow record found for branch '{branch}'. "
                    f"Run: vibe3 flow rebuild {issue_number} --yes"
                )
            self._do_rebuild(
                branch,
                issue_number,
                reason,
                ensure_worktree=ensure_worktree,
                include_remote=include_remote,
            )
            self._do_resume(branch, issue_number, reason)
            return RecoveryResult(
                action=RecoveryAction.REBUILD,
                success=True,
                detail="No flow record; rebuilt scene and cleared blocked markers",
            )

        consistency = check_flow_consistency(
            branch, flow_state, git_client=self.git_client
        )

        # --- Classify ---
        if consistency.code == FlowConsistencyCode.OK:
            self._do_resume(branch, issue_number, reason)
            return RecoveryResult(
                action=RecoveryAction.RESUME_ONLY,
                success=True,
                detail="Scene consistent; cleared blocked markers",
            )

        if consistency.fix_action:
            applied = apply_consistency_fix(consistency, branch, store=self.store)
            if applied:
                logger.bind(
                    domain="recovery", branch=branch, fix=consistency.fix_action
                ).info("Applied cheap consistency fix")
            self._do_resume(branch, issue_number, reason)
            return RecoveryResult(
                action=RecoveryAction.FIX_AND_RESUME,
                success=True,
                detail=(
                    f"Applied fix ({consistency.fix_action}); "
                    "cleared blocked markers"
                ),
            )

        if consistency.needs_rebuild:
            if not auto:
                raise UserError(
                    f"{consistency.reason}. "
                    f"Run: vibe3 flow rebuild {issue_number} --yes"
                )
            self._do_rebuild(
                branch,
                issue_number,
                reason,
                ensure_worktree=ensure_worktree,
                include_remote=include_remote,
            )
            self._do_resume(branch, issue_number, reason)
            return RecoveryResult(
                action=RecoveryAction.REBUILD,
                success=True,
                detail=(
                    f"Rebuilt scene and cleared blocked markers: "
                    f"{consistency.reason}"
                ),
            )

        # Should not reach here
        self._do_resume(branch, issue_number, reason)
        return RecoveryResult(
            action=RecoveryAction.RESUME_ONLY,
            success=True,
            detail="Fallback: cleared blocked markers",
        )

    def _do_resume(self, branch: str, issue_number: int, reason: str) -> None:
        """Clear blocked markers from all three sources (DB, body, label).

        Raises:
            RuntimeError: If label write fails (RC2: prevents silent failure)
        """
        from vibe3.models import IssueState
        from vibe3.models.flow import FlowState
        from vibe3.services.blocked_state_service import BlockedStateService
        from vibe3.services.flow_resume_resolver import infer_resume_label

        # Determine target state from flow progress
        fs_dict = self.store.get_flow_state(branch)
        if fs_dict and isinstance(fs_dict, dict):
            try:
                target_state = infer_resume_label(FlowState.model_validate(fs_dict))
            except Exception:
                # Fallback to READY if validation fails
                target_state = IssueState.READY
        else:
            target_state = IssueState.READY

        service = BlockedStateService(
            github_client=self.github_client,
            label_service=None,  # uses default
            store=self.store,
        )
        result = service.unblock(
            branch=branch,
            target_state=target_state,
            issue_number=issue_number,
            detail=f"Recovery resume: {reason}",
        )

        # RC2 fix: Fail-fast if label not cleared to prevent blocked loop
        if not result.label_cleared:
            raise RuntimeError(
                f"Failed to clear state/blocked label on issue #{issue_number}. "
                f"Manual fix: gh issue edit {issue_number} "
                "--remove-label state/blocked"
            )

    def _do_rebuild(
        self,
        branch: str,
        issue_number: int,
        reason: str,
        *,
        ensure_worktree: bool = True,
        include_remote: bool = False,
    ) -> None:
        """Hard rebuild through the canonical rebuild usecase."""
        from vibe3.config.orchestra_settings import load_orchestra_config
        from vibe3.models import IssueInfo, IssueState
        from vibe3.services.flow_rebuild_usecase import FlowRebuildUsecase
        from vibe3.services.shared.issue_utils import load_issue_info

        # Load issue info from GitHub
        config = load_orchestra_config()
        try:
            issue_info = load_issue_info(
                issue_number, config=config, github=self.github_client
            )
        except Exception:
            issue_info = IssueInfo(
                number=issue_number,
                title=f"Issue {issue_number}",
                labels=[IssueState.READY.to_label()],
                state=IssueState.READY,
            )

        FlowRebuildUsecase(
            store=self.store,
            git_client=self.git_client,
            github_client=self.github_client,
            label_resume=lambda **_: None,
        ).rebuild_issue_flow(
            issue=issue_info,
            branch=branch,
            reason=reason,
            ensure_worktree=ensure_worktree,
            include_remote=include_remote,
        )
