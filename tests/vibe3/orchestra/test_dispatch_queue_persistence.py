"""Tests for frozen queue persistence across server restarts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.global_dispatch_coordinator import (
    GlobalDispatchCoordinator,
    QueueEntry,
)


@pytest.fixture
def coordinator_deps():
    """Common coordinator dependencies."""
    config = OrchestraConfig(repo="owner/repo")
    config.manager_usernames = ["manager-bot"]
    config.supervisor_handoff.issue_label = "supervisor"

    github = MagicMock()
    capacity = MagicMock()
    capacity.config.max_concurrent_flows = 10
    capacity._backend = None
    flow_manager = MagicMock()

    return {
        "config": config,
        "github": github,
        "capacity": capacity,
        "flow_manager": flow_manager,
    }


@pytest.fixture
def real_store(tmp_path: Path) -> SQLiteClient:
    """Create real SQLite client with temporary database."""
    db_path = str(tmp_path / "test.db")
    return SQLiteClient(db_path)


@pytest.fixture
def patch_load_issue():
    """Patch module-level load_issue during coordinator construction."""
    import vibe3.orchestra.global_dispatch_coordinator as coord_module

    original_load_issue = coord_module.load_issue

    def _patch(mock_fn):
        coord_module.load_issue = mock_fn

    def _restore():
        coord_module.load_issue = original_load_issue

    yield _patch, _restore


class TestRestartRecovery:
    """Tests for queue recovery on server restart."""

    def test_restore_queue_on_init(
        self, real_store: SQLiteClient, coordinator_deps, patch_load_issue
    ) -> None:
        """Test that persisted queue is restored on coordinator init."""
        # Persist queue entries
        real_store.save_frozen_queue(
            [
                {"issue_number": 1, "collected_state": "ready", "waiting_state": None},
                {
                    "issue_number": 2,
                    "collected_state": "in-progress",
                    "waiting_state": "in-progress",
                },
            ]
        )

        # Mock load_issue before coordinator creation
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

        patch, restore = patch_load_issue
        patch(mock_load_issue)

        try:
            coordinator = GlobalDispatchCoordinator(
                config=coordinator_deps["config"],
                capacity=coordinator_deps["capacity"],
                github=coordinator_deps["github"],
                store=real_store,
                flow_manager=coordinator_deps["flow_manager"],
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
            restore()

    @pytest.mark.parametrize(
        "issue_state,labels,description",
        [
            (IssueState.DONE, [IssueState.DONE.to_label()], "DONE issue"),
            pytest.param(None, None, "non-existent issue", id="invalid"),
            pytest.param(
                IssueState.READY,
                [IssueState.READY.to_label(), "supervisor"],
                "supervisor-labeled issue",
            ),
        ],
    )
    def test_cleanup_on_restore(
        self,
        issue_state,
        labels,
        description,
        real_store: SQLiteClient,
        coordinator_deps,
        patch_load_issue,
    ) -> None:
        """Test that filtered issues are removed from persisted queue on restore."""
        # Persist an issue that should be filtered
        real_store.save_frozen_queue(
            [{"issue_number": 1, "collected_state": "ready", "waiting_state": None}]
        )

        # Mock load_issue based on case
        def mock_load_issue(issue_number: int, *args, **kwargs) -> IssueInfo | None:
            if issue_state is None:
                return None
            return IssueInfo(
                number=issue_number,
                title=f"Issue {issue_number}",
                state=issue_state,
                labels=labels,
                assignees=["manager-bot"],
            )

        patch, restore = patch_load_issue
        patch(mock_load_issue)

        try:
            coordinator = GlobalDispatchCoordinator(
                config=coordinator_deps["config"],
                capacity=coordinator_deps["capacity"],
                github=coordinator_deps["github"],
                store=real_store,
                flow_manager=coordinator_deps["flow_manager"],
                registry=None,
            )

            # Verify queue is empty (filtered issue was cleaned up)
            assert coordinator._frozen_queue is None

            # Verify entry was removed from database
            persisted = real_store.load_frozen_queue()
            assert len(persisted) == 0
        finally:
            restore()


class TestQueuePersistence:
    """Tests for queue persistence during operations."""

    def test_collect_persists_queue(
        self, real_store: SQLiteClient, coordinator_deps
    ) -> None:
        """Test that queue is persisted after collection."""
        coordinator_deps["capacity"].get_capacity_status = MagicMock(
            return_value={"remaining": 0}
        )

        coordinator = GlobalDispatchCoordinator(
            config=coordinator_deps["config"],
            capacity=coordinator_deps["capacity"],
            github=coordinator_deps["github"],
            store=real_store,
            flow_manager=coordinator_deps["flow_manager"],
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

        import asyncio

        asyncio.run(coordinator.coordinate())

        # Verify queue was persisted
        persisted = real_store.load_frozen_queue()
        assert len(persisted) == 2
        issue_numbers = {e["issue_number"] for e in persisted}
        assert issue_numbers == {1, 2}

    def test_dispatch_updates_persistence(
        self, real_store: SQLiteClient, coordinator_deps
    ) -> None:
        """Test that queue is persisted after dispatch sets waiting_state."""
        coordinator_deps["capacity"].get_capacity_status = MagicMock(
            return_value={"remaining": 1}
        )

        coordinator = GlobalDispatchCoordinator(
            config=coordinator_deps["config"],
            capacity=coordinator_deps["capacity"],
            github=coordinator_deps["github"],
            store=real_store,
            flow_manager=coordinator_deps["flow_manager"],
            registry=None,
        )
        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready", waiting_state=None),
        ]

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

        import asyncio

        asyncio.run(coordinator.coordinate())

        # Verify waiting_state was persisted
        persisted = real_store.load_frozen_queue()
        assert len(persisted) == 1
        assert persisted[0]["waiting_state"] == "ready"

    def test_removal_persists(
        self, real_store: SQLiteClient, coordinator_deps, patch_load_issue
    ) -> None:
        """Test that queue is persisted after issue removal."""
        # Pre-populate the queue in the database
        real_store.save_frozen_queue(
            [
                {"issue_number": 1, "collected_state": "ready", "waiting_state": None},
                {"issue_number": 2, "collected_state": "ready", "waiting_state": None},
            ]
        )

        coordinator_deps["capacity"].get_capacity_status = MagicMock(
            return_value={"remaining": 1}
        )

        # Mock load_issue: issue 1 doesn't exist (will be removed)
        def mock_load_issue(issue_number: int, *args, **kwargs) -> IssueInfo | None:
            if issue_number == 1:
                return None
            return IssueInfo(
                number=issue_number,
                title=f"Issue {issue_number}",
                state=IssueState.READY,
                labels=[IssueState.READY.to_label()],
                assignees=["manager-bot"],
            )

        patch, restore = patch_load_issue
        patch(mock_load_issue)

        try:
            coordinator = GlobalDispatchCoordinator(
                config=coordinator_deps["config"],
                capacity=coordinator_deps["capacity"],
                github=coordinator_deps["github"],
                store=real_store,
                flow_manager=coordinator_deps["flow_manager"],
                registry=None,
            )

            # Issue 1 should have been removed during restore
            assert coordinator._frozen_queue is not None
            assert len(coordinator._frozen_queue) == 1
            assert coordinator._frozen_queue[0].issue_number == 2

            # Verify issue 1 was removed from database
            persisted = real_store.load_frozen_queue()
            issue_numbers = {e["issue_number"] for e in persisted}
            assert 1 not in issue_numbers
            assert 2 in issue_numbers
        finally:
            restore()

    def test_queue_emptied_clears_db(
        self, real_store: SQLiteClient, coordinator_deps
    ) -> None:
        """Test that database is cleared when queue becomes empty."""
        # Persist some entries
        real_store.save_frozen_queue(
            [{"issue_number": 1, "collected_state": "ready", "waiting_state": None}]
        )

        # Mock _poll_issues_by_state to return no issues
        async def mock_poll(state: IssueState) -> list[IssueInfo]:
            return []

        coordinator = GlobalDispatchCoordinator(
            config=coordinator_deps["config"],
            capacity=coordinator_deps["capacity"],
            github=coordinator_deps["github"],
            store=real_store,
            flow_manager=coordinator_deps["flow_manager"],
            registry=None,
        )
        coordinator._poll_issues_by_state = mock_poll

        import asyncio

        asyncio.run(coordinator.coordinate())

        # Verify database is cleared
        persisted = real_store.load_frozen_queue()
        assert len(persisted) == 0
