"""Generic sync/async runner for issue-scoped roles."""

from __future__ import annotations

import typer

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.execution.actor_support import format_agent_actor
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.execution.session_service import load_session_id
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo
from vibe3.roles.definitions import IssueRoleSyncSpec


def _load_issue_info(config: OrchestraConfig, issue_number: int) -> IssueInfo:
    issue_payload = GitHubClient().view_issue(issue_number, repo=config.repo)
    if not isinstance(issue_payload, dict):
        if issue_payload == "network_error":
            typer.echo(
                (
                    f"Error: Unable to load issue #{issue_number} "
                    "(GitHub read timed out or auth/network is unavailable)."
                ),
                err=True,
            )
        else:
            typer.echo(
                f"Error: Unable to load issue #{issue_number}.",
                err=True,
            )
        raise typer.Exit(1)

    issue = IssueInfo.from_github_payload(issue_payload)
    if issue is not None:
        return issue

    title = str(issue_payload.get("title") or f"Issue {issue_number}")
    labels = [
        label.get("name", "")
        for label in issue_payload.get("labels", [])
        if isinstance(label, dict)
    ]
    return IssueInfo(number=issue_number, title=title, labels=labels)


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
    issue = _load_issue_info(config, issue_number)

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
            if not result.launched:
                typer.echo(
                    f"{spec.role_name} dispatch queued/throttled: {result.reason}"
                )
                return

            typer.echo(f"-> {spec.role_name} run: issue #{issue_number}")
            typer.echo(f"Tmux session: {result.tmux_session}")
            typer.echo(f"Session log: {result.log_path}")
            return
        except BaseException as exc:
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
    issue = _load_issue_info(config, issue_number)

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

    if dry_run:
        typer.echo(f"-> {spec.role_name} run: issue #{issue_number} (dry-run)")
        return

    if not sync_result.launched:
        # Soft-skip reason codes: coordinator intentionally declined, not a failure
        _skip_codes = {"capacity_full"}
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
