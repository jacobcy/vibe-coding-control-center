"""Tests for frozen queue persistence across server restarts."""

from __future__ import annotations

from unittest.mock import MagicMock

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.global_dispatch_coordinator import (
    GlobalDispatchCoordinator,
    QueueEntry,
)


class TestRestartRecovery:
    """Tests for queue recovery on server restart."""

    def test_restore_queue_on_init(self, tmp_path) -> None:
        """Test that persisted queue is restored on coordinator init."""
        # Setup: Create a real SQLite database with persisted queue
        db_path = str(tmp_path / "test.db")
        store = SQLiteClient(db_path)

        # Persist some queue entries
        store.save_frozen_queue(
            [
                {
                    "issue_number": 1,
                    "collected_state": "ready",
                    "waiting_state": None,
                },
                {
                    "issue_number": 2,
                    "collected_state": "in-progress",
                    "waiting_state": "in-progress",
                },
            ]
        )

        # Mock dependencies
        config = OrchestraConfig(repo="owner/repo")
        config.manager_usernames = ["manager-bot"]
        config.supervisor_handoff.issue_label = "supervisor"

        github = MagicMock()
        capacity = MagicMock()
        capacity.config.max_concurrent_flows = 10
        capacity._backend = None
        flow_manager = MagicMock()

        # Mock _load_issue to return valid issues BEFORE creating coordinator
        def mock_load_issue(issue_number: int, *args, **kwargs) -> IssueInfo | None:
            return IssueInfo(
                number=issue_number,
                title=f"Issue {issue_number}",
                state=IssueState.READY if issue_number == 1 else IssueState.IN_PROGRESS,
                labels=[
                    (
                        IssueState.READY.to_label()
                        if issue_number == 1
                        else IssueState.IN_PROGRESS.to_label()
                    )
                ],
                assignees=["manager-bot"],
            )

        # Patch load_issue at module level before coordinator init
        import vibe3.orchestra.global_dispatch_coordinator as coord_module

        original_load_issue = coord_module.load_issue
        coord_module.load_issue = mock_load_issue

        try:
            # Create coordinator - it should restore the queue
            coordinator = GlobalDispatchCoordinator(
                config=config,
                capacity=capacity,
                github=github,
                store=store,
                flow_manager=flow_manager,
                registry=None,
            )

            # Verify queue was restored
            assert coordinator._frozen_queue is not None
            assert len(coordinator._frozen_queue) == 2
            assert coordinator._frozen_queue[0].issue_number == 1
            assert coordinator._frozen_queue[1].issue_number == 2
            # waiting_state should be reset to None for re-dispatch
            assert coordinator._frozen_queue[0].waiting_state is None
            assert coordinator._frozen_queue[1].waiting_state is None
        finally:
            # Restore original function
            coord_module.load_issue = original_load_issue

    def test_cleanup_done_issues_on_restore(self, tmp_path) -> None:
        """Test that DONE issues are removed from persisted queue on restore."""
        # Setup: Create a real SQLite database
        db_path = str(tmp_path / "test.db")
        store = SQLiteClient(db_path)

        # Persist a DONE issue
        store.save_frozen_queue(
            [
                {
                    "issue_number": 1,
                    "collected_state": "ready",
                    "waiting_state": None,
                },
            ]
        )

        # Mock dependencies
        config = OrchestraConfig(repo="owner/repo")
        config.manager_usernames = ["manager-bot"]
        config.supervisor_handoff.issue_label = "supervisor"

        github = MagicMock()
        capacity = MagicMock()
        capacity.config.max_concurrent_flows = 10
        capacity._backend = None
        flow_manager = MagicMock()

        # Mock _load_issue to return a DONE issue
        def mock_load_issue(issue_number: int) -> IssueInfo | None:
            return IssueInfo(
                number=issue_number,
                title=f"Issue {issue_number}",
                state=IssueState.DONE,
                labels=[IssueState.DONE.to_label()],
                assignees=["manager-bot"],
            )

        # Create coordinator
        coordinator = GlobalDispatchCoordinator(
            config=config,
            capacity=capacity,
            github=github,
            store=store,
            flow_manager=flow_manager,
            registry=None,
        )
        coordinator._load_issue = mock_load_issue

        # Verify queue is empty (DONE issue was cleaned up)
        assert coordinator._frozen_queue is None

        # Verify entry was removed from database
        persisted = store.load_frozen_queue()
        assert len(persisted) == 0

    def test_cleanup_invalid_issues_on_restore(self, tmp_path) -> None:
        """Test that non-existent issues are removed from persisted queue on restore."""
        # Setup: Create a real SQLite database
        db_path = str(tmp_path / "test.db")
        store = SQLiteClient(db_path)

        # Persist an issue that doesn't exist
        store.save_frozen_queue(
            [
                {
                    "issue_number": 999,
                    "collected_state": "ready",
                    "waiting_state": None,
                },
            ]
        )

        # Mock dependencies
        config = OrchestraConfig(repo="owner/repo")
        config.manager_usernames = ["manager-bot"]
        config.supervisor_handoff.issue_label = "supervisor"

        github = MagicMock()
        capacity = MagicMock()
        capacity.config.max_concurrent_flows = 10
        capacity._backend = None
        flow_manager = MagicMock()

        # Mock _load_issue to return None (issue doesn't exist)
        def mock_load_issue(issue_number: int) -> IssueInfo | None:
            return None

        # Create coordinator
        coordinator = GlobalDispatchCoordinator(
            config=config,
            capacity=capacity,
            github=github,
            store=store,
            flow_manager=flow_manager,
            registry=None,
        )
        coordinator._load_issue = mock_load_issue

        # Verify queue is empty (invalid issue was cleaned up)
        assert coordinator._frozen_queue is None

        # Verify entry was removed from database
        persisted = store.load_frozen_queue()
        assert len(persisted) == 0

    def test_cleanup_supervisor_issues_on_restore(self, tmp_path) -> None:
        """Test that supervisor-labeled issues are removed from persisted queue.

        On restore, supervisor-labeled issues should be filtered out.
        """
        # Setup: Create a real SQLite database
        db_path = str(tmp_path / "test.db")
        store = SQLiteClient(db_path)

        # Persist a supervisor-labeled issue
        store.save_frozen_queue(
            [
                {
                    "issue_number": 1,
                    "collected_state": "ready",
                    "waiting_state": None,
                },
            ]
        )

        # Mock dependencies
        config = OrchestraConfig(repo="owner/repo")
        config.manager_usernames = ["manager-bot"]
        config.supervisor_handoff.issue_label = "supervisor"

        github = MagicMock()
        capacity = MagicMock()
        capacity.config.max_concurrent_flows = 10
        capacity._backend = None
        flow_manager = MagicMock()

        # Mock _load_issue to return a supervisor-labeled issue
        def mock_load_issue(issue_number: int) -> IssueInfo | None:
            return IssueInfo(
                number=issue_number,
                title=f"Issue {issue_number}",
                state=IssueState.READY,
                labels=[IssueState.READY.to_label(), "supervisor"],
                assignees=["manager-bot"],
            )

        # Create coordinator
        coordinator = GlobalDispatchCoordinator(
            config=config,
            capacity=capacity,
            github=github,
            store=store,
            flow_manager=flow_manager,
            registry=None,
        )
        coordinator._load_issue = mock_load_issue

        # Verify queue is empty (supervisor issue was cleaned up)
        assert coordinator._frozen_queue is None

        # Verify entry was removed from database
        persisted = store.load_frozen_queue()
        assert len(persisted) == 0


