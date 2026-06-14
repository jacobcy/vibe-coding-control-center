"""Event routing rule engine.

Loads declarative event→action rules from YAML and evaluates them
on every published domain event via EventPublisher.on_publish hook.
"""

from __future__ import annotations

import functools
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import yaml
from loguru import logger

if TYPE_CHECKING:
    from vibe3.models import DomainEvent

# Module-level callback registry for queue refresh
_queue_refresh_callback: Callable[[int], None] | None = None

# Debounce state for queue refresh
QUEUE_REFRESH_COOLDOWN_SECONDS = 5
_last_queue_refresh: dict[int, float] = {}


def register_queue_refresh_callback(callback: Callable[[int], None]) -> None:
    """Register callback for event-driven queue refresh.

    Args:
        callback: Function to call with issue_number when queue refresh is triggered
    """
    global _queue_refresh_callback
    _queue_refresh_callback = callback


@dataclass(frozen=True)
class EventRule:
    """Single event routing rule."""

    event: str  # DomainEvent class name (e.g. "ManagerDispatchIntent")
    action: str  # Action identifier (e.g. "log", "enqueue_command_job")
    params: dict[str, str]  # Template parameters with {{ event.field }} syntax
    enabled: bool = True
    scope: tuple[str, ...] = ()  # Optional scope filter


def load_rules(policy_dir: Path) -> tuple[EventRule, ...]:
    """Load rules from YAML files in policy_dir.

    Args:
        policy_dir: Directory containing event-rules.yaml

    Returns:
        Tuple of EventRule objects. Empty tuple if directory or file missing.
    """
    rules_file = policy_dir / "event-rules.yaml"
    if not rules_file.exists():
        logger.bind(domain="event_rules").debug(
            f"Event rules file not found: {rules_file}, using empty ruleset"
        )
        return ()

    try:
        content = yaml.safe_load(rules_file.read_text())
    except Exception as exc:
        logger.bind(domain="event_rules").warning(
            f"Failed to load event rules from {rules_file}: {exc}"
        )
        return ()

    if not content or "rules" not in content:
        return ()

    rules: list[EventRule] = []
    for idx, rule_data in enumerate(content["rules"]):
        if not isinstance(rule_data, dict):
            logger.bind(domain="event_rules").warning(
                f"Rule #{idx} is not a dict, skipping"
            )
            continue

        # Validate required fields
        if "event" not in rule_data or "action" not in rule_data:
            logger.bind(domain="event_rules").warning(
                f"Rule #{idx} missing required field (event/action), skipping"
            )
            continue

        try:
            rule = EventRule(
                event=str(rule_data["event"]),
                action=str(rule_data["action"]),
                params=rule_data.get("params", {}),
                enabled=rule_data.get("enabled", True),
                scope=tuple(rule_data.get("scope", [])),
            )
            rules.append(rule)
        except Exception as exc:
            logger.bind(domain="event_rules").warning(
                f"Failed to create rule #{idx}: {exc}, skipping"
            )
            continue

    logger.bind(domain="event_rules").info(
        f"Loaded {len(rules)} event rules from {rules_file}"
    )
    return tuple(rules)


def expand_template(template: str, event: DomainEvent) -> str:
    """Expand {{ event.field }} placeholders using event attribute values.

    Args:
        template: String with {{ event.field }} placeholders
        event: DomainEvent instance to extract values from

    Returns:
        String with placeholders replaced by attribute values.
        Unknown attributes are replaced with empty string.
    """

    def replace_match(match: re.Match[str]) -> str:
        field_path = match.group(1).strip()
        # Handle dot-path for nested attributes (e.g., event.issue.number)
        parts = field_path.split(".")
        if not parts or parts[0] != "event":
            return match.group(0)  # Return original if not event.*

        value: object = event
        for part in parts[1:]:
            try:
                value = getattr(value, part)
            except AttributeError:
                logger.bind(domain="event_rules").warning(
                    f"Event missing attribute '{field_path}', preserving placeholder"
                )
                return match.group(0)

        return str(value)

    return re.sub(r"\{\{\s*([^}]+)\s*\}\}", replace_match, template)


