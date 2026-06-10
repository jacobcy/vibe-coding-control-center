"""Event routing rule engine.

Loads declarative event→action rules from YAML and evaluates them
on every published domain event via EventPublisher.on_publish hook.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import yaml
from loguru import logger

if TYPE_CHECKING:
    from vibe3.models import DomainEvent


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


def build_action_handlers() -> dict[str, Callable[[dict[str, str]], None]]:
    """Build action handlers dict for rule evaluation.

    Returns:
        Dict mapping action names to handler functions.
        Currently supports: log, enqueue_command_job
    """

    def log_action(params: dict[str, str]) -> None:
        """Log action handler."""
        message = params.get("message", "")
        logger.bind(domain="event_rules").info(message)

    def enqueue_command_job_action(params: dict[str, str]) -> None:
        """Enqueue command job action handler.

        NOTE: This is a placeholder for now. Full implementation
        requires integration with the job queue system.
        """
        command = params.get("command", "")
        actor = params.get("actor", "system")
        logger.bind(domain="event_rules").info(
            f"Would enqueue command: {command} (actor={actor})"
        )
        # TODO: Integrate with actual job queue when available

    return {
        "log": log_action,
        "enqueue_command_job": enqueue_command_job_action,
    }
