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
    from vibe3.models import (
        CommandType as CommandTypeType,
    )
    from vibe3.models import (
        DomainEvent,
        ExecutionRequest,
        IssueInfo,
        OrchestraConfig,
    )


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


def _dispatch_command_job(
    command_type: str,
    issue_number: int,
    actor: str,
    refs: dict[str, str] | None = None,
) -> None:
    """Internal helper to dispatch a command job via ExecutionCoordinator.

    Args:
        command_type: CommandType value (plan, run, review, manager)
        issue_number: Issue number to dispatch for
        actor: Actor identifier for the dispatch
        refs: Optional refs dict for the execution request
    """
    from vibe3.clients import get_store
    from vibe3.config import load_orchestra_config
    from vibe3.execution import ExecutionCoordinator
    from vibe3.models import CommandType
    from vibe3.services import load_issue_info

    config = load_orchestra_config()
    effective_refs = {"issue_number": str(issue_number)}
    if refs:
        effective_refs.update(refs)

    try:
        cmd_type = CommandType(command_type)
    except ValueError:
        logger.bind(domain="event_rules").warning(
            f"Unknown command_type '{command_type}', skipping dispatch"
        )
        return

    with get_store() as store:
        issue = load_issue_info(issue_number, config=config)
        if issue is None:
            logger.bind(domain="event_rules").warning(
                f"Failed to load issue #{issue_number}, skipping dispatch"
            )
            return

        # Build ExecutionRequest based on command type
        request = _build_execution_request(
            cmd_type, config, issue, actor, effective_refs
        )
        if request is None:
            logger.bind(domain="event_rules").warning(
                f"Failed to build execution request for {cmd_type.value} "
                f"on #{issue_number}"
            )
            return

        coordinator = ExecutionCoordinator(config, store)
        result = coordinator.dispatch_execution(request)

        if result.launched:
            logger.bind(
                domain="event_rules",
                command_type=command_type,
                issue_number=issue_number,
            ).info(f"Command job dispatched: {command_type}")
        elif result.skipped:
            logger.bind(
                domain="event_rules",
                command_type=command_type,
                issue_number=issue_number,
            ).info(f"Command job skipped: {result.reason}")
        else:
            logger.bind(
                domain="event_rules",
                command_type=command_type,
                issue_number=issue_number,
            ).warning(f"Command job dispatch failed: {result.reason}")


