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
    from vibe3.services.flow_recovery_service import FlowRecoveryService
    from vibe3.services.flow_resume_resolver import infer_resume_label
    from vibe3.services.flow_service import FlowService
    from vibe3.services.handoff_service import HandoffService
    from vibe3.services.handoff_status_service import HandoffStatusService
    from vibe3.services.issue.collection import IssueCollectionService
    from vibe3.services.issue.context import load_issue_info
    from vibe3.services.issue.failure import (
        block_manager_noop_issue,
        fail_executor_issue,
        fail_manager_issue,
        fail_planner_issue,
        fail_reviewer_issue,
    )
    from vibe3.services.issue.flow import IssueFlowService
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
    from vibe3.services.pr.create import PRCreateUsecase
    from vibe3.services.pr.ready import PrReadyAbortedError, PrReadyUsecase
    from vibe3.services.pr.service import PRService
    from vibe3.services.role_policy_helpers import get_role_block_function
    from vibe3.services.status_query_service import StatusQueryService
    from vibe3.services.task_binding_guard import build_bind_task_hint
    from vibe3.services.task_resume_operations import TaskResumeOperations
    from vibe3.services.task_resume_usecase import TaskResumeUsecase
    from vibe3.services.task_service import TaskService
    from vibe3.services.task_status_classifier import TaskStatusBucket
    from vibe3.services.verdict_service import VerdictService

