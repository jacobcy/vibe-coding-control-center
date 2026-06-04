"""Shared helpers for issue-scoped role execution."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Iterable

from vibe3.clients import SQLiteClient
from vibe3.execution.role_interfaces import IssueRoleSyncSpec
from vibe3.models import (
    AgentOptions,
    ExecutionRequest,
    IssueInfo,
    SessionRole,
    WorktreeRequirement,
)
from vibe3.roles.definitions import IssueRoleSyncSpec as IssueRoleSyncSpecImpl


def resolve_orchestra_repo_root() -> Path:
    """Resolve the main repository root for orchestra operations.

    Delegates to find_repo_root() — the single source of truth in git_client.
    """
    from vibe3.clients.git_client import find_repo_root

    return find_repo_root()


def resolve_async_cli_project_root(repo_path: Path | None = None) -> Path:
    """Resolve the code/project root used by async child self-invocation.

    Rules:
    - If `VIBE3_ASYNC_CLI_PROJECT_ROOT` is set (non-empty), use it.
      Reserved for manual debugging scenarios only.
      Note: Serve command no longer auto-sets this (as of PR #1662).
    - Otherwise, derive from this module's location (installed/source vibe3).
    - Falls back to repo_path / orchestra root if module location fails.

    This ensures cross-project dispatch always uses the global vibe3 installation,
    not the caller repository, preventing wrong cli.py resolution.
    """
    override_root = os.environ.get("VIBE3_ASYNC_CLI_PROJECT_ROOT", "").strip()
    if override_root:
        return Path(override_root).expanduser().resolve()

    module_root = Path(__file__).resolve().parents[3]
    cli_path = module_root / "src" / "vibe3" / "cli.py"
    if cli_path.exists():
        return module_root

    return (repo_path or resolve_orchestra_repo_root()).resolve()


def resolve_task_flow_branch(
    store: SQLiteClient,
    issue_number: int,
    current_branch: str,
    *,
    fallback_branch: str,
) -> str:
    """Resolve preferred task flow branch for issue-scoped role execution."""
    flows = store.get_flows_by_issue(issue_number, role="task")
    if not isinstance(flows, list) or not flows:
        return fallback_branch

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
    return branch or fallback_branch


def use_current_branch(
    store: SQLiteClient,
    issue_number: int,
    current_branch: str,
) -> str:
    """Return the caller branch unchanged for roles without flow branch lookup."""
    _ = store
    _ = issue_number
    return current_branch


def build_task_flow_branch_resolver(
    *,
    fallback_branch: str | Callable[[int, str], str],
) -> Callable[[SQLiteClient, int, str], str]:
    """Build a shared task-flow branch resolver for issue-scoped roles."""

    def resolver(
        store: SQLiteClient,
        issue_number: int,
        current_branch: str,
    ) -> str:
        fallback = (
            fallback_branch(issue_number, current_branch)
            if callable(fallback_branch)
            else fallback_branch
        )
        return resolve_task_flow_branch(
            store,
            issue_number,
            current_branch,
            fallback_branch=fallback,
        )

    return resolver


def build_issue_async_cli_request(
    *,
    role: str,
    issue: IssueInfo,
    target_branch: str,
    command_args: Iterable[str],
    actor: str,
    execution_name: str,
    refs: dict[str, str] | None,
    worktree_requirement: WorktreeRequirement,
    repo_path: Path | None = None,
    tick_id: int = 0,
) -> ExecutionRequest:
    """Build a generic async self-invocation request for an issue role."""
    root = (repo_path or resolve_orchestra_repo_root()).resolve()
    command_root = resolve_async_cli_project_root(root)
    env = dict(os.environ)
    env["VIBE3_ASYNC_CHILD"] = "1"
    return ExecutionRequest(
        role=role,
        target_branch=target_branch,
        target_id=issue.number,
        execution_name=execution_name,
        cmd=[
            "uv",
            "run",
            "--project",
            str(command_root),
            "python",
            "-I",
            str((command_root / "src" / "vibe3" / "cli.py").resolve()),
            *command_args,
        ],
        repo_path=str(root),
        env=env,
        refs=refs or {},
        actor=actor,
        mode="async",
        worktree_requirement=worktree_requirement,
        tick_id=tick_id,
    )


def build_issue_sync_prompt_request(
    *,
    role: str,
    issue: IssueInfo,
    target_branch: str,
    prompt: str,
    task: str,
    options: object,
    actor: str,
    execution_name: str,
    worktree_requirement: WorktreeRequirement,
    session_id: str | None = None,
    repo_path: Path | None = None,
    dry_run: bool = False,
    show_prompt: bool = False,
    include_global_notice: bool = True,
    fallback_prompt: str | None = None,
    fallback_include_global_notice: bool = True,
    extra_refs: dict[str, str] | None = None,
    dry_run_summary: dict[str, Any] | None = None,
    tick_id: int = 0,
) -> ExecutionRequest:
    """Build a generic sync prompt-based request for an issue role."""
    root = (repo_path or resolve_orchestra_repo_root()).resolve()
    refs = {"task": task}
    if session_id:
        refs["session_id"] = session_id
    if extra_refs:
        refs.update(extra_refs)
    return ExecutionRequest(
        role=role,
        target_branch=target_branch,
        target_id=issue.number,
        execution_name=execution_name,
        prompt=prompt,
        options=options,
        # Keep sync issue-role requests worktree-agnostic so the coordinator can
        # resolve the correct permanent worktree from target_branch.
        cwd=None,
        repo_path=str(root),
        refs=refs,
        actor=actor,
        mode="sync",
        dry_run=dry_run,
        show_prompt=show_prompt,
        include_global_notice=include_global_notice,
        fallback_prompt=fallback_prompt,
        fallback_include_global_notice=fallback_include_global_notice,
        dry_run_summary=dry_run_summary or {},
        worktree_requirement=worktree_requirement,
        tick_id=tick_id,
    )


def resolve_env_overridable_agent_options(
    *,
    backend_env_key: str,
    model_env_key: str,
    fallback_resolver: Callable[[], Any],
) -> Any:
    """Resolve role options with optional env override."""
    backend_override = os.environ.get(backend_env_key)
    model_override = os.environ.get(model_env_key) or None
    if backend_override:
        return AgentOptions(backend=backend_override, model=model_override)
    return fallback_resolver()


def build_issue_sync_spec(
    *,
    role_name: SessionRole,
    resolve_options: Callable[[Any], Any],
    resolve_branch: Callable[[SQLiteClient, int, str], str],
    build_async_request: Callable[[Any, IssueInfo, str], ExecutionRequest | None],
    build_sync_request: Callable[
        [
            Any,
            IssueInfo,
            str,
            dict[str, object] | None,
            str | None,
            Any,
            str,
            bool,
            bool,
        ],
        ExecutionRequest,
    ],
    failure_handler: Callable[..., None],
) -> IssueRoleSyncSpec:
    """Build the minimal sync spec shared by issue-scoped roles."""
    return IssueRoleSyncSpecImpl(
        role_name=role_name,
        resolve_options=resolve_options,
        resolve_branch=resolve_branch,
        build_async_request=build_async_request,
        build_sync_request=build_sync_request,
        failure_handler=failure_handler,
    )
