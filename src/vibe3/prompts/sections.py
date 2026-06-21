from __future__ import annotations

from typing import cast

from vibe3.clients import resolve_runtime_asset
from vibe3.config import ConventionResolver

PROJECT_POLICIES_DIR = ".vibe/policies"

# Maps section key → policy file name in PROJECT_POLICIES_DIR
_SECTION_POLICY_NAMES: dict[str, str] = {
    "common.rules": "common",
    "plan.policy": "plan",
    "run.policy": "run",
    "review.policy": "review",
}


def discover_project_scope_overlays() -> dict[str, str]:
    """Return {section_key: path} for each .vibe/policies/*.md file that exists.

    Used by dry-run display to show which sections have project-scope overrides.
    """
    result: dict[str, str] = {}
    for section_key, policy_name in _SECTION_POLICY_NAMES.items():
        path = f"{PROJECT_POLICIES_DIR}/{policy_name}.md"
        resolved = resolve_runtime_asset(path)
        if resolved.exists():
            result[section_key] = path
    return result


def _read_file(path: str | None) -> str | None:
    """Read file content, returning None if path is None or file doesn't exist."""
    if not path:
        return None
    resolved = resolve_runtime_asset(path)
    if not resolved.exists():
        return None
    try:
        return resolved.read_text(encoding="utf-8")
    except OSError:
        return None


def build_tools_guide_section(tools_guide_path: str | None) -> str | None:
    """Build tools guide section from file.

    Source: config/v3/settings.yaml (review.common_rules)

    Args:
        tools_guide_path: Path to tools guide file (optional)

    Returns:
        Tools guide section or None if not configured/available
    """
    content = _read_file(tools_guide_path)
    if content is None:
        return None
    return f"## Available Tools\n\n{content}"


def build_policy_section(
    user_path: str | None,
    policy_name: str,
) -> str | None:
    """Build a policy section with user + project scope.

    Loads user-scope policy from user_path, then appends project-scope
    content from .vibe/policies/{policy_name}.md if it exists.

    Args:
        user_path: Path to the user-scope policy file
        policy_name: Policy name used to locate the project-scope counterpart

    Returns:
        Combined policy content or None
    """
    user_content = _read_file(user_path)
    project_content = _read_file(f"{PROJECT_POLICIES_DIR}/{policy_name}.md")

    if project_content:
        if user_content:
            return f"{user_content}\n\n{project_content}"
        return project_content

    return user_content


def resolve_common_rules_path(
    agent_common_rules: str | None,
    resolver: ConventionResolver,
) -> str | None:
    """Resolve common rules path from agent config or convention resolver fallback.

    Args:
        agent_common_rules: Configured common rules path from agent config
        resolver: Convention resolver for fallback policy path resolution

    Returns:
        Resolved common rules path or None
    """
    if agent_common_rules is not None:
        return agent_common_rules
    # Cast needed: lazy __getattr__ import loses type info
    return cast(str | None, resolver.get_policy_path("common"))


def build_common_rules_section(
    agent_common_rules: str | None,
    resolver: ConventionResolver,
) -> str | None:
    """Build common rules section with user + project scope.

    Reads user-scope content as-is (preserving its own headers), then
    appends project-scope content from .vibe/policies/common.md.

    Args:
        agent_common_rules: Configured common rules path from agent config
        resolver: Convention resolver for fallback policy path resolution

    Returns:
        Combined common rules section or None
    """
    user_path = resolve_common_rules_path(agent_common_rules, resolver)
    user_content = _read_file(user_path)
    project_content = _read_file(f"{PROJECT_POLICIES_DIR}/common.md")

    if project_content:
        if user_content:
            return f"{user_content}\n\n{project_content}"
        return project_content

    return user_content