__all__ = [
    "BaseResolutionUsecase",
    "BlockedStateService",
    "BootstrapAction",
    "BootstrapActionKind",
    "BootstrapContextService",
    "BootstrapPlan",
    "CheckCleanupService",
    "CheckResult",
    "CheckService",
    "ConventionResolver",
    "CoordinationResolver",
    "ErrorTrackingService",
    "ExpiredResourceCleanupService",
    "FlowCategory",
    "FlowCleanupService",
    "FlowOrchestratorService",
    "FlowProjection",
    "FlowProjectionService",
    "FlowRebuildUsecase",
    "FlowRecoveryService",
    "FlowService",
    "FlowState",
    "FlowStatusResolver",
    "HandoffService",
    "HandoffStatusService",
    "InitResult",
    "IssueCollectionService",
    "IssueFlowService",
    "IssueStatusEntry",
    "IssueTitleCacheService",
    "LabelService",
    "MissingTaskIssueError",
    "OrchestraSnapshot",
    "OrchestraStatusService",
    "PRCreateUsecase",
    "PRDimensions",
    "PRService",
    "PrReadyAbortedError",
    "PrReadyUsecase",
    "ServeStatusService",
    "SignatureService",
    "SpecRefService",
    "StatusQueryService",
    "TaskResumeOperations",
    "TaskResumeUsecase",
    "TaskService",
    "TaskShowResult",
    "TaskStatusBucket",
    "VerdictService",
    "analyze_critical_files",
    "block_manager_noop_issue",
    "build_bind_task_hint",
    "build_pr_analysis",
    "calculate_pr_risk_score",
    "check_ref_exists",
    "clean_old_state_labels",
    "classify_flow",
    "classify_task_issues_for_rendering",
    "create_flow_manager",
    "emit_issue_failed",
    "fail_executor_issue",
    "fail_manager_issue",
    "fail_planner_issue",
    "fail_reviewer_issue",
    "fetch_task_status_data",
    "filter_critical_files",
    "format_agent_actor",
    "format_issue_runtime_line",
    "format_issue_summary_line",
    "generate_score_report",
    "get_flow_state",
    "get_handoff_state_label",
    "get_manager_usernames",
    "get_pr_changed_files",
    "get_pr_commit_count",
    "get_recent_commits",
    "get_role_block_function",
    "has_recent_specific_error",
    "infer_resume_label",
    "is_auto_task_branch",
    "is_running_issue",
    "load_issue_info",
    "normalize_assignees",
    "normalize_labels",
    "record_dispatch_failure_if_unexpected",
    "record_error",
    "ref_to_handoff_cmd",
    "requires_audit_ref",
    "resolve_branch_and_issue",
    "resolve_branch_arg",
    "resolve_branch_from_pr",
    "resolve_command_branch",
    "resolve_handoff_target",
    "resolve_issue_branch_input",
    "resolve_ref_path",
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
    "CheckCleanupService": "vibe3.services.check_cleanup_service",
    "CheckResult": "vibe3.services.check_service",
    "CheckService": "vibe3.services.check_service",
    "ConventionResolver": "vibe3.config.convention_resolver",
    "CoordinationResolver": "vibe3.services.coordination_resolver",
    "ErrorTrackingService": "vibe3.services.error_tracking_service",
    "ExpiredResourceCleanupService": "vibe3.services.expired_resource_cleanup_service",
    "FlowCategory": "vibe3.services.flow_classifier",
    "FlowCleanupService": "vibe3.services.flow_cleanup_service",
    "FlowOrchestratorService": "vibe3.services.flow_orchestrator_service",
    "FlowProjection": "vibe3.services.flow_projection_service",
    "FlowProjectionService": "vibe3.services.flow_projection_service",
    "FlowRebuildUsecase": "vibe3.services.flow_rebuild_usecase",
    "FlowRecoveryService": "vibe3.services.flow_recovery_service",
    "FlowService": "vibe3.services.flow_service",
    "FlowState": "vibe3.services.flow_classifier",
    "FlowStatusResolver": "vibe3.services.flow_status_resolver",
    "HandoffService": "vibe3.services.handoff_service",
    "HandoffStatusService": "vibe3.services.handoff_status_service",
    "InitResult": "vibe3.services.check_remote",
    "IssueCollectionService": "vibe3.services.issue.collection",
    "IssueFlowService": "vibe3.services.issue.flow",
    "IssueStatusEntry": "vibe3.services.orchestra_status_service",
    "IssueTitleCacheService": "vibe3.services.issue.title_cache",
    "LabelService": "vibe3.services.label_service",
    "MissingTaskIssueError": "vibe3.services.task_binding_guard",
    "OrchestraSnapshot": "vibe3.services.orchestra_status_service",
    "OrchestraStatusService": "vibe3.services.orchestra_status_service",
    "PRCreateUsecase": "vibe3.services.pr.create",
    "PRDimensions": "vibe3.services.pr.scoring",
    "PRService": "vibe3.services.pr.service",
    "PrReadyAbortedError": "vibe3.services.pr.ready",
    "PrReadyUsecase": "vibe3.services.pr.ready",
    "ServeStatusService": "vibe3.services.serve_status_service",
    "SignatureService": "vibe3.services.signature_service",
    "SpecRefService": "vibe3.services.spec_ref_service",
    "StatusQueryService": "vibe3.services.status_query_service",
    "TaskResumeOperations": "vibe3.services.task.resume",
    "TaskResumeUsecase": "vibe3.services.task.resume",
    "TaskService": "vibe3.services.task.service",
    "TaskShowResult": "vibe3.services.task.show",
    "TaskStatusBucket": "vibe3.services.task.classifier",
    "VerdictService": "vibe3.services.verdict_service",
    # Functions
    "analyze_critical_files": "vibe3.services.pr.analysis",
    "block_manager_noop_issue": "vibe3.services.issue.failure",
    "build_bind_task_hint": "vibe3.services.task_binding_guard",
    "build_pr_analysis": "vibe3.services.pr.analysis",
    "calculate_pr_risk_score": "vibe3.services.pr.analysis",
    "check_ref_exists": "vibe3.services.path_helpers",
    "classify_flow": "vibe3.services.flow_classifier",
    "classify_task_issues_for_rendering": "vibe3.services.task.status",
    "create_flow_manager": "vibe3.services.flow_factory",
    "emit_issue_failed": "vibe3.services.event_helpers",
    "fail_executor_issue": "vibe3.services.issue.failure",
    "fail_manager_issue": "vibe3.services.issue.failure",
    "fail_planner_issue": "vibe3.services.issue.failure",
    "fail_reviewer_issue": "vibe3.services.issue.failure",
    "format_agent_actor": "vibe3.services.actor_support",
    "filter_critical_files": "vibe3.services.pr.analysis",
    "fetch_task_status_data": "vibe3.services.task.status",
    "format_issue_runtime_line": "vibe3.services.orchestra_status_service",
    "format_issue_summary_line": "vibe3.services.orchestra_status_service",
    "generate_score_report": "vibe3.services.pr.scoring",
    "get_flow_state": "vibe3.services.flow_classifier",
    "get_handoff_state_label": "vibe3.services.orchestra_helpers",
    "get_manager_usernames": "vibe3.services.orchestra_helpers",
    "get_pr_changed_files": "vibe3.services.pr.analysis",
    "get_pr_commit_count": "vibe3.services.pr.analysis",
    "get_recent_commits": "vibe3.services.pr.analysis",
    "get_role_block_function": "vibe3.services.role_policy_helpers",
    "has_recent_specific_error": "vibe3.services.error_helpers",
    "infer_resume_label": "vibe3.services.flow_resume_resolver",
    "is_auto_task_branch": "vibe3.services.status_query_service",
    "is_running_issue": "vibe3.services.orchestra_status_service",
    "load_issue_info": "vibe3.services.issue.context",
    "normalize_assignees": "vibe3.services.label_utils",
    "normalize_labels": "vibe3.services.label_utils",
    "record_dispatch_failure_if_unexpected": "vibe3.services.error_helpers",
    "record_error": "vibe3.services.error_helpers",
    "ref_to_handoff_cmd": "vibe3.services.path_helpers",
    "requires_audit_ref": "vibe3.services.verdict_policy",
    "resolve_branch_and_issue": "vibe3.services.branch_arg",
    "resolve_branch_arg": "vibe3.services.branch_arg",
    "resolve_branch_from_pr": "vibe3.services.pr.resolver",
    "resolve_command_branch": "vibe3.services.pr.resolver",
    "resolve_handoff_target": "vibe3.services.handoff_resolution",
    "resolve_issue_branch_input": "vibe3.services.issue_branch_resolver",
    "resolve_ref_path": "vibe3.services.path_helpers",
    "sanitize_event_detail_paths": "vibe3.services.path_helpers",
    "clean_old_state_labels": "vibe3.services.label_utils",
    "should_skip_from_queue": "vibe3.services.label_utils",
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
