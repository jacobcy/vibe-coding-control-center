"""Unified capacity service: capacity control for all execution roles.

Provides simple capacity control based on live session count.
No in-flight or launching state tracking — true dispatch deduplication
should only rely on live tmux session existence.

Usage Guide: docs/v3/architecture/infrastructure-guide.md#capacityservice
"""

from __future__ import annotations

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

    Simple capacity model based on live session count only:
        remaining = max_concurrent_flows - active_count

    Where:
        - active_count: live worker sessions (starting/running) across all roles

    No in-flight or launching state tracking. True dispatch deduplication
    is handled by live tmux session check in GlobalDispatchCoordinator.

    Usage:
        service = CapacityService(config, store, backend)

        # Check capacity
        if service.can_dispatch(role):
            # ... dispatch logic ...
    """

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

    def can_dispatch(self, role: str) -> bool:
        """Check if global capacity allows another dispatch.

        Args:
            role: Execution role (used for logging only)

        Returns:
            True if capacity available, False if full
        """
        active_count = self._registry.count_live_worker_sessions()
        max_capacity = self.config.max_concurrent_flows
        remaining = max(0, max_capacity - active_count)

        can_dispatch = remaining > 0

        if not can_dispatch:
            logger.bind(
                domain="capacity",
                role=role,
                active=active_count,
                max=max_capacity,
            ).info(
                f"Global capacity full, skipping {role} "
                f"(live={active_count}, max={max_capacity})"
            )

        return can_dispatch

    def get_capacity_status(self, role: str) -> dict[str, int]:
        """Get current capacity status.

        Uses the same global pool model as can_dispatch for consistency.
        The role parameter is kept for logging/context only.

        Args:
            role: Execution role (used for context/logging)

        Returns:
            Dict with active_count, max_capacity, remaining
        """
        active_count = self._registry.count_live_worker_sessions()
        max_capacity = self.config.max_concurrent_flows
        remaining = max(0, max_capacity - active_count)

        return {
            "active_count": active_count,
            "max_capacity": max_capacity,
            "remaining": remaining,
        }
