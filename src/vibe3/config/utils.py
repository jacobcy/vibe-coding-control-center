"""Variable expansion utilities for YAML configuration dictionaries."""

import re
from pathlib import Path
from typing import Any

_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")
_MAX_EXPANSION_ITERATIONS = 10  # Prevent infinite loops from circular ${} references


def expand_config_variables(
    config: dict[str, Any], context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Expand variable references like ${paths.policies_root} in config values.

    Supports ${path.to.value} syntax for referencing other config values.
    Performs iterative expansion to handle nested references with cycle detection.
    Also expands ~ to home directory in path values.

    Args:
        config: Configuration dictionary to expand.
        context: Optional context dictionary for variable resolution.
                 If None, uses config itself as context.

    Returns:
        Expanded configuration dictionary.
    """
    if context is None:
        context = config

    def replace_var(match: re.Match[str]) -> str:
        var_path = match.group(1)
        current: Any = context
        for part in var_path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return match.group(0)
        return str(current) if not isinstance(current, dict) else match.group(0)

    def expand_value(value: Any, ctx: dict[str, Any]) -> Any:
        if isinstance(value, str):
            expanded = value
            for _ in range(_MAX_EXPANSION_ITERATIONS):
                new_expanded = _VAR_PATTERN.sub(replace_var, expanded)
                if new_expanded == expanded:
                    break
                expanded = new_expanded

            if expanded.startswith("~") or "/~" in expanded:
                expanded = str(Path(expanded).expanduser())

            return expanded
        elif isinstance(value, dict):
            return {k: expand_value(v, ctx) for k, v in value.items()}
        else:
            return value

    return expand_value(config, context)  # type: ignore[no-any-return]
