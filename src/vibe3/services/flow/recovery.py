"""Unified flow recovery service.

Single entry point for all recovery paths, split by authority (#3289):

- ``recover_auto``: observer path (health check, orchestra). Repairs the
  physical scene when needed, then runs read-only auto resume eligibility.
  Scene repair preserves business blocked truth; auto resume never clears a
  human reason and never infers target from local refs.
- ``recover_manual``: human command path (``vibe3 task resume``). Applies only
  cheap scene fixes (bails on rebuild with a UserError), then invokes the
  authorized ``manual_resume`` which clears blocked_reason and advances to an
  explicit / manually-inferred target.

Decision tree (shared classify):
  consistency OK            --> eligibility / resume only
  MISSING_RECORDED_WORKTREE --> fix (backfill DB) + eligibility / resume
  MISSING_WORKTREE          --> rebuild (auto) / UserError (manual)
  MISSING_REF               --> manual: guide user; auto: rebuild + eligibility
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.exceptions import UserError
from vibe3.services.flow.blocked_state_types import (
    AutoResumeVerdict,
    ResumeResult,
)
from vibe3.services.flow.consistency import (
    FlowConsistencyCode,
    FlowConsistencyResult,
    apply_consistency_fix,
    check_flow_consistency,
)

if TYPE_CHECKING:
    from vibe3.clients import GitClient, GitHubClient, SQLiteClient
    from vibe3.models import IssueState


class RecoveryAction(StrEnum):
    """What kind of recovery is needed."""

    RESUME_ONLY = "resume_only"
    FIX_AND_RESUME = "fix_and_resume"
    REBUILD = "rebuild"
    # A recorded artifact disappeared in a healthy worktree. The scene is NOT
    # rebuilt; it stays blocked waiting for explicit rebind/regeneration
    # (spec 012 US2, SC-002).
    ARTIFACT_BLOCKED = "artifact_blocked"


@dataclass
class RecoveryResult:
    """Outcome of a recovery attempt."""

    action: RecoveryAction
    success: bool
    detail: str = ""


class FlowRecoveryService:
    """Unified recovery: classify scene, act, then resume by authority.

    All recovery paths (health check auto-recover, manual task resume) call
    into this service so the logic is never duplicated.
    """

    def __init__(
        self,
        *,
        store: "SQLiteClient",
        git_client: "GitClient",
        github_client: "GitHubClient",
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

        # Placeholder flows (blocked + no branch) need resume only
        if flow_state.get("flow_status") == "blocked":
            if not self.git_client.branch_exists(branch):
                return (RecoveryAction.RESUME_ONLY, None)

        consistency = check_flow_consistency(
            branch, flow_state, git_client=self.git_client
        )

        if consistency.code == FlowConsistencyCode.OK:
            return (RecoveryAction.RESUME_ONLY, consistency)
        if consistency.fix_action:
            return (RecoveryAction.FIX_AND_RESUME, consistency)
        if consistency.code == FlowConsistencyCode.MISSING_ARTIFACT:
            # Healthy worktree, missing historical artifact: never rebuild.
            return (RecoveryAction.ARTIFACT_BLOCKED, consistency)
        if consistency.needs_rebuild:
            return (RecoveryAction.REBUILD, consistency)
        return (RecoveryAction.RESUME_ONLY, consistency)

    # ========================================================================
    # Auto path: scene repair + read-only resume eligibility
    # ========================================================================

    def recover_auto(
        self,
        *,
        branch: str,
        issue_number: int,
        reason: str,
        ensure_worktree: bool = True,
        include_remote: bool = False,
    ) -> RecoveryResult:
        """Auto recovery: classify scene, repair, then evaluate resume eligibility.

        Scene repair (fix / rebuild) preserves business blocked truth. After
        repair, runs ``evaluate_auto_eligibility``; if eligible, applies the
        snapshot-bound ``apply_auto_resume`` (existing flow -> handoff,
        pre-flow -> ready). If not eligible, zero business mutation.

        Per #3289 the auto path has no callable API capable of clearing a
        human blocked_reason.
        """
        # Special case: no branch (pre-flow issue) -> eligibility check only
        if not branch:
            return self._auto_resume_attempt(
                issue_number, branch, RecoveryAction.RESUME_ONLY
            )

        flow_state = self.store.get_flow_state(branch)

        # No flow record -> rebuild scene, then evaluate eligibility
        if flow_state is None:
            self._do_rebuild(
                branch,
                issue_number,
                reason,
                ensure_worktree=ensure_worktree,
                include_remote=include_remote,
            )
            return self._auto_resume_attempt(
                issue_number, branch, RecoveryAction.REBUILD
            )

        consistency = check_flow_consistency(
            branch, flow_state, git_client=self.git_client
        )

        if consistency.code == FlowConsistencyCode.OK:
            return self._auto_resume_attempt(
                issue_number, branch, RecoveryAction.RESUME_ONLY
            )

        if consistency.fix_action:
            applied = apply_consistency_fix(consistency, branch, store=self.store)
            if applied:
                logger.bind(
                    domain="recovery", branch=branch, fix=consistency.fix_action
                ).info("Applied cheap consistency fix")
            return self._auto_resume_attempt(
                issue_number, branch, RecoveryAction.FIX_AND_RESUME
            )

        if consistency.code == FlowConsistencyCode.MISSING_ARTIFACT:
            # A recorded artifact disappeared in a healthy worktree: NEVER rebuild
            # the scene. Manual path guides the user to rebind/regenerate; auto path
            # keeps the flow blocked for repair (no resume, no rebuild) — spec 012
            # US2, SC-002.
            return RecoveryResult(
                action=RecoveryAction.ARTIFACT_BLOCKED,
                success=False,
                detail=f"Artifact blocker (scene kept blocked): {consistency.reason}",
            )

        if consistency.needs_rebuild:
            self._do_rebuild(
                branch,
                issue_number,
                reason,
                ensure_worktree=ensure_worktree,
                include_remote=include_remote,
            )
            return self._auto_resume_attempt(
                issue_number, branch, RecoveryAction.REBUILD
            )

        return self._auto_resume_attempt(
            issue_number, branch, RecoveryAction.RESUME_ONLY
        )

    def _auto_resume_attempt(
        self,
        issue_number: int,
        branch: str,
        scene_action: RecoveryAction,
    ) -> RecoveryResult:
        """Evaluate auto eligibility and apply if eligible (read-only otherwise)."""
        from vibe3.services.flow.blocked_state_service import BlockedStateService

        service = BlockedStateService(
            github_client=self.github_client,
            store=self.store,
        )
        decision = service.evaluate_auto_eligibility(issue_number, branch)
        if decision.verdict == AutoResumeVerdict.ELIGIBLE:
            result = service.apply_auto_resume(decision)
            return RecoveryResult(
                action=scene_action,
                success=True,
                detail=f"Scene repaired; {result.detail}",
            )
        return RecoveryResult(
            action=scene_action,
            success=True,
            detail=(
                f"Scene repaired; auto resume not eligible "
                f"({decision.reason_code.value})"
            ),
        )

    # ========================================================================
    # Manual path: scene fix only (bail on rebuild) + authorized manual_resume
    # ========================================================================

    def recover_manual(
        self,
        *,
        branch: str,
        issue_number: int,
        reason: str,
        target_state: "IssueState | None" = None,
        actor: str = "human:resume",
        force: bool = False,
    ) -> ResumeResult:
        """Manual resume: apply cheap scene fixes, then authorized manual_resume.

        Raises UserError when a full rebuild is needed (guide user to
        ``vibe3 flow rebuild`` first) — manual resume must not accidentally
        trigger a destructive scene rebuild.
        """
        from vibe3.services.flow.blocked_state_service import BlockedStateService

        # Special case: no branch (pre-flow issue) -> manual_resume directly
        if not branch:
            service = BlockedStateService(
                github_client=self.github_client,
                store=self.store,
            )
            return service.manual_resume(
                issue_number=issue_number,
                branch=branch,
                target_state=target_state,
                actor=actor,
                reason=reason,
                force=force,
            )

        flow_state = self.store.get_flow_state(branch)

        # No flow record -> guide user to rebuild first
        if flow_state is None:
            raise UserError(
                f"No flow record found for branch '{branch}'. "
                f"Run: vibe3 flow rebuild {issue_number} --yes"
            )

        consistency = check_flow_consistency(
            branch, flow_state, git_client=self.git_client
        )

        if consistency.code == FlowConsistencyCode.OK:
            pass  # Scene fine, proceed to manual_resume
        elif consistency.fix_action:
            applied = apply_consistency_fix(consistency, branch, store=self.store)
            if applied:
                logger.bind(
                    domain="recovery", branch=branch, fix=consistency.fix_action
                ).info("Applied cheap consistency fix before manual resume")
        elif consistency.needs_rebuild:
            raise UserError(
                f"{consistency.reason}. "
                f"Run: vibe3 flow rebuild {issue_number} --yes"
            )

        service = BlockedStateService(
            github_client=self.github_client,
            store=self.store,
        )
        return service.manual_resume(
            issue_number=issue_number,
            branch=branch,
            target_state=target_state,
            actor=actor,
            reason=reason,
            force=force,
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
        """Hard rebuild through the canonical rebuild usecase.

        Per #3289 the rebuild usecase defaults to a no-op label_resume, so the
        physical scene is repaired without clearing business blocked truth.
        """
        from vibe3.config import load_orchestra_config
        from vibe3.models import IssueInfo, IssueState
        from vibe3.services.flow.rebuild import FlowRebuildUsecase
        from vibe3.services.issue.context import load_issue_info

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
            orchestrator=None,
        ).rebuild_issue_flow(
            issue=issue_info,
            branch=branch,
            reason=reason,
            ensure_worktree=ensure_worktree,
            include_remote=include_remote,
        )