def evaluate_rules(
    event: DomainEvent,
    rules: tuple[EventRule, ...],
    action_handlers: dict[str, Callable[[dict[str, str]], None]],
) -> None:
    """Evaluate all matching rules for an event and execute their actions.

    Args:
        event: DomainEvent instance to evaluate
        rules: Tuple of EventRule objects to check
        action_handlers: Dict mapping action names to handler functions
    """
    event_type = type(event).__name__

    for rule in rules:
        if not rule.enabled:
            continue

        if rule.event != event_type:
            continue

        # Expand template parameters
        expanded_params: dict[str, str] = {}
        for key, value in rule.params.items():
            if isinstance(value, str):
                expanded_params[key] = expand_template(value, event)
            else:
                expanded_params[key] = str(value)

        # Scope filter: if rule has scope, check against params
        if rule.scope:
            # For now, scope is informational; can be extended for filtering
            pass

        # Execute action
        handler = action_handlers.get(rule.action)
        if not handler:
            logger.bind(domain="event_rules").warning(
                f"No handler registered for action '{rule.action}', skipping"
            )
            continue

        try:
            handler(expanded_params)
        except Exception as exc:
            logger.bind(domain="event_rules").error(
                f"Action handler '{rule.action}' failed: {exc}"
            )


def _resolve_branch_from_issue(params: dict[str, str], issue_number: int) -> str:
    """Resolve branch name from params or use convention.

    Args:
        params: Action parameters dict
        issue_number: Issue number to resolve branch for

    Returns:
        Branch name from params or convention-based canonical branch
    """
    branch = params.get("branch")
    if branch:
        return branch
    from vibe3.config import get_convention

    convention = get_convention()
    return convention.branch.canonical_branch(issue_number)


