"""Models package."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.models.branch_convention import BranchConvention
    from vibe3.models.change_source import (
        BranchSource,
        ChangeSource,
        ChangeSourceType,
        CommitSource,
        PRSource,
        UncommittedSource,
    )
    from vibe3.models.coordination_truth import CoordinationTruth
    from vibe3.models.coverage import CoverageReport, LayerCoverage
    from vibe3.models.data_source import DataSource
    from vibe3.models.dead_code import DeadCodeFinding, DeadCodeReport
    from vibe3.models.domain_events import (
        DomainEvent,
        ExecutorDispatchIntent,
        IssueFailed,
        ManagerDispatchIntent,
        PlannerDispatchIntent,
        ReviewerDispatchIntent,
        SupervisorIssueIdentified,
    )
    from vibe3.models.execution_handle import AsyncExecutionHandle
    from vibe3.models.execution_request import ExecutionLaunchResult, ExecutionRequest
    from vibe3.models.flow import (
        FlowEvent,
        FlowState,
        FlowStatusResponse,
        IssueLink,
        MainBranchProtectedError,
        TimelineEvent,
    )
    from vibe3.models.inspection import CallNode, CommandInspection
    from vibe3.models.issue_body import FlowStateProjection
    from vibe3.models.orchestra_config import OrchestraConfig, SupervisorHandoffConfig
    from vibe3.models.orchestration import (
        ALLOWED_TRANSITIONS,
        FORBIDDEN_TRANSITIONS,
        IssueInfo,
        IssueState,
        StateTransition,
    )
    from vibe3.models.plan import PlanRequest, PlanScope, PlanSpecInput
    from vibe3.models.pr import (
        CICheck,
        CreatePRRequest,
        PRMetadata,
        PRResponse,
        PRState,
        UpdatePRRequest,
        VersionBumpResponse,
        VersionBumpType,
    )
    from vibe3.models.pr_analysis import (
        CommitInfo,
        CriticalFileInfo,
        PRCriticalAnalysis,
    )
    from vibe3.models.prompt_meta import PromptContextMode
    from vibe3.models.queue_entry import QueueEntry
    from vibe3.models.review import ReviewRequest, ReviewScope
    from vibe3.models.review_runner import AgentOptions, AgentResult
    from vibe3.models.session_types import SessionRole
    from vibe3.models.snapshot import (
        DependencyChange,
        DependencyEdge,
        DiffSummary,
        DiffWarning,
        FileChange,
        FileSnapshot,
        FunctionSnapshot,
        ModuleChange,
        ModuleSnapshot,
        StructureDiff,
        StructureMetrics,
        StructureSnapshot,
    )
    from vibe3.models.state_machine import (
        STATE_LABEL_META,
        VIBE_TASK_LABEL,
        can_transition,
        validate_transition,
    )
    from vibe3.models.trace import ExecutionStep, TraceOutput
    from vibe3.models.verdict import VerdictRecord
    from vibe3.models.verdict_types import VerdictValue
    from vibe3.models.worktree import WorktreeRequirement

# Lazy imports
_LAZY_IMPORTS = {
    "DomainEvent": "vibe3.models.domain_events",
    "ExecutorDispatchIntent": "vibe3.models.domain_events",
    "IssueFailed": "vibe3.models.domain_events",
    "ManagerDispatchIntent": "vibe3.models.domain_events",
    "PlannerDispatchIntent": "vibe3.models.domain_events",
    "ReviewerDispatchIntent": "vibe3.models.domain_events",
    "SupervisorIssueIdentified": "vibe3.models.domain_events",
    "STATE_LABEL_META": "vibe3.models.state_machine",
    "VIBE_TASK_LABEL": "vibe3.models.state_machine",
    "can_transition": "vibe3.models.state_machine",
    "validate_transition": "vibe3.models.state_machine",
    "ALLOWED_TRANSITIONS": "vibe3.models.orchestration",
    "BranchConvention": "vibe3.models.branch_convention",
    "BranchSource": "vibe3.models.change_source",
    "CommitInfo": "vibe3.models.pr_analysis",
    "CoordinationTruth": "vibe3.models.coordination_truth",
    "CreatePRRequest": "vibe3.models.pr",
    "CriticalFileInfo": "vibe3.models.pr_analysis",
    "DataSource": "vibe3.models.data_source",
    "ChangeSource": "vibe3.models.change_source",
    "ChangeSourceType": "vibe3.models.change_source",
    "CICheck": "vibe3.models.pr",
    "CommitSource": "vibe3.models.change_source",
    "FORBIDDEN_TRANSITIONS": "vibe3.models.orchestration",
    "PRSource": "vibe3.models.change_source",
    "UncommittedSource": "vibe3.models.change_source",
    "CoverageReport": "vibe3.models.coverage",
    "LayerCoverage": "vibe3.models.coverage",
    "DeadCodeFinding": "vibe3.models.dead_code",
    "DeadCodeReport": "vibe3.models.dead_code",
    "AsyncExecutionHandle": "vibe3.models.execution_handle",
    "ExecutionLaunchResult": "vibe3.models.execution_request",
    "ExecutionRequest": "vibe3.models.execution_request",
    "CallNode": "vibe3.models.inspection",
    "CommandInspection": "vibe3.models.inspection",
    "OrchestraConfig": "vibe3.models.orchestra_config",
    "SupervisorHandoffConfig": "vibe3.models.orchestra_config",
    "FlowEvent": "vibe3.models.flow",
    "FlowState": "vibe3.models.flow",
    "FlowStateProjection": "vibe3.models.issue_body",
    "FlowStatusResponse": "vibe3.models.flow",
    "IssueInfo": "vibe3.models.orchestration",
    "IssueLink": "vibe3.models.flow",
    "IssueState": "vibe3.models.orchestration",
    "MainBranchProtectedError": "vibe3.models.flow",
    "PRCriticalAnalysis": "vibe3.models.pr_analysis",
    "PRMetadata": "vibe3.models.pr",
    "PRResponse": "vibe3.models.pr",
    "PRState": "vibe3.models.pr",
    "PlanRequest": "vibe3.models.plan",
    "PlanScope": "vibe3.models.plan",
    "PlanSpecInput": "vibe3.models.plan",
    "PromptContextMode": "vibe3.models.prompt_meta",
    "QueueEntry": "vibe3.models.queue_entry",
    "ReviewRequest": "vibe3.models.review",
    "ReviewScope": "vibe3.models.review",
    "AgentOptions": "vibe3.models.review_runner",
    "AgentResult": "vibe3.models.review_runner",
    "SessionRole": "vibe3.models.session_types",
    "DependencyChange": "vibe3.models.snapshot",
    "DependencyEdge": "vibe3.models.snapshot",
    "DiffSummary": "vibe3.models.snapshot",
    "DiffWarning": "vibe3.models.snapshot",
    "FileChange": "vibe3.models.snapshot",
    "FileSnapshot": "vibe3.models.snapshot",
    "FunctionSnapshot": "vibe3.models.snapshot",
    "ModuleChange": "vibe3.models.snapshot",
    "ModuleSnapshot": "vibe3.models.snapshot",
    "StructureDiff": "vibe3.models.snapshot",
    "StructureMetrics": "vibe3.models.snapshot",
    "StructureSnapshot": "vibe3.models.snapshot",
    "ExecutionStep": "vibe3.models.trace",
    "TraceOutput": "vibe3.models.trace",
    "UpdatePRRequest": "vibe3.models.pr",
    "StateTransition": "vibe3.models.orchestration",
    "TimelineEvent": "vibe3.models.flow",
    "VerdictRecord": "vibe3.models.verdict",
    "VerdictValue": "vibe3.models.verdict_types",
    "VersionBumpResponse": "vibe3.models.pr",
    "VersionBumpType": "vibe3.models.pr",
    "WorktreeRequirement": "vibe3.models.worktree",
}


def __getattr__(name: str) -> object:
    """Lazy import for models symbols to avoid circular dependencies."""
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__: list[str] = [
    "AgentOptions",
    "AgentResult",
    "ALLOWED_TRANSITIONS",
    "AsyncExecutionHandle",
    "BranchConvention",
    "BranchSource",
    "CallNode",
    "ChangeSource",
    "ChangeSourceType",
    "CICheck",
    "CommandInspection",
    "CommitInfo",
    "CommitSource",
    "CoordinationTruth",
    "CoverageReport",
    "CreatePRRequest",
    "CriticalFileInfo",
    "DataSource",
    "DeadCodeFinding",
    "DeadCodeReport",
    "DependencyChange",
    "DomainEvent",
    "DependencyEdge",
    "DiffSummary",
    "DiffWarning",
    "ExecutionLaunchResult",
    "ExecutionRequest",
    "ExecutionStep",
    "ExecutorDispatchIntent",
    "FileChange",
    "FileSnapshot",
    "FlowEvent",
    "FlowState",
    "FlowStateProjection",
    "FlowStatusResponse",
    "FORBIDDEN_TRANSITIONS",
    "FunctionSnapshot",
    "IssueFailed",
    "IssueInfo",
    "IssueLink",
    "IssueState",
    "LayerCoverage",
    "MainBranchProtectedError",
    "ManagerDispatchIntent",
    "ModuleChange",
    "ModuleSnapshot",
    "OrchestraConfig",
    "PRCriticalAnalysis",
    "PRMetadata",
    "PRResponse",
    "PlannerDispatchIntent",
    "PlanRequest",
    "PlanScope",
    "PlanSpecInput",
    "PRSource",
    "PRState",
    "PromptContextMode",
    "QueueEntry",
    "ReviewerDispatchIntent",
    "ReviewRequest",
    "ReviewScope",
    "SessionRole",
    "STATE_LABEL_META",
    "StateTransition",
    "StructureDiff",
    "StructureMetrics",
    "StructureSnapshot",
    "SupervisorHandoffConfig",
    "SupervisorIssueIdentified",
    "TimelineEvent",
    "TraceOutput",
    "UncommittedSource",
    "VIBE_TASK_LABEL",
    "UpdatePRRequest",
    "VerdictRecord",
    "VerdictValue",
    "VersionBumpResponse",
    "VersionBumpType",
    "WorktreeRequirement",
    "can_transition",
    "validate_transition",
]
