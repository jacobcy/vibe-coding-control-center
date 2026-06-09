"""Execution control plane public interface."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.execution.actor import ActorRegistry, ActorStatus, JobActor, JobType
    from vibe3.execution.capacity_service import CapacityService
    from vibe3.execution.codeagent_runner import CodeagentExecutionService
    from vibe3.execution.codeagent_support import build_self_invocation
    from vibe3.execution.command_adapter import (
        CommandAdapterEntry,
        CommandAdapterError,
        CommandAdapterRegistry,
        ResolvedAdapter,
        build_default_registry,
    )
    from vibe3.execution.coordinator import ExecutionCoordinator
    from vibe3.execution.execution_lifecycle import (
        execution_prefix,
        persist_execution_lifecycle_event,
    )
    from vibe3.execution.execution_role_policy import ExecutionRolePolicyService
    from vibe3.execution.governance_sync_runner import (
        run_governance_async,
        run_governance_sync,
    )
    from vibe3.execution.issue_role_support import (
        build_issue_async_cli_request,
        build_issue_sync_prompt_request,
        build_task_flow_branch_resolver,
        resolve_async_cli_project_root,
        resolve_env_overridable_agent_options,
        resolve_orchestra_repo_root,
        use_current_branch,
    )
    from vibe3.execution.issue_role_sync_runner import (
        run_issue_role_async,
        run_issue_role_sync,
    )
    from vibe3.execution.job_executor import (
        COMMAND_TYPE_TO_EXECUTION_ROLE,
        JobExecutor,
    )
    from vibe3.execution.noop_gate import apply_unified_noop_gate
    from vibe3.execution.prompt_meta import PromptMeta, build_prompt_meta
    from vibe3.execution.role_interfaces import GovernanceFunctions
    from vibe3.execution.role_request_factory import (
        build_role_async_request,
        build_role_sync_request,
    )
    from vibe3.execution.session_service import load_session_id

# Lazy imports for self-references (avoid circular init dependencies)
_LAZY_IMPORTS = {
    "ActorRegistry": "vibe3.execution.actor",
    "ActorStatus": "vibe3.execution.actor",
    "JobActor": "vibe3.execution.actor",
    "JobType": "vibe3.execution.actor",
    "CapacityService": "vibe3.execution.capacity_service",
    "CodeagentExecutionService": "vibe3.execution.codeagent_runner",
    "CommandAdapterEntry": "vibe3.execution.command_adapter",
    "CommandAdapterError": "vibe3.execution.command_adapter",
    "CommandAdapterRegistry": "vibe3.execution.command_adapter",
    "ExecutionCoordinator": "vibe3.execution.coordinator",
    "ResolvedAdapter": "vibe3.execution.command_adapter",
    "build_default_registry": "vibe3.execution.command_adapter",
    "execution_prefix": "vibe3.execution.execution_lifecycle",
    "persist_execution_lifecycle_event": "vibe3.execution.execution_lifecycle",
    "apply_unified_noop_gate": "vibe3.execution.noop_gate",
    "load_session_id": "vibe3.execution.session_service",
    # Role policy
    "ExecutionRolePolicyService": "vibe3.execution.execution_role_policy",
    # Issue role support
    "resolve_orchestra_repo_root": "vibe3.execution.issue_role_support",
    "build_task_flow_branch_resolver": "vibe3.execution.issue_role_support",
    "resolve_env_overridable_agent_options": "vibe3.execution.issue_role_support",
    "build_issue_async_cli_request": "vibe3.execution.issue_role_support",
    "build_issue_sync_prompt_request": "vibe3.execution.issue_role_support",
    "resolve_async_cli_project_root": "vibe3.execution.issue_role_support",
    "use_current_branch": "vibe3.execution.issue_role_support",
    # Codeagent support
    "build_self_invocation": "vibe3.execution.codeagent_support",
    # Prompt metadata
    "build_prompt_meta": "vibe3.execution.prompt_meta",
    "PromptMeta": "vibe3.execution.prompt_meta",
    # Role request factory
    "build_role_async_request": "vibe3.execution.role_request_factory",
    "build_role_sync_request": "vibe3.execution.role_request_factory",
    "GovernanceFunctions": "vibe3.execution.role_interfaces",
    # Sync runners
    "run_governance_sync": "vibe3.execution.governance_sync_runner",
    "run_governance_async": "vibe3.execution.governance_sync_runner",
    "run_issue_role_async": "vibe3.execution.issue_role_sync_runner",
    "run_issue_role_sync": "vibe3.execution.issue_role_sync_runner",
    # Job executor
    "JobExecutor": "vibe3.execution.job_executor",
    "COMMAND_TYPE_TO_EXECUTION_ROLE": "vibe3.execution.job_executor",
}


def __getattr__(name: str) -> object:
    """Lazy import for execution symbols to avoid circular dependencies."""
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Actor supervision
    "ActorRegistry",
    "ActorStatus",
    "JobActor",
    "JobType",
    # Core services
    "ExecutionCoordinator",
    "CodeagentExecutionService",
    "CapacityService",
    # Command adapter registry
    "CommandAdapterRegistry",
    "CommandAdapterEntry",
    "CommandAdapterError",
    "ResolvedAdapter",
    "build_default_registry",
    # Lifecycle utilities
    "execution_prefix",
    "persist_execution_lifecycle_event",
    "load_session_id",
    # Gates
    "apply_unified_noop_gate",
    # Role policy
    "ExecutionRolePolicyService",
    # Issue role support
    "resolve_orchestra_repo_root",
    "build_task_flow_branch_resolver",
    "resolve_env_overridable_agent_options",
    "build_issue_async_cli_request",
    "build_issue_sync_prompt_request",
    "resolve_async_cli_project_root",
    "use_current_branch",
    # Codeagent support
    "build_self_invocation",
    # Prompt metadata
    "build_prompt_meta",
    "PromptMeta",
    # Role request factory
    "build_role_async_request",
    "build_role_sync_request",
    "GovernanceFunctions",
    # Sync runners
    "run_governance_sync",
    "run_governance_async",
    "run_issue_role_async",
    "run_issue_role_sync",
    # Job executor
    "JobExecutor",
    "COMMAND_TYPE_TO_EXECUTION_ROLE",
]
