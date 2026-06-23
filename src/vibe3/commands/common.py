"""Common utilities for command layer."""

from __future__ import annotations

import os
from typing import Any

import typer

from vibe3.commands.check_support import execute_check_mode


def validate_trace_options(trace: bool, min_ms: float | None) -> None:
    """Validate trace options combination.

    Args:
        trace: Whether --trace is enabled
        min_ms: The --min-ms value if provided

    Raises:
        typer.Exit: If min_ms is provided without --trace
    """
    if min_ms is not None and not trace:
        typer.echo(
            "Error: --min-ms requires --trace to be enabled",
            err=True,
        )
        raise typer.Exit(1)


def enable_method_trace(min_ms: float | None = None) -> None:
    """Enable method-level tracing via @trace_method decorator.

    Sets VIBE3_TRACE=1 environment variable.
    Use -v or -vv separately to control log verbosity.

    Args:
        min_ms: Minimum duration in milliseconds to show in trace.
            Must be non-negative. None resets to no filtering (0).
    """
    os.environ["VIBE3_TRACE"] = "1"

    from vibe3.observability import set_trace_min_ms

    if min_ms is not None:
        set_trace_min_ms(min_ms)
    else:
        set_trace_min_ms(0.0)


def run_full_check_shortcut() -> None:
    """Run the full check shortcut used by status-style commands.

    The status dashboard should still render even if the full check reports
    unfixable issues or raises unexpectedly, but users must see a warning.
    """
    from vibe3.services.check import CheckService

    try:
        result = execute_check_mode(CheckService(), "fix_all", show_progress=False)
    except Exception as exc:
        typer.echo(
            f"Warning: vibe3 check failed before status: {exc}",
            err=True,
        )
        return

    if not result.success:
        typer.echo(
            f"Warning: vibe3 check incomplete before status: {result.summary}",
            err=True,
        )


def _resolve_dry_run_actor(
    role: str,
    agent: str | None,
    backend: str | None,
    model: str | None,
) -> str:
    """Resolve the dry-run actor string from CLI args plus configured defaults.

    Resolution order:
    1. If backend/model explicitly provided → return formatted backend/model
    2. If agent preset provided → resolve via config, return formatted backend/model
    3. If no flags (no-args case) → read default_backend/default_model from models.json
    4. Fall back to role default (vibe-planner/vibe-executor/vibe-reviewer)
    """
    from vibe3.config import (
        read_models_json,
        repo_models_json_path,
        resolve_effective_agent_options,
    )
    from vibe3.exceptions import AgentPresetNotFoundError
    from vibe3.models import AgentOptions
    from vibe3.services.shared import format_agent_actor

    options = AgentOptions(agent=agent, backend=backend, model=model)
    try:
        resolved = resolve_effective_agent_options(options)
        if resolved.backend:
            return format_agent_actor(resolved)
        # No backend resolved - fall through to defaults
    except AgentPresetNotFoundError:
        # Agent preset not found in config
        if agent:
            # Agent was explicitly provided but not found - return as-is
            return agent
        # No agent was provided - fall through to defaults

    # No-flags case: try to read configured defaults
    data = read_models_json(repo_models_json_path())
    default_backend = data.get("default_backend")
    default_model = data.get("default_model")

    if isinstance(default_backend, str) and default_backend.strip():
        default_options = AgentOptions(
            backend=default_backend.strip(),
            model=(
                str(default_model).strip() if isinstance(default_model, str) else None
            ),
        )
        return format_agent_actor(default_options)

    # No defaults configured - fall back to role default
    role_to_default = {
        "planner": "vibe-planner",
        "executor": "vibe-executor",
        "reviewer": "vibe-reviewer",
    }
    return role_to_default.get(role, role)


def echo_dry_run_header(
    role: str,
    issue_number: int | None,
    branch: str,
    agent: str | None,
    backend: str | None,
    model: str | None,
) -> None:
    """Echo unified dry-run header for plan/run/review commands."""
    from vibe3.services.shared import format_dry_run_header

    actor_display = _resolve_dry_run_actor(role, agent, backend, model)
    header = format_dry_run_header(role, issue_number, branch, actor_display)
    typer.echo(header)


def _handle_codeagent_result(result: Any, label: str) -> None:
    """Display CodeagentResult and exit with error if execution failed.

    Shared helper for plan/run commands that use publish_and_wait pattern.
    """
    if result:
        from rich.console import Console

        from vibe3.ui import display_codeagent_result

        console = Console()
        display_codeagent_result(console, result, label)

        if not result.success:
            raise typer.Exit(1)
