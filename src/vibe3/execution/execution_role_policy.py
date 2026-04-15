"""Execution role policy service."""

from dataclasses import dataclass
from typing import Literal

from loguru import logger

from vibe3.agents.backends.codeagent_config import (
    resolve_effective_agent_options as resolve_backend_effective_agent_options,
)
from vibe3.agents.backends.codeagent_config import sync_models_json
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.review_runner import AgentOptions


@dataclass(frozen=True)
class PromptContract:
    template: str
    supervisor_file: str | None = None
    include_supervisor_content: bool = True


@dataclass(frozen=True)
class SessionStrategy:
    mode: Literal["tmux", "inline", "async"]
    timeout: int | None = None


@dataclass(frozen=True)
class ConcurrencyClass:
    max_concurrent: int = 3
    semaphore_key: str = "default"


class ExecutionRolePolicyService:
    """Resolve execution policy by role."""

    _ROLE_CONFIG_MAP: dict[str, str] = {
        "manager": "assignee_dispatch",
        "planner": "assignee_dispatch",
        "executor": "assignee_dispatch",
        "reviewer": "assignee_dispatch",
        "supervisor": "supervisor_handoff",
        "governance": "governance",
    }

    def __init__(self, config: OrchestraConfig | None = None) -> None:
        self._config = config or OrchestraConfig.from_settings()

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

    def resolve_prompt_contract(self, role: str) -> PromptContract:
        section_name = self._ROLE_CONFIG_MAP.get(role)
        if not section_name:
            raise ValueError(f"Unknown role: {role}")

        section = getattr(self._config, section_name, None)
        if not section:
            raise ValueError(f"No config section for role: {role}")

        template = getattr(section, "prompt_template", None)
        if not template:
            raise ValueError(f"No prompt_template for role: {role}")

        supervisor_file = getattr(section, "supervisor_file", None)
        include_supervisor = getattr(section, "include_supervisor_content", True)

        return PromptContract(
            template=template,
            supervisor_file=supervisor_file,
            include_supervisor_content=include_supervisor,
        )

    def resolve_session_strategy(self, role: str) -> SessionStrategy:
        section_name = self._ROLE_CONFIG_MAP.get(role)
        if not section_name:
            return SessionStrategy(mode="async")

        section = getattr(self._config, section_name, None)
        if not section:
            return SessionStrategy(mode="async")

        use_worktree = getattr(section, "use_worktree", True)
        async_mode = getattr(section, "async_mode", True)
        timeout = getattr(section, "timeout_seconds", None)

        mode: Literal["tmux", "inline", "async"] = "async"
        if use_worktree and async_mode:
            mode = "tmux"
        elif not async_mode:
            mode = "inline"

        return SessionStrategy(mode=mode, timeout=timeout)

    def resolve_concurrency_class(self, role: str) -> ConcurrencyClass:
        if role == "manager":
            return ConcurrencyClass(
                max_concurrent=self._config.max_concurrent_flows,
                semaphore_key="manager",
            )

        return ConcurrencyClass(
            max_concurrent=10,
            semaphore_key=role,
        )
