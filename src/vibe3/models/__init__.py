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
    from vibe3.models.coverage import CoverageReport, LayerCoverage
    from vibe3.models.dead_code import DeadCodeFinding, DeadCodeReport
    from vibe3.models.execution_handle import AsyncExecutionHandle
    from vibe3.models.execution_request import ExecutionLaunchResult, ExecutionRequest
    from vibe3.models.inspection import CallNode, CommandInspection
    from vibe3.models.orchestra_config import OrchestraConfig, SupervisorHandoffConfig
    from vibe3.models.orchestration import IssueInfo, IssueState
    from vibe3.models.plan import PlanRequest
    from vibe3.models.prompt_meta import PromptContextMode
    from vibe3.models.queue_entry import QueueEntry
    from vibe3.models.review import ReviewRequest
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
    from vibe3.models.trace import ExecutionStep, TraceOutput
    from vibe3.models.verdict import VerdictRecord
    from vibe3.models.verdict_types import VerdictValue
    from vibe3.models.worktree import WorktreeRequirement

# Lazy imports
_LAZY_IMPORTS = {
    "BranchConvention": "vibe3.models.branch_convention",
    "BranchSource": "vibe3.models.change_source",
    "ChangeSource": "vibe3.models.change_source",
    "ChangeSourceType": "vibe3.models.change_source",
    "CommitSource": "vibe3.models.change_source",
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
    "IssueInfo": "vibe3.models.orchestration",
    "IssueState": "vibe3.models.orchestration",
    "PlanRequest": "vibe3.models.plan",
    "PromptContextMode": "vibe3.models.prompt_meta",
    "QueueEntry": "vibe3.models.queue_entry",
    "ReviewRequest": "vibe3.models.review",
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
    "VerdictRecord": "vibe3.models.verdict",
    "VerdictValue": "vibe3.models.verdict_types",
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
    "AsyncExecutionHandle",
    "BranchConvention",
    "BranchSource",
    "CallNode",
    "ChangeSource",
    "ChangeSourceType",
    "CommandInspection",
    "CommitSource",
    "CoverageReport",
    "DeadCodeFinding",
    "DeadCodeReport",
    "DependencyChange",
    "DependencyEdge",
    "DiffSummary",
    "DiffWarning",
    "ExecutionLaunchResult",
    "ExecutionRequest",
    "ExecutionStep",
    "FileChange",
    "FileSnapshot",
    "FunctionSnapshot",
    "LayerCoverage",
    "ModuleChange",
    "ModuleSnapshot",
    "IssueInfo",
    "IssueState",
    "OrchestraConfig",
    "PlanRequest",
    "PRSource",
    "PromptContextMode",
    "QueueEntry",
    "ReviewRequest",
    "SessionRole",
    "StructureDiff",
    "StructureMetrics",
    "StructureSnapshot",
    "SupervisorHandoffConfig",
    "TraceOutput",
    "UncommittedSource",
    "VerdictRecord",
    "VerdictValue",
    "WorktreeRequirement",
]
