"""
Job execution contracts for the vibe3 command dispatch system.

This module defines typed models that capture canonical command invocations
without importing business modules (services, commands, agents). These models
represent existing async dispatch paths (ExecutionRequest + *DispatchIntent)
in a unified, serializable contract.

Semantic Equivalence Contract:
    Server-driven (heartbeat/webhook) and manual CLI-driven execution of the
    same CommandType with equivalent issue_number, branch, and refs MUST
    produce semantically equivalent results. They differ only in `source`
    provenance, not in command semantics.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

WorktreeRequirementValue = Literal["none", "permanent", "temporary"]
"""Constrained string matching WorktreeRequirement enum values."""


class CommandType(str, Enum):
    """
    Canonical vibe3 command verbs that the job system dispatches.

    Maps to the six command paths identified in:
    - src/vibe3/execution/role_request_factory.py
    - src/vibe3/domain/handlers/dispatch.py
    """

    PLAN = "plan"
    RUN = "run"
    REVIEW = "review"
    MANAGER = "manager"
    GOVERNANCE_SCAN = "governance-scan"
    SUPERVISOR_APPLY = "supervisor-apply"


JobSource = Literal[
    "heartbeat-tick",  # SupervisorScanService → *DispatchIntent
    "cli-manual",  # vibe3 plan/run/review commands
    "cli-resume",  # vibe3 task resume
    "webhook",  # Future: GitHub webhook
]
"""
Distinguishes trigger provenance without importing event classes.
"""


class JobEnvelope(BaseModel):
    """
    Canonical command invocation.

    Carries everything needed to dispatch without importing business modules.
    Server-driven (heartbeat/webhook) and manual CLI-driven execution of the
    same CommandType with equivalent issue_number, branch, and refs MUST
    produce semantically equivalent results.
    """

    command_type: CommandType
    issue_number: int
    branch: str

    # Source provenance
    source: JobSource
    source_event_type: str | None = None
    # e.g. "PlannerDispatchIntent", "cli-manual"
    actor: str = "orchestra:system"

    # Command adapter path (resolved by #2164 registry)
    adapter_path: str | None = None
    # e.g. "vibe3.execution.role_request_factory.build_plan_async_request"

    # Payload
    refs: dict[str, str] = Field(default_factory=dict)
    # plan_ref, audit_ref, report_ref, session_id, etc.

    # Policy/material hashes (placeholder — current code has none)
    policy_hash: str | None = None
    material_hash: str | None = None

    # Execution metadata
    tick_id: int = 0
    worktree_requirement: WorktreeRequirementValue = "none"

    # Dispatch mode
    mode: Literal["sync", "async"] = "async"
    # Sync mode uses build_sync_request, async uses build_async_request

    # CLI overrides for sync runner
    cli_overrides: dict[str, str] | None = None
    # agent/backend/model/fresh_session overrides

    # Governance-specific parameters
    governance_tick_count: int = 0
    governance_material_override: str | None = None

    model_config = {"frozen": True}


class JobContext(BaseModel):
    """
    Runtime context populated when a job begins execution.

    Captures the tmux/session/log environment.
    """

    issue_number: int
    branch: str

    # Execution environment
    tmux_session: str | None = None
    session_id: str | None = None
    log_path: str | None = None
    worktree_path: str | None = None
    cwd: str | None = None
    repo_path: str | None = None

    # Execution mode
    mode: Literal["sync", "async"] = "async"

    model_config = {"frozen": True}


class JobResult(BaseModel):
    """
    Outcome of a job execution.

    Not frozen — downstream may update status incrementally.
    """

    command_type: CommandType
    issue_number: int
    branch: str

    # Outcome
    status: Literal["launched", "completed", "failed", "skipped", "aborted"] = (
        "launched"
    )
    exit_code: int | None = None

    # Resolved adapter
    adapter_path: str | None = None

    # Execution metadata
    context: JobContext | None = None

    # Content hashes at execution time
    policy_hash: str | None = None
    material_hash: str | None = None

    # Payload summary
    payload_summary: dict[str, str] = Field(default_factory=dict)
    # Lightweight key-value summary of what was processed

    # Timing (ISO 8601 strings)
    started_at: str | None = None
    finished_at: str | None = None

    # Error info
    error_message: str | None = None
    error_code: str | None = None

    # Semantic equivalence marker
    source: JobSource | None = None
