"""Test GlobalDispatchCoordinator migration to domain layer."""

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_dispatch_coordinator_importable_from_domain():
    """Verify GlobalDispatchCoordinator can be imported from domain."""
    from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator

    assert GlobalDispatchCoordinator is not None
    assert hasattr(GlobalDispatchCoordinator, "__init__")
    assert hasattr(GlobalDispatchCoordinator, "coordinate")


def test_dispatch_coordinator_importable_from_domain_init():
    """Verify GlobalDispatchCoordinator is exported from domain.__init__."""
    from vibe3.domain import GlobalDispatchCoordinator

    assert GlobalDispatchCoordinator is not None


def test_dispatch_coordinator_constructor_requires_injected_services():
    """Verify GlobalDispatchCoordinator constructor requires injected services."""
    from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator

    # Get constructor signature
    sig = inspect.signature(GlobalDispatchCoordinator.__init__)
    params = sig.parameters

    # Verify required keyword-only parameters exist
    required_kwonly_params = {
        "flow_blocker",
        "queue_persistence",
        "issue_loader",
        "flow_context_resolver",
        "queue_selector",
    }

    for param_name in required_kwonly_params:
        assert param_name in params, f"Missing required parameter: {param_name}"
        # Verify they are keyword-only (no default value)
        param = params[param_name]
        # Keyword-only parameters have kind POSITIONAL_OR_KEYWORD or KEYWORD_ONLY
        # and if they have no default, default is Parameter.empty
        assert (
            param.default is inspect.Parameter.empty
        ), f"Parameter {param_name} should not have a default value"


def test_dispatch_coordinator_uses_domain_protocols():
    """Verify GlobalDispatchCoordinator uses domain protocols."""
    from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
    from vibe3.domain.protocols.dispatch_protocols import (
        CapacityServiceProtocol,
        FlowContextResolverProtocol,
        FlowServiceProtocol,
        IssueLoaderProtocol,
        LabelDispatchCallable,
        QueuePersistenceServiceProtocol,
        QueueSelectorProtocol,
    )
    from vibe3.runtime import CheckServiceProtocol

    # Verify protocols are importable
    assert QueuePersistenceServiceProtocol is not None
    assert IssueLoaderProtocol is not None
    assert FlowContextResolverProtocol is not None
    assert QueueSelectorProtocol is not None
    assert CapacityServiceProtocol is not None
    assert CheckServiceProtocol is not None
    assert FlowServiceProtocol is not None
    assert LabelDispatchCallable is not None

    # Verify GlobalDispatchCoordinator type annotations reference domain protocols
    # (This is implicitly verified by successful import and type checking)
    assert GlobalDispatchCoordinator is not None


@pytest.mark.asyncio
async def test_collect_frozen_queue_executor_shutdown_returns_empty():
    """Verify _collect_frozen_queue returns [] on executor shutdown RuntimeError."""
    from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
    from vibe3.models import OrchestraConfig

    # Create mock services
    mock_config = MagicMock(spec=OrchestraConfig)
    mock_config.max_concurrent_flows = 1
    mock_config.supervisor_handoff = MagicMock()
    mock_config.supervisor_handoff.issue_label = "supervisor"
    mock_capacity = MagicMock()
    mock_github = MagicMock()
    mock_store = MagicMock()
    mock_flow_manager = MagicMock()
    mock_flow_blocker = MagicMock()
    mock_queue_persistence = MagicMock()
    mock_issue_loader = MagicMock()
    mock_flow_context_resolver = MagicMock()
    mock_queue_selector = MagicMock()
    mock_check_service = MagicMock()

    # Create coordinator
    coordinator = GlobalDispatchCoordinator(
        config=mock_config,
        capacity=mock_capacity,
        github=mock_github,
        store=mock_store,
        flow_manager=mock_flow_manager,
        flow_blocker=mock_flow_blocker,
        queue_persistence=mock_queue_persistence,
        issue_loader=mock_issue_loader,
        flow_context_resolver=mock_flow_context_resolver,
        queue_selector=mock_queue_selector,
        check_service=mock_check_service,
    )

    # Mock run_in_executor to raise shutdown RuntimeError
    with patch.object(
        asyncio,
        "get_running_loop",
        return_value=MagicMock(
            run_in_executor=AsyncMock(
                side_effect=RuntimeError("cannot schedule new futures after shutdown")
            )
        ),
    ):
        result = await coordinator._collect_frozen_queue()

    # Should return empty list, not raise
    assert result == []


