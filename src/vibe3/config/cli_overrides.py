"""Helpers for building runtime config CLI overrides."""

ROLE_CONFIG_SECTIONS: dict[str, str] = {
    "executor": "run",
    "planner": "plan",
    "reviewer": "review",
}


def build_role_cli_overrides(
    role: str,
    agent: str | None,
    backend: str | None,
    model: str | None,
) -> dict[str, str]:
    """Build cli_overrides dict for load_runtime_config."""
    overrides: dict[str, str] = {}
    if backend:
        overrides[f"{role}.agent_config.backend"] = backend
    if model:
        overrides[f"{role}.agent_config.model"] = model
    if agent:
        overrides[f"{role}.agent_config.agent"] = agent
    return overrides


def build_issue_role_cli_overrides(
    role_name: str,
    agent: str | None,
    backend: str | None,
    model: str | None,
) -> dict[str, str]:
    """Build runtime CLI overrides for an issue-scoped role."""
    config_section = ROLE_CONFIG_SECTIONS.get(role_name)
    if config_section is None:
        return {}
    return build_role_cli_overrides(config_section, agent, backend, model)
