"""Execution role policy service."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from loguru import logger

from vibe3.agents import sync_models_json
from vibe3.config import (
    diagnose_profile,
    load_orchestra_config,
)
from vibe3.config import (
    resolve_effective_agent_options as resolve_backend_effective_agent_options,
)
from vibe3.exceptions import DiagnosticContext, MissingResourceError
from vibe3.models import AgentOptions, OrchestraConfig


@dataclass(frozen=True)
class PromptContract:
    template: str


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
        # backend is always set (resolve_backend falls back to "claude").
        # Callers must not treat backend as a user-specified override —
        # _build_command uses has_agent_env_override() to distinguish whether
        # an env override is active and should use --backend/--model directly,
        # vs. using the agent preset name (which carries yolo/model config).
        agent = self.resolve_agent(role)
        backend = self.resolve_backend(role)
        model = self.resolve_model(role)
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
            raise MissingResourceError(
                resource=f"config section for role '{role}'",
                context=DiagnosticContext(
                    resource_type="role-config",
                    search_paths=[str(Path("config/v3/settings.yaml"))],
                    profile=diagnose_profile(),
                    remediation=(
                        f"Add {section_name} configuration to config/v3/settings.yaml"
                    ),
                    ref_issue=1925,
                ),
            )

        template = getattr(section, "prompt_template", None)
        if not template:
            raise MissingResourceError(
                resource=f"prompt_template for role '{role}'",
                context=DiagnosticContext(
                    resource_type="role-config",
                    search_paths=[str(Path("config/v3/settings.yaml"))],
                    profile=diagnose_profile(),
                    remediation=(
                        f"Add prompt_template to {section_name} in "
                        "config/v3/settings.yaml"
                    ),
                    ref_issue=1907,
                ),
            )

        return PromptContract(template=template)

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