def build_action_handlers() -> dict[str, Callable[[dict[str, str]], None]]:
    """Build action handlers dict for rule evaluation.

    Returns:
        Dict mapping action names to handler functions.
        Supports: log, enqueue_command_job, enqueue_plan, enqueue_run,
        enqueue_review, refresh_queue_priority, reload_material,
        trigger_governance_scan, notify
    """

    def log_action(params: dict[str, str]) -> None:
        """Log action handler."""
        message = params.get("message", "")
        logger.bind(domain="event_rules").info(message)

    def enqueue_command_job_action(params: dict[str, str]) -> None:
        """Enqueue command job action handler.

        Publishes DispatchIntent events for the corresponding command type.
        Params:
            - command_type: CommandType value (plan, run, review, manager)
            - issue_number: Issue number to dispatch for
            - actor: Actor identifier (optional, defaults to
              "event:enqueue_command_job")
            - branch: Branch name (optional, defaults to convention)
        """
        from vibe3.domain import publish

        command_type = params.get("command_type")
        if not command_type:
            logger.bind(domain="event_rules").warning(
                "enqueue_command_job missing 'command_type' param, skipping"
            )
            return

        issue_number_str = params.get("issue_number")
        if not issue_number_str:
            logger.bind(domain="event_rules").warning(
                "enqueue_command_job missing 'issue_number' param, skipping"
            )
            return

        try:
            issue_number = int(issue_number_str)
        except ValueError:
            logger.bind(domain="event_rules").warning(
                f"enqueue_command_job invalid issue_number "
                f"'{issue_number_str}', skipping"
            )
            return

        actor = params.get("actor", "event:enqueue_command_job")
        branch = _resolve_branch_from_issue(params, issue_number)

        # Map command_type to DispatchIntent class and trigger_state
        command_type_lower = command_type.lower()
        intent_type_name: str
        if command_type_lower == "manager":
            from vibe3.models import ManagerDispatchIntent

            manager_event = ManagerDispatchIntent(
                issue_number=issue_number,
                branch=branch,
                trigger_state="ready",
                actor=actor,
            )
            publish(manager_event)
            intent_type_name = "ManagerDispatchIntent"
        elif command_type_lower == "plan":
            from vibe3.models import PlannerDispatchIntent

            planner_event = PlannerDispatchIntent(
                issue_number=issue_number,
                branch=branch,
                trigger_state="claimed",
                actor=actor,
            )
            publish(planner_event)
            intent_type_name = "PlannerDispatchIntent"
        elif command_type_lower == "run":
            from vibe3.models import ExecutorDispatchIntent

            executor_event = ExecutorDispatchIntent(
                issue_number=issue_number,
                branch=branch,
                trigger_state="in-progress",
                actor=actor,
            )
            publish(executor_event)
            intent_type_name = "ExecutorDispatchIntent"
        elif command_type_lower == "review":
            from vibe3.models import ReviewerDispatchIntent

            reviewer_event = ReviewerDispatchIntent(
                issue_number=issue_number,
                branch=branch,
                trigger_state="review",
                actor=actor,
            )
            publish(reviewer_event)
            intent_type_name = "ReviewerDispatchIntent"
        else:
            logger.bind(domain="event_rules").warning(
                f"enqueue_command_job unknown command_type '{command_type}', "
                "skipping"
            )
            return

        logger.bind(
            domain="event_rules",
            command_type=command_type,
            issue_number=issue_number,
        ).info(f"Published {intent_type_name} for command dispatch")

    def _enqueue_by_role(role: str, params: dict[str, str]) -> None:
        """Validate params and publish role-specific DispatchIntent."""
        from vibe3.domain import publish

        issue_number_str = params.get("issue_number")
        if not issue_number_str:
            logger.bind(domain="event_rules").warning(
                f"enqueue_{role} missing 'issue_number' param, skipping"
            )
            return

        try:
            issue_number = int(issue_number_str)
        except ValueError:
            logger.bind(domain="event_rules").warning(
                f"enqueue_{role} invalid issue_number '{issue_number_str}', skipping"
            )
            return

        actor = params.get("actor", f"event:enqueue_{role}")
        branch = _resolve_branch_from_issue(params, issue_number)

        # Map role to DispatchIntent class and trigger_state
        intent_type_name: str
        if role == "plan":
            from vibe3.models import PlannerDispatchIntent

            planner_event = PlannerDispatchIntent(
                issue_number=issue_number,
                branch=branch,
                trigger_state="claimed",
                actor=actor,
            )
            publish(planner_event)
            intent_type_name = "PlannerDispatchIntent"
        elif role == "run":
            from vibe3.models import ExecutorDispatchIntent

            executor_event = ExecutorDispatchIntent(
                issue_number=issue_number,
                branch=branch,
                trigger_state="in-progress",
                actor=actor,
            )
            publish(executor_event)
            intent_type_name = "ExecutorDispatchIntent"
        elif role == "review":
            from vibe3.models import ReviewerDispatchIntent

            reviewer_event = ReviewerDispatchIntent(
                issue_number=issue_number,
                branch=branch,
                trigger_state="review",
                actor=actor,
            )
            publish(reviewer_event)
            intent_type_name = "ReviewerDispatchIntent"
        else:
            logger.bind(domain="event_rules").warning(
                f"Unknown role '{role}' for enqueue_by_role, skipping"
            )
            return

        logger.bind(
            domain="event_rules",
            role=role,
            issue_number=issue_number,
        ).info(f"Published {intent_type_name} for role dispatch")

    def refresh_queue_priority_action(params: dict[str, str]) -> None:
        """Refresh queue priority action handler.

        When callback is registered, calls it directly for queue refresh.
        Otherwise (test environment), falls back to ManagerDispatchIntent publish.
        Uses debounce cooldown to prevent rapid successive refreshes.
        """
        issue_number_str = params.get("issue")
        if not issue_number_str:
            issue_number_str = params.get("issue_number")

        if not issue_number_str:
            logger.bind(domain="event_rules").warning(
                "refresh_queue_priority missing 'issue' param, skipping"
            )
            return

        try:
            issue_number = int(issue_number_str)
        except ValueError:
            logger.bind(domain="event_rules").warning(
                f"refresh_queue_priority invalid issue '{issue_number_str}', skipping"
            )
            return

        # Debounce: skip if same issue was refreshed within cooldown window
        current_time = time.time()
        last_refresh = _last_queue_refresh.get(issue_number, 0.0)
        if current_time - last_refresh < QUEUE_REFRESH_COOLDOWN_SECONDS:
            logger.bind(domain="event_rules", issue_number=issue_number).debug(
                f"refresh_queue_priority debounced "
                f"(cooldown: {QUEUE_REFRESH_COOLDOWN_SECONDS}s)"
            )
            return

        # Update debounce timestamp
        _last_queue_refresh[issue_number] = current_time

        # If callback is registered, use it for direct queue refresh
        if _queue_refresh_callback is not None:
            _queue_refresh_callback(issue_number)
            logger.bind(domain="event_rules", issue_number=issue_number).info(
                "Called queue refresh callback"
            )
            return

        # Fallback: publish ManagerDispatchIntent (test environment)
        from vibe3.domain import publish
        from vibe3.models import ManagerDispatchIntent

        # Loop guard for fallback path
        actor_param = params.get("actor", "")
        if actor_param == "event:refresh_queue_priority":
            logger.bind(domain="event_rules").debug(
                "refresh_queue_priority loop detected, skipping re-entrant publish"
            )
            return

        # Get branch from params or use convention
        branch = params.get("branch")
        if not branch:
            from vibe3.config import get_convention

            convention = get_convention()
            branch = convention.branch.canonical_branch(issue_number)

        actor = params.get("actor", "event:refresh_queue_priority")

        event = ManagerDispatchIntent(
            issue_number=issue_number,
            branch=branch,
            trigger_state="ready",
            actor=actor,
        )
        publish(event)

        logger.bind(
            domain="event_rules",
            issue_number=issue_number,
        ).info("Published ManagerDispatchIntent for queue refresh (fallback)")

    def _publish_governance_scan(actor: str, tick_count: int) -> None:
        """Publish GovernanceScanStarted with the given actor and tick."""
        from vibe3.domain import publish
        from vibe3.domain.events.governance import GovernanceScanStarted

        publish(GovernanceScanStarted(tick_count=tick_count, actor=actor))

    def reload_material_action(params: dict[str, str]) -> None:
        """Reload material action handler.

        Publishes GovernanceScanStarted to trigger governance material re-read.
        """
        tick_count = 0
        tick_str = params.get("tick_count")
        if tick_str:
            try:
                tick_count = int(tick_str)
            except ValueError:
                pass

        _publish_governance_scan("event:reload_material", tick_count)
        logger.bind(domain="event_rules").info(
            f"Published GovernanceScanStarted for material reload (tick={tick_count})"
        )

    def trigger_governance_scan_action(params: dict[str, str]) -> None:
        """Trigger governance scan action handler.

        Publishes GovernanceScanStarted directly (bypasses heartbeat interval gating).
        """
        tick_count = 0
        tick_str = params.get("tick_count")
        if tick_str:
            try:
                tick_count = int(tick_str)
            except ValueError:
                pass

        actor = params.get("actor", "event:trigger_governance_scan")
        _publish_governance_scan(actor, tick_count)
        logger.bind(domain="event_rules").info(
            f"Published GovernanceScanStarted (tick={tick_count})"
        )

    def notify_action(params: dict[str, str]) -> None:
        """Notify action handler (stub).

        Logs notification intent for future channel integration.
        """
        message = params.get("message", "")
        target = params.get("target", "unknown")

        logger.bind(domain="event_rules").info(
            f"[NOTIFY] target={target} message={message}"
        )

    return {
        "log": log_action,
        "refresh_queue_priority": refresh_queue_priority_action,
        "enqueue_command_job": enqueue_command_job_action,
        "enqueue_plan": functools.partial(_enqueue_by_role, "plan"),
        "enqueue_run": functools.partial(_enqueue_by_role, "run"),
        "enqueue_review": functools.partial(_enqueue_by_role, "review"),
        "reload_material": reload_material_action,
        "trigger_governance_scan": trigger_governance_scan_action,
        "notify": notify_action,
    }
