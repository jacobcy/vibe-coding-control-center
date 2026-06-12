"""Tests for event routing rule engine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from vibe3.domain.event_rules import (
    EventRule,
    build_action_handlers,
    evaluate_rules,
    expand_template,
    load_rules,
)
from vibe3.models.domain_events import DomainEvent


@dataclass(frozen=True)
class _TestEvent(DomainEvent):
    """Test event for rule tests."""

    issue_number: int = 123
    reason: str = "test reason"
    actor: str = "test_actor"


class TestLoadRules:
    """Test load_rules function."""

    def test_load_rules_parses_yaml(self, tmp_path: Path) -> None:
        """Valid YAML → correct EventRule tuples."""
        rules_file = tmp_path / "event-rules.yaml"
        rules_file.write_text("""
rules:
  - event: TestEvent
    action: log
    params:
      message: "test message"
  - event: AnotherEvent
    action: enqueue
    params:
      command: "test command"
    enabled: false
""")

        rules = load_rules(tmp_path)

        assert len(rules) == 2
        assert rules[0].event == "TestEvent"
        assert rules[0].action == "log"
        assert rules[0].params == {"message": "test message"}
        assert rules[0].enabled is True
        assert rules[1].enabled is False

    def test_load_rules_returns_empty_for_missing_dir(self, tmp_path: Path) -> None:
        """Graceful degradation when directory missing."""
        missing_dir = tmp_path / "nonexistent"
        rules = load_rules(missing_dir)

        assert rules == ()

    def test_load_rules_skips_invalid_yaml(self, tmp_path: Path) -> None:
        """No crash on bad YAML."""
        rules_file = tmp_path / "event-rules.yaml"
        rules_file.write_text("invalid: yaml: ::")

        rules = load_rules(tmp_path)
        assert rules == ()

    def test_load_rules_skips_missing_required_fields(self, tmp_path: Path) -> None:
        """Rules missing event/action are skipped."""
        rules_file = tmp_path / "event-rules.yaml"
        rules_file.write_text("""
rules:
  - event: TestEvent
    # missing action
  - action: log
    # missing event
  - event: GoodEvent
    action: log
    params:
      message: "good"