def _build_execution_request(
    command_type: "CommandTypeType",
    config: "OrchestraConfig",
    issue: "IssueInfo",
    actor: str,
    refs: dict[str, str],
) -> "ExecutionRequest | None":
    """Build ExecutionRequest for a given command type."""
    from vibe3.config import get_convention
    from vibe3.models import ExecutionRequest, WorktreeRequirement

    convention = get_convention()
    target_branch = convention.branch.canonical_branch(issue.number)

    # Map command type to role and worktree requirement
    role_map = {
        "plan": ("planner", WorktreeRequirement.PERMANENT),
        "run": ("executor", WorktreeRequirement.PERMANENT),
        "review": ("reviewer", WorktreeRequirement.PERMANENT),
        "manager": ("manager", WorktreeRequirement.PERMANENT),
    }

    role, wt_req = role_map.get(
        command_type.value, ("unknown", WorktreeRequirement.NONE)
    )

    return ExecutionRequest(
        role=role,
        target_branch=target_branch,
        target_id=issue.number,
        execution_name=f"vibe3-{role}-issue-{issue.number}",
        actor=actor,
        refs=refs,
        worktree_requirement=wt_req,
        mode="async",
    )


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

        Dispatches a command job via ExecutionCoordinator.
        Params:
            - command_type: CommandType value (plan, run, review, manager)
            - issue_number: Issue number to dispatch for
            - actor: Actor identifier (optional, defaults to
              "event:enqueue_command_job")
        """
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
        refs = {
            k: v
            for k, v in params.items()
            if k not in ("command_type", "issue_number", "actor")
        }

        _dispatch_command_job(command_type, issue_number, actor, refs)

    def enqueue_plan_action(params: dict[str, str]) -> None:
        """Enqueue plan action handler (syntactic sugar for enqueue_command_job)."""
        issue_number_str = params.get("issue_number")
        if not issue_number_str:
            logger.bind(domain="event_rules").warning(
                "enqueue_plan missing 'issue_number' param, skipping"
            )
            return

        try:
            issue_number = int(issue_number_str)
        except ValueError:
            logger.bind(domain="event_rules").warning(
                f"enqueue_plan invalid issue_number '{issue_number_str}', skipping"
            )
            return

        actor = params.get("actor", "event:enqueue_plan")
        refs = {k: v for k, v in params.items() if k not in ("issue_number", "actor")}

        _dispatch_command_job("plan", issue_number, actor, refs)

    def enqueue_run_action(params: dict[str, str]) -> None:
        """Enqueue run action handler (syntactic sugar for enqueue_command_job)."""
        issue_number_str = params.get("issue_number")
        if not issue_number_str:
            logger.bind(domain="event_rules").warning(
                "enqueue_run missing 'issue_number' param, skipping"
            )
            return

        try:
            issue_number = int(issue_number_str)
        except ValueError:
            logger.bind(domain="event_rules").warning(
                f"enqueue_run invalid issue_number '{issue_number_str}', skipping"
            )
            return

        actor = params.get("actor", "event:enqueue_run")
        refs = {k: v for k, v in params.items() if k not in ("issue_number", "actor")}

        _dispatch_command_job("run", issue_number, actor, refs)

    def enqueue_review_action(params: dict[str, str]) -> None:
        """Enqueue review action handler (syntactic sugar for enqueue_command_job)."""
        issue_number_str = params.get("issue_number")
        if not issue_number_str:
            logger.bind(domain="event_rules").warning(
                "enqueue_review missing 'issue_number' param, skipping"
            )
            return

        try:
            issue_number = int(issue_number_str)
        except ValueError:
            logger.bind(domain="event_rules").warning(
                f"enqueue_review invalid issue_number '{issue_number_str}', skipping"
            )
            return

        actor = params.get("actor", "event:enqueue_review")
        refs = {k: v for k, v in params.items() if k not in ("issue_number", "actor")}

        _dispatch_command_job("review", issue_number, actor, refs)

    def refresh_queue_priority_action(params: dict[str, str]) -> None:
        """Refresh queue priority action handler.

        Publishes ManagerDispatchIntent to trigger queue rebuild.
        Uses actor-based loop guard to prevent re-entrant publishing.
        """
        from vibe3.domain import publish
        from vibe3.models import ManagerDispatchIntent

        # Loop guard: skip if we're already in a refresh cycle
        actor_param = params.get("actor", "")
        if actor_param == "event:refresh_queue_priority":
            logger.bind(domain="event_rules").debug(
                "refresh_queue_priority loop detected, skipping re-entrant publish"
            )
            return

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
        ).info("Published ManagerDispatchIntent for queue refresh")

    def reload_material_action(params: dict[str, str]) -> None:
        """Reload material action handler.

        Publishes GovernanceScanStarted to trigger governance material re-read.
        """
        from vibe3.domain import publish
        from vibe3.domain.events.governance import GovernanceScanStarted

        tick_count = 0
        tick_str = params.get("tick_count")
        if tick_str:
            try:
                tick_count = int(tick_str)
            except ValueError:
                pass

        event = GovernanceScanStarted(
            tick_count=tick_count,
            actor="event:reload_material",
        )
        publish(event)

        logger.bind(domain="event_rules").info(
            f"Published GovernanceScanStarted for material reload (tick={tick_count})"
        )

    def trigger_governance_scan_action(params: dict[str, str]) -> None:
        """Trigger governance scan action handler.

        Publishes GovernanceScanStarted directly (bypasses heartbeat interval gating).
        """
        from vibe3.domain import publish
        from vibe3.domain.events.governance import GovernanceScanStarted

        tick_count = 0
        tick_str = params.get("tick_count")
        if tick_str:
            try:
                tick_count = int(tick_str)
            except ValueError:
                pass

        actor = params.get("actor", "event:trigger_governance_scan")

        event = GovernanceScanStarted(
            tick_count=tick_count,
            actor=actor,
        )
        publish(event)

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
        "enqueue_plan": enqueue_plan_action,
        "enqueue_run": enqueue_run_action,
        "enqueue_review": enqueue_review_action,
        "reload_material": reload_material_action,
        "trigger_governance_scan": trigger_governance_scan_action,
        "notify": notify_action,
    }
