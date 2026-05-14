"""Executor role definition and request builders (aggregated exports)."""

from __future__ import annotations

# Re-export all symbols for backward compatibility
from vibe3.roles.run_command import (
    dispatch_run_command_async,
    execute_manual_run,
)
from vibe3.roles.run_helpers import (
    EXECUTOR_PUBLISH_ROLE,
    EXECUTOR_ROLE,
    RUN_BRANCH_RESOLVER,
    ensure_plan_file_exists,
    find_skill_file,
    publish_run_command_failure,
    publish_run_command_success,
    resolve_run_mode,
    resolve_run_options,
    validate_run_prerequisites,
)
from vibe3.roles.run_request import (
    RUN_SYNC_SPEC,
    build_run_request,
    build_run_sync_request,
)

__all__ = [
    "EXECUTOR_PUBLISH_ROLE",
    "EXECUTOR_ROLE",
    "RUN_BRANCH_RESOLVER",
    "RUN_SYNC_SPEC",
    "build_run_request",
    "build_run_sync_request",
    "dispatch_run_command_async",
    "ensure_plan_file_exists",
    "execute_manual_run",
    "find_skill_file",
    "publish_run_command_failure",
    "publish_run_command_success",
    "resolve_run_mode",
    "resolve_run_options",
    "validate_run_prerequisites",
]