""")

        rules = load_rules(tmp_path)

        assert len(rules) == 1
        assert rules[0].event == "GoodEvent"

    def test_load_rules_missing_rules_key(self, tmp_path: Path) -> None:
        """YAML without rules key returns empty."""
        rules_file = tmp_path / "event-rules.yaml"
        rules_file.write_text("other: data")

        rules = load_rules(tmp_path)
        assert rules == ()


class TestExpandTemplate:
    """Test expand_template function."""

    def test_expand_template_substitutes_fields(self) -> None:
        """{{ event.field }} → actual value."""
        event = _TestEvent(issue_number=456, reason="testing")
        template = "issue #{{ event.issue_number }}: {{ event.reason }}"

        result = expand_template(template, event)

        assert result == "issue #456: testing"

    def test_expand_template_unknown_field_preserves_placeholder(self) -> None:
        """No crash on missing attr, preserves placeholder."""
        event = _TestEvent()
        template = "missing: {{ event.nonexistent }}"

        result = expand_template(template, event)

        assert result == "missing: {{ event.nonexistent }}"

    def test_expand_template_with_whitespace(self) -> None:
        """Template handles whitespace in placeholders."""
        event = _TestEvent(issue_number=789)
        template = "issue {{  event.issue_number  }}"

        result = expand_template(template, event)

        assert result == "issue 789"

    def test_expand_template_multiple_placeholders(self) -> None:
        """Multiple placeholders in one template."""
        event = _TestEvent(issue_number=100, actor="alice")
        template = "{{ event.actor }} reported issue #{{ event.issue_number }}"

        result = expand_template(template, event)

        assert result == "alice reported issue #100"


class TestEvaluateRules:
    """Test evaluate_rules function."""

    def test_evaluate_rules_matches_event_type(self) -> None:
        """Correct handler called for matching event."""
        event = _TestEvent()
        rules = (
            EventRule(
                event="_TestEvent",
                action="test_action",
                params={"value": "{{ event.issue_number }}"},
            ),
        )
        handler_calls: list[dict[str, str]] = []

        def test_handler(params: dict[str, str]) -> None:
            handler_calls.append(params)

        action_handlers = {"test_action": test_handler}
        evaluate_rules(event, rules, action_handlers)

        assert len(handler_calls) == 1
        assert handler_calls[0] == {"value": "123"}

    def test_evaluate_rules_no_match(self) -> None:
        """Handler NOT called when event type doesn't match."""
        event = _TestEvent()
        rules = (
            EventRule(
                event="DifferentEvent",
                action="test_action",
                params={},
            ),
        )
        handler_calls: list[dict[str, str]] = []

        def test_handler(params: dict[str, str]) -> None:
            handler_calls.append(params)

        action_handlers = {"test_action": test_handler}
        evaluate_rules(event, rules, action_handlers)

        assert len(handler_calls) == 0

    def test_evaluate_rules_disabled_rule_skipped(self) -> None:
        """enabled: false rules are ignored."""
        event = _TestEvent()
        rules = (
            EventRule(
                event="_TestEvent",
                action="test_action",
                params={},
                enabled=False,
            ),
        )
        handler_calls: list[dict[str, str]] = []

        def test_handler(params: dict[str, str]) -> None:
            handler_calls.append(params)

        action_handlers = {"test_action": test_handler}
        evaluate_rules(event, rules, action_handlers)

        assert len(handler_calls) == 0

    def test_evaluate_rules_action_error_does_not_block(self) -> None:
        """Action exception is caught, doesn't block other rules."""
        event = _TestEvent()
        rules = (
            EventRule(
                event="_TestEvent",
                action="bad_action",
                params={},
            ),
            EventRule(
                event="_TestEvent",
                action="good_action",
                params={},
            ),
        )
        handler_calls: list[str] = []

        def bad_handler(params: dict[str, str]) -> None:
            raise RuntimeError("action failed")

        def good_handler(params: dict[str, str]) -> None:
            handler_calls.append("good")

        action_handlers = {
            "bad_action": bad_handler,
            "good_action": good_handler,
        }
        evaluate_rules(event, rules, action_handlers)

        assert "good" in handler_calls

    def test_evaluate_rules_unknown_action_skipped(self) -> None:
        """Unknown action logs warning, doesn't crash."""
        event = _TestEvent()
        rules = (
            EventRule(
                event="_TestEvent",
                action="unknown_action",
                params={},
            ),
        )
        action_handlers: dict[str, Callable[[dict[str, str]], None]] = {}

        # Should not raise
        evaluate_rules(event, rules, action_handlers)


class TestBuildActionHandlers:
    """Test build_action_handlers function."""

    def test_build_action_handlers_returns_dict(self) -> None:
        """Returns dict with expected action handlers."""
        handlers = build_action_handlers()

        assert isinstance(handlers, dict)
        assert "log" in handlers
        assert "enqueue_command_job" in handlers

    def test_log_handler_callable(self) -> None:
        """log action handler is callable."""
        handlers = build_action_handlers()
        log_handler = handlers["log"]

        # Should not raise
        log_handler({"message": "test message"})

    def test_enqueue_handler_callable(self) -> None:
        """enqueue_command_job action handler is callable."""
        handlers = build_action_handlers()
        enqueue_handler = handlers["enqueue_command_job"]

        # Should not raise (placeholder implementation)
        enqueue_handler({"command": "test command", "actor": "test"})


