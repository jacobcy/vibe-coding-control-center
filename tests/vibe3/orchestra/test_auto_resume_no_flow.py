"""Tests for auto-resume of orphaned issues without flow scene."""

from __future__ import annotations

from unittest.mock import MagicMock

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.queue_operations import (
    _auto_resume_to_ready,
    select_ready_issues_from_collected_issues,
)


class TestAutoResumeNoFlowScene:
    """Tests for auto-resume of orphaned issues without flow scene."""

    def test_auto_resume_claimed_no_branch(self, make_issue_info, monkeypatch) -> None:
        """Issue with CLAIMED state and no branch triggers auto-resume."""
        from vibe3.models.orchestra_config import OrchestraConfig

        config = OrchestraConfig(repo="owner/repo")
        issue = make_issue_info(100, IssueState.CLAIMED)

        mock_label_service = MagicMock()
        mock_label_service.transition = MagicMock()

        event_calls = []

        def mock_append_event(source: str, message: str) -> None:
            event_calls.append((source, message))

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.append_orchestra_event",
            mock_append_event,
        )

        _auto_resume_to_ready(issue, config, label_service=mock_label_service)

        mock_label_service.transition.assert_called_once_with(
            100,
            IssueState.READY,
            actor="orchestra:auto-resume",
            force=True,
        )

        assert len(event_calls) == 1
        assert event_calls[0][0] == "dispatcher"
        assert "auto-resume #100" in event_calls[0][1]
        assert "state=claimed" in event_calls[0][1]
        assert "recovered to ready" in event_calls[0][1]

    def test_no_auto_resume_ready_no_branch(self, make_issue_info, monkeypatch) -> None:
        """Issue with READY state and no branch does NOT trigger auto-resume."""
        from vibe3.models.orchestra_config import OrchestraConfig

        config = OrchestraConfig(repo="owner/repo")
        issue = make_issue_info(101, IssueState.READY)

        mock_label_service = MagicMock()
        mock_label_service.transition = MagicMock()

        # Call the function with READY issue
        _auto_resume_to_ready(issue, config, label_service=mock_label_service)

        # Verify transition is NOT called (defensive guard)
        mock_label_service.transition.assert_not_called()

    def test_no_auto_resume_blocked_no_branch(
        self, make_issue_info, monkeypatch
    ) -> None:
        """Issue with BLOCKED state and no branch does NOT trigger auto-resume."""
        from vibe3.models.orchestra_config import OrchestraConfig

        config = OrchestraConfig(repo="owner/repo")
        issue = make_issue_info(102, IssueState.BLOCKED)

        mock_label_service = MagicMock()
        mock_label_service.transition = MagicMock()

        # Call the function with BLOCKED issue
        _auto_resume_to_ready(issue, config, label_service=mock_label_service)

        # Verify transition is NOT called (state machine invariant)
        mock_label_service.transition.assert_not_called()

    def test_auto_resume_failure_does_not_crash(
        self, make_issue_info, monkeypatch
    ) -> None:
        """LabelService.transition() raises exception - verify log and no crash."""
        from vibe3.models.orchestra_config import OrchestraConfig

        config = OrchestraConfig(repo="owner/repo")
        issue = make_issue_info(103, IssueState.CLAIMED)

        mock_label_service = MagicMock()
        mock_label_service.transition = MagicMock(side_effect=RuntimeError("API error"))

        event_calls = []

        def mock_append_event(source: str, message: str) -> None:
            event_calls.append((source, message))

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.append_orchestra_event",
            mock_append_event,
        )

        # Should not raise exception
        _auto_resume_to_ready(issue, config, label_service=mock_label_service)

        mock_label_service.transition.assert_called_once()

        assert len(event_calls) == 1
        assert event_calls[0][0] == "dispatcher"
        assert "auto-resume #103 failed" in event_calls[0][1]
        assert "API error" in event_calls[0][1]

    def test_auto_resume_skipped_for_manager_role(
        self, make_issue, make_issue_info, make_capacity, make_coordinator, monkeypatch
    ) -> None:
        """Manager role dispatch skips branch check entirely, no auto-resume."""
        coordinator = make_coordinator(
            "manager",
            capacity=make_capacity(remaining=1),
            mock_health_check=True,
        )

        # Manager role should not check branches at all
        issues = [
            make_issue_info(200, IssueState.READY, assignees=[]),
        ]

        mock_label_service = MagicMock()
        mock_label_service.transition = MagicMock()

        event_calls = []

        def mock_append_event(source: str, message: str) -> None:
            event_calls.append((source, message))

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.append_orchestra_event",
            mock_append_event,
        )

        # Call the queue selector directly
        select_ready_issues_from_collected_issues(
            issues=issues,
            trigger_state=IssueState.READY,
            config=coordinator._config,
            github=coordinator._github,
            store=coordinator._store,
            flow_manager=coordinator._flow_manager,
            qualify_gate=coordinator._qualify_gate,
            supervisor_label=coordinator._config.supervisor_handoff.issue_label,
            label_service=mock_label_service,
        )

        # Manager role skips branch check, so no auto-resume should be triggered
        mock_label_service.transition.assert_not_called()

        # No auto-resume events should be logged
        auto_resume_calls = [call for call in event_calls if "auto-resume" in call[1]]
        assert len(auto_resume_calls) == 0

    def test_auto_resume_triggered_for_claimed_no_branch_integration(
        self, make_issue_info, make_capacity, make_coordinator, monkeypatch
    ) -> None:
        """Integration test: CLAIMED issue with no branch triggers auto-resume."""
        coordinator = make_coordinator(
            "planner",
            capacity=make_capacity(remaining=1),
            mock_health_check=True,
        )

        # Setup CLAIMED issue with no branch (orphaned)
        issues = [
            make_issue_info(300, IssueState.CLAIMED),
        ]

        # Mock get_flow_context to return no branch
        def mock_get_flow_context(*args, **kwargs):
            return (None, None)

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.get_flow_context",
            mock_get_flow_context,
        )

        # Mock qualify gate to return the trigger state (allow issue through)
        coordinator._qualify_gate.run_qualify_gate = MagicMock(
            return_value=IssueState.CLAIMED
        )

        mock_label_service = MagicMock()
        mock_label_service.transition = MagicMock()

        event_calls = []

        def mock_append_event(source: str, message: str) -> None:
            event_calls.append((source, message))

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.append_orchestra_event",
            mock_append_event,
        )

        # Call the queue selector - should trigger auto-resume
        select_ready_issues_from_collected_issues(
            issues=issues,
            trigger_state=IssueState.CLAIMED,
            config=coordinator._config,
            github=coordinator._github,
            store=coordinator._store,
            flow_manager=coordinator._flow_manager,
            qualify_gate=coordinator._qualify_gate,
            supervisor_label=coordinator._config.supervisor_handoff.issue_label,
            label_service=mock_label_service,
        )

        # Verify auto-resume was triggered
        mock_label_service.transition.assert_called_once_with(
            300,
            IssueState.READY,
            actor="orchestra:auto-resume",
            force=True,
        )

        # Verify event logged
        auto_resume_calls = [
            call for call in event_calls if "auto-resume #300" in call[1]
        ]
        assert len(auto_resume_calls) == 1

    def test_auto_resume_not_triggered_for_blocked_no_branch_integration(
        self, make_issue_info, make_capacity, make_coordinator, monkeypatch
    ) -> None:
        """Integration test: BLOCKED issue with no branch does NOT trigger."""
        coordinator = make_coordinator(
            "planner",
            capacity=make_capacity(remaining=1),
            mock_health_check=True,
        )

        # Setup BLOCKED issue with no branch
        issues = [
            make_issue_info(301, IssueState.BLOCKED),
        ]

        # Mock get_flow_context to return no branch
        def mock_get_flow_context(*args, **kwargs):
            return (None, None)

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.get_flow_context",
            mock_get_flow_context,
        )

        # Mock qualify gate to return the trigger state (allow issue through)
        coordinator._qualify_gate.run_qualify_gate = MagicMock(
            return_value=IssueState.BLOCKED
        )

        mock_label_service = MagicMock()
        mock_label_service.transition = MagicMock()

        event_calls = []

        def mock_append_event(source: str, message: str) -> None:
            event_calls.append((source, message))

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.append_orchestra_event",
            mock_append_event,
        )

        # Call the queue selector - should NOT trigger auto-resume
        select_ready_issues_from_collected_issues(
            issues=issues,
            trigger_state=IssueState.BLOCKED,
            config=coordinator._config,
            github=coordinator._github,
            store=coordinator._store,
            flow_manager=coordinator._flow_manager,
            qualify_gate=coordinator._qualify_gate,
            supervisor_label=coordinator._config.supervisor_handoff.issue_label,
            label_service=mock_label_service,
        )

        # Verify auto-resume was NOT triggered (state machine invariant)
        mock_label_service.transition.assert_not_called()

        # Verify no auto-resume events logged
        auto_resume_calls = [call for call in event_calls if "auto-resume" in call[1]]
        assert len(auto_resume_calls) == 0
