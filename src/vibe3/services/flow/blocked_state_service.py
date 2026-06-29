"""Unified blocked state management service.

This service provides a single entry point for managing blocked state across
three data sources: database, issue body, and issue labels.

Design Principles:
1. Issue body + labels = Authoritative truth (remote-first)
2. Database = Performance cache (local optimization)
3. Qualify gate = Cache synchronizer (ensures coherence)
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients import GitHubClient
from vibe3.models import FlowStateProjection, IssueState
from vibe3.services.flow.blocked_state_io import BlockedStateIO
from vibe3.services.flow.blocked_state_types import (
    BlockedState,
    ConsistencyReport,
)
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
        """Authoritatively block flow by writing body truth, then reconcile.

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
        self.reconcile_blocked(issue_number, branch, clear_reason=False, actor=actor)

    def clear_block(
        self,
        issue_number: int,
        branch: str,
        *,
        clear_reason: bool = False,
        actor: str = "system",
    ) -> None:
        """Clear block status by invoking reconcile_blocked."""
        self.reconcile_blocked(
            issue_number, branch, clear_reason=clear_reason, actor=actor
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
            # Reset transition counters on unblock (replaces old clear_database_cache)
            update_kwargs["transition_count"] = 0
            update_kwargs["aup_rejection_count"] = 0
            update_kwargs["last_aup_rejection_at"] = None
        self.store.update_flow_state(branch, **update_kwargs)

        # Clear transition history on unblock to reset per-pair loop detection
        if not is_blocked:
            try:
                with sqlite3.connect(self.store.db_path) as conn:
                    self.store.clear_transition_history(conn, branch)
            except Exception as exc:
                logger.bind(
                    domain="blocked_state",
                    action="rebuild_cache",
                    branch=branch,
                ).warning(f"Failed to clear transition history: {exc}")

        # Update flow_issue_links dependencies list
        current_deps = self.store.get_dependency_links(branch)
        to_remove = set(current_deps) - set(open_tasks)
        to_add = set(open_tasks) - set(current_deps)

        for dep in to_remove:
            self.store.remove_issue_link(branch, dep, "dependency")
        for dep in to_add:
            self.store.add_issue_link(branch, dep, "dependency")

    def reconcile_blocked(
        self,
        issue_number: int,
        branch: str,
        *,
        clear_reason: bool = False,
        actor: str = "system",
    ) -> IssueState | None:
        """Authoritatively reconcile blocked state across body, labels, and cache."""
        from vibe3.models import FlowState
        from vibe3.observability import DegradedModeReason, get_degraded_manager
        from vibe3.services.flow.resume_resolver import infer_resume_label
        from vibe3.services.issue.body import parse_projection
        from vibe3.services.shared import DependencyResolutionService

        # 1. Read Remote Truth (handling Degraded Mode)
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
                action="reconcile_blocked",
                issue_number=issue_number,
                error=str(exc),
            ).warning("GitHub read failed; falling back to DB cache")
            # None = stay blocked / degraded. Callers must NOT treat None as
            # "recovered"; it means we could not verify truth, so we
            # conservatively keep blocking and skip cache rebuild.
            return None

        # 2. Clear Reason if requested (e.g. manual resume)
        if clear_reason:
            truth.blocked_reason = None
            new_proj = FlowStateProjection(
                state=truth.state,
                blocked_by=truth.blocked_by,
                blocked_reason=None,
            )
            self._io.write_projection(issue_number, new_proj)

        # 3. Check for open dependencies
        open_tasks: list[int] = []
        for task in truth.blocked_by:
            res = DependencyResolutionService.is_dependency_resolved(
                task,
                github_client=self._io.github,
            )
            if not res.resolved:
                open_tasks.append(task)

        # 4. Resolve State & Sync remote state section + labels
        effective_blocked = bool(truth.blocked_reason) or bool(open_tasks)
        if effective_blocked:
            target = None
            # R5: Prune closed deps from body so they aren't re-checked each cycle.
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
            # Always write label to ensure remote state/blocked is present.
            # DB cache cannot confirm remote label state (§7).
            self._io.write_label_state(issue_number, IssueState.BLOCKED, actor=actor)
        else:
            # Determine resume target
            target = IssueState.READY
            if branch and self.store:
                fs_dict = self.store.get_flow_state(branch)
            else:
                fs_dict = None
            if fs_dict:
                try:
                    target = infer_resume_label(FlowState.model_validate(fs_dict))
                except Exception:
                    target = IssueState.READY

            # Clear remote body state section
            new_proj = FlowStateProjection(
                state="active",
                blocked_by=[],
                blocked_reason=None,
            )
            self._io.write_projection(issue_number, new_proj)
            self._io.write_label_state(issue_number, target, actor=actor, force=True)
            truth = new_proj

        # 5. Rebuild Cache
        if branch:
            self.rebuild_cache_from_truth(branch, truth, open_tasks, actor=actor)

        return target

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
