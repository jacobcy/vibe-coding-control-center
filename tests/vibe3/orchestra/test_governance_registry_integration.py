"""Tests for GovernanceService domain-first no-op tick behavior."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.models.orchestra_config import GovernanceConfig, OrchestraConfig
from vibe3.orchestra.services.governance_service import GovernanceService
from vibe3.services.orchestra_status_service import OrchestraSnapshot


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
    """Tests for GovernanceService no-op tick behavior."""

    @pytest.mark.asyncio
    async def test_on_tick_is_stub_not_affected_by_registry(self) -> None:
        """on_tick() is a stub and never dispatches from the service layer."""

        service = GovernanceService(
            config=OrchestraConfig(
                governance=GovernanceConfig(interval_ticks=1, dry_run=False)
            ),
            status_service=MockStatusService(),
            manager=_make_dispatcher(),
        )

        run_called = {"count": 0}

        async def fake_run() -> None:
            run_called["count"] += 1

        service._run_governance = fake_run  # type: ignore[method-assign]

        with patch(_APPEND_EVENT_PATH):
            await service.on_tick()

        # Domain-first: on_tick is a stub — no dispatch regardless of registry state
        assert run_called["count"] == 0, (
            "on_tick() should not call _run_governance(). "
            "Governance dispatch is triggered via OrchestrationFacade "
            "-> GovernanceScanStarted."
        )

    @pytest.mark.asyncio
    async def test_on_tick_is_stub_does_not_dispatch_even_when_no_live_session(
        self,
    ) -> None:
        """on_tick() is a stub, does NOT call _run_governance even when capacity free.

        Capacity availability check + dispatch is handled by the domain handler
        for GovernanceScanStarted (via CapacityService). on_tick() is never the
        dispatcher — it only increments the tick counter.
        """
        service = GovernanceService(
            config=OrchestraConfig(
                governance=GovernanceConfig(interval_ticks=1, dry_run=False)
            ),
            status_service=MockStatusService(),
            manager=_make_dispatcher(),
        )

        run_called = {"count": 0}

        async def fake_run() -> None:
            run_called["count"] += 1

        service._run_governance = fake_run  # type: ignore[method-assign]

        with patch(_APPEND_EVENT_PATH):
            await service.on_tick()

        # Domain-first: on_tick is a stub — no dispatch
        assert run_called["count"] == 0, (
            "on_tick() should not call _run_governance(). "
            "Governance dispatch is triggered via OrchestrationFacade "
            "-> GovernanceScanStarted."
        )

    @pytest.mark.asyncio
    async def test_on_tick_is_stub_does_not_depend_on_backend_state(self) -> None:
        """on_tick() is a stub and does not need backend/session knowledge."""
        service = GovernanceService(
            config=OrchestraConfig(
                governance=GovernanceConfig(interval_ticks=1, dry_run=False)
            ),
            status_service=MockStatusService(),
            manager=_make_dispatcher(),
        )

        run_called = {"count": 0}

        async def fake_run() -> None:
            run_called["count"] += 1

        service._run_governance = fake_run  # type: ignore[method-assign]

        with patch(_APPEND_EVENT_PATH):
            await service.on_tick()

        # Domain-first: on_tick is a stub — no dispatch, no tmux check
        assert run_called["count"] == 0, (
            "on_tick() should not call _run_governance(). "
            "Backend/session state is handled outside GovernanceService."
        )
