"""Config package."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.config.agent_preset import (
        find_missing_backend_commands,
        has_agent_env_override,
        read_models_json,
        repo_models_json_path,
        resolve_effective_agent_options,
        resolve_repo_agent_preset,
        resolve_repo_agent_preset_name,
    )
    from vibe3.config.cli_overrides import (
        ROLE_CONFIG_SECTIONS,
        RoleCliOverrides,
        build_role_cli_overrides,
    )
    from vibe3.config.config_loader import load_config_for_role
    from vibe3.config.convention_resolver import (
        ConventionResolver,
        diagnose_profile,
        get_convention,
        get_resolver,
    )
    from vibe3.config.env_override import OVERRIDE_RULES
    from vibe3.config.loader import (
        get_config,
        get_config_with_env_override,
        load_config,
        load_runtime_config,
    )
    from vibe3.config.manager_config import (
        get_handoff_state_label,
        get_manager_usernames,
    )
    from vibe3.models import OrchestraConfig
    from vibe3.config.orchestra_settings import load_orchestra_config
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
        FlowConfig,
        MergeGateConfig,
        PathsConfig,
        PlanConfig,
        PRScoringConfig,
        ReviewConfig,
        RunConfig,
        VibeConfig,
        get_commands_root,
        get_source_root,
    )
    from vibe3.config.timeline_comment_policy import (
        DEFAULT_COMMENT_POLICY,
        TimelineCommentPolicy,
    )
    
__all__ = [
    "AIConfig",
    "AgentPromptConfig",
    "ConventionResolver",
    "DEFAULT_COMMENT_POLICY",
    "EXECUTOR_GATE_CONFIG",
    "FlowConfig",
    "GOVERNANCE_GATE_CONFIG",
    "MANAGER_GATE_CONFIG",
    "MergeGateConfig",
    "PLANNER_GATE_CONFIG",
    "PlanConfig",
    "PRScoringConfig",
    "REVIEWER_GATE_CONFIG",
    "ROLE_CONFIG_SECTIONS",
    "SUPERVISOR_APPLY_GATE_CONFIG",
    "SUPERVISOR_IDENTIFY_GATE_CONFIG",
    "ReviewConfig",
    "RoleCliOverrides",
    "RoleOutputContract",
    "RunConfig",
    "TimelineCommentPolicy",
    "VibeConfig",
    "OVERRIDE_RULES",
    "OrchestraConfig",
    "PathsConfig",
    "build_role_cli_overrides",
    "diagnose_profile",
    "find_missing_backend_commands",
    "get_commands_root",
    "get_config",
    "get_config_with_env_override",
    "get_convention",
    "get_handoff_state_label",
    "get_manager_usernames",
    "get_resolver",
    "get_role_output_contract",
    "get_role_section",
    "get_source_root",
    "has_agent_env_override",
    "load_config",
    "load_config_for_role",
    "load_orchestra_config",
    "load_runtime_config",
    "read_models_json",
    "repo_models_json_path",
    "resolve_effective_agent_options",
    "resolve_repo_agent_preset",
    "resolve_repo_agent_preset_name",
]

# Lazy import mapping for symbols to avoid circular dependencies
_SYMBOL_MODULES = {
    "AIConfig": "vibe3.config.settings",
    "AgentPromptConfig": "vibe3.config.settings",
    "ConventionResolver": "vibe3.config.convention_resolver",
    "EXECUTOR_GATE_CONFIG": "vibe3.config.role_gates",
    "FlowConfig": "vibe3.config.settings",
    "GOVERNANCE_GATE_CONFIG": "vibe3.config.role_gates",
    "MANAGER_GATE_CONFIG": "vibe3.config.role_gates",
    "MergeGateConfig": "vibe3.config.settings",
    "PLANNER_GATE_CONFIG": "vibe3.config.role_gates",
    "PlanConfig": "vibe3.config.settings",
    "PRScoringConfig": "vibe3.config.settings",
    "REVIEWER_GATE_CONFIG": "vibe3.config.role_gates",
    "ROLE_CONFIG_SECTIONS": "vibe3.config.cli_overrides",
    "SUPERVISOR_APPLY_GATE_CONFIG": "vibe3.config.role_gates",
    "SUPERVISOR_IDENTIFY_GATE_CONFIG": "vibe3.config.role_gates",
    "ReviewConfig": "vibe3.config.settings",
    "RoleCliOverrides": "vibe3.config.cli_overrides",
    "RoleOutputContract": "vibe3.config.role_policy",
    "RunConfig": "vibe3.config.settings",
    "TimelineCommentPolicy": "vibe3.config.timeline_comment_policy",
    "DEFAULT_COMMENT_POLICY": "vibe3.config.timeline_comment_policy",
    "VibeConfig": "vibe3.config.settings",
    "OVERRIDE_RULES": "vibe3.config.env_override",
    "OrchestraConfig": "vibe3.models.orchestra_config",
    "PathsConfig": "vibe3.config.settings",
    "build_role_cli_overrides": "vibe3.config.cli_overrides",
    "diagnose_profile": "vibe3.config.convention_resolver",
    "find_missing_backend_commands": "vibe3.config.agent_preset",
    "get_commands_root": "vibe3.config.settings",
    "get_config": "vibe3.config.loader",
    "get_config_with_env_override": "vibe3.config.loader",
    "get_convention": "vibe3.config.convention_resolver",
    "get_handoff_state_label": "vibe3.config.manager_config",
    "get_manager_usernames": "vibe3.config.manager_config",
    "get_resolver": "vibe3.config.convention_resolver",
    "get_role_output_contract": "vibe3.config.role_policy",
    "get_role_section": "vibe3.config.role_policy",
    "get_source_root": "vibe3.config.settings",
    "has_agent_env_override": "vibe3.config.agent_preset",
    "load_config": "vibe3.config.loader",
    "load_config_for_role": "vibe3.config.config_loader",
    "load_orchestra_config": "vibe3.config.orchestra_settings",
    "load_runtime_config": "vibe3.config.loader",
    "read_models_json": "vibe3.config.agent_preset",
    "repo_models_json_path": "vibe3.config.agent_preset",
    "resolve_effective_agent_options": "vibe3.config.agent_preset",
    "resolve_repo_agent_preset": "vibe3.config.agent_preset",
    "resolve_repo_agent_preset_name": "vibe3.config.agent_preset",
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