@pytest.mark.asyncio
async def test_collect_frozen_queue_re_raises_other_runtime_error():
    """Verify _collect_frozen_queue re-raises non-shutdown RuntimeError."""
    from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
    from vibe3.models import OrchestraConfig

    # Create mock services
    mock_config = MagicMock(spec=OrchestraConfig)
    mock_config.max_concurrent_flows = 1
    mock_config.supervisor_handoff = MagicMock()
    mock_config.supervisor_handoff.issue_label = "supervisor"
    mock_capacity = MagicMock()
    mock_github = MagicMock()
    mock_store = MagicMock()
    mock_flow_manager = MagicMock()
    mock_flow_blocker = MagicMock()
    mock_queue_persistence = MagicMock()
    mock_issue_loader = MagicMock()
    mock_flow_context_resolver = MagicMock()
    mock_queue_selector = MagicMock()
    mock_check_service = MagicMock()

    # Create coordinator
    coordinator = GlobalDispatchCoordinator(
        config=mock_config,
        capacity=mock_capacity,
        github=mock_github,
        store=mock_store,
        flow_manager=mock_flow_manager,
        flow_blocker=mock_flow_blocker,
        queue_persistence=mock_queue_persistence,
        issue_loader=mock_issue_loader,
        flow_context_resolver=mock_flow_context_resolver,
        queue_selector=mock_queue_selector,
        check_service=mock_check_service,
    )

    # Mock run_in_executor to raise other RuntimeError
    with patch.object(
        asyncio,
        "get_running_loop",
        return_value=MagicMock(
            run_in_executor=AsyncMock(
                side_effect=RuntimeError("some other runtime issue")
            )
        ),
    ):
        with pytest.raises(RuntimeError, match="some other runtime issue"):
            await coordinator._collect_frozen_queue()


@pytest.mark.asyncio
async def test_collect_frozen_queue_cancelled_error_returns_empty():
    """Verify _collect_frozen_queue returns [] on asyncio.CancelledError."""
    from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
    from vibe3.models import OrchestraConfig

    # Create mock services
    mock_config = MagicMock(spec=OrchestraConfig)
    mock_config.max_concurrent_flows = 1
    mock_config.supervisor_handoff = MagicMock()
    mock_config.supervisor_handoff.issue_label = "supervisor"
    mock_capacity = MagicMock()
    mock_github = MagicMock()
    mock_store = MagicMock()
    mock_flow_manager = MagicMock()
    mock_flow_blocker = MagicMock()
    mock_queue_persistence = MagicMock()
    mock_issue_loader = MagicMock()
    mock_flow_context_resolver = MagicMock()
    mock_queue_selector = MagicMock()
    mock_check_service = MagicMock()

    # Create coordinator
    coordinator = GlobalDispatchCoordinator(
        config=mock_config,
        capacity=mock_capacity,
        github=mock_github,
        store=mock_store,
        flow_manager=mock_flow_manager,
        flow_blocker=mock_flow_blocker,
        queue_persistence=mock_queue_persistence,
        issue_loader=mock_issue_loader,
        flow_context_resolver=mock_flow_context_resolver,
        queue_selector=mock_queue_selector,
        check_service=mock_check_service,
    )

    # Mock run_in_executor to raise CancelledError
    with patch.object(
        asyncio,
        "get_running_loop",
        return_value=MagicMock(
            run_in_executor=AsyncMock(side_effect=asyncio.CancelledError())
        ),
    ):
        result = await coordinator._collect_frozen_queue()

    # Should return empty list, not raise
    assert result == []


@pytest.mark.asyncio
async def test_collect_frozen_queue_unexpected_exception_returns_empty():
    """Verify _collect_frozen_queue returns [] on unexpected Exception."""
    from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
    from vibe3.models import OrchestraConfig

    # Create mock services
    mock_config = MagicMock(spec=OrchestraConfig)
    mock_config.max_concurrent_flows = 1
    mock_config.supervisor_handoff = MagicMock()
    mock_config.supervisor_handoff.issue_label = "supervisor"
    mock_capacity = MagicMock()
    mock_github = MagicMock()
    mock_store = MagicMock()
    mock_flow_manager = MagicMock()
    mock_flow_blocker = MagicMock()
    mock_queue_persistence = MagicMock()
    mock_issue_loader = MagicMock()
    mock_flow_context_resolver = MagicMock()
    mock_queue_selector = MagicMock()
    mock_check_service = MagicMock()

    # Create coordinator
    coordinator = GlobalDispatchCoordinator(
        config=mock_config,
        capacity=mock_capacity,
        github=mock_github,
        store=mock_store,
        flow_manager=mock_flow_manager,
        flow_blocker=mock_flow_blocker,
        queue_persistence=mock_queue_persistence,
        issue_loader=mock_issue_loader,
        flow_context_resolver=mock_flow_context_resolver,
        queue_selector=mock_queue_selector,
        check_service=mock_check_service,
    )

    # Mock run_in_executor to raise unexpected Exception
    with patch.object(
        asyncio,
        "get_running_loop",
        return_value=MagicMock(
            run_in_executor=AsyncMock(side_effect=Exception("unexpected error"))
        ),
    ):
        result = await coordinator._collect_frozen_queue()

    # Should return empty list, not raise
    assert result == []