class TestQueuePersistence:
    """Tests for queue persistence during operations."""

    def test_collect_persists_queue(self, tmp_path) -> None:
        """Test that queue is persisted after collection."""
        # Setup: Create a real SQLite database
        db_path = str(tmp_path / "test.db")
        store = SQLiteClient(db_path)

        config = OrchestraConfig(repo="owner/repo")
        config.manager_usernames = ["manager-bot"]
        config.supervisor_handoff.issue_label = "supervisor"

        github = MagicMock()
        capacity = MagicMock()
        capacity.config.max_concurrent_flows = 10
        capacity.get_capacity_status = MagicMock(
            return_value={"remaining": 0}  # Block dispatch
        )
        capacity._backend = None
        flow_manager = MagicMock()

        # Create coordinator
        coordinator = GlobalDispatchCoordinator(
            config=config,
            capacity=capacity,
            github=github,
            store=store,
            flow_manager=flow_manager,
            registry=None,
        )

        # Mock _poll_issues_by_state to return some issues
        async def mock_poll(state: IssueState) -> list[IssueInfo]:
            if state == IssueState.READY:
                return [
                    IssueInfo(
                        number=1,
                        title="Issue 1",
                        state=IssueState.READY,
                        labels=[IssueState.READY.to_label()],
                        assignees=["manager-bot"],
                    ),
                    IssueInfo(
                        number=2,
                        title="Issue 2",
                        state=IssueState.READY,
                        labels=[IssueState.READY.to_label()],
                        assignees=["manager-bot"],
                    ),
                ]
            return []

        coordinator._poll_issues_by_state = mock_poll

        # Run coordinate to trigger queue collection
        import asyncio

        asyncio.run(coordinator.coordinate())

        # Verify queue was persisted
        persisted = store.load_frozen_queue()
        assert len(persisted) == 2
        issue_numbers = {e["issue_number"] for e in persisted}
        assert issue_numbers == {1, 2}

    def test_dispatch_updates_persistence(self, tmp_path) -> None:
        """Test that queue is persisted after dispatch sets waiting_state."""
        # Setup: Create a real SQLite database
        db_path = str(tmp_path / "test.db")
        store = SQLiteClient(db_path)

        config = OrchestraConfig(repo="owner/repo")
        config.manager_usernames = ["manager-bot"]
        config.supervisor_handoff.issue_label = "supervisor"

        github = MagicMock()
        capacity = MagicMock()
        capacity.config.max_concurrent_flows = 10
        capacity.get_capacity_status = MagicMock(return_value={"remaining": 1})
        capacity._backend = None
        flow_manager = MagicMock()

        # Create coordinator with a queue
        coordinator = GlobalDispatchCoordinator(
            config=config,
            capacity=capacity,
            github=github,
            store=store,
            flow_manager=flow_manager,
            registry=None,
        )
        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready", waiting_state=None),
        ]

        # Mock _load_issue and other methods
        def mock_load_issue(issue_number: int) -> IssueInfo | None:
            return IssueInfo(
                number=issue_number,
                title=f"Issue {issue_number}",
                state=IssueState.READY,
                labels=[IssueState.READY.to_label()],
                assignees=["manager-bot"],
            )

        coordinator._load_issue = mock_load_issue
        coordinator._flow_context = lambda n: ("task/issue-1", None)
        coordinator._emit_dispatch_intent = MagicMock()

        # Run coordinate to trigger dispatch
        import asyncio

        asyncio.run(coordinator.coordinate())

        # Verify waiting_state was persisted
        persisted = store.load_frozen_queue()
        assert len(persisted) == 1
        assert persisted[0]["waiting_state"] == "ready"

    def test_removal_persists(self, tmp_path) -> None:
        """Test that queue is persisted after issue removal."""
        # Setup: Create a real SQLite database
        db_path = str(tmp_path / "test.db")
        store = SQLiteClient(db_path)

        # Pre-populate the queue in the database
        store.save_frozen_queue(
            [
                {"issue_number": 1, "collected_state": "ready", "waiting_state": None},
                {"issue_number": 2, "collected_state": "ready", "waiting_state": None},
            ]
        )

        config = OrchestraConfig(repo="owner/repo")
        config.manager_usernames = ["manager-bot"]
        config.supervisor_handoff.issue_label = "supervisor"

        github = MagicMock()
        capacity = MagicMock()
        capacity.config.max_concurrent_flows = 10
        capacity.get_capacity_status = MagicMock(return_value={"remaining": 1})
        capacity._backend = None
        flow_manager = MagicMock()

        # Mock _load_issue to return None for issue 1 (will be removed)
        def mock_load_issue(issue_number: int, *args, **kwargs) -> IssueInfo | None:
            if issue_number == 1:
                return None  # Issue doesn't exist, will be removed
            return IssueInfo(
                number=issue_number,
                title=f"Issue {issue_number}",
                state=IssueState.READY,
                labels=[IssueState.READY.to_label()],
                assignees=["manager-bot"],
            )

        # Patch load_issue at module level before coordinator init
        import vibe3.orchestra.global_dispatch_coordinator as coord_module

        original_load_issue = coord_module.load_issue
        coord_module.load_issue = mock_load_issue

        try:
            # Create coordinator - it should restore and clean up the queue
            coordinator = GlobalDispatchCoordinator(
                config=config,
                capacity=capacity,
                github=github,
                store=store,
                flow_manager=flow_manager,
                registry=None,
            )

            # Issue 1 should have been removed during restore
            assert coordinator._frozen_queue is not None
            assert len(coordinator._frozen_queue) == 1
            assert coordinator._frozen_queue[0].issue_number == 2

            # Verify issue 1 was removed from database
            persisted = store.load_frozen_queue()
            issue_numbers = {e["issue_number"] for e in persisted}
            assert 1 not in issue_numbers
            assert 2 in issue_numbers
        finally:
            # Restore original function
            coord_module.load_issue = original_load_issue

    def test_queue_emptied_clears_db(self, tmp_path) -> None:
        """Test that database is cleared when queue becomes empty."""
        # Setup: Create a real SQLite database
        db_path = str(tmp_path / "test.db")
        store = SQLiteClient(db_path)

        # Persist some entries
        store.save_frozen_queue(
            [
                {"issue_number": 1, "collected_state": "ready", "waiting_state": None},
            ]
        )

        config = OrchestraConfig(repo="owner/repo")
        config.manager_usernames = ["manager-bot"]
        config.supervisor_handoff.issue_label = "supervisor"

        github = MagicMock()
        capacity = MagicMock()
        capacity.config.max_concurrent_flows = 10
        capacity._backend = None
        flow_manager = MagicMock()

        # Mock _poll_issues_by_state to return no issues
        async def mock_poll(state: IssueState) -> list[IssueInfo]:
            return []

        # Create coordinator
        coordinator = GlobalDispatchCoordinator(
            config=config,
            capacity=capacity,
            github=github,
            store=store,
            flow_manager=flow_manager,
            registry=None,
        )
        coordinator._poll_issues_by_state = mock_poll

        # Run coordinate - should collect empty queue and persist it
        import asyncio

        asyncio.run(coordinator.coordinate())

        # Verify database is cleared
        persisted = store.load_frozen_queue()
        assert len(persisted) == 0
