"""Tests for event rules DispatchIntent publishing."""

from __future__ import annotations

from vibe3.domain.event_rules import build_action_handlers


class TestDispatchIntentPublishing:
    """Test DispatchIntent event publishing for enqueue actions."""

    def test_enqueue_command_job_publishes_manager_intent(self) -> None:
        """enqueue_command_job(manager) publishes ManagerDispatchIntent."""
        from unittest.mock import MagicMock, patch

        from vibe3.models import ManagerDispatchIntent

        handlers = build_action_handlers()
        handler = handlers["enqueue_command_job"]

        mock_publish = MagicMock()
        with patch("vibe3.domain.publish", mock_publish):
            handler(
                {
                    "command_type": "manager",
                    "issue_number": "100",
                    "actor": "test_actor",
                }
            )

        assert mock_publish.called
        event = mock_publish.call_args[0][0]
        assert isinstance(event, ManagerDispatchIntent)
        assert event.issue_number == 100
        assert event.branch == "task/issue-100"
        assert event.trigger_state == "ready"
        assert event.actor == "test_actor"

    def test_enqueue_command_job_publishes_plan_intent(self) -> None:
        """enqueue_command_job(plan) publishes PlannerDispatchIntent."""
        from unittest.mock import MagicMock, patch

        from vibe3.models import PlannerDispatchIntent

        handlers = build_action_handlers()
        handler = handlers["enqueue_command_job"]

        mock_publish = MagicMock()
        with patch("vibe3.domain.publish", mock_publish):
            handler(
                {"command_type": "plan", "issue_number": "200", "actor": "test_actor"}
            )

        assert mock_publish.called
        event = mock_publish.call_args[0][0]
        assert isinstance(event, PlannerDispatchIntent)
        assert event.issue_number == 200
        assert event.branch == "task/issue-200"
        assert event.trigger_state == "claimed"
        assert event.actor == "test_actor"

    def test_enqueue_command_job_publishes_run_intent(self) -> None:
        """enqueue_command_job(run) publishes ExecutorDispatchIntent."""
        from unittest.mock import MagicMock, patch

        from vibe3.models import ExecutorDispatchIntent

        handlers = build_action_handlers()
        handler = handlers["enqueue_command_job"]

        mock_publish = MagicMock()
        with patch("vibe3.domain.publish", mock_publish):
            handler(
                {"command_type": "run", "issue_number": "300", "actor": "test_actor"}
            )

        assert mock_publish.called
        event = mock_publish.call_args[0][0]
        assert isinstance(event, ExecutorDispatchIntent)
        assert event.issue_number == 300
        assert event.branch == "task/issue-300"
        assert event.trigger_state == "in-progress"
        assert event.actor == "test_actor"

    def test_enqueue_command_job_publishes_review_intent(self) -> None:
        """enqueue_command_job(review) publishes ReviewerDispatchIntent."""
        from unittest.mock import MagicMock, patch

        from vibe3.models import ReviewerDispatchIntent

        handlers = build_action_handlers()
        handler = handlers["enqueue_command_job"]

        mock_publish = MagicMock()
        with patch("vibe3.domain.publish", mock_publish):
            handler(
                {"command_type": "review", "issue_number": "400", "actor": "test_actor"}
            )

        assert mock_publish.called
        event = mock_publish.call_args[0][0]
        assert isinstance(event, ReviewerDispatchIntent)
        assert event.issue_number == 400
        assert event.branch == "task/issue-400"
        assert event.trigger_state == "review"
        assert event.actor == "test_actor"

    def test_enqueue_command_job_unknown_command_type(self) -> None:
        """enqueue_command_job with unknown command_type logs warning."""
        from unittest.mock import MagicMock, patch

        handlers = build_action_handlers()
        handler = handlers["enqueue_command_job"]

        mock_publish = MagicMock()
        with patch("vibe3.domain.publish", mock_publish):
            handler({"command_type": "unknown_type", "issue_number": "500"})

        # Should not publish any event
        assert not mock_publish.called

    def test_enqueue_command_job_no_execution_request_constructed(self) -> None:
        """Verify that enqueue handlers do not construct ExecutionRequest objects."""
        from unittest.mock import MagicMock, patch

        handlers = build_action_handlers()
        handler = handlers["enqueue_command_job"]

        # Mock ExecutionRequest constructor to ensure it's never called
        mock_execution_request = MagicMock()
        with patch("vibe3.models.ExecutionRequest", mock_execution_request):
            with patch("vibe3.domain.publish", MagicMock()):
                handler({"command_type": "plan", "issue_number": "600"})

        # ExecutionRequest should never be instantiated
        assert not mock_execution_request.called

    def test_enqueue_plan_callable(self) -> None:
        """enqueue_plan action handler publishes PlannerDispatchIntent."""
        from unittest.mock import MagicMock, patch

        from vibe3.models import PlannerDispatchIntent

        handlers = build_action_handlers()
        handler = handlers["enqueue_plan"]

        mock_publish = MagicMock()
        with patch("vibe3.domain.publish", mock_publish):
            handler({"issue_number": "123", "actor": "test_actor"})

        assert mock_publish.called
        event = mock_publish.call_args[0][0]
        assert isinstance(event, PlannerDispatchIntent)
        assert event.issue_number == 123
        assert event.branch == "task/issue-123"
        assert event.trigger_state == "claimed"
        assert event.actor == "test_actor"

    def test_enqueue_run_callable(self) -> None:
        """enqueue_run action handler publishes ExecutorDispatchIntent."""
        from unittest.mock import MagicMock, patch

        from vibe3.models import ExecutorDispatchIntent

        handlers = build_action_handlers()
        handler = handlers["enqueue_run"]

        mock_publish = MagicMock()
        with patch("vibe3.domain.publish", mock_publish):
            handler({"issue_number": "456", "actor": "test_actor"})

        assert mock_publish.called
        event = mock_publish.call_args[0][0]
        assert isinstance(event, ExecutorDispatchIntent)
        assert event.issue_number == 456
        assert event.branch == "task/issue-456"
        assert event.trigger_state == "in-progress"
        assert event.actor == "test_actor"

    def test_enqueue_review_callable(self) -> None:
        """enqueue_review action handler publishes ReviewerDispatchIntent."""
        from unittest.mock import MagicMock, patch

        from vibe3.models import ReviewerDispatchIntent

        handlers = build_action_handlers()
        handler = handlers["enqueue_review"]

        mock_publish = MagicMock()
        with patch("vibe3.domain.publish", mock_publish):
            handler({"issue_number": "789", "actor": "test_actor"})

        assert mock_publish.called
        event = mock_publish.call_args[0][0]
        assert isinstance(event, ReviewerDispatchIntent)
        assert event.issue_number == 789
        assert event.branch == "task/issue-789"
        assert event.trigger_state == "review"
        assert event.actor == "test_actor"