class TestActionHandlers:
    """Test new action handlers."""

    def test_build_action_handlers_all_keys(self) -> None:
        """Dict contains all 9 expected keys."""
        handlers = build_action_handlers()

        expected_keys = {
            "log",
            "refresh_queue_priority",
            "enqueue_command_job",
            "enqueue_plan",
            "enqueue_run",
            "enqueue_review",
            "reload_material",
            "trigger_governance_scan",
            "notify",
        }
        assert set(handlers.keys()) == expected_keys

    def test_refresh_queue_priority_publishes_intent(self) -> None:
        """ManagerDispatchIntent is published with correct issue_number."""
        from unittest.mock import MagicMock, patch

        handlers = build_action_handlers()
        handler = handlers["refresh_queue_priority"]

        mock_publish = MagicMock()
        with patch("vibe3.domain.publish", mock_publish):
            handler({"issue": "123", "actor": "test_actor"})

        assert mock_publish.called
        event = mock_publish.call_args[0][0]
        assert event.issue_number == 123
        assert event.trigger_state == "ready"
        assert event.actor == "test_actor"

    def test_refresh_queue_priority_loop_guard(self) -> None:
        """Re-entrant call with actor='event:refresh_queue_priority' is skipped."""
        from unittest.mock import MagicMock, patch

        handlers = build_action_handlers()
        handler = handlers["refresh_queue_priority"]

        mock_publish = MagicMock()
        with patch("vibe3.domain.publish", mock_publish):
            # This should be skipped due to loop guard
            handler({"issue": "123", "actor": "event:refresh_queue_priority"})

        assert not mock_publish.called

    def test_enqueue_command_job_missing_command_type(self) -> None:
        """Graceful handling of missing command_type."""
        handlers = build_action_handlers()
        handler = handlers["enqueue_command_job"]

        # Should not raise, just log warning
        handler({"issue_number": "123", "actor": "test"})

    def test_enqueue_command_job_missing_issue_number(self) -> None:
        """Graceful handling of missing issue_number."""
        handlers = build_action_handlers()
        handler = handlers["enqueue_command_job"]

        # Should not raise, just log warning
        handler({"command_type": "plan", "actor": "test"})

    def test_enqueue_command_job_invalid_issue_number(self) -> None:
        """Graceful handling of invalid issue_number."""
        handlers = build_action_handlers()
        handler = handlers["enqueue_command_job"]

        # Should not raise, just log warning
        handler({"command_type": "plan", "issue_number": "not_a_number"})

    def test_enqueue_command_job_publishes_manager_intent(self) -> None:
        """enqueue_command_job(manager) publishes ManagerDispatchIntent."""
        from unittest.mock import MagicMock, patch

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
        assert event.issue_number == 100
        assert event.trigger_state == "ready"
        assert event.actor == "test_actor"

    def test_enqueue_command_job_publishes_plan_intent(self) -> None:
        """enqueue_command_job(command_type='plan') publishes PlannerDispatchIntent."""
        from unittest.mock import MagicMock, patch

        handlers = build_action_handlers()
        handler = handlers["enqueue_command_job"]

        mock_publish = MagicMock()
        with patch("vibe3.domain.publish", mock_publish):
            handler(
                {"command_type": "plan", "issue_number": "200", "actor": "test_actor"}
            )

        assert mock_publish.called
        event = mock_publish.call_args[0][0]
        assert event.issue_number == 200
        assert event.trigger_state == "claimed"
        assert event.actor == "test_actor"

    def test_enqueue_command_job_publishes_run_intent(self) -> None:
        """enqueue_command_job(command_type='run') publishes ExecutorDispatchIntent."""
        from unittest.mock import MagicMock, patch

        handlers = build_action_handlers()
        handler = handlers["enqueue_command_job"]

        mock_publish = MagicMock()
        with patch("vibe3.domain.publish", mock_publish):
            handler(
                {"command_type": "run", "issue_number": "300", "actor": "test_actor"}
            )

        assert mock_publish.called
        event = mock_publish.call_args[0][0]
        assert event.issue_number == 300
        assert event.trigger_state == "in-progress"
        assert event.actor == "test_actor"

    def test_enqueue_command_job_publishes_review_intent(self) -> None:
        """enqueue_command_job(review) publishes ReviewerDispatchIntent."""
        from unittest.mock import MagicMock, patch

        handlers = build_action_handlers()
        handler = handlers["enqueue_command_job"]

        mock_publish = MagicMock()
        with patch("vibe3.domain.publish", mock_publish):
            handler(
                {"command_type": "review", "issue_number": "400", "actor": "test_actor"}
            )

        assert mock_publish.called
        event = mock_publish.call_args[0][0]
        assert event.issue_number == 400
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

        handlers = build_action_handlers()
        handler = handlers["enqueue_plan"]

        mock_publish = MagicMock()
        with patch("vibe3.domain.publish", mock_publish):
            handler({"issue_number": "123", "actor": "test_actor"})

        assert mock_publish.called
        event = mock_publish.call_args[0][0]
        assert event.issue_number == 123
        assert event.trigger_state == "claimed"
        assert event.actor == "test_actor"

    def test_enqueue_run_callable(self) -> None:
        """enqueue_run action handler publishes ExecutorDispatchIntent."""
        from unittest.mock import MagicMock, patch

        handlers = build_action_handlers()
        handler = handlers["enqueue_run"]

        mock_publish = MagicMock()
        with patch("vibe3.domain.publish", mock_publish):
            handler({"issue_number": "456", "actor": "test_actor"})

        assert mock_publish.called
        event = mock_publish.call_args[0][0]
        assert event.issue_number == 456
        assert event.trigger_state == "in-progress"
        assert event.actor == "test_actor"

    def test_enqueue_review_callable(self) -> None:
        """enqueue_review action handler publishes ReviewerDispatchIntent."""
        from unittest.mock import MagicMock, patch

        handlers = build_action_handlers()
        handler = handlers["enqueue_review"]

        mock_publish = MagicMock()
        with patch("vibe3.domain.publish", mock_publish):
            handler({"issue_number": "789", "actor": "test_actor"})

        assert mock_publish.called
        event = mock_publish.call_args[0][0]
        assert event.issue_number == 789
        assert event.trigger_state == "review"
        assert event.actor == "test_actor"

    def test_reload_material_publishes_event(self) -> None:
        """GovernanceScanStarted is published."""
        from unittest.mock import MagicMock, patch

        handlers = build_action_handlers()
        handler = handlers["reload_material"]

        mock_publish = MagicMock()
        with patch("vibe3.domain.publish", mock_publish):
            handler({"tick_count": "5"})

        assert mock_publish.called
        event = mock_publish.call_args[0][0]
        assert event.tick_count == 5
        assert event.actor == "event:reload_material"

    def test_trigger_governance_scan_publishes_event(self) -> None:
        """GovernanceScanStarted is published."""
        from unittest.mock import MagicMock, patch

        handlers = build_action_handlers()
        handler = handlers["trigger_governance_scan"]

        mock_publish = MagicMock()
        with patch("vibe3.domain.publish", mock_publish):
            handler({"tick_count": "10", "actor": "custom_actor"})

        assert mock_publish.called
        event = mock_publish.call_args[0][0]
        assert event.tick_count == 10
        assert event.actor == "custom_actor"

    def test_notify_logs_message(self) -> None:
        """Handler is callable and logs with [NOTIFY] prefix."""
        from unittest.mock import patch

        handlers = build_action_handlers()
        handler = handlers["notify"]

        # Should not raise
        with patch("vibe3.domain.event_rules.logger") as mock_logger:
            handler({"message": "test notification", "target": "manager"})
            # Verify the bind was called
            assert mock_logger.bind.called


class TestRulesHaveMatchingHandlers:
    """Test that rules in config have matching handlers."""

    def test_rules_have_matching_handlers(self, tmp_path: Path) -> None:
        """All rules in config have matching action handlers."""
        from vibe3.utils import find_repo_root

        rules_dir = find_repo_root() / "config" / "policies"
        rules = load_rules(rules_dir)
        handlers = build_action_handlers()

        missing_actions: list[str] = []
        for rule in rules:
            if rule.action not in handlers:
                missing_actions.append(rule.action)

        assert not missing_actions, f"Missing handlers for actions: {missing_actions}"
