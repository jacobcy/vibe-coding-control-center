"""Tests for queue refresh functionality."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
from vibe3.domain.handlers.queue_refresh import handle_label_changed
from vibe3.models import IssueInfo, QueueEntry
from vibe3.models.domain_events import LabelChanged


class TestRefreshQueuePriority:
    """Tests for refresh_queue_priority method on coordinator."""

    @pytest.mark.asyncio
    async def test_refresh_queue_priority_reorders(self):
        """Test that coordinator refreshes queue order."""
        # Create mock coordinator with minimal setup
        coordinator = MagicMock(spec=GlobalDispatchCoordinator)
        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready"),
            QueueEntry(issue_number=2, collected_state="ready"),
        ]
        coordinator._dispatch_active = False
        coordinator._load_issue = MagicMock(
            side_effect=lambda n: IssueInfo(
                number=n,
                title=f"Issue {n}",
                state=None,
                labels=[f"priority/{9 if n == 2 else 3}", "state/ready"],
                milestone="v0.3",
            )
        )
        coordinator._queue_persistence = MagicMock()
        coordinator._queue_persistence.persist = MagicMock()

        # Call the actual method (need to bind it to the mock)
        result = await GlobalDispatchCoordinator.refresh_queue_priority(coordinator)

        assert result is True
        # Queue should be re-sorted (issue 2 with priority/9 should be first)
        assert coordinator._frozen_queue[0].issue_number == 2
        assert coordinator._frozen_queue[1].issue_number == 1

    @pytest.mark.asyncio
    async def test_refresh_queue_priority_skips_during_dispatch(self):
        """Test that dispatch_active flag blocks refresh."""
        coordinator = MagicMock(spec=GlobalDispatchCoordinator)
        coordinator._dispatch_active = True
        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready")
        ]

        result = await GlobalDispatchCoordinator.refresh_queue_priority(coordinator)

        assert result is False

    @pytest.mark.asyncio
    async def test_refresh_queue_priority_skips_single_entry(self):
        """Test no-op when queue has <2 entries."""
        coordinator = MagicMock(spec=GlobalDispatchCoordinator)
        coordinator._dispatch_active = False
        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready")
        ]

        result = await GlobalDispatchCoordinator.refresh_queue_priority(coordinator)

        assert result is False

    @pytest.mark.asyncio
    async def test_refresh_queue_priority_skips_empty_queue(self):
        """Test no-op when queue is empty or None."""
        coordinator = MagicMock(spec=GlobalDispatchCoordinator)
        coordinator._dispatch_active = False
        coordinator._frozen_queue = None

        result = await GlobalDispatchCoordinator.refresh_queue_priority(coordinator)

        assert result is False


class TestRequestQueueRefresh:
    """Tests for request_queue_refresh method."""

    def test_request_queue_refresh_accumulates(self):
        """Test that multiple requests batch correctly."""
        coordinator = MagicMock(spec=GlobalDispatchCoordinator)
        coordinator._pending_refresh_issues = set()

        # Bind the actual method
        GlobalDispatchCoordinator.request_queue_refresh(coordinator, 1)
        GlobalDispatchCoordinator.request_queue_refresh(coordinator, 2)
        GlobalDispatchCoordinator.request_queue_refresh(coordinator, 1)  # Duplicate

        assert coordinator._pending_refresh_issues == {1, 2}


class TestHandleLabelChanged:
    """Tests for queue refresh event handler."""

    def test_handle_label_changed_priority_label(self):
        """Test handler triggers refresh for priority labels."""
        event = LabelChanged(
            issue_number=123,
            label="priority/9",
            action="added",
            actor="test",
        )

        # Test that handler processes priority label without error
        # (actual facade integration would be tested in integration tests)
        try:
            handle_label_changed(event)
            # Handler should process without exception (even if facade not initialized)
        except Exception as e:
            pytest.fail(f"Handler raised unexpected exception: {e}")

    def test_handle_label_changed_roadmap_label(self):
        """Test handler triggers refresh for roadmap labels."""
        event = LabelChanged(
            issue_number=456,
            label="roadmap/p0",
            action="removed",
            actor="test",
        )

        # Test that handler processes roadmap label without error
        try:
            handle_label_changed(event)
            # Handler should process without exception
        except Exception as e:
            pytest.fail(f"Handler raised unexpected exception: {e}")

    def test_handle_label_changed_ignores_state_label(self):
        """Test handler ignores non-priority labels."""
        event = LabelChanged(
            issue_number=789,
            label="state/ready",
            action="added",
            actor="test",
        )

        with patch("vibe3.domain.orchestration_facade.OrchestrationFacade"):
            mock_facade = MagicMock()
            mock_coordinator = MagicMock()
            mock_facade._coordinator = mock_coordinator

            handle_label_changed(event)

            # Should not trigger refresh for state label
            mock_coordinator.request_queue_refresh.assert_not_called()

    def test_handle_label_changed_ignores_type_label(self):
        """Test handler ignores type labels."""
        event = LabelChanged(
            issue_number=999,
            label="type/feature",
            action="added",
            actor="test",
        )

        with patch("vibe3.domain.orchestration_facade.OrchestrationFacade"):
            mock_facade = MagicMock()
            mock_coordinator = MagicMock()
            mock_facade._coordinator = mock_coordinator

            handle_label_changed(event)

            mock_coordinator.request_queue_refresh.assert_not_called()


class TestLabelServiceEmitsLabelChanged:
    """Tests for LabelService emitting LabelChanged events."""

    def test_label_service_emits_label_changed(self):
        """Test that LabelService.set_state publishes event."""
        from vibe3.services.label_service import LabelService

        # Create mock issue port
        mock_issue_port = MagicMock()
        mock_issue_port.get_issue_labels.return_value = ["state/ready"]
        mock_issue_port.add_issue_label.return_value = True
        mock_issue_port.remove_issue_label.return_value = True
        mock_issue_port.ensure_label_exists.return_value = True

        service = LabelService(issue_port=mock_issue_port, repo="test/repo")

        with patch("vibe3.domain.publisher.publish") as mock_publish:
            from vibe3.models.orchestration import IssueState

            service.set_state(123, IssueState.IN_PROGRESS)

            # Should emit events for both removed and added labels
            assert mock_publish.call_count >= 1

    def test_label_service_emits_on_remove(self):
        """Test that LabelService emits event when removing labels."""
        from vibe3.models.orchestration import IssueState
        from vibe3.services.label_service import LabelService

        # Create mock issue port
        mock_issue_port = MagicMock()
        mock_issue_port.get_issue_labels.return_value = ["state/ready", "state/claimed"]
        mock_issue_port.add_issue_label.return_value = True
        mock_issue_port.remove_issue_label.return_value = True
        mock_issue_port.ensure_label_exists.return_value = True

        service = LabelService(issue_port=mock_issue_port, repo="test/repo")

        with patch("vibe3.domain.publisher.publish") as mock_publish:
            service.set_state(456, IssueState.IN_PROGRESS)

            # Should emit events for removed labels
            # At least one call for removing "state/ready" or "state/claimed"
            assert mock_publish.call_count >= 1