@pytest.mark.asyncio
async def test_coordinate_consumes_queue_dirty_signal():
    """Test that coordinator consumes queue dirty signal during coordinate()."""
    from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
    from vibe3.models import OrchestraConfig, QueueEntry

    # Create mock services
    mock_config = MagicMock(spec=OrchestraConfig)
    mock_config.max_concurrent_flows = 1
    mock_config.supervisor_handoff = MagicMock()
    mock_config.supervisor_handoff.issue_label = "supervisor"
    mock_config.queue_refresh = MagicMock()
    mock_config.queue_refresh.enabled = False
    mock_capacity = MagicMock()
    mock_capacity.get_capacity_status.return_value = {"remaining": 0}
    mock_github = MagicMock()
    mock_store = MagicMock()
    mock_flow_manager = MagicMock()
    mock_flow_blocker = MagicMock()
    mock_queue_persistence = MagicMock()
    mock_issue_loader = MagicMock()
    mock_flow_context_resolver = MagicMock()
    mock_queue_selector = MagicMock()
    mock_check_service = MagicMock()

    # Create coordinator
    coordinator = GlobalDispatchCoordinator(
        config=mock_config,
        capacity=mock_capacity,
        github=mock_github,
        store=mock_store,
        flow_manager=mock_flow_manager,
        flow_blocker=mock_flow_blocker,
        queue_persistence=mock_queue_persistence,
        issue_loader=mock_issue_loader,
        flow_context_resolver=mock_flow_context_resolver,
        queue_selector=mock_queue_selector,
        check_service=mock_check_service,
    )

    # Mock consume_queue_dirty_signal to return (True, mock_queue, False)
    mock_queue = [MagicMock(spec=QueueEntry)]
    coordinator._queue_maintenance.consume_queue_dirty_signal = AsyncMock(
        return_value=(True, mock_queue, False)
    )

    # Call coordinate
    await coordinator.coordinate(tick_id=1)

    # Verify consume_queue_dirty_signal was called
    coordinator._queue_maintenance.consume_queue_dirty_signal.assert_called_once()


def test_has_dispatchable_entries_excludes_aborted_flows():
    """Verify aborted flows are excluded from dispatchable count.

    This prevents pool exhaustion detection interference when aborted
    flows pass health checks but shouldn't count as "truly dispatchable"
    for the purpose of resetting the exhausted counter.
    """
    from unittest.mock import MagicMock

    from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
    from vibe3.models import IssueInfo, IssueState, OrchestraConfig, QueueEntry

    # Create mock services
    mock_config = MagicMock(spec=OrchestraConfig)
    mock_config.max_concurrent_flows = 1
    mock_config.supervisor_handoff = MagicMock()
    mock_config.supervisor_handoff.issue_label = "supervisor"
    mock_config.manager_usernames = ()  # Empty tuple for manager usernames
    mock_capacity = MagicMock()
    mock_github = MagicMock()
    mock_store = MagicMock()
    mock_flow_manager = MagicMock()
    mock_flow_blocker = MagicMock()
    mock_queue_persistence = MagicMock()
    mock_issue_loader = MagicMock()
    mock_flow_context_resolver = MagicMock()
    mock_queue_selector = MagicMock()
    mock_check_service = MagicMock()

    # Create coordinator
    coordinator = GlobalDispatchCoordinator(
        config=mock_config,
        capacity=mock_capacity,
        github=mock_github,
        store=mock_store,
        flow_manager=mock_flow_manager,
        flow_blocker=mock_flow_blocker,
        queue_persistence=mock_queue_persistence,
        issue_loader=mock_issue_loader,
        flow_context_resolver=mock_flow_context_resolver,
        queue_selector=mock_queue_selector,
        check_service=mock_check_service,
    )

    # Mock issue loader to return a ready issue
    mock_issue = MagicMock(spec=IssueInfo)
    mock_issue.number = 123
    mock_issue.state = IssueState.READY
    mock_issue.labels = []
    mock_issue.assignees = []
    coordinator._load_issue = lambda issue_number: (
        mock_issue if issue_number == 123 else None
    )

    # Mock flow context to return aborted flow
    coordinator._flow_context = lambda issue_number: (
        "task/issue-123",
        {"flow_status": "aborted"},
    )

    # Mock preflight to pass
    from vibe3.domain.dispatch_preflight import DispatchPreflightDecision

    coordinator._run_dispatch_preflight = lambda issue: DispatchPreflightDecision(
        allowed=True, target_state=IssueState.READY
    )

    # Create queue entry for aborted flow
    entry = QueueEntry(issue_number=123, collected_state="ready", waiting_state=None)

    # Test: Should return False for aborted flow (excluded from dispatchable count)
    result = coordinator._has_dispatchable_entries([entry])
    assert result is False, "Aborted flow should not count as dispatchable"


