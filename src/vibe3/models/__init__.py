"""Models package."""

from vibe3.models.dead_code import DeadCodeFinding, DeadCodeReport
from vibe3.models.inspection import CallNode, CommandInspection
from vibe3.models.prompt_meta import PromptContextMode
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

__all__: list[str] = [
    "CallNode",
    "CommandInspection",
    "DeadCodeFinding",
    "DeadCodeReport",
    "DependencyChange",
    "DependencyEdge",
    "DiffSummary",
    "DiffWarning",
    "ExecutionStep",
    "FileChange",
    "FileSnapshot",
    "FunctionSnapshot",
    "ModuleChange",
    "ModuleSnapshot",
    "PromptContextMode",
    "StructureDiff",
    "StructureMetrics",
    "StructureSnapshot",
    "TraceOutput",
]
