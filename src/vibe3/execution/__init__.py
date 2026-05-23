"""Execution control plane package.

Public interface for the Vibe3 execution layer. All external consumers
should import from ``vibe3.execution`` rather than internal submodules.

Import concrete modules explicitly from ``vibe3.execution.*`` to keep
package boundaries explicit and avoid re-export compatibility layers.

Core classes:
    - :class:`ExecutionCoordinator`: Orchestrates role execution lifecycle,
      worktree allocation, and capacity-aware dispatch.
    - :class:`CapacityService`: Global concurrency limiter based on live
      session count.
    - :class:`CodeagentExecutionService`: Sync execution shell for
      command-mode codeagent runs.
    - :class:`ExecutionLifecycleService`: Records started/completed/failed
      lifecycle events for all roles.

Data contracts:
    - :class:`ExecutionRequest`: Request to launch a role execution.
    - :class:`ExecutionLaunchResult`: Result of an execution launch attempt.

Functions:
    - :func:`execution_prefix`: Return the lifecycle prefix for a role.
    - :func:`persist_execution_lifecycle_event`: Persist lifecycle state
      and timeline events.
    - :func:`run_governance_sync`: Run governance scan synchronously.
    - :func:`run_governance_async`: Run governance scan asynchronously.
"""

from __future__ import annotations

from vibe3.execution.capacity_service import CapacityService
from vibe3.execution.codeagent_runner import CodeagentExecutionService
from vibe3.execution.contracts import ExecutionLaunchResult, ExecutionRequest
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.execution.execution_lifecycle import (
    ExecutionLifecycleEvent,
    ExecutionLifecycleService,
    ExecutionRole,
    execution_prefix,
    persist_execution_lifecycle_event,
)
from vibe3.execution.governance_sync_runner import (
    run_governance_async,
    run_governance_sync,
)

__all__: list[str] = [
    # Core classes
    "ExecutionCoordinator",
    "CapacityService",
    "CodeagentExecutionService",
    "ExecutionLifecycleService",
    # Data contracts
    "ExecutionRequest",
    "ExecutionLaunchResult",
    # Types
    "ExecutionRole",
    "ExecutionLifecycleEvent",
    # Functions
    "execution_prefix",
    "persist_execution_lifecycle_event",
    "run_governance_sync",
    "run_governance_async",
]
