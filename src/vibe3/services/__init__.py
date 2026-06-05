"""Vibe3 services layer."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.config.convention_resolver import ConventionResolver
    from vibe3.services.actor_support import format_agent_actor
    from vibe3.services.base_resolution_usecase import BaseResolutionUsecase
    from vibe3.services.blocked_state_service import BlockedStateService
    from vibe3.services.bootstrap_context_service import (
        BootstrapAction,
        BootstrapActionKind,
        BootstrapContextService,
        BootstrapPlan,
    )
    from vibe3.services.check_service import CheckResult, CheckService
    from vibe3.services.coordination_resolver import CoordinationResolver

    # Functions used in domain/execution/roles
    from vibe3.services.error_helpers import (
        record_dispatch_failure_if_unexpected,
        record_error,
    )
    from vibe3.services.error_tracking_service import ErrorTrackingService
    from vibe3.services.flow_cleanup_service import FlowCleanupService
    from vibe3.services.flow_orchestrator_service import FlowOrchestratorService
    from vibe3.services.flow_projection_service import FlowProjectionService
    from vibe3.services.flow_rebuild_usecase import FlowRebuildUsecase
    from vibe3.services.flow_resume_resolver import infer_resume_label
    from vibe3.services.flow_service import FlowService
    from vibe3.services.handoff_service import HandoffService
    from vibe3.services.handoff_status_service import HandoffStatusService
    from vibe3.services.issue_collection_service import IssueCollectionService
    from vibe3.services.issue_context_loader import load_issue_info
    from vibe3.services.issue_failure_service import (
        block_manager_noop_issue,
        fail_executor_issue,
        fail_manager_issue,
        fail_planner_issue,
        fail_reviewer_issue,
    )
    from vibe3.services.issue_flow_service import IssueFlowService
    from vibe3.services.label_service import LabelService
    from vibe3.services.label_utils import (
        clean_old_state_labels,
        normalize_assignees,
        normalize_labels,
        should_skip_from_queue,
    )
    from vibe3.services.orchestra_helpers import (
        get_handoff_state_label,
        get_manager_usernames,
    )
    from vibe3.services.orchestra_status_service import OrchestraStatusService
    from vibe3.services.path_helpers import (
        check_ref_exists,
        ref_to_handoff_cmd,
        sanitize_event_detail_paths,
    )
    from vibe3.services.pr_create_usecase import PRCreateUsecase
    from vibe3.services.pr_ready_usecase import PrReadyAbortedError, PrReadyUsecase
    from vibe3.services.pr_service import PRService
    from vibe3.services.role_policy_helpers import get_role_block_function
    from vibe3.services.status_query_service import StatusQueryService
    from vibe3.services.task_binding_guard import build_bind_task_hint
    from vibe3.services.task_resume_operations import TaskResumeOperations
    from vibe3.services.task_resume_usecase import TaskResumeUsecase
    from vibe3.services.task_service import TaskService
    from vibe3.services.task_status_classifier import TaskStatusBucket
    from vibe3.services.verdict_service import VerdictService

__all__ = [
    "BootstrapAction",
    "block_manager_noop_issue",
    "BaseResolutionUsecase",
    "BlockedStateService",
    "BootstrapActionKind",
    "BootstrapContextService",
    "BootstrapPlan",
    "CheckResult",
    "CheckService",
    "ConventionResolver",
    "CoordinationResolver",
    "ErrorTrackingService",
    "FlowCleanupService",
    "FlowOrchestratorService",
    "FlowProjectionService",
    "FlowRebuildUsecase",
    "FlowService",
    "HandoffService",
    "HandoffStatusService",
    "InitResult",
    "IssueCollectionService",
    "IssueFlowService",
    "LabelService",
    "MissingTaskIssueError",
    "OrchestraStatusService",
    "PRCreateUsecase",
    "PRService",
    "PrReadyAbortedError",
    "PrReadyUsecase",
    "StatusQueryService",
    "TaskResumeOperations",
    "TaskResumeUsecase",
    "TaskService",
    "TaskStatusBucket",
    "VerdictService",
    "build_bind_task_hint",
    "build_pr_analysis",
    "check_ref_exists",
    "clean_old_state_labels",
    "fail_executor_issue",
    "fail_manager_issue",
    "fail_planner_issue",
    "fail_reviewer_issue",
    "format_agent_actor",
    "get_handoff_state_label",
    "get_manager_usernames",
    "get_role_block_function",
    "has_recent_specific_error",
    "infer_resume_label",
    "is_auto_task_branch",
    "load_issue_info",
    "normalize_assignees",
    "normalize_labels",
    "record_dispatch_failure_if_unexpected",
    "record_error",
    "ref_to_handoff_cmd",
    "requires_audit_ref",
    "resolve_branch_arg",
    "resolve_branch_from_pr",
    "resolve_command_branch",
    "resolve_handoff_target",
    "resolve_issue_branch_input",
    "sanitize_event_detail_paths",
    "should_skip_from_queue",
]

# Lazy import mapping for symbols not directly imported above
_SYMBOL_MODULES = {
    # Bootstrap symbols
    "BootstrapAction": "vibe3.services.bootstrap_context_service",
    "BootstrapActionKind": "vibe3.services.bootstrap_context_service",
    "BootstrapContextService": "vibe3.services.bootstrap_context_service",
    "BootstrapPlan": "vibe3.services.bootstrap_context_service",
    # Services
    "BaseResolutionUsecase": "vibe3.services.base_resolution_usecase",
    "BlockedStateService": "vibe3.services.blocked_state_service",
    "CheckResult": "vibe3.services.check_service",
    "CheckService": "vibe3.services.check_service",
    "ConventionResolver": "vibe3.config.convention_resolver",
    "CoordinationResolver": "vibe3.services.coordination_resolver",
    "ErrorTrackingService": "vibe3.services.error_tracking_service",
    "FlowCleanupService": "vibe3.services.flow_cleanup_service",
    "FlowOrchestratorService": "vibe3.services.flow_orchestrator_service",
    "FlowProjectionService": "vibe3.services.flow_projection_service",
    "FlowService": "vibe3.services.flow_service",
    "HandoffService": "vibe3.services.handoff_service",
    "HandoffStatusService": "vibe3.services.handoff_status_service",
    "InitResult": "vibe3.services.check_remote",
    "IssueCollectionService": "vibe3.services.issue_collection_service",
    "IssueFlowService": "vibe3.services.issue_flow_service",
    "LabelService": "vibe3.services.label_service",
    "MissingTaskIssueError": "vibe3.services.task_binding_guard",
    "OrchestraStatusService": "vibe3.services.orchestra_status_service",
    "PRCreateUsecase": "vibe3.services.pr_create_usecase",
    "PRService": "vibe3.services.pr_service",
    "PrReadyAbortedError": "vibe3.services.pr_ready_usecase",
    "PrReadyUsecase": "vibe3.services.pr_ready_usecase",
    "StatusQueryService": "vibe3.services.status_query_service",
    "TaskResumeOperations": "vibe3.services.task_resume_operations",
    "TaskResumeUsecase": "vibe3.services.task_resume_usecase",
    "TaskService": "vibe3.services.task_service",
    "TaskStatusBucket": "vibe3.services.task_status_classifier",
    "VerdictService": "vibe3.services.verdict_service",
    # Functions
    "block_manager_noop_issue": "vibe3.services.issue_failure_service",
    "build_bind_task_hint": "vibe3.services.task_binding_guard",
    "build_pr_analysis": "vibe3.services.pr_analysis_service",
    "check_ref_exists": "vibe3.services.path_helpers",
    "fail_executor_issue": "vibe3.services.issue_failure_service",
    "fail_manager_issue": "vibe3.services.issue_failure_service",
    "fail_planner_issue": "vibe3.services.issue_failure_service",
    "fail_reviewer_issue": "vibe3.services.issue_failure_service",
    "format_agent_actor": "vibe3.services.actor_support",
    "get_handoff_state_label": "vibe3.services.orchestra_helpers",
    "get_manager_usernames": "vibe3.services.orchestra_helpers",
    "get_role_block_function": "vibe3.services.role_policy_helpers",
    "has_recent_specific_error": "vibe3.services.error_helpers",
    "infer_resume_label": "vibe3.services.flow_resume_resolver",
    "is_auto_task_branch": "vibe3.services.status_query_service",
    "load_issue_info": "vibe3.services.issue_context_loader",
    "normalize_assignees": "vibe3.services.label_utils",
    "normalize_labels": "vibe3.services.label_utils",
    "record_dispatch_failure_if_unexpected": "vibe3.services.error_helpers",
    "record_error": "vibe3.services.error_helpers",
    "ref_to_handoff_cmd": "vibe3.services.path_helpers",
    "requires_audit_ref": "vibe3.services.verdict_policy",
    "resolve_branch_arg": "vibe3.services.branch_arg",
    "resolve_branch_from_pr": "vibe3.services.pr_branch_resolver",
    "resolve_command_branch": "vibe3.services.pr_branch_resolver",
    "resolve_handoff_target": "vibe3.services.handoff_resolution",
    "resolve_issue_branch_input": "vibe3.services.issue_branch_resolver",
    "sanitize_event_detail_paths": "vibe3.services.path_helpers",
    "clean_old_state_labels": "vibe3.services.label_utils",
    "should_skip_from_queue": "vibe3.services.label_utils",
    "FlowRebuildUsecase": "vibe3.services.flow_rebuild_usecase",
}


def __getattr__(name: str) -> Any:
    """Lazy import for services symbols to avoid circular dependencies.

    This allows external modules to use:
        from vibe3.services import FlowService, CheckService

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
