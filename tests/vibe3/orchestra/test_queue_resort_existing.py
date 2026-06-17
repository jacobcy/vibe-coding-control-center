"""Tests for _queue_resort_existing trigger."""

from __future__ import annotations

from unittest.mock import MagicMock

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.global_dispatch_coordinator import QueueEntry


class TestQueueResortExisting:
    """Tests for _queue_resort_existing trigger."""

    def test_preserves_waiting_entries(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
        install_issue_loader,
    ) -> None:
        """Entries with waiting_state set retain their order and are not re-sorted."""
        _ = make_issue(1)
        _ = make_issue(2)
        capacity = make_capacity(remaining=10)

        coordinator = make_coordinator(
            "manager", capacity=capacity, with_branches=True, mock_health_check=True
        )

        install_issue_loader(
            coordinator,
            {
                1: IssueState.IN_PROGRESS,
                2: IssueState.READY,
            },
        )

        coordinator._frozen_queue = [
            QueueEntry(
                issue_number=1,
                collected_state="in-progress",
                waiting_state="in-progress",
            ),
            QueueEntry(issue_number=2, collected_state="ready", waiting_state="ready"),
        ]

        coordinator._queue_resort_existing()

        assert len(coordinator._frozen_queue) == 2
        assert coordinator._frozen_queue[0].issue_number == 1
        assert coordinator._frozen_queue[0].waiting_state == "in-progress"
        assert coordinator._frozen_queue[1].issue_number == 2
        assert coordinator._frozen_queue[1].waiting_state == "ready"

    def test_reorders_by_priority_change(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
    ) -> None:
        """Non-waiting entries are re-sorted when priority label changes."""
        from vibe3.models import IssueInfo

        capacity = make_capacity(remaining=10)
        coordinator = make_coordinator(
            "manager", capacity=capacity, with_branches=True, mock_health_check=True
        )

        def loader(issue_number: int) -> IssueInfo | None:
            if issue_number == 1:
                return IssueInfo(
                    number=1,
                    title="Low priority",
                    state=IssueState.READY,
                    labels=["state/ready", "priority/low"],
                    assignees=["manager-bot"],
                )
            elif issue_number == 2:
                return IssueInfo(
                    number=2,
                    title="High priority",
                    state=IssueState.READY,
                    labels=["state/ready", "priority/high"],
                    assignees=["manager-bot"],
                )
            return None

        coordinator._load_issue = loader

        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready"),
            QueueEntry(issue_number=2, collected_state="ready"),
        ]

        coordinator._queue_resort_existing()

        assert len(coordinator._frozen_queue) == 2
        assert coordinator._frozen_queue[0].issue_number == 2
        assert coordinator._frozen_queue[1].issue_number == 1

    def test_removes_done_issue(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
        install_issue_loader,
    ) -> None:
        """Entry referencing a DONE issue is removed."""
        _ = make_issue(1)
        _ = make_issue(2)
        capacity = make_capacity(remaining=10)

        coordinator = make_coordinator(
            "manager", capacity=capacity, with_branches=True, mock_health_check=True
        )

        install_issue_loader(
            coordinator,
            {
                1: IssueState.DONE,
                2: IssueState.READY,
            },
        )

        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="done"),
            QueueEntry(issue_number=2, collected_state="ready"),
        ]

        coordinator._queue_resort_existing()

        assert len(coordinator._frozen_queue) == 1
        assert coordinator._frozen_queue[0].issue_number == 2

    def test_removes_missing_issue(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
        install_issue_loader,
    ) -> None:
        """Entry whose issue _load_issue returns None is removed."""
        _ = make_issue(1)
        _ = make_issue(2)
        capacity = make_capacity(remaining=10)

        coordinator = make_coordinator(
            "manager", capacity=capacity, with_branches=True, mock_health_check=True
        )

        install_issue_loader(
            coordinator,
            {
                1: None,
                2: IssueState.READY,
            },
        )

        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready"),
            QueueEntry(issue_number=2, collected_state="ready"),
        ]

        coordinator._queue_resort_existing()

        assert len(coordinator._frozen_queue) == 1
        assert coordinator._frozen_queue[0].issue_number == 2

    def test_removes_supervisor_issue(
        self,
        make_capacity,
        make_coordinator,
    ) -> None:
        """Entry whose issue has supervisor label is removed."""
        from vibe3.models import IssueInfo

        capacity = make_capacity(remaining=10)
        coordinator = make_coordinator(
            "manager", capacity=capacity, with_branches=True, mock_health_check=True
        )

        def loader(issue_number: int) -> IssueInfo | None:
            if issue_number == 1:
                return IssueInfo(
                    number=1,
                    title="Supervisor issue",
                    state=IssueState.READY,
                    labels=["state/ready", "supervisor"],
                    assignees=["manager-bot"],
                )
            elif issue_number == 2:
                return IssueInfo(
                    number=2,
                    title="Normal issue",
                    state=IssueState.READY,
                    labels=["state/ready"],
                    assignees=["manager-bot"],
                )
            return None

        coordinator._load_issue = loader

        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready"),
            QueueEntry(issue_number=2, collected_state="ready"),
        ]

        coordinator._queue_resort_existing()

        assert len(coordinator._frozen_queue) == 1
        assert coordinator._frozen_queue[0].issue_number == 2

    def test_empty_queue_noop(
        self,
        make_capacity,
        make_coordinator,
    ) -> None:
        """Empty queue produces no error."""
        capacity = make_capacity(remaining=10)
        coordinator = make_coordinator(
            "manager", capacity=capacity, with_branches=True, mock_health_check=True
        )

        coordinator._frozen_queue = []

        coordinator._queue_resort_existing()

        assert coordinator._frozen_queue == []

    def test_no_full_collection_call(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
        install_issue_loader,
    ) -> None:
        """Resort does not call _collect_open_issues."""
        _ = make_issue(1)
        capacity = make_capacity(remaining=10)

        coordinator = make_coordinator(
            "manager", capacity=capacity, with_branches=True, mock_health_check=True
        )

        install_issue_loader(coordinator, {1: IssueState.READY})

        original_collect = coordinator._collect_open_issues
        coordinator._collect_open_issues = MagicMock(side_effect=original_collect)

        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready")
        ]

        coordinator._queue_resort_existing()

        coordinator._collect_open_issues.assert_not_called()

    def test_updates_collected_state(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
    ) -> None:
        """Reloaded issue state is reflected in entry's collected_state."""
        from vibe3.models import IssueInfo

        capacity = make_capacity(remaining=10)
        coordinator = make_coordinator(
            "manager", capacity=capacity, with_branches=True, mock_health_check=True
        )

        def loader(issue_number: int) -> IssueInfo | None:
            if issue_number == 1:
                return IssueInfo(
                    number=1,
                    title="Changed state",
                    state=IssueState.IN_PROGRESS,
                    labels=["state/in-progress"],
                    assignees=["manager-bot"],
                )
            return None

        coordinator._load_issue = loader

        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready")
        ]

        coordinator._queue_resort_existing()

        assert coordinator._frozen_queue[0].collected_state == "in-progress"

    def test_mixed_waiting_and_nonwaiting(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
    ) -> None:
        """Waiting entries stay at front; non-waiting sorted after."""
        from vibe3.models import IssueInfo

        capacity = make_capacity(remaining=10)
        coordinator = make_coordinator(
            "manager", capacity=capacity, with_branches=True, mock_health_check=True
        )

        def loader(issue_number: int) -> IssueInfo | None:
            priorities = {
                1: "priority/low",
                2: "priority/high",
                3: "priority/medium",
            }
            return IssueInfo(
                number=issue_number,
                title=f"Issue {issue_number}",
                state=IssueState.READY,
                labels=["state/ready", priorities.get(issue_number, "")],
                assignees=["manager-bot"],
            )

        coordinator._load_issue = loader

        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready", waiting_state="ready"),
            QueueEntry(issue_number=2, collected_state="ready", waiting_state="ready"),
            QueueEntry(issue_number=3, collected_state="ready"),
            QueueEntry(issue_number=1, collected_state="ready"),
        ]

        coordinator._queue_resort_existing()

        assert len(coordinator._frozen_queue) == 4
        assert coordinator._frozen_queue[0].issue_number == 1
        assert coordinator._frozen_queue[0].waiting_state == "ready"
        assert coordinator._frozen_queue[1].issue_number == 2
        assert coordinator._frozen_queue[1].waiting_state == "ready"
        assert coordinator._frozen_queue[2].issue_number == 3
        assert coordinator._frozen_queue[3].issue_number == 1
