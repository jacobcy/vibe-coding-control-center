"""Manager execution service.

This module handles manager mode execution for issue processing
and orchestration.

Note: Repository-local async logs (temp/logs/issues/*/manager.async.log) are
runtime execution logs, not prompt provenance storage. Full agent prompts are
filtered from these logs by the CodeagentBackend async log filter to prevent
sensitive information from appearing in repository logs.
"""

from __future__ import annotations

import os
from pathlib import Path

import typer

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.agents.review_runner import format_agent_actor
from vibe3.agents.session_service import load_session_id
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.manager.prompts import render_manager_prompt
from vibe3.manager.session_naming import (
    get_manager_session_name,
)
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.runtime.no_progress_policy import has_progress_changed, snapshot_progress
from vibe3.services.abandon_flow_service import AbandonFlowService
from vibe3.services.issue_failure_service import (
    block_manager_noop_issue,
    fail_manager_issue,
)


def _handle_closed_issue_post_run(
    *,
    store: SQLiteClient,
    issue_number: int,
    branch: str,
    actor: str,
    before_snapshot: dict[str, object],
    after_snapshot: dict[str, object],
) -> bool:
    """Finalize abandon-flow handling when manager closed the issue."""
    if after_snapshot.get("issue_state") != "closed":
        return False

    before_state_label = before_snapshot.get("state_label", "")
    source_state: IssueState | None = None
    if before_state_label == "state/ready":
        source_state = IssueState.READY
    elif before_state_label == "state/handoff":
        source_state = IssueState.HANDOFF

    if source_state is None:
        store.add_event(
            branch,
            "manager_closed_issue_unexpected_state",
            actor,
            detail=(
                f"Issue #{issue_number} closed but was in {before_state_label} "
                f"(expected state/ready or state/handoff)"
            ),
            refs={"issue": str(issue_number)},
        )
        return True

    abandon_result = AbandonFlowService().abandon_flow(
        issue_number=issue_number,
        branch=branch,
        source_state=source_state,
        reason="manager closed issue without finalizing abandon flow",
        actor=actor,
        issue_already_closed=True,
        flow_already_aborted=after_snapshot.get("flow_status") == "aborted",
    )
    store.add_event(
        branch,
        "manager_abandoned_flow",
        actor,
        detail=(
            f"Manager abandoned flow for issue #{issue_number} "
            f"(issue={abandon_result.get('issue')}, "
            f"pr={abandon_result.get('pr')}, "
            f"flow={abandon_result.get('flow')})"
        ),
        refs={"issue": str(issue_number), "result": str(abandon_result)},
    )
    return True


def _block_manager_if_noop(
    *,
    store: SQLiteClient,
    issue_number: int,
    branch: str,
    actor: str,
    repo: str | None,
    before_snapshot: dict[str, object],
    after_snapshot: dict[str, object],
) -> bool:
    """Block manager runs that do not make required state progress."""
    current_state_label = before_snapshot.get("state_label", "")
    allow_close = current_state_label in ("state/ready", "state/handoff")
    if has_progress_changed(
        before_snapshot,
        after_snapshot,
        require_state_transition=True,
        allow_close_as_progress=allow_close,
    ):
        return False

    reason = "manager 本轮未产生状态迁移（must leave READY/HANDOFF per contract）"
    store.add_event(
        branch,
        "manager_noop_blocked",
        actor,
        detail=f"Manager auto-blocked issue #{issue_number}: {reason}",
        refs={"issue": str(issue_number), "reason": reason},
    )
    block_manager_noop_issue(
        issue_number=issue_number,
        repo=repo,
        reason=reason,
        actor=actor,
    )
    return True


