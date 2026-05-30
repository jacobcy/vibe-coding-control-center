"""Vibe3 services layer."""

# Bootstrap services
# External consumption symbols (from AST scan)
# Note: Some imports are deferred to avoid circular dependency
from vibe3.services.base_resolution_usecase import BaseResolutionUsecase
from vibe3.services.blocked_state_service import BlockedStateService
from vibe3.services.bootstrap_context_service import (
    BootstrapAction,
    BootstrapActionKind,
    BootstrapContextService,
    BootstrapPlan,
)
from vibe3.services.branch_arg import resolve_branch_arg
from vibe3.services.branch_resolver import resolve_branch_from_pr
from vibe3.services.check_cleanup_service import CheckCleanupService
from vibe3.services.check_remote import InitResult
from vibe3.services.check_service import CheckResult, CheckService
from vibe3.services.convention_resolver import ConventionResolver
from vibe3.services.coordination_resolver import CoordinationResolver
from vibe3.services.error_helpers import (
    record_dispatch_failure_if_unexpected,
    record_error,
)
from vibe3.services.error_tracking_queries import get_all_errors_status
from vibe3.services.error_tracking_service import ErrorTrackingService
from vibe3.services.expired_resource_cleanup_service import (
    ExpiredResourceCleanupService,
)
from vibe3.services.flow_classifier import (
    FlowCategory,
    FlowState,
    classify_flow,
    get_flow_state,
)
from vibe3.services.flow_cleanup_service import (
    FlowCleanupService,
    LiveSessionsDetectedError,
)
from vibe3.services.flow_orchestrator_service import FlowOrchestratorService
from vibe3.services.flow_projection_service import FlowProjection, FlowProjectionService
from vibe3.services.flow_resume_resolver import infer_resume_label
from vibe3.services.flow_service import FlowService
from vibe3.services.flow_status_resolver import FlowStatusResolver
from vibe3.services.git_path_client import get_worktree_root
from vibe3.services.handoff_resolution import resolve_handoff_target
from vibe3.services.handoff_service import HandoffService
from vibe3.services.handoff_status_service import (
    HandoffStatusResult,
    HandoffStatusService,
)
from vibe3.services.issue_branch_resolver import (
    _format_flow_details,
    resolve_issue_branch_input,
)
from vibe3.services.issue_collection_service import IssueCollectionService
from vibe3.services.issue_context_loader import load_issue_info
from vibe3.services.issue_failure_service import (
    block_manager_noop_issue,
    fail_executor_issue,
    fail_issue,
    fail_manager_issue,
    fail_planner_issue,
    fail_reviewer_issue,
)
from vibe3.services.issue_flow_service import IssueFlowService
from vibe3.services.issue_title_cache_service import IssueTitleCacheService
from vibe3.services.label_service import LabelService
from vibe3.services.label_utils import (
    clean_old_state_labels,
    has_manager_assignee,
    normalize_assignees,
    normalize_labels,
    should_skip_from_queue,
)

