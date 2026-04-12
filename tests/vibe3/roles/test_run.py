"""Tests for executor role lifecycle publishing helpers."""

from pathlib import Path
from unittest.mock import patch

import pytest

from vibe3.agents.models import CodeagentResult
from vibe3.domain.events import IssueFailed, IssueStateChanged, ReportRefRequired
from vibe3.domain.publisher import EventPublisher
from vibe3.models.orchestration import IssueState
from vibe3.roles.run import publish_run_command_failure, publish_run_command_success


class TestPublishRunCommandSuccess:
    def test_publishes_issue_state_changed_when_handoff_exists(self) -> None:
        result = CodeagentResult(
            success=True,
            exit_code=0,
            stdout="Task completed",
            stderr="",
            handoff_file=Path("/tmp/handoff.md"),
            session_id="test-session-id",
        )

        EventPublisher.reset()
        published_events = []
        with patch.object(EventPublisher, "publish") as mock_publish:
            mock_publish.side_effect = lambda event: published_events.append(event)
            publish_run_command_success(
                issue_number=123,
                branch="dev/test-123",
                result=result,
            )

        assert len(published_events) == 1
        event = published_events[0]
        assert isinstance(event, IssueStateChanged)
        assert event.issue_number == 123
        assert event.to_state == IssueState.HANDOFF.value
        assert event.actor == "agent:run"

    def test_publishes_report_ref_required_when_handoff_missing(self) -> None:
        result = CodeagentResult(
            success=True,
            exit_code=0,
            stdout="Task completed",
            stderr="",
            handoff_file=None,
            session_id="test-session-id",
        )

        EventPublisher.reset()
        published_events = []
        with patch.object(EventPublisher, "publish") as mock_publish:
            mock_publish.side_effect = lambda event: published_events.append(event)
            publish_run_command_success(
                issue_number=456,
                branch="dev/test-456",
                result=result,
            )

        assert len(published_events) == 1
        event = published_events[0]
        assert isinstance(event, ReportRefRequired)
        assert event.issue_number == 456
        assert event.branch == "dev/test-456"
        assert event.ref_name == "report_ref"
        assert "report_ref was registered" in event.reason
        assert event.actor == "agent:run"

    def test_handles_non_codeagent_result_gracefully(self) -> None:
        EventPublisher.reset()
        published_events = []
        with patch.object(EventPublisher, "publish") as mock_publish:
            mock_publish.side_effect = lambda event: published_events.append(event)
            publish_run_command_success(
                issue_number=999,
                branch="dev/test-999",
                result=object(),
            )

        assert len(published_events) == 1
        assert isinstance(published_events[0], ReportRefRequired)

    def test_publish_errors_propagate(self) -> None:
        result = CodeagentResult(
            success=True,
            exit_code=0,
            stdout="Task completed",
            stderr="",
            handoff_file=Path("/tmp/handoff.md"),
            session_id="test-session-id",
        )

        EventPublisher.reset()
        with patch.object(EventPublisher, "publish") as mock_publish:
            mock_publish.side_effect = RuntimeError("Publisher failed")
            with pytest.raises(RuntimeError):
                publish_run_command_success(
                    issue_number=111,
                    branch="dev/test-111",
                    result=result,
                )


def test_publish_run_command_failure_emits_issue_failed() -> None:
    EventPublisher.reset()
    published_events = []
    with patch.object(EventPublisher, "publish") as mock_publish:
        mock_publish.side_effect = lambda event: published_events.append(event)
        publish_run_command_failure(
            issue_number=789,
            reason="Execution failed: timeout expired",
        )

    assert len(published_events) == 1
    event = published_events[0]
    assert isinstance(event, IssueFailed)
    assert event.issue_number == 789
    assert "timeout expired" in event.reason
    assert event.actor == "agent:run"
