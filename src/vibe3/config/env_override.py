"""Unified environment variable override framework.

This module provides a centralized mechanism for applying environment variable
overrides to configuration objects, replacing scattered os.environ.get() calls
throughout the codebase.

Design Principles:
1. Single source of truth: All override rules in OVERRIDE_RULES
2. Explicit is better than implicit: Each rule declares env key and config path
3. Type safety: Converters handle type conversion with error handling
4. Graceful degradation: Invalid values log warnings but don't crash
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from typing import Any, Callable

from loguru import logger


@dataclass
class EnvOverrideRule:
    """Environment variable override rule definition.

    Attributes:
        env_key: Environment variable name (e.g., "MANAGER_USERNAMES")
        config_path: Dot-separated path in config (e.g., "orchestra.manager_usernames")
        converter: Function to convert string to target type
        description: Human-readable description for documentation
    """

    env_key: str
    config_path: str
    converter: Callable[[str], Any] = str
    description: str = ""


# Centralized override rules registry
# Each rule defines: env_key -> config_path mapping with type conversion
OVERRIDE_RULES: list[EnvOverrideRule] = [
    # Manager usernames (orchestra configuration)
    EnvOverrideRule(
        env_key="MANAGER_USERNAMES",
        config_path="orchestra.manager_usernames",
        converter=lambda s: tuple(s.split(",")),
        description="Comma-separated list of manager GitHub usernames",
    ),
    # Code limits (quality standards)
    EnvOverrideRule(
        env_key="VIBE_CODE_LIMITS_V2_SHELL_TOTAL_LOC",
        config_path="code_limits.total_file_loc.v2_shell",
        converter=int,
        description="Total lines of code limit for V2 shell scripts",
    ),
    EnvOverrideRule(
        env_key="VIBE_CODE_LIMITS_V3_PYTHON_TOTAL_LOC",
        config_path="code_limits.total_file_loc.v3_python",
        converter=int,
        description="Total lines of code limit for V3 Python code",
    ),
    # Test coverage requirements
    EnvOverrideRule(
        env_key="VIBE_TEST_COVERAGE_SERVICES",
        config_path="quality.test_coverage.services",
        converter=int,
        description="Test coverage requirement for services layer",
    ),
    # Manager backend/model (agent configuration)
    EnvOverrideRule(
        env_key="VIBE_BACKEND_MANAGER",
        config_path="orchestra.assignee_dispatch.backend",
        description="Backend override for manager agent",
    ),
    EnvOverrideRule(
        env_key="VIBE_MODEL_MANAGER",
        config_path="orchestra.assignee_dispatch.model",
        description="Model override for manager agent",
    ),
    # Governance backend/model
    EnvOverrideRule(
        env_key="VIBE_BACKEND_GOVERNANCE",
        config_path="orchestra.governance.backend",
        description="Backend override for governance agent",
    ),
    EnvOverrideRule(
        env_key="VIBE_MODEL_GOVERNANCE",
        config_path="orchestra.governance.model",
        description="Model override for governance agent",
    ),
    # Supervisor backend/model
    EnvOverrideRule(
        env_key="VIBE_BACKEND_SUPERVISOR",
        config_path="orchestra.supervisor_handoff.backend",
        description="Backend override for supervisor agent",
    ),
    EnvOverrideRule(
        env_key="VIBE_MODEL_SUPERVISOR",
        config_path="orchestra.supervisor_handoff.model",
        description="Model override for supervisor agent",
    ),
]


def _set_nested_value(obj: dict[str, Any], path: str, value: Any) -> None:
    """Set a value in a nested dictionary using dot-separated path.

    Args:
        obj: Dictionary to modify
        path: Dot-separated path (e.g., "orchestra.manager_usernames")
        value: Value to set

    Example:
        >>> obj = {}
        >>> _set_nested_value(obj, "a.b.c", 42)
        >>> obj
        {'a': {'b': {'c': 42}}}
    """
    keys = path.split(".")
    current = obj

    # Navigate to parent, creating intermediate dicts as needed
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        elif not isinstance(current[key], dict):
            # If path component exists but is not a dict, replace it
            current[key] = {}
        current = current[key]

    # Set the final value
    current[keys[-1]] = value


def apply_env_overrides(
    config_dict: dict[str, Any], rules: list[EnvOverrideRule] | None = None
) -> dict[str, Any]:
    """Apply environment variable overrides to configuration dictionary.

    Returns a new dictionary with overrides applied; the original is unchanged.

    Args:
        config_dict: Configuration dictionary to base overrides on
        rules: Override rules to apply (default: OVERRIDE_RULES)

    Returns:
        New configuration dictionary with overrides applied

    Example:
        >>> config = {"orchestra": {"manager_usernames": ["vibe-manager-agent"]}}
        >>> os.environ["MANAGER_USERNAMES"] = "custom-manager"
        >>> result = apply_env_overrides(config)
        >>> result["orchestra"]["manager_usernames"]
        ('custom-manager',)
        >>> config["orchestra"]["manager_usernames"]  # original unchanged
        ['vibe-manager-agent']
    """
    if rules is None:
        rules = OVERRIDE_RULES

    result = copy.deepcopy(config_dict)

    for rule in rules:
        env_value = os.environ.get(rule.env_key)
        if env_value is None:
            continue

        try:
            converted = rule.converter(env_value)
            _set_nested_value(result, rule.config_path, converted)
            logger.bind(
                domain="config",
                env_key=rule.env_key,
                config_path=rule.config_path,
            ).debug(f"Applied env override: {rule.env_key} -> {rule.config_path}")
        except (ValueError, TypeError) as e:
            logger.bind(
                domain="config",
                env_key=rule.env_key,
                config_path=rule.config_path,
            ).warning(
                f"Invalid env value for {rule.env_key}: {env_value!r}, error: {e}"
            )

    return result


def get_env_override(
    env_key: str,
    converter: Callable[[str], Any] = str,
    default: Any = None,
) -> Any:
    """Get environment variable value with type conversion.

    Convenience function for one-off env var reads outside of config loading.

    Args:
        env_key: Environment variable name
        converter: Type conversion function
        default: Default value if not set or invalid

    Returns:
        Converted value or default

    Example:
        >>> get_env_override("MANAGER_USERNAMES", lambda s: tuple(s.split(",")))
        ('vibe-manager-agent',)
    """
    value = os.environ.get(env_key)
    if value is None:
        return default

    try:
        return converter(value)
    except (ValueError, TypeError) as e:
        logger.bind(domain="config", env_key=env_key).warning(
            f"Invalid env value for {env_key}: {value!r}, "
            f"using default: {default}, error: {e}"
        )
        return default


__all__ = [
    "EnvOverrideRule",
    "OVERRIDE_RULES",
    "apply_env_overrides",
    "get_env_override",
]