# orchestra_helpers imports deferred (causes circular import with utils.comment_utils)
from vibe3.services.orchestra_status_service import (
    IssueStatusEntry,
    OrchestraSnapshot,
    OrchestraStatusService,
    format_issue_runtime_line,
    format_issue_summary_line,
    is_running_issue,
)
from vibe3.services.path_helpers import (
    check_ref_exists,
    ref_to_handoff_cmd,
    resolve_ref_path,
    sanitize_event_detail_paths,
)
from vibe3.services.pr_analysis_service import (
    _analyze_critical_files,
    _calculate_risk_score,
    _filter_critical_files,
    _get_pr_changed_files,
    _get_pr_commit_count,
    _get_recent_commits,
    build_pr_analysis,
)
from vibe3.services.pr_branch_resolver import resolve_command_branch
from vibe3.services.pr_create_usecase import PRCreateUsecase
from vibe3.services.pr_ready_usecase import PrReadyAbortedError, PrReadyUsecase
from vibe3.services.pr_scoring_service import PRDimensions, generate_score_report
from vibe3.services.pr_service import PRService
from vibe3.services.role_policy_helpers import get_role_block_function  # noqa: F401
from vibe3.services.scan_service import (
    dispatch_governance_execution,
    dispatch_supervisor_execution,
    fetch_supervisor_candidates,
    get_available_governance_materials,
    governance_material_exists,
    list_governance_materials,
)
from vibe3.services.serve_status_service import ServeStatusService
from vibe3.services.signature_service import SignatureService
from vibe3.services.spec_ref_service import SpecRefService
from vibe3.services.status_query_service import StatusQueryService, is_auto_task_branch
from vibe3.services.task_binding_guard import (
    MissingTaskIssueError,
    build_bind_task_hint,
)
from vibe3.services.task_resume_usecase import TaskResumeUsecase
from vibe3.services.task_service import (
    TaskCommentSummary,
    TaskPRSummary,
    TaskRefSummary,
    TaskService,
    TaskShowResult,
)
from vibe3.services.task_status_classifier import (
    TaskStatusBucket,
    classify_task_status,
)
from vibe3.services.verdict_policy import requires_audit_ref  # noqa: F401
from vibe3.services.verdict_service import VerdictService


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    """Lazy import for symbols that cause circular dependencies."""
    if name == "format_agent_actor":
        from vibe3.services.actor_support import format_agent_actor as _symbol

        return _symbol
    if name == "get_handoff_state_label":
        from vibe3.services.orchestra_helpers import (  # type: ignore[assignment]
            get_handoff_state_label as _symbol,
        )

        return _symbol
    if name == "get_manager_usernames":
        from vibe3.services.orchestra_helpers import (  # type: ignore[assignment]
            get_manager_usernames as _symbol,
        )

        return _symbol
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BaseResolutionUsecase",
    "BootstrapAction",
    "BootstrapActionKind",
    "BootstrapContextService",
    "BootstrapPlan",
    "BlockedStateService",
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
    "FlowService",
    "FlowState",
    "FlowStatusResolver",
    "HandoffService",
    "HandoffStatusResult",
    "HandoffStatusService",
    "InitResult",
    "IssueCollectionService",
    "IssueFlowService",
    "IssueStatusEntry",
    "IssueTitleCacheService",
    "LabelService",
    "LiveSessionsDetectedError",
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
    "TaskCommentSummary",
    "TaskPRSummary",
    "TaskRefSummary",
    "TaskResumeUsecase",
    "TaskService",
    "TaskShowResult",
    "TaskStatusBucket",
    "VerdictService",
    "_analyze_critical_files",
    "_calculate_risk_score",
    "_filter_critical_files",
    "_format_flow_details",
    "_get_pr_changed_files",
    "_get_pr_commit_count",
    "_get_recent_commits",
    "block_manager_noop_issue",
    "build_bind_task_hint",
    "build_pr_analysis",
    "check_ref_exists",
    "classify_flow",
    "classify_task_status",
    "clean_old_state_labels",
    "dispatch_governance_execution",
    "dispatch_supervisor_execution",
    "fail_executor_issue",
    "fail_issue",
    "fail_manager_issue",
    "fail_planner_issue",
    "fail_reviewer_issue",
    "fetch_supervisor_candidates",
    "format_agent_actor",
    "format_issue_runtime_line",
    "format_issue_summary_line",
    "generate_score_report",
    "get_all_errors_status",
    "get_available_governance_materials",
    "get_flow_state",
    "get_handoff_state_label",
    "get_manager_usernames",
    "get_worktree_root",
    "governance_material_exists",
    "has_manager_assignee",
    "infer_resume_label",
    "is_auto_task_branch",
    "is_running_issue",
    "list_governance_materials",
    "load_issue_info",
    "normalize_assignees",
    "normalize_labels",
    "record_dispatch_failure_if_unexpected",
    "record_error",
    "ref_to_handoff_cmd",
    "resolve_branch_arg",
    "resolve_branch_from_pr",
    "resolve_command_branch",
    "resolve_handoff_target",
    "resolve_issue_branch_input",
    "resolve_ref_path",
    "sanitize_event_detail_paths",
    "should_skip_from_queue",
]
