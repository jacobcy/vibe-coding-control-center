"""Executor request builders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vibe3.agents import (
    describe_run_plan_sections,
    make_run_context_builder,
)
from vibe3.clients import SQLiteClient
from vibe3.config import VibeConfig, get_convention
from vibe3.execution import (
    build_prompt_meta,
    build_role_async_request,
    build_role_sync_request,
)
from vibe3.models import ExecutionRequest, IssueInfo, OrchestraConfig
from vibe3.roles.definitions import IssueRoleSyncSpec
from vibe3.roles.run_helpers import (
    EXECUTOR_ROLE,
    RUN_BRANCH_RESOLVER,
    resolve_run_options,
)
from vibe3.services.issue import fail_executor_issue


def build_run_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    *,
    branch: str | None = None,
    repo_path: Path | None = None,
    plan_ref: str | None = None,
    audit_ref: str | None = None,
    commit_mode: bool = False,
    actor: str = "orchestra:executor",
    tick_id: int = 0,
) -> ExecutionRequest:
    """Build the executor async execution request for dispatch."""
    refs: dict[str, str] = {}
    if plan_ref:
        refs["plan_ref"] = plan_ref
    if audit_ref:
        refs["audit_ref"] = audit_ref

    convention = get_convention()
    target_branch = branch or convention.branch.canonical_branch(issue.number)
    if commit_mode:
        command_args = [
            "run",
            "--branch",
            target_branch,
            "--skill",
            "vibe-commit",
            "--no-async",
        ]
        refs["commit_mode"] = "true"
    elif plan_ref:
        command_args = [
            "run",
            "--branch",
            target_branch,
            "--plan",
            plan_ref,
            "--no-async",
        ]
    else:
        command_args = [
            "run",
            "--branch",
            target_branch,
            "--no-async",
        ]

    return build_role_async_request(
        role="executor",
        config=config,
        issue=issue,
        command_args=command_args,
        worktree_requirement=EXECUTOR_ROLE.worktree,
        branch=branch,
        repo_path=repo_path,
        actor=actor,
        refs=refs,
        tick_id=tick_id,
    )


def build_run_sync_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    branch: str,
    flow_state: dict[str, object] | None,
    session_id: str | None,
    options: Any,
    actor: str,
    dry_run: bool,
    show_prompt: bool,
    tick_id: int = 0,
) -> ExecutionRequest:
    """Build the executor sync execution request."""
    store = SQLiteClient()
    flow_state = store.get_flow_state(branch) if branch else None
    meta = build_prompt_meta(
        flow_state,
        ref_keys=("plan_ref", "report_ref", "audit_ref"),
        retry_ref_keys=("report_ref", "audit_ref"),
        session_id=session_id,
        default_mode="coding",
    )
    run_config = getattr(config, "run", None)
    run_prompt = run_config.run_prompt if run_config else None
    task = (
        run_prompt or f"Execute implementation for issue #{issue.number}: {issue.title}"
    )
    summary_sections = describe_run_plan_sections(
        meta.prompt_mode,  # type: ignore[arg-type]
        meta.context_mode,
    )
    refs = dict(meta.refs)
    plan_ref = refs.get("plan_ref")
    audit_ref = refs.get("audit_ref")
    dry_run_summary = meta.summary(summary_sections)
    fallback_prompt = None
    if meta.fallback_context_mode is not None:
        fallback_prompt = make_run_context_builder(
            plan_ref,
            VibeConfig.get_defaults(),
            audit_file=audit_ref,
            mode=meta.prompt_mode,  # type: ignore[arg-type]
            context_mode=meta.fallback_context_mode,
        )()

    return build_role_sync_request(
        role="executor",
        config=config,
        issue=issue,
        branch=branch,
        prompt=make_run_context_builder(
            plan_ref,
            VibeConfig.get_defaults(),
            audit_file=audit_ref,
            mode=meta.prompt_mode,  # type: ignore[arg-type]
            context_mode=meta.context_mode,
        )(),
        task=task,
        options=options,
        worktree_requirement=EXECUTOR_ROLE.worktree,
        session_id=session_id,
        actor=actor,
        dry_run=dry_run,
        show_prompt=show_prompt,
        include_global_notice=meta.include_global_notice,
        fallback_prompt=fallback_prompt,
        fallback_include_global_notice=True,
        extra_refs={k: str(v) for k, v in refs.items()},
        dry_run_summary=dry_run_summary,
        tick_id=tick_id,
    )


RUN_SYNC_SPEC = IssueRoleSyncSpec(
    role_name="executor",
    resolve_options=resolve_run_options,
    resolve_branch=RUN_BRANCH_RESOLVER,
    build_async_request=lambda config, issue, actor, branch: build_run_request(
        config,
        issue,
        branch=branch,
        actor=actor,
    ),
    build_sync_request=build_run_sync_request,
    failure_handler=lambda issue_number, reason: fail_executor_issue(
        issue_number=issue_number,
        reason=reason,
        actor="agent:run",
    ),
)