def run_manager_issue_mode(
    *,
    issue_number: int,
    dry_run: bool,
    async_mode: bool,
    fresh_session: bool = False,
) -> None:
    """Execute manager run mode for issue processing.

    Args:
        issue_number: GitHub issue number
        dry_run: If True, only show what would be done
        async_mode: If True, run in async mode (tmux session)
        fresh_session: If True, skip session resume
    """
    orchestra_config = OrchestraConfig.from_settings()
    issue_payload = GitHubClient().view_issue(issue_number, repo=orchestra_config.repo)
    if not isinstance(issue_payload, dict):
        if issue_payload == "network_error":
            typer.echo(
                (
                    f"Error: Unable to load issue #{issue_number} for manager run "
                    "(GitHub read timed out or auth/network is unavailable)."
                ),
                err=True,
            )
        else:
            typer.echo(
                f"Error: Unable to load issue #{issue_number} for manager run.",
                err=True,
            )
        raise typer.Exit(1)

    issue = IssueInfo.from_github_payload(issue_payload)
    if issue is None:
        title = str(issue_payload.get("title") or f"Issue {issue_number}")
        labels = [
            label.get("name", "")
            for label in issue_payload.get("labels", [])
            if isinstance(label, dict)
        ]
        issue = IssueInfo(number=issue_number, title=title, labels=labels)

    runtime_config = VibeConfig.get_defaults()
    store = SQLiteClient()
    current_branch = GitClient().get_current_branch()
    branch = resolve_manager_branch(
        store=store,
        issue_number=issue_number,
        current_branch=current_branch,
    )
    session_id = None if fresh_session else load_session_id("manager", branch=branch)
    launch_cwd = resolve_manager_execution_cwd(
        orchestra_config=orchestra_config,
        issue_number=issue_number,
        target_branch=branch,
        current_branch=current_branch,
        session_id=session_id,
    )
    # Prefer dispatcher-injected backend/model over local config resolution.
    # This ensures task worktrees use the dispatcher's resolved config regardless
    # of which branch the task worktree is on.
    _backend_override = os.environ.get("VIBE3_MANAGER_BACKEND")
    _model_override = os.environ.get("VIBE3_MANAGER_MODEL") or None
    if _backend_override:
        from vibe3.models.review_runner import AgentOptions

        options = AgentOptions(
            backend=_backend_override,
            model=_model_override,
        )
    else:
        from vibe3.runtime.agent_resolver import resolve_manager_agent_options

        options = resolve_manager_agent_options(
            orchestra_config,
            runtime_config,
        )
    actor = format_agent_actor(options)
    backend = CodeagentBackend()
    rendered = render_manager_prompt(orchestra_config, issue)
    prompt = rendered.rendered_text
    before_snapshot = snapshot_progress(
        issue_number=issue_number,
        branch=branch,
        store=store,
        github=GitHubClient(),
        repo=orchestra_config.repo,
    )
    manager_task = (
        f"Manage issue #{issue_number}: {issue.title}\n"
        "Act as the manager state controller for this issue. "
        "Inspect the scene, read issue comments and handoff, update labels/comments/"
        "handoff when allowed, and stop when the current state rule requires exit."
    )

    if async_mode and not dry_run:
        from vibe3.execution.contracts import ExecutionRequest
        from vibe3.execution.coordinator import ExecutionCoordinator

        coordinator = ExecutionCoordinator(orchestra_config, store, backend)

        refs = {"task": manager_task}
        if session_id:
            refs["session_id"] = session_id

        request = ExecutionRequest(
            role="manager",
            target_branch=branch,
            target_id=issue_number,
            execution_name=get_manager_session_name(issue_number),
            prompt=prompt,
            options=options,
            cwd=str(launch_cwd),
            env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
            refs=refs,
            actor=actor,
            mode="async",
        )

        try:
            result = coordinator.dispatch_execution(request)
            if not result.launched:
                # Capacity full or dispatch rejected - this is a normal
                # throttling result, not an execution failure.
                # Do not mark issue as failed.
                typer.echo(f"Manager dispatch queued/throttled: {result.reason}")
                return

            typer.echo(f"-> Manager run: issue #{issue_number}")
            typer.echo(f"Tmux session: {result.tmux_session}")
            typer.echo(f"Session log: {result.log_path}")
            return
        except BaseException as exc:
            store.add_event(
                branch,
                "manager_failed",
                actor,
                detail=f"Manager execution failed for issue #{issue_number}: {exc}",
                refs={"issue": str(issue_number), "reason": str(exc)},
            )
            fail_manager_issue(
                issue_number=issue_number,
                reason=f"manager async start failed: {exc}",
            )
            raise typer.Exit(1) from exc

    sync_request = ExecutionRequest(
        role="manager",
        target_branch=branch,
        target_id=issue_number,
        execution_name=get_manager_session_name(issue_number),
        prompt=prompt,
        options=options,
        cwd=str(launch_cwd),
        refs={
            "task": manager_task,
            **({"session_id": session_id} if session_id else {}),
        },
        actor=actor,
        mode="sync",
        dry_run=dry_run,
    )
    sync_result = ExecutionCoordinator(
        orchestra_config, store, backend
    ).dispatch_execution(sync_request)

    if dry_run:
        typer.echo(f"-> Manager run: issue #{issue_number} (dry-run)")
        return

    if not sync_result.launched:
        fail_manager_issue(
            issue_number=issue_number,
            reason=sync_result.reason or "manager exited with failure",
        )
        raise typer.Exit(1)

    store.update_flow_state(branch, latest_actor=actor)
    after_snapshot = snapshot_progress(
        issue_number=issue_number,
        branch=branch,
        store=store,
        github=GitHubClient(),
        repo=orchestra_config.repo,
    )
    if _handle_closed_issue_post_run(
        store=store,
        issue_number=issue_number,
        branch=branch,
        actor=actor,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    ):
        return

    if _block_manager_if_noop(
        store=store,
        issue_number=issue_number,
        branch=branch,
        actor=actor,
        repo=orchestra_config.repo,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    ):
        return


