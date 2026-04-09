"""Execution role policy service.

统一解析各执行角色的配置，包括 backend、prompt template、session strategy 等。

Usage Guide: docs/v3/architecture/infrastructure-guide.md#executionrolepolicyservice
"""

from dataclasses import dataclass
from typing import Literal

from loguru import logger

from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.review_runner import AgentOptions


@dataclass(frozen=True)
class PromptContract:
    """Prompt/task contract for a role."""

    template: str
    """Dotted prompts.yaml path (e.g., 'orchestra.assignee_dispatch.manager')"""

    supervisor_file: str | None = None
    """Optional supervisor file to include"""

    include_supervisor_content: bool = True
    """Whether to inline supervisor file content"""


@dataclass(frozen=True)
class SessionStrategy:
    """Session execution strategy."""

    mode: Literal["tmux", "inline", "async"]
    """Execution mode"""

    timeout: int | None = None
    """Optional timeout in seconds"""


@dataclass(frozen=True)
class ConcurrencyClass:
    """Concurrency control configuration."""

    max_concurrent: int = 3
    """Maximum concurrent executions"""

    semaphore_key: str = "default"
    """Semaphore key for concurrency control"""


class ExecutionRolePolicyService:
    """Resolve execution policy by role.

    统一配置解析接口，避免每个链路重复实现。
    支持 roles: manager, planner, executor, reviewer, supervisor, governance.
    """

    # Role 到 config section 的映射
    _ROLE_CONFIG_MAP: dict[str, str] = {
        "manager": "assignee_dispatch",
        "planner": "assignee_dispatch",  # 使用 manager 配置（共享 backend）
        "executor": "assignee_dispatch",
        "reviewer": "assignee_dispatch",
        "supervisor": "supervisor_handoff",
        "governance": "governance",
    }

    def __init__(self, config: OrchestraConfig | None = None) -> None:
        """Initialize with optional config.

        Args:
            config: OrchestraConfig instance. If None, loads from settings.
        """
        if config is None:
            config = OrchestraConfig.from_settings()
        self._config = config

    def resolve_backend(self, role: str) -> str:
        """Resolve backend for a role.

        Args:
            role: Execution role (manager/planner/executor/reviewer/
                supervisor/governance)

        Returns:
            Backend identifier (e.g., "claude", "openai")

        Raises:
            ValueError: If role is unknown
        """
        section_name = self._ROLE_CONFIG_MAP.get(role)
        if not section_name:
            raise ValueError(f"Unknown role: {role}")

        section = getattr(self._config, section_name, None)
        if not section:
            logger.bind(domain="execution_policy").warning(
                f"No config section for role: {role}, using default backend"
            )
            return "claude"  # Default backend

        backend: str | None = getattr(section, "backend", None)
        if backend:
            return backend

        # Fallback to agent preset or default
        agent = getattr(section, "agent", None)
        if agent:
            # Agent preset will be resolved by agent runner
            return "claude"

        return "claude"  # Default backend

    def resolve_agent(self, role: str) -> str | None:
        """Resolve agent preset for a role.

        Args:
            role: Execution role

        Returns:
            Agent preset name if configured, None otherwise

        Raises:
            ValueError: If role is unknown
        """
        section_name = self._ROLE_CONFIG_MAP.get(role)
        if not section_name:
            raise ValueError(f"Unknown role: {role}")

        section = getattr(self._config, section_name, None)
        if not section:
            return None

        return getattr(section, "agent", None)

    def resolve_model(self, role: str) -> str | None:
        """Resolve model override for a role.

        Args:
            role: Execution role

        Returns:
            Model name if configured, None otherwise

        Raises:
            ValueError: If role is unknown
        """
        section_name = self._ROLE_CONFIG_MAP.get(role)
        if not section_name:
            raise ValueError(f"Unknown role: {role}")

        section = getattr(self._config, section_name, None)
        if not section:
            return None

        return getattr(section, "model", None)

    def resolve_timeout(self, role: str) -> int:
        """Resolve timeout for a role.

        Args:
            role: Execution role

        Returns:
            Timeout in seconds (default: 1800)

        Raises:
            ValueError: If role is unknown
        """
        section_name = self._ROLE_CONFIG_MAP.get(role)
        if not section_name:
            raise ValueError(f"Unknown role: {role}")

        section = getattr(self._config, section_name, None)
        if not section:
            return 1800  # Default timeout

        return getattr(section, "timeout_seconds", 1800)

    def resolve_agent_options(self, role: str) -> AgentOptions:
        """Resolve complete agent options for a role.

        Args:
            role: Execution role

        Returns:
            AgentOptions with agent/backend/model/timeout

        Raises:
            ValueError: If role is unknown
        """
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

    def resolve_prompt_contract(self, role: str) -> PromptContract:
        """Resolve prompt/task contract for a role.

        Args:
            role: Execution role

        Returns:
            PromptContract with template and supervisor file info

        Raises:
            ValueError: If role is unknown
        """
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
        """Resolve session strategy for a role.

        Args:
            role: Execution role

        Returns:
            SessionStrategy with mode and timeout
        """
        section_name = self._ROLE_CONFIG_MAP.get(role)
        if not section_name:
            # Default to async for unknown roles
            return SessionStrategy(mode="async")

        section = getattr(self._config, section_name, None)
        if not section:
            return SessionStrategy(mode="async")

        # Determine session mode based on role and config
        use_worktree = getattr(section, "use_worktree", True)
        async_mode = getattr(section, "async_mode", True)
        timeout = getattr(section, "timeout_seconds", None)

        # Session mode priority: tmux > async > inline
        mode: Literal["tmux", "inline", "async"] = "async"
        if use_worktree and async_mode:
            mode = "tmux"
        elif not async_mode:
            mode = "inline"

        return SessionStrategy(mode=mode, timeout=timeout)

    def resolve_concurrency_class(self, role: str) -> ConcurrencyClass:
        """Resolve concurrency control for a role.

        Args:
            role: Execution role

        Returns:
            ConcurrencyClass with max concurrent and semaphore key
        """
        # For manager, use max_concurrent_flows from orchestra config
        if role == "manager":
            return ConcurrencyClass(
                max_concurrent=self._config.max_concurrent_flows,
                semaphore_key="manager",
            )

        # For other roles, default to no concurrency limit
        return ConcurrencyClass(
            max_concurrent=10,  # Allow more parallel execution for agents
            semaphore_key=role,
        )
