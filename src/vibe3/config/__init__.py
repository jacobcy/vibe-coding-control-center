"""Config package."""

from typing import Any

from vibe3.config.agent_preset import (
    find_missing_backend_commands,
    has_agent_env_override,
    read_models_json,
    repo_models_json_path,
    resolve_effective_agent_options,
    resolve_repo_agent_preset_name,
)
from vibe3.config.branch_convention import BranchConvention
from vibe3.config.loader import (
    get_config,
    load_config,
    load_keys_env_fallback,
    load_runtime_config,
    reload_config,
)
from vibe3.config.manager_config import get_manager_usernames
from vibe3.config.orchestra_config import PeriodicCheckConfig
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.config.profile_config import ProfileConfig
from vibe3.config.profile_convention import LabelsConvention, ProfileConvention
from vibe3.config.role_gates import (
    EXECUTOR_GATE_CONFIG,
    GOVERNANCE_GATE_CONFIG,
    MANAGER_GATE_CONFIG,
    PLANNER_GATE_CONFIG,
    REVIEWER_GATE_CONFIG,
    SUPERVISOR_APPLY_GATE_CONFIG,
    SUPERVISOR_IDENTIFY_GATE_CONFIG,
)
from vibe3.config.role_policy import (
    RoleOutputContract,
    get_role_output_contract,
    get_role_section,
)
from vibe3.config.settings import (
    AgentPromptConfig,
    AIConfig,
    CodeLimitsConfig,
    CodePathsConfig,
    FlowConfig,
    MergeGateConfig,
    PlanConfig,
    PRScoringConfig,
    QualityConfig,
    ReviewConfig,
    ReviewScopeConfig,
    RunConfig,
    SingleFileLocConfig,
    TestPathsConfig,
    TotalFileLocConfig,
    VibeConfig,
)
from vibe3.config.timeline_comment_policy import TimelineCommentPolicy

__all__ = [
    "AIConfig",
    "AgentPromptConfig",
    "BranchConvention",
    "CodeLimitsConfig",
    "CodePathsConfig",
    "ConventionResolver",
    "EXECUTOR_GATE_CONFIG",
    "FlowConfig",
    "GOVERNANCE_GATE_CONFIG",
    "LabelsConvention",
    "MANAGER_GATE_CONFIG",
    "MergeGateConfig",
    "PeriodicCheckConfig",
    "PLANNER_GATE_CONFIG",
    "PlanConfig",
    "ProfileConfig",
    "ProfileConvention",
    "PRScoringConfig",
    "QualityConfig",
    "REVIEWER_GATE_CONFIG",
    "SUPERVISOR_APPLY_GATE_CONFIG",
    "SUPERVISOR_IDENTIFY_GATE_CONFIG",
    "ReviewConfig",
    "ReviewScopeConfig",
    "RoleOutputContract",
    "RunConfig",
    "SingleFileLocConfig",
    "TestPathsConfig",
    "TimelineCommentPolicy",
    "TotalFileLocConfig",
    "VibeConfig",
    "find_missing_backend_commands",
    "get_config",
    "get_manager_usernames",
    "get_role_output_contract",
    "get_role_section",
    "has_agent_env_override",
    "load_config",
    "load_keys_env_fallback",
    "load_orchestra_config",
    "load_runtime_config",
    "read_models_json",
    "reload_config",
    "repo_models_json_path",
    "resolve_effective_agent_options",
    "resolve_repo_agent_preset_name",
]

# Lazy import mapping for symbols to avoid circular dependencies
_SYMBOL_MODULES = {
    "ConventionResolver": "vibe3.config.convention_resolver",
}


def __getattr__(name: str) -> Any:
    """Lazy import for config symbols to avoid circular dependencies.

    This allows external modules to use:
        from vibe3.config import ConventionResolver

    While avoiding circular imports at module load time.
    """
    if name in _SYMBOL_MODULES:
        import importlib

        module = importlib.import_module(_SYMBOL_MODULES[name])
        symbol = getattr(module, name)
        # Cache in module globals for faster subsequent access
        globals()[name] = symbol
        return symbol

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
