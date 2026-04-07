"""Tests for GovernanceService registry integration."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.orchestra.config import GovernanceConfig, OrchestraConfig
from vibe3.orchestra.services.governance_service import GovernanceService
from vibe3.orchestra.services.status_service import OrchestraSnapshot
from vibe3.services.session_registry import SessionRegistryService


class MockStatusService:
    """Mock status service for testing."""

    def __init__(self, snapshot: OrchestraSnapshot | None = None):
        self._snapshot = snapshot

    def snapshot(self) -> OrchestraSnapshot:
        if self._snapshot:
            return self._snapshot
        return OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(),
            active_flows=0,
            active_worktrees=0,
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
        )


def _make_dispatcher() -> MagicMock:
    """Create a mock manager-like dependency with repo_path."""
    dispatcher = MagicMock()
    dispatcher.repo_path = "/repo"
    return dispatcher


_APPEND_EVENT_PATH = (
    "vibe3.orchestra.services.governance_service.append_governance_event"
)


class TestGovernanceRegistryIntegration:
    """Tests for GovernanceService registry-backed live dispatch detection."""

    @pytest.mark.asyncio
    async def test_skips_when_live_governance_session_in_registry(self) -> None:
        """Skip tick when registry reports a live governance session."""
        registry = MagicMock(spec=SessionRegistryService)
        registry.count_live_governance_sessions.return_value = 1

        backend = MagicMock()
        backend.has_tmux_session_prefix.return_value = False

        service = GovernanceService(
            config=OrchestraConfig(
                governance=GovernanceConfig(interval_ticks=1, dry_run=False)
            ),
            status_service=MockStatusService(),
            manager=_make_dispatcher(),
            backend=backend,
            registry=registry,
        )
        service._tick_count = 0

        run_called = {"count": 0}

        async def fake_run() -> None:
            run_called["count"] += 1

        service._run_governance = fake_run  # type: ignore[method-assign]

        with patch(_APPEND_EVENT_PATH):
            await service.on_tick()

        assert run_called["count"] == 0
        registry.count_live_governance_sessions.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatches_when_no_live_governance_session_in_registry(
        self,
    ) -> None:
        """Dispatch governance when registry reports no live governance session."""
        registry = MagicMock(spec=SessionRegistryService)
        registry.count_live_governance_sessions.return_value = 0

        backend = MagicMock()
        backend.has_tmux_session_prefix.return_value = False

        service = GovernanceService(
            config=OrchestraConfig(
                governance=GovernanceConfig(interval_ticks=1, dry_run=False)
            ),
            status_service=MockStatusService(),
            manager=_make_dispatcher(),
            backend=backend,
            registry=registry,
        )
        service._tick_count = 0

        run_called = {"count": 0}

        async def fake_run() -> None:
            run_called["count"] += 1

        service._run_governance = fake_run  # type: ignore[method-assign]

        with patch(_APPEND_EVENT_PATH):
            await service.on_tick()

        assert run_called["count"] == 1

    @pytest.mark.asyncio
    async def test_fallback_to_tmux_prefix_when_no_registry(self) -> None:
        """Without registry, falls back to tmux prefix detection."""
        backend = MagicMock()
        backend.has_tmux_session_prefix.return_value = True

        service = GovernanceService(
            config=OrchestraConfig(
                governance=GovernanceConfig(interval_ticks=1, dry_run=False)
            ),
            status_service=MockStatusService(),
            manager=_make_dispatcher(),
            backend=backend,
        )
        service._tick_count = 0

        run_called = {"count": 0}

        async def fake_run() -> None:
            run_called["count"] += 1

        service._run_governance = fake_run  # type: ignore[method-assign]

        with patch(_APPEND_EVENT_PATH):
            await service.on_tick()

        assert run_called["count"] == 0
        backend.has_tmux_session_prefix.assert_called_once_with("vibe3-governance-scan")
