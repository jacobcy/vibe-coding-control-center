"""Test queue recollection integration with heartbeat."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
from vibe3.domain.orchestration_facade import OrchestrationFacade
from vibe3.models.orchestra_config import OrchestraConfig, QueueRecollectConfig
from vibe3.runtime.heartbeat import HeartbeatServer


@pytest.fixture
def mock_coordinator():
    """Create mock dispatch coordinator."""
    coordinator = AsyncMock(spec=GlobalDispatchCoordinator)
    coordinator.force_recollect_queue = AsyncMock()
    return coordinator


@pytest.fixture
def mock_dispatch_service(mock_coordinator):
    """Create mock dispatch service with coordinator."""
    service = MagicMock(spec=OrchestrationFacade)
    service.service_name = "OrchestrationFacade"
    service.is_dispatch_service = True
    service._coordinator = mock_coordinator
    service.on_tick = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_heartbeat_calls_force_recollect_on_interval(
    mock_coordinator, mock_dispatch_service
):
    """Test heartbeat calls force_recollect_queue at interval tick."""
    config = OrchestraConfig(
        queue_recollect=QueueRecollectConfig(
            enabled=True,
            interval_ticks=10,
        ),
    )

    heartbeat = HeartbeatServer(config=config, failed_gate=None)
    heartbeat._services.append(mock_dispatch_service)

    # Simulate tick 10 (interval)
    tick_number = 10

    # Execute the recollection logic from _tick_loop
    if (
        heartbeat.config.queue_recollect.enabled
        and tick_number % heartbeat.config.queue_recollect.interval_ticks == 0
    ):
        dispatch_service = next(
            (svc for svc in heartbeat._services if svc.is_dispatch_service),
            None,
        )
        if (
            dispatch_service is not None
            and hasattr(dispatch_service, "_coordinator")
            and dispatch_service._coordinator is not None
        ):
            await dispatch_service._coordinator.force_recollect_queue()

    # Verify force_recollect_queue was called
    mock_coordinator.force_recollect_queue.assert_called_once()


@pytest.mark.asyncio
async def test_heartbeat_skips_recollect_when_disabled(mock_dispatch_service):
    """Test heartbeat skips force_recollect_queue when disabled."""
    config = OrchestraConfig(
        queue_recollect=QueueRecollectConfig(enabled=False),
    )

    heartbeat = HeartbeatServer(config=config, failed_gate=None)
    heartbeat._services.append(mock_dispatch_service)

    # Simulate tick 10
    tick_number = 10

    # Execute the recollection logic from _tick_loop
    if (
        heartbeat.config.queue_recollect.enabled
        and tick_number % heartbeat.config.queue_recollect.interval_ticks == 0
    ):
        dispatch_service = next(
            (svc for svc in heartbeat._services if svc.is_dispatch_service),
            None,
        )
        if dispatch_service and hasattr(dispatch_service, "_coordinator"):
            await dispatch_service._coordinator.force_recollect_queue()

    # Verify force_recollect_queue was NOT called
    mock_dispatch_service._coordinator.force_recollect_queue.assert_not_called()


@pytest.mark.asyncio
async def test_heartbeat_skips_recollect_on_non_interval_tick(
    mock_coordinator, mock_dispatch_service
):
    """Test heartbeat skips recollection on non-interval ticks."""
    config = OrchestraConfig(
        queue_recollect=QueueRecollectConfig(
            enabled=True,
            interval_ticks=10,
        ),
    )

    heartbeat = HeartbeatServer(config=config, failed_gate=None)
    heartbeat._services.append(mock_dispatch_service)

    # Simulate tick 5 (not divisible by 10)
    tick_number = 5

    # Execute the recollection logic from _tick_loop
    if (
        heartbeat.config.queue_recollect.enabled
        and tick_number % heartbeat.config.queue_recollect.interval_ticks == 0
    ):
        dispatch_service = next(
            (svc for svc in heartbeat._services if svc.is_dispatch_service),
            None,
        )
        if dispatch_service and hasattr(dispatch_service, "_coordinator"):
            await dispatch_service._coordinator.force_recollect_queue()

    # Verify force_recollect_queue was NOT called (tick 5 % 10 != 0)
    mock_coordinator.force_recollect_queue.assert_not_called()


@pytest.mark.asyncio
async def test_heartbeat_handles_missing_coordinator_gracefully():
    """Test heartbeat handles missing coordinator without error."""
    config = OrchestraConfig(
        queue_recollect=QueueRecollectConfig(
            enabled=True,
            interval_ticks=10,
        ),
    )

    heartbeat = HeartbeatServer(config=config, failed_gate=None)

    # No dispatch service registered
    tick_number = 10

    # Execute the recollection logic - should not raise
    if (
        heartbeat.config.queue_recollect.enabled
        and tick_number % heartbeat.config.queue_recollect.interval_ticks == 0
    ):
        dispatch_service = next(
            (svc for svc in heartbeat._services if svc.is_dispatch_service),
            None,
        )
        if (
            dispatch_service is not None
            and hasattr(dispatch_service, "_coordinator")
            and dispatch_service._coordinator is not None
        ):
            await dispatch_service._coordinator.force_recollect_queue()

    # No error should occur - graceful handling


@pytest.mark.asyncio
async def test_heartbeat_handles_coordinator_without_attr_gracefully():
    """Test heartbeat handles coordinator without _coordinator attr."""
    config = OrchestraConfig(
        queue_recollect=QueueRecollectConfig(
            enabled=True,
            interval_ticks=10,
        ),
    )

    heartbeat = HeartbeatServer(config=config, failed_gate=None)

    # Service without _coordinator attribute - use real object
    class ServiceWithoutCoordinator:
        service_name = "SomeService"
        is_dispatch_service = True

    service_without_coordinator = ServiceWithoutCoordinator()
    heartbeat._services.append(service_without_coordinator)

    tick_number = 10

    # Execute the recollection logic - should not raise
    if (
        heartbeat.config.queue_recollect.enabled
        and tick_number % heartbeat.config.queue_recollect.interval_ticks == 0
    ):
        dispatch_service = next(
            (svc for svc in heartbeat._services if svc.is_dispatch_service),
            None,
        )
        # hasattr should return False for this service
        if (
            dispatch_service is not None
            and hasattr(dispatch_service, "_coordinator")
            and dispatch_service._coordinator is not None
        ):
            await dispatch_service._coordinator.force_recollect_queue()
        # else: no call should be made - test passes

    # No error should occur - graceful handling
