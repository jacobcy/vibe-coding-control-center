"""Vibe3 services layer.

This package provides the service layer for the Vibe3 system, with subpackages for
each domain (check, flow, handoff, issue, orchestra, pr, task, shared).

Public API Contract:
- Root barrel exports service classes and frequently-used functions for convenience
- Direct imports from submodules are preferred for internal use
- The __all__ list represents the approved public API surface
- Dead exports are actively removed to keep the API contract explicit

Architecture Tests:
- test_root_barrel_import_count: Tracks usage of root barrel imports
- test_pure_bridge_module_count: Tracks pure bridge modules (baseline=0)
- test_layer_crossing_bridge_count: Tracks layer-crossing bridges (baseline=0)
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.config import (
        get_handoff_state_label,
        get_manager_usernames,
    )
    from vibe3.services.check.remote import InitResult
    from vibe3.services.check.service import CheckResult, CheckService
    from vibe3.services.flow.blocked_state_service import BlockedStateService
    from vibe3.services.flow.classifier import (
        FlowCategory,
        FlowState,
        classify_flow,
        get_flow_state,
    )
    from vibe3.services.flow.cleanup import FlowCleanupService
    from vibe3.services.flow.event_projection import build_event_projection_hook
    from vibe3.services.flow.factory import create_flow_manager
    from vibe3.services.flow.projection import (
        FlowProjection,
        FlowProjectionService,
    )
    from vibe3.services.flow.rebuild import FlowRebuildUsecase
    from vibe3.services.flow.recovery import FlowRecoveryService
    from vibe3.services.flow.resume_resolver import infer_resume_label
    from vibe3.services.flow.service import FlowService
    from vibe3.services.flow.status import FlowStatusService
    from vibe3.services.flow.status_resolver import FlowStatusResolver
    from vibe3.services.flow.timeline import FlowTimelineService
    from vibe3.services.handoff.resolution import resolve_handoff_target
    from vibe3.services.handoff.service import HandoffService
    from vibe3.services.handoff.status import HandoffStatusService
    from vibe3.services.issue.collection import IssueCollectionService
    from vibe3.services.issue.context import load_issue_info
    from vibe3.services.issue.failure import (
        block_manager_noop_issue,
        fail_executor_issue,
        fail_issue,
        fail_manager_issue,
        fail_planner_issue,
        fail_reviewer_issue,
    )
    from vibe3.services.issue.flow import IssueFlowService
    from vibe3.services.issue.title_cache import IssueTitleCacheService
    from vibe3.services.orchestra.coordination import CoordinationResolver
    from vibe3.services.orchestra.error_tracking import ErrorTrackingService
    from vibe3.services.orchestra.orchestrator import FlowOrchestratorService
    from vibe3.services.orchestra.serve_status import (
        ServeStatusService,
        fetch_serve_status_data,
    )
    from vibe3.services.orchestra.status import (
        IssueStatusEntry,
        OrchestraSnapshot,
        OrchestraStatusService,
        format_issue_runtime_line,
        format_issue_summary_line,
        is_running_issue,
    )
    from vibe3.services.pr.analysis import (
        analyze_critical_files,
        build_pr_analysis,
        calculate_pr_risk_score,
        filter_critical_files,
        get_pr_changed_files,
        get_pr_commit_count,
        get_recent_commits,
    )
    from vibe3.services.pr.base_resolution import BaseResolutionUsecase
    from vibe3.services.pr.create import PRCreateUsecase
    from vibe3.services.pr.ready import PrReadyAbortedError, PrReadyUsecase
    from vibe3.services.pr.resolver import (
        resolve_command_branch,
    )
    from vibe3.services.pr.service import PRService
    from vibe3.services.pr.verdict_service import VerdictService
    from vibe3.services.shared.actors import format_agent_actor
    from vibe3.services.shared.binding_guard import (
        MissingTaskIssueError,
        build_bind_task_hint,
    )
    from vibe3.services.shared.branch_resolver import resolve_issue_branch_input
    from vibe3.services.shared.branches import (
        resolve_branch_and_issue,
        resolve_branch_arg,
    )
    from vibe3.services.shared.errors import (
        has_recent_specific_error,
        log_dispatch_error,
        record_dispatch_failure_if_unexpected,
        record_error,
    )

    # Functions used in domain/execution/roles
    from vibe3.services.shared.events import emit_issue_failed
    from vibe3.services.shared.file_loader import (
        material_loader,
        policy_loader,
    )
    from vibe3.services.shared.label_service import LabelService
    from vibe3.services.shared.labels import (
        ORCHESTRA_GOVERNED_LABEL,
        clean_old_state_labels,
        has_orchestra_governed,
        has_roadmap_label,
        normalize_assignees,
        normalize_labels,
        should_skip_from_queue,
    )
    from vibe3.services.shared.paths import (
        check_ref_exists,
        ref_to_handoff_cmd,
        resolve_ref_path,
        sanitize_event_detail_paths,
    )
    from vibe3.services.shared.roles import get_role_block_function
    from vibe3.services.shared.signatures import SignatureService
    from vibe3.services.shared.spec_ref import SpecRefService
    from vibe3.services.shared.status_query import (
        StatusQueryService,
        is_auto_task_branch,
        is_dev_collab_branch,
    )
    from vibe3.services.task.classifier import TaskStatusBucket
    from vibe3.services.task.resume import (
        TaskResumeOperations,
        TaskResumeUsecase,
    )
    from vibe3.services.task.service import TaskService
    from vibe3.services.task.show import TaskShowResult
    from vibe3.services.task.status import (
        build_api_task_data,
        classify_task_issues_for_rendering,
        fetch_task_status_data,
    )

__all__ = [
    "BaseResolutionUsecase",
    "BlockedStateService",
    "CheckCleanupService",
    "CheckResult",
    "CheckService",
    "CoordinationResolver",
    "ErrorTrackingService",
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
    "FlowStatusService",
    "FlowTimelineService",
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
    "ORCHESTRA_GOVERNED_LABEL",
    "PRCreateUsecase",
    "PRService",
    "material_loader",
    "policy_loader",
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
    "build_api_task_data",
    "build_bind_task_hint",
    "build_event_projection_hook",
    "build_pr_analysis",
    "calculate_pr_risk_score",
    "check_ref_exists",
    "clean_old_state_labels",
    "classify_flow",
    "classify_task_issues_for_rendering",
    "create_flow_manager",
    "emit_issue_failed",
    "fail_executor_issue",
    "fail_issue",
    "fail_manager_issue",
    "fail_planner_issue",
    "fail_reviewer_issue",
    "fetch_serve_status_data",
    "fetch_task_status_data",
    "filter_critical_files",
    "format_agent_actor",
    "format_issue_runtime_line",
    "format_issue_summary_line",
    "has_merged_pr_for_issue",
    "get_flow_state",
    "get_handoff_state_label",
    "get_manager_usernames",
    "get_pr_changed_files",
    "get_pr_commit_count",
    "get_recent_commits",
    "get_role_block_function",
    "has_recent_specific_error",
    "has_orchestra_governed",
    "has_roadmap_label",
    "infer_resume_label",
    "is_auto_task_branch",
    "is_dev_collab_branch",
    "is_running_issue",
    "load_issue_info",
    "log_dispatch_error",
    "normalize_assignees",
    "normalize_labels",
    "record_dispatch_failure_if_unexpected",
    "record_error",
    "ref_to_handoff_cmd",
    "resolve_branch_and_issue",
    "resolve_branch_arg",
    "resolve_command_branch",
    "resolve_handoff_target",
    "resolve_issue_branch_input",
    "resolve_ref_path",
    "sanitize_event_detail_paths",
    "should_skip_from_queue",
]

# Lazy import mapping for symbols not directly imported above
_SYMBOL_MODULES = {
    # Services
    "BaseResolutionUsecase": "vibe3.services.pr.base_resolution",
    "BlockedStateService": "vibe3.services.flow.blocked_state_service",
    "CheckCleanupService": "vibe3.services.check.cleanup",
    "CheckResult": "vibe3.services.check.service",
    "CheckService": "vibe3.services.check.service",
    "CoordinationResolver": "vibe3.services.orchestra.coordination",
    "ErrorTrackingService": "vibe3.services.orchestra.error_tracking.service",
    "FlowCategory": "vibe3.services.flow.classifier",
    "FlowCleanupService": "vibe3.services.flow.cleanup",
    "FlowOrchestratorService": "vibe3.services.orchestra.orchestrator",
    "FlowProjection": "vibe3.services.flow.projection",
    "FlowProjectionService": "vibe3.services.flow.projection",
    "FlowRebuildUsecase": "vibe3.services.flow.rebuild",
    "FlowRecoveryService": "vibe3.services.flow.recovery",
    "FlowService": "vibe3.services.flow.service",
    "FlowState": "vibe3.services.flow.classifier",
    "FlowStatusResolver": "vibe3.services.flow.status_resolver",
    "FlowStatusService": "vibe3.services.flow.status",
    "FlowTimelineService": "vibe3.services.flow.timeline",
    "HandoffService": "vibe3.services.handoff.service",
    "HandoffStatusService": "vibe3.services.handoff.status",
    "InitResult": "vibe3.services.check.remote",
    "IssueCollectionService": "vibe3.services.issue.collection",
    "IssueFlowService": "vibe3.services.issue.flow",
    "IssueStatusEntry": "vibe3.services.orchestra.status",
    "IssueTitleCacheService": "vibe3.services.issue.title_cache",
    "LabelService": "vibe3.services.shared.label_service",
    "material_loader": "vibe3.services.shared.file_loader",
    "MissingTaskIssueError": "vibe3.services.shared.binding_guard",
    "OrchestraSnapshot": "vibe3.services.orchestra.status",
    "OrchestraStatusService": "vibe3.services.orchestra.status",
    "PRCreateUsecase": "vibe3.services.pr.create",
    "PRService": "vibe3.services.pr.service",
    "policy_loader": "vibe3.services.shared.file_loader",
    "PrReadyAbortedError": "vibe3.services.pr.ready",
    "PrReadyUsecase": "vibe3.services.pr.ready",
    "ServeStatusService": "vibe3.services.orchestra.serve_status",
    "SignatureService": "vibe3.services.shared.signatures",
    "SpecRefService": "vibe3.services.shared.spec_ref",
    "StatusQueryService": "vibe3.services.shared.status_query",
    "TaskResumeOperations": "vibe3.services.task.resume",
    "TaskResumeUsecase": "vibe3.services.task.resume",
    "TaskService": "vibe3.services.task.service",
    "TaskShowResult": "vibe3.services.task.show",
    "TaskStatusBucket": "vibe3.services.task.classifier",
    "VerdictService": "vibe3.services.pr.verdict_service",
    # Functions
    "analyze_critical_files": "vibe3.services.pr.analysis",
    "block_manager_noop_issue": "vibe3.services.issue.failure",
    "build_api_task_data": "vibe3.services.task.status",
    "build_bind_task_hint": "vibe3.services.shared.binding_guard",
    "build_event_projection_hook": "vibe3.services.flow.event_projection",
    "build_pr_analysis": "vibe3.services.pr.analysis",
    "calculate_pr_risk_score": "vibe3.services.pr.analysis",
    "check_ref_exists": "vibe3.services.shared.paths",
    "classify_flow": "vibe3.services.flow.classifier",
    "classify_task_issues_for_rendering": "vibe3.services.task.status",
    "create_flow_manager": "vibe3.services.flow.factory",
    "emit_issue_failed": "vibe3.services.shared.events",
    "fail_executor_issue": "vibe3.services.issue.failure",
    "fail_issue": "vibe3.services.issue.failure",
    "fail_manager_issue": "vibe3.services.issue.failure",
    "fail_planner_issue": "vibe3.services.issue.failure",
    "fail_reviewer_issue": "vibe3.services.issue.failure",
    "fetch_serve_status_data": "vibe3.services.orchestra.serve_status",
    "fetch_task_status_data": "vibe3.services.task.status",
    "filter_critical_files": "vibe3.services.pr.analysis",
    "format_agent_actor": "vibe3.services.shared.actors",
    "has_merged_pr_for_issue": "vibe3.services.pr.status_checker",
    "format_issue_runtime_line": "vibe3.services.orchestra.status",
    "format_issue_summary_line": "vibe3.services.orchestra.status",
    "get_flow_state": "vibe3.services.flow.classifier",
    "get_handoff_state_label": "vibe3.config",
    "get_manager_usernames": "vibe3.config",
    "get_pr_changed_files": "vibe3.services.pr.analysis",
    "get_pr_commit_count": "vibe3.services.pr.analysis",
    "get_recent_commits": "vibe3.services.pr.analysis",
    "get_role_block_function": "vibe3.services.shared.roles",
    "has_recent_specific_error": "vibe3.services.shared.errors",
    "has_orchestra_governed": "vibe3.services.shared.labels",
    "has_roadmap_label": "vibe3.services.shared.labels",
    "infer_resume_label": "vibe3.services.flow.resume_resolver",
    "is_auto_task_branch": "vibe3.services.shared.status_query",
    "is_dev_collab_branch": "vibe3.services.shared.status_query",
    "is_running_issue": "vibe3.services.orchestra.status",
    "load_issue_info": "vibe3.services.issue.context",
    "log_dispatch_error": "vibe3.services.shared.errors",
    "normalize_assignees": "vibe3.services.shared.labels",
    "normalize_labels": "vibe3.services.shared.labels",
    "record_dispatch_failure_if_unexpected": "vibe3.services.shared.errors",
    "record_error": "vibe3.services.shared.errors",
    "ref_to_handoff_cmd": "vibe3.services.shared.paths",
    "resolve_branch_and_issue": "vibe3.services.shared.branches",
    "resolve_branch_arg": "vibe3.services.shared.branches",
    "resolve_command_branch": "vibe3.services.pr.resolver",
    "resolve_handoff_target": "vibe3.services.handoff.resolution",
    "resolve_issue_branch_input": "vibe3.services.shared.branch_resolver",
    "resolve_ref_path": "vibe3.services.shared.paths",
    "sanitize_event_detail_paths": "vibe3.services.shared.paths",
    "clean_old_state_labels": "vibe3.services.shared.labels",
    "should_skip_from_queue": "vibe3.services.shared.labels",
    "ORCHESTRA_GOVERNED_LABEL": "vibe3.services.shared.labels",
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
