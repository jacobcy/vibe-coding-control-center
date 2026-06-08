"""Shared utilities for configuration processing."""

import re
from pathlib import Path
from typing import Any, cast


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

    def expand_value(value: Any, ctx: dict[str, Any]) -> Any:
        if isinstance(value, str):
            # Expand ${...} variable references iteratively
            expanded = value
            max_iterations = 10  # Prevent infinite loops
            for _ in range(max_iterations):
                pattern = r"\$\{([^}]+)\}"

                def replace_var(match: re.Match[str]) -> str:
                    var_path = match.group(1)
                    # Navigate to referenced value
                    current: Any = ctx
                    for part in var_path.split("."):
                        if isinstance(current, dict) and part in current:
                            current = current[part]
                        else:
                            # Variable not found, keep original reference
                            return match.group(0)
                    return (
                        str(current)
                        if not isinstance(current, dict)
                        else match.group(0)
                    )

                new_expanded = re.sub(pattern, replace_var, expanded)
                if new_expanded == expanded:
                    break  # No more changes, reached fixpoint
                expanded = new_expanded

            # Expand ~ to home directory for path values
            if expanded.startswith("~") or "/~" in expanded:
                expanded = str(Path(expanded).expanduser())

            return expanded
        elif isinstance(value, dict):
            return {k: expand_value(v, ctx) for k, v in value.items()}
        else:
            return value

    return cast(dict, expand_value(config, context))
