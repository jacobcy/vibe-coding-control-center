"""Execution role policy service."""

from loguru import logger

from vibe3.agents import sync_models_json
from vibe3.config import load_orchestra_config
from vibe3.config import (
    resolve_effective_agent_options as resolve_backend_effective_agent_options,
)
from vibe3.models import AgentOptions, OrchestraConfig


class ExecutionRolePolicyService:
    """Resolve execution policy by role."""

    # Orchestra roles configuration mapping
    # Command roles (planner/executor/reviewer)
    _ROLE_CONFIG_MAP: dict[str, str] = {
        "manager": "assignee_dispatch",
        "supervisor": "supervisor_handoff",
        "governance": "governance",
    }

    def __init__(self, config: OrchestraConfig | None = None) -> None:
        self._config = config or load_orchestra_config()

    def resolve_backend(self, role: str) -> str:
        section_name = self._ROLE_CONFIG_MAP.get(role)
        if not section_name:
            raise ValueError(f"Unknown role: {role}")

        section = getattr(self._config, section_name, None)
        if not section:
            logger.bind(domain="execution_policy").warning(
                f"No config section for role: {role}, using default backend"
            )
            return "claude"

        backend: str | None = getattr(section, "backend", None)
        if backend:
            return backend

        agent = getattr(section, "agent", None)
        if agent:
            return "claude"

        return "claude"

    def resolve_agent(self, role: str) -> str | None:
        section_name = self._ROLE_CONFIG_MAP.get(role)
        if not section_name:
            raise ValueError(f"Unknown role: {role}")

        section = getattr(self._config, section_name, None)
        if not section:
            return None

        return getattr(section, "agent", None)

    def resolve_model(self, role: str) -> str | None:
        section_name = self._ROLE_CONFIG_MAP.get(role)
        if not section_name:
            raise ValueError(f"Unknown role: {role}")

        section = getattr(self._config, section_name, None)
        if not section:
            return None

        return getattr(section, "model", None)

    def resolve_timeout(self, role: str) -> int:
        section_name = self._ROLE_CONFIG_MAP.get(role)
        if not section_name:
            raise ValueError(f"Unknown role: {role}")

        section = getattr(self._config, section_name, None)
        if not section:
            return 3600

        return getattr(section, "timeout_seconds", 3600)

    def resolve_agent_options(self, role: str) -> AgentOptions:
        agent = self.resolve_agent(role)
        backend = self.resolve_backend(role) if not agent else None
        model = self.resolve_model(role) if backend else None
        timeout = self.resolve_timeout(role)

        return AgentOptions(
            agent=agent,
            backend=backend,
            model=model,
            timeout_seconds=timeout,
        )

    def resolve_effective_agent_options(self, role: str) -> AgentOptions:
        """Resolve preset-backed agent options and sync codeagent models."""
        effective = resolve_backend_effective_agent_options(
            self.resolve_agent_options(role)
        )
        sync_models_json(effective)
        return effective
