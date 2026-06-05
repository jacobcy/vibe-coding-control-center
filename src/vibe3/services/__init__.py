"""Vibe3 services layer."""

from typing import Any

# Direct imports for bootstrap symbols (no circular dep risk)
from vibe3.services.bootstrap_context_service import (
    BootstrapAction,
    BootstrapActionKind,
    BootstrapContextService,
    BootstrapPlan,
)

__all__ = [
    # Bootstrap symbols (direct import)
    "BootstrapAction",
    "BootstrapActionKind",
    "BootstrapContextService",
    "BootstrapPlan",
    # Services (lazy import)
    "BaseResolutionUsecase",
    "CheckResult",
    "CheckService",
    "ConventionResolver",
    "CoordinationResolver",
    "ErrorTrackingService",
    "FlowOrchestratorService",
    "FlowProjectionService",
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
    "TaskResumeUsecase",
    "TaskService",
    "TaskStatusBucket",
    "VerdictService",
    # Functions (lazy import)
    "block_manager_noop_issue",
    "build_bind_task_hint",
    "build_pr_analysis",
    "check_ref_exists",
    "fail_executor_issue",
    "fail_manager_issue",
    "fail_planner_issue",
    "fail_reviewer_issue",
    "format_agent_actor",
    "extract_role_from_actor",
    "resolve_actor_backend_model",
    "get_handoff_state_label",
    "get_manager_usernames",
    "get_role_block_function",
    "has_manager_assignee",
    "infer_resume_label",
    "is_auto_task_branch",
    "load_issue_info",
    "normalize_assignees",
    "normalize_labels",
    "record_dispatch_failure_if_unexpected",
    "ref_to_handoff_cmd",
    "requires_audit_ref",
    "resolve_branch_arg",
    "resolve_branch_from_pr",
    "resolve_command_branch",
    "resolve_handoff_target",
    "resolve_issue_branch_input",
    "sanitize_event_detail_paths",
    "should_skip_from_queue",
    "clean_old_state_labels",
    # Verdict utilities
    "ALL_VERDICTS",
    "PASSING_VERDICTS",
    "AUDIT_REQUIRED_VERDICTS",
    "MERGE_BLOCKING_VERDICTS",
    "passes_review",
    "blocks_merge",
    # Timeline utilities
    "parse_timeline_from_comments",
]

# Lazy import mapping for symbols not directly imported above
_SYMBOL_MODULES = {
    # Services
    "BaseResolutionUsecase": "vibe3.services.base_resolution_usecase",
    "CheckResult": "vibe3.services.check_service",
    "CheckService": "vibe3.services.check_service",
    "ConventionResolver": "vibe3.config.convention_resolver",
    "CoordinationResolver": "vibe3.services.coordination_resolver",
    "ErrorTrackingService": "vibe3.services.error_tracking_service",
    "FlowOrchestratorService": "vibe3.services.flow_orchestrator_service",
    "FlowProjectionService": "vibe3.services.flow_projection_service",
    "FlowService": "vibe3.services.flow_service",
    "HandoffService": "vibe3.services.handoff_service",
    "HandoffStatusService": "vibe3.services.handoff_status_service",
    "InitResult": "vibe3.services.check_remote",
    "IssueCollectionService": "vibe3.services.issue_collection_service",
    "IssueFlowService": "vibe3.services.issue_flow_service",
    "LabelService": "vibe3.services.shared.labels",
    "MissingTaskIssueError": "vibe3.services.task_binding_guard",
    "OrchestraStatusService": "vibe3.services.orchestra_status_service",
    "PRCreateUsecase": "vibe3.services.pr_create_usecase",
    "PRService": "vibe3.services.pr_service",
    "PrReadyAbortedError": "vibe3.services.pr_ready_usecase",
    "PrReadyUsecase": "vibe3.services.pr_ready_usecase",
    "StatusQueryService": "vibe3.services.status_query_service",
    "TaskResumeUsecase": "vibe3.services.task_resume_usecase",
    "TaskService": "vibe3.services.task_service",
    "TaskStatusBucket": "vibe3.services.task_status_classifier",
    "VerdictService": "vibe3.services.verdict_service",
    # Functions
    "block_manager_noop_issue": "vibe3.services.issue_failure_service",
    "build_bind_task_hint": "vibe3.services.task_binding_guard",
    "build_pr_analysis": "vibe3.services.pr_analysis_service",
    "check_ref_exists": "vibe3.services.shared.paths",
    "fail_executor_issue": "vibe3.services.issue_failure_service",
    "fail_manager_issue": "vibe3.services.issue_failure_service",
    "fail_planner_issue": "vibe3.services.issue_failure_service",
    "fail_reviewer_issue": "vibe3.services.issue_failure_service",
    "format_agent_actor": "vibe3.services.shared.actors",
    "extract_role_from_actor": "vibe3.services.shared.actors",
    "resolve_actor_backend_model": "vibe3.services.shared.actors",
    "get_handoff_state_label": "vibe3.services.shared.orchestra",
    "get_manager_usernames": "vibe3.services.shared.orchestra",
    "get_role_block_function": "vibe3.services.role_policy_helpers",
    "infer_resume_label": "vibe3.services.flow_resume_resolver",
    "is_auto_task_branch": "vibe3.services.status_query_service",
    "load_issue_info": "vibe3.services.issue_context_loader",
    "normalize_assignees": "vibe3.services.shared.labels",
    "normalize_labels": "vibe3.services.shared.labels",
    "has_manager_assignee": "vibe3.services.shared.labels",
    "record_dispatch_failure_if_unexpected": "vibe3.services.shared.errors",
    "ref_to_handoff_cmd": "vibe3.services.shared.paths",
    "requires_audit_ref": "vibe3.services.shared.verdicts",
    "resolve_branch_arg": "vibe3.services.branch_arg",
    "resolve_branch_from_pr": "vibe3.services.pr_branch_resolver",
    "resolve_command_branch": "vibe3.services.pr_branch_resolver",
    "resolve_handoff_target": "vibe3.services.handoff_resolution",
    "resolve_issue_branch_input": "vibe3.services.issue_branch_resolver",
    "sanitize_event_detail_paths": "vibe3.services.shared.paths",
    "should_skip_from_queue": "vibe3.services.shared.labels",
    "clean_old_state_labels": "vibe3.services.shared.labels",
    # Verdict utilities
    "ALL_VERDICTS": "vibe3.services.shared.verdicts",
    "PASSING_VERDICTS": "vibe3.services.shared.verdicts",
    "AUDIT_REQUIRED_VERDICTS": "vibe3.services.shared.verdicts",
    "MERGE_BLOCKING_VERDICTS": "vibe3.services.shared.verdicts",
    "passes_review": "vibe3.services.shared.verdicts",
    "blocks_merge": "vibe3.services.shared.verdicts",
    # Timeline utilities
    "parse_timeline_from_comments": "vibe3.services.shared.timeline",
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
