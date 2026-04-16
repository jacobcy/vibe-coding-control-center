"""Shared helpers for issue-scoped role execution."""

from __future__ import annotations

import os
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterable

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.gates import apply_request_completion_gate
from vibe3.execution.role_contracts import CompletionContract, WorktreeRequirement
from vibe3.execution.session_service import SessionRole
from vibe3.models.orchestration import IssueInfo
from vibe3.models.review_runner import AgentOptions
from vibe3.runtime.no_progress_policy import snapshot_progress

if TYPE_CHECKING:
    from vibe3.roles.definitions import IssueRoleSyncSpec


def resolve_orchestra_repo_root() -> Path:
    """Resolve the active repo root for orchestra self-invocation.

    Prefer the current worktree root so async/sync self-invocations execute the
    same checked-out code the operator is running. Fall back to the shared git
    common dir parent only when worktree resolution is unavailable.
    """
    try:
        worktree_root = GitClient().get_worktree_root()
        if worktree_root:
            return Path(worktree_root)
    except Exception:
        pass
    try:
        git_common_dir = GitClient().get_git_common_dir()
        if git_common_dir:
            return Path(git_common_dir).parent
    except Exception:
        pass
    return Path.cwd()


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
    completion_gate: CompletionContract | None,
    repo_path: Path | None = None,
) -> ExecutionRequest:
    """Build a generic async self-invocation request for an issue role."""
    root = (repo_path or resolve_orchestra_repo_root()).resolve()
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
            str(root),
            "python",
            "-I",
            str((root / "src" / "vibe3" / "cli.py").resolve()),
            *command_args,
        ],
        repo_path=str(root),
        env=env,
        refs=refs or {},
        actor=actor,
        mode="async",
        worktree_requirement=worktree_requirement,
        completion_gate=completion_gate,
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
    completion_gate: CompletionContract | None,
    session_id: str | None = None,
    repo_path: Path | None = None,
    dry_run: bool = False,
) -> ExecutionRequest:
    """Build a generic sync prompt-based request for an issue role."""
    root = (repo_path or resolve_orchestra_repo_root()).resolve()
    refs = {"task": task}
    if session_id:
        refs["session_id"] = session_id
    return ExecutionRequest(
        role=role,
        target_branch=target_branch,
        target_id=issue.number,
        execution_name=execution_name,
        prompt=prompt,
        options=options,
        cwd=str(Path.cwd()) if session_id else None,
        repo_path=str(root),
        refs=refs,
        actor=actor,
        mode="sync",
        dry_run=dry_run,
        worktree_requirement=worktree_requirement,
        completion_gate=completion_gate,
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


def snapshot_issue_role_progress(
    *,
    issue_number: int,
    branch: str,
    store: SQLiteClient,
    repo: str | None,
) -> dict[str, object]:
    """Capture generic issue role progress snapshot."""
    return snapshot_progress(
        issue_number=issue_number,
        branch=branch,
        store=store,
        github=GitHubClient(),
        repo=repo,
    )


def apply_required_ref_post_sync(
    store: SQLiteClient,
    issue_number: int,
    _branch: str,  # Required for signature compatibility, unused
    actor: str,
    config: Any,
    before_snapshot: dict[str, object],
    after_snapshot: dict[str, object],
    request: ExecutionRequest,
    *,
    required_ref: str,
    missing_reason: str,
    missing_ref_handler: Callable[..., None],
    success_handler: Callable[..., None] | None = None,
) -> bool:
    """Apply standard completion gate with required-ref protection.

    Args:
        _branch: Required to match IssueRoleSyncSpec.post_sync_hook signature,
            but not used in this implementation. Prefix underscore indicates
            intentional unused parameter.
        success_handler: Optional callback invoked when required_ref is present
            after execution. Called as success_handler(issue_number, actor).
            Use this to trigger state transitions (e.g. confirm_plan_handoff)
            directly from the sync completion path, bypassing the domain event
            bus (which is in-process only and not accessible from async tmux
            subprocess executions).
    """
    before_refs = before_snapshot.get("refs")
    after_refs = after_snapshot.get("refs")
    if isinstance(before_refs, dict) and isinstance(after_refs, dict):
        before_value = before_refs.get(required_ref)
        after_value = after_refs.get(required_ref)
        if not before_value and not after_value:
            missing_ref_handler(
                issue_number=issue_number,
                reason=missing_reason,
                actor=actor,
                repo=config.repo,
            )
            return True

    # Record state transition if it occurred
    before_state = before_snapshot.get("state_label")
    after_state = after_snapshot.get("state_label")
    if before_state != after_state:
        store.add_event(
            _branch,
            "state_transitioned",
            actor,
            detail=f"State changed: {before_state} → {after_state}",
            refs={
                "before_state": str(before_state or ""),
                "after_state": str(after_state or ""),
                "issue": str(issue_number),
            },
        )

    # required_ref is present — call success_handler to advance state.
    # This is the correct place for state transitions in the async tmux path:
    # domain events published here would be in the subprocess event bus, not
    # in the orchestra process, so direct calls are used instead.
    if success_handler is not None:
        success_handler(issue_number=issue_number, actor=actor)

    return apply_request_completion_gate(
        request=request,
        store=store,
        repo=config.repo,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )


def build_required_ref_sync_spec(
    *,
    role_name: SessionRole,
    resolve_options: Callable[[Any], Any],
    resolve_branch: Callable[[SQLiteClient, int, str], str],
    build_async_request: Callable[[Any, IssueInfo, str], ExecutionRequest | None],
    build_sync_request: Callable[
        [Any, IssueInfo, str, str | None, Any, str, bool], ExecutionRequest
    ],
    required_ref: str,
    missing_reason: str,
    missing_ref_handler: Callable[..., None],
    failure_handler: Callable[..., None],
    success_handler: Callable[..., None] | None = None,
    process_sync_result: Callable[..., None] | None = None,
) -> IssueRoleSyncSpec:
    """Build the standard sync spec shared by plan/run/review-style roles.

    Args:
        success_handler: Optional state-transition callback invoked when
            required_ref is present after execution completes. Called as
            success_handler(issue_number=..., actor=...).
            Use this instead of domain events for async tmux paths where the
            subprocess event bus is separate from the orchestra process.
        process_sync_result: Optional callback to process sync execution output
            before taking the after snapshot. Called as
            process_sync_result(issue_number=..., branch=..., actor=..., stdout=...).
            Use this to write refs (e.g., audit_ref) from stdout before snapshot.
    """
    from vibe3.roles.definitions import IssueRoleSyncSpec

    return IssueRoleSyncSpec(
        role_name=role_name,
        resolve_options=resolve_options,
        resolve_branch=resolve_branch,
        build_async_request=build_async_request,
        build_sync_request=build_sync_request,
        snapshot_progress=lambda issue_number, branch, store, config: (
            snapshot_issue_role_progress(
                issue_number=issue_number,
                branch=branch,
                store=store,
                repo=config.repo,
            )
        ),
        post_sync_hook=partial(
            apply_required_ref_post_sync,
            required_ref=required_ref,
            missing_reason=missing_reason,
            missing_ref_handler=missing_ref_handler,
            success_handler=success_handler,
        ),
        failure_handler=failure_handler,
        process_sync_result=process_sync_result,
    )
