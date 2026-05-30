"""Generic sync/async runner for issue-scoped roles."""

from __future__ import annotations

import typer

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.execution.role_interfaces import IssueRoleSyncSpec
from vibe3.execution.session_service import load_session_id
from vibe3.services import (
    format_agent_actor,
    load_issue_info,
    record_dispatch_failure_if_unexpected,
)


def run_issue_role_async(
    *,
    issue_number: int,
    dry_run: bool,
    spec: IssueRoleSyncSpec,
) -> None:
    """Run a role asynchronously via tmux wrapper.

    Launches tmux session and returns immediately.
    The tmux child then re-enters the sync execution path locally.
    See docs/standards/vibe3-execution-paths-standard.md.
    """
    config = load_orchestra_config()
    issue = load_issue_info(issue_number, config=config)

    store = SQLiteClient()
    current_branch = GitClient().get_current_branch()
    branch = spec.resolve_branch(store, issue_number, current_branch)

    options = spec.resolve_options(config)
    actor = format_agent_actor(options)
    backend = CodeagentBackend()
    coordinator = ExecutionCoordinator(config, store, backend)

    # Early capacity check to avoid wasteful request preparation
    if not dry_run:
        if not coordinator.capacity.can_dispatch(spec.role_name):
            typer.echo(f"{spec.role_name} dispatch queued: Capacity full")
            return

    if not dry_run:
        request = spec.build_async_request(config, issue, actor)
        if request is None:
            if spec.failure_handler is not None:
                spec.failure_handler(
                    issue_number,
                    f"{spec.role_name} async request preparation failed",
                )
            raise typer.Exit(1)

        try:
            result = coordinator.dispatch_execution(request)
            record_dispatch_failure_if_unexpected(
                result=result,
                role=spec.role_name,
                issue_number=issue_number,
                branch=branch,
            )
            if not result.launched:
                typer.echo(
                    f"{spec.role_name} dispatch queued/throttled: {result.reason}"
                )
                return

            typer.echo(f"-> {spec.role_name} run: issue #{issue_number}")
            typer.echo(f"Tmux session: {result.tmux_session}")
            typer.echo(f"Session log: {result.log_path}")
            return
        except Exception as exc:
            record_dispatch_failure_if_unexpected(
                role=spec.role_name,
                issue_number=issue_number,
                branch=branch,
                exception=exc,
            )
            store.add_event(
                branch,
                f"{spec.role_name}_failed",
                actor,
                detail=(
                    f"{spec.role_name} execution failed for "
                    f"issue #{issue_number}: {exc}"
                ),
                refs={"issue": str(issue_number), "reason": str(exc)},
            )
            if spec.failure_handler is not None:
                spec.failure_handler(
                    issue_number,
                    f"{spec.role_name} async start failed: {exc}",
                )
            raise typer.Exit(1) from exc

    typer.echo(f"-> {spec.role_name} run: issue #{issue_number} (async dry-run)")


def run_issue_role_sync(
    *,
    issue_number: int,
    dry_run: bool,
    fresh_session: bool,
    show_prompt: bool,
    spec: IssueRoleSyncSpec,
) -> None:
    """Run a role synchronously (direct execution without tmux wrapper).

    Orchestrated process runs the agent synchronously and waits for completion.
    Worker roles still enter codeagent_runner via ExecutionCoordinator, so
    the same lifecycle / handoff / pre-gate / no-op shell is used.
    See docs/standards/vibe3-execution-paths-standard.md.
    """
    config = load_orchestra_config()
    issue = load_issue_info(issue_number, config=config)

    store = SQLiteClient()
    current_branch = GitClient().get_current_branch()
    branch = spec.resolve_branch(store, issue_number, current_branch)
    flow_state = store.get_flow_state(branch) if branch else None
    session_id = (
        None if fresh_session else load_session_id(spec.role_name, branch=branch)
    )

    options = spec.resolve_options(config)
    actor = format_agent_actor(options)
    backend = CodeagentBackend()
    coordinator = ExecutionCoordinator(config, store, backend)

    sync_request = spec.build_sync_request(
        config,
        issue,
        branch,
        flow_state,
        session_id,
        options,
        actor,
        dry_run,
        show_prompt,
    )
    sync_result = coordinator.dispatch_execution(sync_request)
    record_dispatch_failure_if_unexpected(
        result=sync_result,
        role=spec.role_name,
        issue_number=issue_number,
        branch=branch,
    )

    if dry_run:
        typer.echo(f"-> {spec.role_name} run: issue #{issue_number} (dry-run)")
        return

    if not sync_result.launched:
        # Soft-skip reason codes: coordinator intentionally declined, not a failure
        _skip_codes = {"capacity_full", "duplicate_dispatch"}
        if sync_result.reason_code in _skip_codes:
            typer.echo(
                f"{spec.role_name} dispatch queued/throttled: {sync_result.reason}"
            )
            return
        if spec.failure_handler is not None:
            spec.failure_handler(
                issue_number,
                sync_result.reason or f"{spec.role_name} exited with failure",
            )
        raise typer.Exit(1)
