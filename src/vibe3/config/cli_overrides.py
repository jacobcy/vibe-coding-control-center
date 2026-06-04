"""Helpers for building runtime config CLI overrides."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RoleCliOverrides:
    """CLI override parameters for role configuration."""

    agent: str | None = None
    backend: str | None = None
    model: str | None = None
    fresh_session: bool = False

    def to_config_overrides(self, role: str) -> dict[str, str]:
        """Convert to config override dict for load_runtime_config."""
        overrides: dict[str, str] = {}
        if self.backend:
            overrides[f"{role}.agent_config.backend"] = self.backend
        if self.model:
            overrides[f"{role}.agent_config.model"] = self.model
        if self.agent:
            overrides[f"{role}.agent_config.agent"] = self.agent
        return overrides

    def to_argv(self) -> list[str]:
        """Convert to argv list for CLI invocation."""
        args: list[str] = []
        if self.agent:
            args += ["--agent", self.agent]
        if self.backend:
            args += ["--backend", self.backend]
        if self.model:
            args += ["--model", self.model]
        if self.fresh_session:
            args += ["--fresh-session"]
        return args


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
    return RoleCliOverrides(
        agent=agent, backend=backend, model=model
    ).to_config_overrides(role)


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
    return RoleCliOverrides(
        agent=agent, backend=backend, model=model
    ).to_config_overrides(config_section)
