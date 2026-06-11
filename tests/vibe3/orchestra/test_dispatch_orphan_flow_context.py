"""Regression tests for orphan flow dispatch health checks."""

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.models.queue_entry import QueueEntry
from vibe3.orchestra.global_dispatch_coordinator import GlobalDispatchCoordinator

if TYPE_CHECKING:
    pass


def _make_mock_coordinator_dependencies():
    """Create mock dependencies for GlobalDispatchCoordinator construction."""
    flow_blocker = MagicMock()
    queue_persistence = MagicMock()
    queue_persistence.frozen_queue = None
    issue_loader = MagicMock(return_value=None)
    flow_context_resolver = MagicMock(return_value=("", None))
    queue_selector = MagicMock(return_value=[])
    check_service = MagicMock()
    return {
        "flow_blocker": flow_blocker,
        "queue_persistence": queue_persistence,
        "issue_loader": issue_loader,
        "flow_context_resolver": flow_context_resolver,
        "queue_selector": queue_selector,
        "check_service": check_service,
    }


def test_health_check_skips_non_ready_issue_without_flow_context() -> None:
    config = MagicMock(repo="owner/repo")
    config.max_concurrent_flows = 10
    config.supervisor_handoff.issue_label = "supervisor"
    store = MagicMock(db_path=":memory:")
    mock_deps = _make_mock_coordinator_dependencies()
    coordinator = GlobalDispatchCoordinator(
        config=config,
        capacity=MagicMock(),
        github=MagicMock(),
        store=store,
        flow_manager=MagicMock(),
        **mock_deps,
    )
    issue = IssueInfo(
        number=1013,
        title="Orphan claimed issue",
        state=IssueState.CLAIMED,
        labels=["state/claimed"],
        github_state="OPEN",
    )
    coordinator._flow_context = MagicMock(return_value=("", None))

    with patch(
        "vibe3.domain.dispatch_coordinator.append_orchestra_event"
    ) as append_event:
        result = coordinator._check_dispatch_health(issue)

    assert result is False
    # Check that an event was logged with the right message
    assert any(
        "missing flow context" in str(call) for call in append_event.call_args_list
    )


@patch("vibe3.domain.dispatch_coordinator.get_manager_usernames", return_value=[])
def test_dispatch_loop_logs_missing_flow_context_once(
    mock_get_manager_usernames,
) -> None:
    config = MagicMock(repo="owner/repo")
    config.max_concurrent_flows = 10
    config.supervisor_handoff.issue_label = "supervisor"
    config.manager_usernames = []
    mock_deps = _make_mock_coordinator_dependencies()
    coordinator = GlobalDispatchCoordinator(
        config=config,
        capacity=MagicMock(),
        github=MagicMock(),
        store=MagicMock(db_path=":memory:"),
        flow_manager=MagicMock(),
        **mock_deps,
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

    with patch(
        "vibe3.domain.dispatch_coordinator.append_orchestra_event"
    ) as append_event:
        dispatched = coordinator._dispatch_loop()

    messages = [call.args[1] for call in append_event.call_args_list]
    assert dispatched == 0
    assert len([msg for msg in messages if "missing flow context" in msg]) == 1
    assert all("(health check failed)" not in msg for msg in messages)
