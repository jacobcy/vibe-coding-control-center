"""Unified capacity service: capacity control for all execution roles.

Solves the dual-layer throttling problem by providing a single capacity check
point that combines live session count and in-flight dispatch tracking.

Usage Guide: docs/v3/architecture/infrastructure-guide.md#capacityservice
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients.protocols import BackendProtocol
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.environment.session_registry import SessionRegistryService
from vibe3.models.orchestra_config import OrchestraConfig

if TYPE_CHECKING:
    pass


class CapacityService:
    """Unified capacity control for all execution roles.

    Combines live session count and in-flight dispatch tracking to prevent
    dual-layer throttling issues between StateLabelDispatchService and
    ManagerExecutor.

    Capacity Formula:
        remaining = max_capacity(role) - active_count(role) - in_flight_count(role)

    Where:
        - active_count: live worker sessions (starting/running) for the role
        - in_flight_count: targets being dispatched right now for the role

    Usage:
        service = CapacityService(config, store, backend)

        # Check before dispatch
        if service.can_dispatch("manager", issue_number):
            service.mark_in_flight("manager", issue_number)
            # ... dispatch logic ...
            service.prune_in_flight("manager", {issue_number})
    """

    _shared_in_flight_dispatches: dict[str, dict[str, set[int]]] = {}

    def __init__(
        self,
        config: OrchestraConfig,
        store: SQLiteClient,
        backend: BackendProtocol,
    ) -> None:
        """Initialize capacity service.

        Args:
            config: Orchestra config with max_concurrent_flows
            store: SQLite client for session registry
            backend: Backend protocol for tmux liveness check
        """
        self.config = config
        self._store = store
        self._backend = backend
        self._registry = SessionRegistryService(store, backend)
        # Track in-flight dispatches per role, shared by the underlying handoff DB
        # so separate handlers/ticks see the same dispatch truth.
        shared_key = str(Path(store.db_path).resolve())
        shared = self._shared_in_flight_dispatches.get(shared_key)
        if shared is None:
            shared = defaultdict(set)
            self._shared_in_flight_dispatches[shared_key] = shared
        self._in_flight_dispatches = shared

    def can_dispatch(self, role: str, target_id: int) -> bool:
        """Check if global capacity allows another dispatch.

        Uses a GLOBAL pool shared across all worker roles, so the total
        number of concurrently active agents (any role) is capped at
        max_concurrent_flows. This prevents role-local pools from
        individually filling up to 3× or 4× the intended concurrency.

        Args:
            role: Execution role (manager, planner, executor, reviewer, supervisor)
            target_id: Target ID (e.g., issue number)

        Returns:
            True if capacity available, False if should throttle/queue
        """
        # Count ALL live worker sessions, not just this role's.
        active_count = self._registry.count_live_worker_sessions()
        # Count ALL in-flight dispatches across every role.
        in_flight_count = sum(len(v) for v in self._in_flight_dispatches.values())
        max_capacity = self.config.max_concurrent_flows
        remaining = max(0, max_capacity - active_count - in_flight_count)

        can_dispatch = remaining > 0

        if not can_dispatch:
            logger.bind(
                domain="capacity",
                role=role,
                target=target_id,
                active=active_count,
                in_flight=in_flight_count,
                max=max_capacity,
            ).info(
                f"Global capacity full, skipping {role} #{target_id} "
                f"(live={active_count}, in_flight={in_flight_count}, "
                f"max={max_capacity})"
            )

        return can_dispatch

    def mark_in_flight(self, role: str, target_id: int) -> None:
        """Mark target as in-flight (being dispatched) for role.

        Args:
            role: Execution role
            target_id: Target ID to track
        """
        self._in_flight_dispatches[role].add(target_id)
        logger.bind(
            domain="capacity",
            role=role,
            target=target_id,
            in_flight_count=len(self._in_flight_dispatches[role]),
        ).debug(f"Marked {role} #{target_id} as in-flight")

    def prune_in_flight(self, role: str, target_ids: set[int]) -> None:
        """Remove in-flight markers for completed/failed dispatches.

        Args:
            role: Execution role
            target_ids: Targets to prune
        """
        before = len(self._in_flight_dispatches.get(role, set()))
        self._in_flight_dispatches[role].difference_update(target_ids)
        after = len(self._in_flight_dispatches.get(role, set()))

        if before != after:
            logger.bind(
                domain="capacity",
                role=role,
                pruned=before - after,
                remaining_in_flight=after,
            ).debug(f"Pruned {before - after} in-flight dispatches for {role}")

    def reconcile_in_flight(self) -> None:
        """Prune in-flight markers that are now live SQLite sessions.

        Called at the start of each coordinator tick to prevent permanent
        capacity deadlock: when a successfully-dispatched agent registers in
        SQLite, its in-flight marker is no longer needed and must be removed,
        otherwise it double-counts against capacity forever.
        """
        for role in list(self._in_flight_dispatches.keys()):
            pending = self._in_flight_dispatches.get(role)
            if not pending:
                continue
            # Get live sessions for this role from SQLite
            live_sessions = self._store.list_live_runtime_sessions(role=role)
            live_target_ids: set[int] = set()
            for session in live_sessions:
                raw = session.get("target_id")
                if raw is not None:
                    try:
                        live_target_ids.add(int(raw))
                    except (ValueError, TypeError):
                        pass
            # Prune in_flight for any target now registered as a live session
            now_live = pending & live_target_ids
            if now_live:
                self.prune_in_flight(role, now_live)
                logger.bind(
                    domain="capacity",
                    role=role,
                    reconciled=sorted(now_live),
                ).debug(
                    f"reconcile_in_flight: pruned {len(now_live)} stale "
                    f"in-flight entries for {role} (now live in SQLite)"
                )

    @property
    def in_flight_dispatches(self) -> dict[str, set[int]]:
        """Current in-flight dispatches per role."""
        return self._in_flight_dispatches

    def get_capacity_status(self, role: str) -> dict[str, int]:
        """Get current capacity status.

        Uses the same global pool model as can_dispatch for consistency.
        The role parameter is kept for logging/context only.

        Args:
            role: Execution role (used for context/logging)

        Returns:
            Dict with active_count, in_flight_count, max_capacity, remaining
        """
        active_count = self._registry.count_live_worker_sessions()
        in_flight_count = sum(len(v) for v in self._in_flight_dispatches.values())
        max_capacity = self.config.max_concurrent_flows
        remaining = max(0, max_capacity - active_count - in_flight_count)

        return {
            "active_count": active_count,
            "in_flight_count": in_flight_count,
            "max_capacity": max_capacity,
            "remaining": remaining,
        }

    def _get_max_capacity(self, role: str) -> int:
        """Get max capacity for role.

        Args:
            role: Execution role

        Returns:
            Maximum concurrent dispatches for the role
        """
        # Per-role capacity configuration
        role_capacity_map = {
            "manager": self.config.max_concurrent_flows,
            "governance": self.config.governance_max_concurrent,
            "supervisor": self.config.supervisor_max_concurrent,
            "planner": self.config.max_concurrent_flows,  # Uses default
            "executor": self.config.max_concurrent_flows,  # Uses default
            "reviewer": self.config.max_concurrent_flows,  # Uses default
        }

        return role_capacity_map.get(role, self.config.max_concurrent_flows)
