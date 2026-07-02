"""Unified blocked state management service.

This service provides a single entry point for managing blocked state across
three data sources: database, issue body, and issue labels.

Design Principles:
1. Issue body + labels = Authoritative truth (remote-first)
2. Database = Performance cache (local optimization)
3. Qualify gate = Cache synchronizer (ensures coherence)

Authority separation (#3289):
- ``sync_block_state``        — align cache/label to truth (no resume, no
                                reason clearing, no target inference).
- ``evaluate_auto_eligibility`` — read-only eligibility check bound to an
                                ``updatedAt`` snapshot; never mutates.
- ``apply_auto_resume``       — consume a snapshot-bound decision; existing
                                flow -> handoff, pre-flow -> ready. Rejects
                                stale decisions when truth changed.
- ``manual_resume``           — human-authorized clear of blocked_reason +
                                explicit/inferred target. Fail closed on open
                                deps unless ``force=True``.

No method on the auto path can clear a human blocked_reason or infer a target
from local refs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients import GitHubClient
from vibe3.exceptions import UserError
from vibe3.models import FlowStateProjection, IssueState
from vibe3.services.flow.blocked_state_io import BlockedStateIO
from vibe3.services.flow.blocked_state_types import (
    AutoResumeDecision,
    AutoResumeReasonCode,
    AutoResumeVerdict,
    BlockedState,
    ConsistencyReport,
    ResumeResult,
)
from vibe3.services.flow.transition_recorder import TransitionRecorder
from vibe3.services.shared.label_service import LabelService

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient


class BlockedStateService:
    """Single entry point for blocked state management.

    Coordinates writes across three sources:
    1. Issue body (truth) - critical, must succeed
    2. Database (cache) - non-critical, can be stale
    3. Labels (signal) - non-critical, can be stale
    """

    def __init__(
        self,
        github_client: GitHubClient | None = None,
        label_service: LabelService | None = None,
        store: SQLiteClient | None = None,
    ) -> None:
        self._io = BlockedStateIO(
            github_client=github_client,
            label_service=label_service,
            store=store,
        )
        self.store = store
        self._transition_recorder = TransitionRecorder(store) if store else None

    # ========================================================================
    # Public API: Write Operations
    # ========================================================================

    def set_block(
        self,
        issue_number: int,
        branch: str,
        *,
        reason: str | None = None,
        tasks: list[int] | None = None,
        actor: str = "system",
    ) -> None:
        """Authoritatively block flow by writing body truth, then sync.

        Caller MUST resolve issue_number to a non-None int before calling;
        cache-only writes (no issue context) should use ``write_cache`` instead.
        """
        current_body = self._io.github.get_issue_body(issue_number)
        if current_body is None:
            raise RuntimeError(f"Issue #{issue_number} body is None")
        from vibe3.services.issue.body import parse_projection

        projection = parse_projection(current_body)

        # Merge fields
        new_blocked_by = set(projection.blocked_by)
        if tasks:
            new_blocked_by.update(tasks)

        new_reason = reason or projection.blocked_reason

        new_projection = FlowStateProjection(
            state="blocked",
            blocked_by=sorted(list(new_blocked_by)),
            blocked_reason=new_reason,
        )

        self._io.write_projection(issue_number, new_projection)
        self.sync_block_state(issue_number, branch, actor=actor)

    def manual_resume(
        self,
        issue_number: int,
        branch: str,
        *,
        target_state: IssueState | None = None,
        actor: str,
        reason: str,
        force: bool = False,
    ) -> ResumeResult:
        """Human-authorized resume: clear blocked_reason and advance to target.

        Only invoked by explicit human commands (``vibe3 task resume``). Using
        this method rather than the auto path carries ``ResumeSource.MANUAL_COMMAND``
        semantics.

        Args:
            issue_number: GitHub issue number.
            branch: Flow branch (may be empty for pre-flow issues).
            target_state: Explicit target label. When None, the authorized
                manual resolver infers it from local refs (plan/pr/verdict).
            actor: Human actor identifier (recorded for audit).
            reason: Human-readable resume reason (recorded for audit).
            force: When True, proceed even if dependencies are still open.
                Auditable override; defaults to False (fail closed).

        Returns:
            ResumeResult with the outcome.

        Raises:
            UserError: When dependencies are open and ``force`` is False, or
                when GitHub truth is unreadable (fail closed).
        """
        from vibe3.observability import DegradedModeReason, get_degraded_manager
        from vibe3.services.issue.body import parse_projection

        # 1. Read Remote Truth (fail closed on degraded mode)
        try:
            body = self._io.github.get_issue_body(issue_number)
            if body is None:
                raise RuntimeError(f"Issue #{issue_number} body is None")
            truth = parse_projection(body)
            get_degraded_manager().exit_degraded_mode()
        except Exception as exc:
            get_degraded_manager().enter_degraded_mode(
                DegradedModeReason.GITHUB_API_ERROR
            )
            raise UserError(
                f"Cannot resume #{issue_number}: GitHub truth unreadable ({exc})"
            ) from exc

        # 2. Check dependencies (fail closed unless force)
        open_deps = self._collect_open_deps(truth.blocked_by)
        if open_deps and not force:
            raise UserError(
                f"Cannot resume #{issue_number}: open dependencies remain "
                f"({open_deps}). Resolve them first, or pass --force to override."
            )

        # 3. Current label must be BLOCKED for a resume transition to make sense
        current_state = self._io.read_issue_state(issue_number)
        if current_state is not None and current_state != IssueState.BLOCKED:
            return ResumeResult(
                success=False,
                target_state=None,
                detail=(
                    f"Issue #{issue_number} is {current_state.to_label()}, "
                    "not blocked; nothing to resume"
                ),
            )

        # 4. Resolve target (explicit > authorized manual inference)
        resolved_target = target_state
        if resolved_target is None:
            resolved_target = self._infer_manual_target(branch) or IssueState.READY

        # 5. Transition budget guard
        if self._would_exceed_budget(branch, IssueState.BLOCKED, resolved_target):
            return ResumeResult(
                success=False,
                target_state=None,
                detail="Transition budget exceeded; flow remains blocked",
            )

        # 6. Authorized clear of blocked_reason + publish target label.
        # If label I/O fails, body and cache must remain blocked.
        write_result = self._io.write_label_state(
            issue_number,
            resolved_target,
            actor=actor,
            force=True,
            normalize=True,
        )
        if write_result not in {"advanced", "normalized"}:
            return ResumeResult(
                success=False,
                target_state=None,
                detail=f"Label transition rejected ({write_result})",
            )

        self._record_confirmed_transition(
            branch, IssueState.BLOCKED, resolved_target, actor, issue_number
        )

        # 7. Clear body projection (authorized) and rebuild cache
        new_proj = FlowStateProjection(
            state="active",
            blocked_by=[],
            blocked_reason=None,
        )
        self._io.write_projection(issue_number, new_proj)
        if branch:
            self.rebuild_cache_from_truth(branch, new_proj, [], actor=actor)

        logger.bind(
            domain="blocked_state",
            action="manual_resume",
            issue_number=issue_number,
            branch=branch,
            target=resolved_target.to_label(),
            actor=actor,
        ).info("Manual resume cleared blocked reason and advanced to target")

        return ResumeResult(
            success=True,
            target_state=resolved_target,
            detail=f"Resumed to {resolved_target.to_label()}",
        )

    def rebuild_cache_from_truth(
        self,
        branch: str,
        truth: FlowStateProjection,
        open_tasks: list[int],
        actor: str = "system",
    ) -> None:
        """Rebuild database flow_state and flow_issue_links cache from body truth."""
        if not branch or not self.store:
            return

        is_blocked = bool(truth.blocked_reason) or bool(open_tasks)
        blocked_by_issue = open_tasks[0] if open_tasks else None

        # Update flow status pointer, reason, and main dependency
        update_kwargs: dict[str, object] = {
            "flow_status": "blocked" if is_blocked else "active",
            "blocked_reason": truth.blocked_reason,
            "blocked_by_issue": blocked_by_issue,
            "latest_actor": actor,
        }
        if not is_blocked:
            update_kwargs["aup_rejection_count"] = 0
            update_kwargs["last_aup_rejection_at"] = None
        self.store.update_flow_state(branch, **update_kwargs)

        # Update flow_issue_links dependencies list
        current_deps = self.store.get_dependency_links(branch)
        to_remove = set(current_deps) - set(open_tasks)
        to_add = set(open_tasks) - set(current_deps)

        for dep in to_remove:
            self.store.remove_issue_link(branch, dep, "dependency")
        for dep in to_add:
            self.store.add_issue_link(branch, dep, "dependency")

    # ========================================================================
    # Public API: Auto resume (read-only eligibility + snapshot-bound apply)
    # ========================================================================

    def evaluate_auto_eligibility(
        self,
        issue_number: int,
        branch: str,
    ) -> AutoResumeDecision:
        """Read-only auto resume eligibility check, bound to a truth snapshot.

        Never mutates body, label, or cache. Returns a decision the caller
        passes to ``apply_auto_resume``; the decision carries the GitHub issue
        ``updatedAt`` as an optimistic-lock snapshot.

        Eligibility requires ALL of:
        - GitHub body truth readable (else ``truth_unreadable``)
        - ``blocked_reason`` absent (else ``human_reason_present``)
        - every ``blocked_by`` dependency CLOSED (else ``dependency_open``)
        """
        from vibe3.observability import DegradedModeReason, get_degraded_manager
        from vibe3.services.issue.body import parse_projection

        # 1. Read body + updatedAt snapshot in a single API call
        try:
            snapshot = self._io.github.get_issue_snapshot(issue_number)
            if snapshot is None:
                raise RuntimeError(f"Issue #{issue_number} snapshot is None")
            body, updated_at = snapshot
            if body is None:
                raise RuntimeError(f"Issue #{issue_number} body is None")
            truth = parse_projection(body)
            get_degraded_manager().exit_degraded_mode()
        except Exception as exc:
            get_degraded_manager().enter_degraded_mode(
                DegradedModeReason.GITHUB_API_ERROR
            )
            logger.bind(
                domain="blocked_state",
                action="evaluate_auto_eligibility",
                issue_number=issue_number,
                error=str(exc),
            ).warning("Auto resume eligibility: truth unreadable")
            return AutoResumeDecision(
                verdict=AutoResumeVerdict.NOT_ELIGIBLE,
                reason_code=AutoResumeReasonCode.TRUTH_UNREADABLE,
                issue_number=issue_number,
                branch=branch,
                truth_snapshot=None,
            )

        # 2. Human blocked_reason present -> auto path must not clear it
        if truth.blocked_reason:
            return AutoResumeDecision(
                verdict=AutoResumeVerdict.NOT_ELIGIBLE,
                reason_code=AutoResumeReasonCode.HUMAN_REASON_PRESENT,
                issue_number=issue_number,
                branch=branch,
                truth_snapshot=updated_at,
            )

        # 3. Every dependency must be confirmed CLOSED
        closed_deps: list[int] = []
        for dep in truth.blocked_by:
            if not self._is_dep_resolved(dep):
                return AutoResumeDecision(
                    verdict=AutoResumeVerdict.NOT_ELIGIBLE,
                    reason_code=AutoResumeReasonCode.DEPENDENCY_OPEN,
                    issue_number=issue_number,
                    branch=branch,
                    truth_snapshot=updated_at,
                )
            closed_deps.append(dep)

        return AutoResumeDecision(
            verdict=AutoResumeVerdict.ELIGIBLE,
            reason_code=AutoResumeReasonCode.ELIGIBLE,
            issue_number=issue_number,
            branch=branch,
            truth_snapshot=updated_at,
            closed_deps=closed_deps,
        )

    def apply_auto_resume(self, decision: AutoResumeDecision) -> ResumeResult:
        """Consume a snapshot-bound eligible decision; reject stale decisions.

        Existing flow scene -> ``state/handoff`` (manager re-checks external
        conditions). Pre-flow issue (no scene) -> ``state/ready``. Never infers
        target from ``plan_ref``/``pr_ref``.

        Returns a failed ResumeResult (zero mutation) when:
        - decision is not eligible (caller error)
        - truth changed between evaluate and apply (stale snapshot)
        - current label is not BLOCKED (already advanced or inconsistent)
        """
        if decision.verdict != AutoResumeVerdict.ELIGIBLE:
            return ResumeResult(
                success=False,
                target_state=None,
                detail=(f"Cannot apply non-eligible decision ({decision.reason_code})"),
            )

        # 1. Optimistic lock: reject if truth changed after evaluation
        current_snapshot = self._safe_get_snapshot(decision.issue_number)
        if (
            decision.truth_snapshot is not None
            and current_snapshot is not None
            and current_snapshot != decision.truth_snapshot
        ):
            logger.bind(
                domain="blocked_state",
                action="apply_auto_resume",
                issue_number=decision.issue_number,
                branch=decision.branch,
            ).warning("Stale auto resume decision rejected (truth changed)")
            return ResumeResult(
                success=False,
                target_state=None,
                detail="Stale decision: issue truth changed after evaluation",
            )

        # 2. Current label must be BLOCKED
        current_state = self._io.read_issue_state(decision.issue_number)
        if current_state is not None and current_state != IssueState.BLOCKED:
            return ResumeResult(
                success=False,
                target_state=None,
                detail=(
                    f"Issue #{decision.issue_number} is "
                    f"{current_state.to_label()}, not blocked; "
                    "auto resume is a no-op"
                ),
            )

        # 3. Target: existing flow scene -> handoff; pre-flow -> ready
        target = self._auto_resume_target(decision.branch)

        # 4. Transition budget guard
        if self._would_exceed_budget(decision.branch, IssueState.BLOCKED, target):
            return ResumeResult(
                success=False,
                target_state=None,
                detail="Transition budget exceeded; flow remains blocked",
            )

        # 5. Publish target label (force=True, normalize=True for resume)
        write_result = self._io.write_label_state(
            decision.issue_number,
            target,
            actor="system:auto_resume",
            force=True,
            normalize=True,
        )
        if write_result not in {"advanced", "normalized"}:
            return ResumeResult(
                success=False,
                target_state=None,
                detail=f"Label transition rejected ({write_result})",
            )

        self._record_confirmed_transition(
            decision.branch,
            IssueState.BLOCKED,
            target,
            "system:auto_resume",
            decision.issue_number,
        )

        # 6. Clear body projection (reason was already absent — eligibility
        # precondition) and rebuild cache from the resolved truth.
        new_proj = FlowStateProjection(
            state="active",
            blocked_by=[],
            blocked_reason=None,
        )
        self._io.write_projection(decision.issue_number, new_proj)
        if decision.branch:
            self.rebuild_cache_from_truth(
                decision.branch, new_proj, [], actor="system:auto_resume"
            )

        logger.bind(
            domain="blocked_state",
            action="apply_auto_resume",
            issue_number=decision.issue_number,
            branch=decision.branch,
            target=target.to_label(),
            closed_deps=decision.closed_deps,
        ).info("Auto resume advanced eligible blocked flow")
        return ResumeResult(
            success=True,
            target_state=target,
            detail=f"Auto resume to {target.to_label()}",
        )

    # ========================================================================
    # Public API: Block synchronization (no resume, no reason clearing)
    # ========================================================================

    def sync_block_state(
        self,
        issue_number: int,
        branch: str,
        *,
        actor: str = "system",
    ) -> None:
        """Align cache and label to body truth — blocked direction only.

        Does NOT clear blocked_reason, infer a target, or resume. When truth is
        no longer blocked, returns without mutation; callers that need to
        advance a flow use ``evaluate_auto_eligibility`` + ``apply_auto_resume``
        (auto) or ``manual_resume`` (authorized).

        Used by ``set_block`` and check rules that align stale cache/label to
        authoritative body truth.
        """
        from vibe3.observability import DegradedModeReason, get_degraded_manager
        from vibe3.services.issue.body import parse_projection

        # 1. Read Remote Truth (handle degraded mode)
        try:
            body = self._io.github.get_issue_body(issue_number)
            if body is None:
                raise RuntimeError(f"Issue #{issue_number} body is None")
            truth = parse_projection(body)
            get_degraded_manager().exit_degraded_mode()
        except Exception as exc:
            get_degraded_manager().enter_degraded_mode(
                DegradedModeReason.GITHUB_API_ERROR
            )
            logger.bind(
                domain="blocked_state",
                action="sync_block_state",
                issue_number=issue_number,
                error=str(exc),
            ).warning("GitHub read failed; skip block sync")
            return

        # 2. Check dependencies
        open_tasks = self._collect_open_deps(truth.blocked_by)

        effective_blocked = bool(truth.blocked_reason) or bool(open_tasks)
        if not effective_blocked:
            # Truth is not blocked — not this method's job to resume.
            return

        # 3. Prune closed deps from body so they aren't re-checked each cycle
        body_needs_update = truth.state != "blocked" or set(open_tasks) != set(
            truth.blocked_by
        )
        if body_needs_update:
            new_proj = FlowStateProjection(
                state="blocked",
                blocked_by=sorted(open_tasks),
                blocked_reason=truth.blocked_reason,
            )
            self._io.write_projection(issue_number, new_proj)
            truth = new_proj

        # 4. Ensure remote label carries state/blocked
        current_state = self._io.read_issue_state(issue_number)
        write_result = self._io.write_label_state(
            issue_number, IssueState.BLOCKED, actor=actor
        )
        if (
            branch
            and current_state is not None
            and current_state != IssueState.BLOCKED
            and write_result in {"advanced", "normalized"}
            and self._transition_recorder is not None
        ):
            self._transition_recorder.record_confirmed(
                branch=branch,
                from_state=current_state.to_label(),
                to_state=IssueState.BLOCKED.to_label(),
                actor=actor,
                issue_number=issue_number,
            )

        # 5. Rebuild cache from truth
        if branch:
            self.rebuild_cache_from_truth(branch, truth, open_tasks, actor=actor)

    # ========================================================================
    # Public API: Query Operations
    # ========================================================================

    def is_blocked(
        self,
        branch: str,
        issue_number: int,
    ) -> bool:
        """Check if flow is blocked (reads from authoritative truth)."""
        state = self.resolve_truth(branch, issue_number)
        return state.is_blocked

    def get_blocked_reason(
        self,
        branch: str,
        issue_number: int,
    ) -> str | None:
        """Get blocked reason from authoritative truth."""
        state = self.resolve_truth(branch, issue_number)
        return state.blocked_reason

    def write_cache(
        self,
        branch: str,
        reason: str | None,
        blocked_by_issue: int | None,
        actor: str = "system",
    ) -> None:
        """Write blocked state to database cache only (no body/label update).

        Use when you need to update the cache without touching the truth source.
        For example, qualify gate uses this to align cache to truth.
        """
        self._io.write_database_cache(
            branch=branch,
            reason=reason,
            blocked_by_issue=blocked_by_issue,
            actor=actor,
        )

    # ========================================================================
    # Public API: Synchronization
    # ========================================================================

    def resolve_truth(
        self,
        branch: str,
        issue_number: int,
    ) -> BlockedState:
        """Resolve authoritative truth, fallback to database in degraded mode."""
        from vibe3.services.issue.body import parse_projection

        try:
            body = self._io.github.get_issue_body(issue_number)
            if body is None:
                raise RuntimeError()
            proj = parse_projection(body)
            return BlockedState(
                is_blocked=proj.state == "blocked",
                blocked_reason=proj.blocked_reason,
                blocked_by=proj.blocked_by,
                state=proj.state,
            )
        except Exception:
            return self._io.read_database_cache(branch)

    def validate_consistency(
        self,
        branch: str,
        issue_number: int,
    ) -> ConsistencyReport:
        """Validate consistency across all three sources."""
        return ConsistencyReport(
            database_state=self._io.read_database_cache(branch),
            body_state=self._io.read_body_projection(issue_number),
            label_state=self._io.read_label_state(issue_number),
        )

    # ========================================================================
    # Internal helpers
    # ========================================================================

    def _is_dep_resolved(self, dep: int) -> bool:
        """Check whether a dependency issue is CLOSED (fail-closed on error)."""
        from vibe3.services.shared import DependencyResolutionService

        return DependencyResolutionService.is_dependency_resolved(
            dep,
            github_client=self._io.github,
        ).resolved

    def _collect_open_deps(self, blocked_by: list[int]) -> list[int]:
        """Return dependency issue numbers that are still open."""
        open_tasks: list[int] = []
        for task in blocked_by:
            if not self._is_dep_resolved(task):
                open_tasks.append(task)
        return open_tasks

    def _safe_get_snapshot(self, issue_number: int) -> str | None:
        """Best-effort read of issue updatedAt; None on any failure."""
        try:
            snapshot = self._io.github.get_issue_snapshot(issue_number)
            if snapshot is None:
                return None
            return snapshot[1]
        except Exception:
            return None

    def _auto_resume_target(self, branch: str) -> IssueState:
        """Existing flow scene -> handoff; pre-flow -> ready.

        Per #3289 the auto path must NOT infer from plan_ref/pr_ref. The only
        safe target for an existing flow is handoff so the manager can
        re-verify external conditions.
        """
        if branch and self.store:
            fs_dict = self.store.get_flow_state(branch)
        else:
            fs_dict = None
        return IssueState.HANDOFF if fs_dict else IssueState.READY

    def _infer_manual_target(self, branch: str) -> IssueState | None:
        """Authorized manual resolver — infers target from local refs.

        Only the manual path may use ref-based inference; the auto path is
        hardcoded to handoff/ready via ``_auto_resume_target``.
        """
        from vibe3.models import FlowState
        from vibe3.services.flow.resume_resolver import infer_resume_label

        if not branch or not self.store:
            return None
        fs_dict = self.store.get_flow_state(branch)
        if not fs_dict:
            return None
        try:
            return infer_resume_label(FlowState.model_validate(fs_dict))
        except Exception:
            return None

    def _would_exceed_budget(
        self, branch: str, from_state: IssueState, to_state: IssueState
    ) -> bool:
        if not branch or self._transition_recorder is None:
            return False
        return self._transition_recorder.would_exceed(
            branch,
            from_state.to_label(),
            to_state.to_label(),
        )

    def _record_confirmed_transition(
        self,
        branch: str,
        from_state: IssueState,
        to_state: IssueState,
        actor: str,
        issue_number: int,
    ) -> None:
        if not branch or self._transition_recorder is None:
            return
        self._transition_recorder.record_confirmed(
            branch=branch,
            from_state=from_state.to_label(),
            to_state=to_state.to_label(),
            actor=actor,
            issue_number=issue_number,
        )