def resolve_manager_launch_cwd(*, session_id: str | None) -> Path:
    """Resolve launch CWD for manager execution.

    Args:
        session_id: Existing session ID (if resuming)

    Returns:
        Path to launch CWD
    """
    if session_id:
        return Path.cwd()
    git_common_dir = Path(GitClient().get_git_common_dir())
    return git_common_dir.parent


def resolve_manager_branch(
    *,
    store: SQLiteClient,
    issue_number: int,
    current_branch: str,
) -> str:
    """Resolve target branch for manager execution.

    Prefers target issue's task flow branch; falls back to canonical task branch.

    Args:
        store: SQLite client for flow state
        issue_number: GitHub issue number
        current_branch: Current git branch

    Returns:
        Target branch name
    """
    flows = store.get_flows_by_issue(issue_number, role="task")
    if not isinstance(flows, list) or not flows:
        return f"task/issue-{issue_number}"

    for flow in flows:
        if flow.get("branch") == current_branch:
            return current_branch

    prioritized = sorted(
        flows,
        key=lambda flow: (
            flow.get("flow_status") == "active",
            flow.get("updated_at") or "",
        ),
        reverse=True,
    )
    branch = str(prioritized[0].get("branch") or "").strip()
    return branch or current_branch


def resolve_manager_execution_cwd(
    *,
    orchestra_config: OrchestraConfig,
    issue_number: int,
    target_branch: str,
    current_branch: str,
    session_id: str | None,
) -> Path:
    """Resolve execution CWD for manager run.

    Args:
        orchestra_config: Orchestra configuration
        issue_number: GitHub issue number
        target_branch: Target branch for execution
        current_branch: Current git branch
        session_id: Existing session ID (if resuming)

    Returns:
        Path: Resolved CWD path
    """
    from vibe3.environment.worktree import WorktreeManager

    # For session resume, use current directory
    if session_id:
        return Path.cwd()

    # For current branch execution
    if target_branch == current_branch:
        return resolve_manager_launch_cwd(
            session_id=session_id,
        )

    # Use WorktreeManager for foreign branch execution
    repo_root = Path(GitClient().get_git_common_dir()).parent
    manager_cwd, _ = WorktreeManager(orchestra_config, repo_root).resolve_manager_cwd(
        issue_number,
        target_branch,
    )
    if manager_cwd is not None:
        return manager_cwd

    # Fallback: use launch cwd resolver
    return resolve_manager_launch_cwd(
        session_id=session_id,
    )
