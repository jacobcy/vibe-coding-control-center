"""Executor role definition and request builders."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from vibe3.agents.review_runner import format_agent_actor
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.gates import apply_request_completion_gate
from vibe3.execution.role_contracts import EXECUTOR_GATE_CONFIG
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.roles.definitions import IssueRoleSyncSpec, TriggerableRoleDefinition
from vibe3.runtime.no_progress_policy import snapshot_progress
from vibe3.services.issue_failure_service import fail_executor_issue

EXECUTOR_ROLE = TriggerableRoleDefinition(
    name="executor",
    registry_role="executor",
    gate_config=EXECUTOR_GATE_CONFIG,
    trigger_name="run",
    trigger_state=IssueState.IN_PROGRESS,
    status_field="executor_status",
    dispatch_predicate=lambda fs, live: (
        bool(fs.get("plan_ref")) and not fs.get("report_ref") and not live
    ),
)


def resolve_orchestra_repo_root() -> Path:
    """Resolve shared repo root anchored at git common dir."""
    try:
        git_common_dir = GitClient().get_git_common_dir()
        if git_common_dir:
            return Path(git_common_dir).parent
    except Exception:
        pass
    return Path.cwd()


def resolve_run_options(config: OrchestraConfig) -> Any:
    """Resolve executor agent options with env override support."""
    _backend_override = os.environ.get("VIBE3_EXECUTOR_BACKEND")
    _model_override = os.environ.get("VIBE3_EXECUTOR_MODEL") or None
    if _backend_override:
        from vibe3.models.review_runner import AgentOptions

        return AgentOptions(
            backend=_backend_override,
            model=_model_override,
        )

    from vibe3.runtime.agent_resolver import resolve_executor_agent_options

    return resolve_executor_agent_options(config, VibeConfig.get_defaults())


def resolve_run_branch(
    store: SQLiteClient,
    issue_number: int,
    current_branch: str,
) -> str:
    """Resolve target branch for executor execution."""
    flows = store.get_flows_by_issue(issue_number, role="task")
    if not isinstance(flows, list) or not flows:
        return current_branch

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


def build_run_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    *,
    branch: str | None = None,
    repo_path: Path | None = None,
    plan_ref: str | None = None,
    actor: str = "orchestra:executor",
) -> ExecutionRequest:
    """Build the executor async execution request for dispatch."""
    _ = config  # interface-compatible; repo resolved from repo_path or git common dir
    root = (repo_path or resolve_orchestra_repo_root()).resolve()
    target_branch = branch or f"task/issue-{issue.number}"

    env = dict(os.environ)
    env["VIBE3_ASYNC_CHILD"] = "1"

    cmd = [
        "uv",
        "run",
        "--project",
        str(root),
        "python",
        "-I",
        str((root / "src" / "vibe3" / "cli.py").resolve()),
        "run",
        "--issue",
        str(issue.number),
        "--no-async",
    ]
    if plan_ref:
        cmd.extend(["--plan-ref", plan_ref])

    refs: dict[str, str] = {"issue_number": str(issue.number)}
    if plan_ref:
        refs["plan_ref"] = plan_ref

    return ExecutionRequest(
        role="executor",
        target_branch=target_branch,
        target_id=issue.number,
        execution_name=f"vibe3-executor-issue-{issue.number}",
        cmd=cmd,
        repo_path=str(root),
        env=env,
        refs=refs,
        actor=actor,
        mode="async",
        worktree_requirement=EXECUTOR_ROLE.gate_config.worktree,
        completion_gate=EXECUTOR_ROLE.gate_config.completion_contract,
    )


def build_run_sync_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    branch: str,
    session_id: str | None,
    options: Any,
    actor: str,
    dry_run: bool,
) -> ExecutionRequest:
    """Build the executor sync execution request."""
    run_config = getattr(config, "run", None)
    run_prompt = run_config.run_prompt if run_config else None
    task = (
        run_prompt or f"Execute implementation for issue #{issue.number}: {issue.title}"
    )

    return ExecutionRequest(
        role="executor",
        target_branch=branch,
        target_id=issue.number,
        execution_name=f"vibe3-executor-issue-{issue.number}",
        prompt=task,
        options=options,
        cwd=str(Path.cwd()) if session_id else None,
        repo_path=str(resolve_orchestra_repo_root()),
        refs={
            "task": task,
            **({"session_id": session_id} if session_id else {}),
        },
        actor=actor,
        mode="sync",
        dry_run=dry_run,
        worktree_requirement=EXECUTOR_ROLE.gate_config.worktree,
        completion_gate=EXECUTOR_ROLE.gate_config.completion_contract,
    )


def handle_run_post_sync(
    store: SQLiteClient,
    issue_number: int,
    _branch: str,
    actor: str,
    config: OrchestraConfig,
    before_snapshot: dict[str, object],
    after_snapshot: dict[str, object],
    request: ExecutionRequest,
) -> bool:
    """Apply executor-specific post-sync hooks and completion gates."""
    # Check if executor produced report_ref
    before_refs = before_snapshot.get("refs")
    after_refs = after_snapshot.get("refs")
    if isinstance(before_refs, dict) and isinstance(after_refs, dict):
        before_report = before_refs.get("report_ref")
        after_report = after_refs.get("report_ref")
        if not before_report and not after_report:
            from vibe3.services.issue_failure_service import block_executor_noop_issue

            block_executor_noop_issue(
                issue_number=issue_number,
                reason="Executor completed without producing report_ref",
                actor=actor,
                repo=config.repo,
            )
            return True

    return apply_request_completion_gate(
        request=request,
        store=store,
        repo=config.repo,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )


def handle_run_failure(
    issue_number: int,
    reason: str,
) -> None:
    """Handle executor execution failure."""
    fail_executor_issue(
        issue_number=issue_number,
        reason=reason,
        actor="agent:run",
    )


def snapshot_run_progress(
    *,
    issue_number: int,
    branch: str,
    store: SQLiteClient,
    config: OrchestraConfig,
) -> dict[str, object]:
    """Capture executor progress snapshot."""
    return snapshot_progress(
        issue_number=issue_number,
        branch=branch,
        store=store,
        github=GitHubClient(),
        repo=config.repo,
    )


def build_run_actor(config: OrchestraConfig) -> tuple[Any, str]:
    """Resolve executor options and actor string together."""
    options = resolve_run_options(config)
    return options, format_agent_actor(options)


RUN_SYNC_SPEC = IssueRoleSyncSpec(
    role_name="executor",
    resolve_options=resolve_run_options,
    resolve_branch=resolve_run_branch,
    build_async_request=lambda config, issue, actor: build_run_request(
        config,
        issue,
        actor=actor,
    ),
    build_sync_request=build_run_sync_request,
    snapshot_progress=lambda issue_number, branch, store, config: (
        snapshot_run_progress(
            issue_number=issue_number,
            branch=branch,
            store=store,
            config=config,
        )
    ),
    post_sync_hook=handle_run_post_sync,
    failure_handler=lambda issue_number, reason: handle_run_failure(
        issue_number=issue_number,
        reason=reason,
    ),
)