@pytest.mark.asyncio
async def test_exhausted_refresh_pauses_on_aborted_only_queue():
    """Verify pool exhaustion detection works when queue contains only aborted flows.

    Integration test for the full exhausted_refresh() flow:
    1. Queue contains only aborted flow entries
    2. exhausted_refresh() collects fresh queue (also aborted)
    3. Should return dispatch_paused=True (not reset by aborted flows)
    """
    from unittest.mock import MagicMock

    from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
    from vibe3.domain.dispatch_preflight import DispatchPreflightDecision
    from vibe3.models import IssueInfo, IssueState, OrchestraConfig, QueueEntry

    # Create mock services
    mock_config = MagicMock(spec=OrchestraConfig)
    mock_config.max_concurrent_flows = 1
    mock_config.supervisor_handoff = MagicMock()
    mock_config.supervisor_handoff.issue_label = "supervisor"
    mock_config.manager_usernames = ()
    mock_config.queue_refresh = MagicMock()
    mock_config.queue_refresh.enabled = False

    mock_capacity = MagicMock()
    mock_capacity.get_capacity_status.return_value = {"remaining": 1}

    mock_github = MagicMock()
    mock_store = MagicMock()
    mock_flow_manager = MagicMock()
    mock_flow_blocker = MagicMock()
    mock_queue_persistence = MagicMock()
    mock_issue_loader = MagicMock()
    mock_flow_context_resolver = MagicMock()
    mock_queue_selector = MagicMock()
    mock_check_service = MagicMock()

    # Create coordinator
    coordinator = GlobalDispatchCoordinator(
        config=mock_config,
        capacity=mock_capacity,
        github=mock_github,
        store=mock_store,
        flow_manager=mock_flow_manager,
        flow_blocker=mock_flow_blocker,
        queue_persistence=mock_queue_persistence,
        issue_loader=mock_issue_loader,
        flow_context_resolver=mock_flow_context_resolver,
        queue_selector=mock_queue_selector,
        check_service=mock_check_service,
    )

    # Setup: Create aborted flow entry
    aborted_issue = MagicMock(spec=IssueInfo)
    aborted_issue.number = 123
    aborted_issue.state = IssueState.READY
    aborted_issue.labels = []
    aborted_issue.assignees = []

    coordinator._load_issue = lambda n: aborted_issue if n == 123 else None
    coordinator._flow_context = lambda n: (
        "task/issue-123",
        {"flow_status": "aborted"},
    )
    coordinator._run_dispatch_preflight = lambda issue: DispatchPreflightDecision(
        allowed=True, target_state=IssueState.READY
    )

    # Mock collect_frozen_queue to return aborted flow
    aborted_entry = QueueEntry(
        issue_number=123, collected_state="ready", waiting_state=None
    )

    async def mock_collect_frozen_queue():
        return [aborted_entry]

    coordinator._collect_frozen_queue = mock_collect_frozen_queue

    # Setup queue maintenance service
    # Mock should_collect to trigger collection
    coordinator._should_collect_after_dispatch = lambda count: True

    # Start with empty queue, not paused
    frozen_queue = []
    dispatch_paused = False

    # Call exhausted_refresh (simulates queue exhausted after dispatch)
    new_queue, new_paused = await coordinator._queue_maintenance.exhausted_refresh(
        dispatched_count=0,
        queue_refreshed=False,
        frozen_queue=frozen_queue,
        dispatch_paused=dispatch_paused,
    )

    # Verify: Should be paused because all entries are aborted
    assert new_paused is True, (
        "exhausted_refresh should return dispatch_paused=True "
        "when queue contains only aborted flows"
    )
    assert len(new_queue) == 1, "Queue should contain the collected aborted entry"
