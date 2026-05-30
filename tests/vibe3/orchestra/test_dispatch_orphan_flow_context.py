"""Regression tests for orphan flow dispatch health checks."""

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.global_dispatch_coordinator import GlobalDispatchCoordinator
from vibe3.orchestra.queue_entry import QueueEntry

if TYPE_CHECKING:
    pass


def _setup_health_check_service(
    coordinator: "GlobalDispatchCoordinator",
    check_service: MagicMock,
    store: MagicMock,
) -> None:
    """Helper to re-create health check service with mocked dependencies."""
    from vibe3.orchestra.dispatch_health_check import DispatchHealthCheckService

    coordinator._health_check_service = DispatchHealthCheckService(
        check_service=check_service,
        flow_blocker=coordinator._flow_blocker,
        store=store,
        flow_context_resolver=coordinator._flow_context,
    )


def test_health_check_skips_non_ready_issue_without_flow_context() -> None:
    config = MagicMock(repo="owner/repo")
    config.max_concurrent_flows = 10
    config.supervisor_handoff.issue_label = "supervisor"
    store = MagicMock(db_path=":memory:")
    coordinator = GlobalDispatchCoordinator(
        config=config,
        capacity=MagicMock(),
        github=MagicMock(),
        store=store,
        flow_manager=MagicMock(),
    )
    issue = IssueInfo(
        number=1013,
        title="Orphan claimed issue",
        state=IssueState.CLAIMED,
        labels=["state/claimed"],
        github_state="OPEN",
    )
    coordinator._flow_context = MagicMock(return_value=("", None))

    # Re-create health check service with mocked flow_context
    mock_check_service = MagicMock()
    _setup_health_check_service(coordinator, mock_check_service, store)

    with patch(
        "vibe3.orchestra.dispatch_health_check.append_orchestra_event"
    ) as append_event:
        result = coordinator._health_check_service.check_issue_health(issue)

    assert result is False
    append_event.assert_called_once()
    assert "missing flow context" in append_event.call_args[0][1]


@patch("vibe3.domain.dispatch_coordinator.get_manager_usernames", return_value=[])
def test_dispatch_loop_logs_missing_flow_context_once(
    mock_get_manager_usernames,
) -> None:
    config = MagicMock(repo="owner/repo")
    config.max_concurrent_flows = 10
    config.supervisor_handoff.issue_label = "supervisor"
    config.manager_usernames = []
    coordinator = GlobalDispatchCoordinator(
        config=config,
        capacity=MagicMock(),
        github=MagicMock(),
        store=MagicMock(db_path=":memory:"),
        flow_manager=MagicMock(),
    )
    coordinator._capacity.get_capacity_status.return_value = {"remaining": 1}
    coordinator._frozen_queue = [
        QueueEntry(issue_number=1013, collected_state="claimed")
    ]
    coordinator._load_issue = MagicMock(
        return_value=IssueInfo(
            number=1013,
            title="Orphan claimed issue",
            state=IssueState.CLAIMED,
            labels=["state/claimed"],
            github_state="OPEN",
        )
    )
    coordinator._flow_context = MagicMock(return_value=("", None))

    # Re-create health check service with mocked flow_context
    mock_check_service = MagicMock()
    _setup_health_check_service(coordinator, mock_check_service, coordinator._store)

    with patch(
        "vibe3.orchestra.dispatch_health_check.append_orchestra_event"
    ) as append_event:
        dispatched = coordinator._dispatch_loop()

    messages = [call.args[1] for call in append_event.call_args_list]
    assert dispatched == 0
    assert len([msg for msg in messages if "missing flow context" in msg]) == 1
    assert all("(health check failed)" not in msg for msg in messages)
