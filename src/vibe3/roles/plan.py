"""Planner role definition and request builders."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from vibe3.agents.plan_prompt import build_plan_prompt_body
from vibe3.agents.review_runner import format_agent_actor
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.gates import apply_request_completion_gate
from vibe3.execution.role_contracts import PLANNER_GATE_CONFIG
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.models.plan import PlanRequest, PlanScope
from vibe3.roles.definitions import IssueRoleSyncSpec, TriggerableRoleDefinition
from vibe3.runtime.no_progress_policy import snapshot_progress
from vibe3.services.issue_failure_service import block_planner_noop_issue

PLANNER_ROLE = TriggerableRoleDefinition(
    name="planner",
    registry_role="planner",
    gate_config=PLANNER_GATE_CONFIG,
    trigger_name="plan",
    trigger_state=IssueState.CLAIMED,
    status_field="planner_status",
    dispatch_predicate=lambda fs, live: not fs.get("plan_ref") and not live,
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


def resolve_plan_options(config: OrchestraConfig) -> Any:
    """Resolve planner agent options with env override support."""
    _backend_override = os.environ.get("VIBE3_PLANNER_BACKEND")
    _model_override = os.environ.get("VIBE3_PLANNER_MODEL") or None
    if _backend_override:
        from vibe3.models.review_runner import AgentOptions

        return AgentOptions(
            backend=_backend_override,
            model=_model_override,
        )

    from vibe3.runtime.agent_resolver import resolve_planner_agent_options

    return resolve_planner_agent_options(config, VibeConfig.get_defaults())


def resolve_plan_branch(
    store: SQLiteClient,
    issue_number: int,
    current_branch: str,
) -> str:
    """Resolve target branch for planner execution."""
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


def _build_plan_task_guidance(
    config: OrchestraConfig,
    issue: IssueInfo,
    branch: str,
) -> str | None:
    """Build plan task guidance from flow and issue context."""
    from vibe3.services.flow_service import FlowService
    from vibe3.services.spec_ref_service import SpecRefService

    flow_service = FlowService()
    flow = flow_service.get_flow_status(branch)
    if not flow:
        return None

    sections: list[str] = []

    # Issue context
    issue_payload = GitHubClient().view_issue(issue.number, repo=config.repo)
    if isinstance(issue_payload, dict):
        title = issue_payload.get("title")
        body = issue_payload.get("body")
        parts = ["## Task Issue Context", f"Issue: #{issue.number}"]
        if title:
            parts.append(f"Title: {title}")
        if body:
            parts.extend(["", str(body)])
        sections.append("\n".join(parts))

    # Spec context
    spec_ref = getattr(flow, "spec_ref", None)
    if spec_ref:
        spec_service = SpecRefService()
        spec_info = spec_service.parse_spec_ref(spec_ref)
        spec_content = spec_service.get_spec_content_for_prompt(spec_info)
        if spec_info.display and spec_info.display != spec_ref:
            sections.append(f"## Spec Reference\nSpec Ref: {spec_info.display}")
        if spec_content:
            sections.append(f"## Spec Context\n{spec_content}")

    return "\n\n".join(sections) if sections else None


def build_plan_prompt(
    config: OrchestraConfig,
    issue: IssueInfo,
    branch: str,
) -> str:
    """Build the plan prompt body for an issue."""
    guidance = _build_plan_task_guidance(config, issue, branch)
    plan_request = PlanRequest(
        scope=PlanScope.for_task(issue.number),
        task_guidance=guidance,
    )
    return build_plan_prompt_body(plan_request, VibeConfig.get_defaults())


def build_plan_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    *,
    branch: str | None = None,
    repo_path: Path | None = None,
    actor: str = "orchestra:planner",
) -> ExecutionRequest:
    """Build the planner async execution request for dispatch."""
    _ = config  # interface-compatible; repo resolved from repo_path or git common dir
    root = (repo_path or resolve_orchestra_repo_root()).resolve()
    target_branch = branch or f"task/issue-{issue.number}"

    env = dict(os.environ)
    env["VIBE3_ASYNC_CHILD"] = "1"

    return ExecutionRequest(
        role="planner",
        target_branch=target_branch,
        target_id=issue.number,
        execution_name=f"vibe3-planner-issue-{issue.number}",
        cmd=[
            "uv",
            "run",
            "--project",
            str(root),
            "python",
            "-I",
            str((root / "src" / "vibe3" / "cli.py").resolve()),
            "plan",
            "--issue",
            str(issue.number),
            "--no-async",
        ],
        repo_path=str(root),
        env=env,
        refs={"issue_number": str(issue.number)},
        actor=actor,
        mode="async",
        worktree_requirement=PLANNER_ROLE.gate_config.worktree,
        completion_gate=PLANNER_ROLE.gate_config.completion_contract,
    )


def build_plan_sync_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    branch: str,
    session_id: str | None,
    options: Any,
    actor: str,
    dry_run: bool,
) -> ExecutionRequest:
    """Build the planner sync execution request."""
    prompt = build_plan_prompt(config, issue, branch)
    task = f"Create implementation plan for issue #{issue.number}: {issue.title}"

    return ExecutionRequest(
        role="planner",
        target_branch=branch,
        target_id=issue.number,
        execution_name=f"vibe3-planner-issue-{issue.number}",
        prompt=prompt,
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
        worktree_requirement=PLANNER_ROLE.gate_config.worktree,
        completion_gate=PLANNER_ROLE.gate_config.completion_contract,
    )


def handle_plan_post_sync(
    store: SQLiteClient,
    issue_number: int,
    _branch: str,
    actor: str,
    config: OrchestraConfig,
    before_snapshot: dict[str, object],
    after_snapshot: dict[str, object],
    request: ExecutionRequest,
) -> bool:
    """Apply planner-specific post-sync hooks and completion gates."""
    # Check if planner produced plan_ref
    before_refs = before_snapshot.get("refs")
    after_refs = after_snapshot.get("refs")
    if isinstance(before_refs, dict) and isinstance(after_refs, dict):
        before_plan = before_refs.get("plan_ref")
        after_plan = after_refs.get("plan_ref")
        if not before_plan and not after_plan:
            block_planner_noop_issue(
                issue_number=issue_number,
                reason="Planner completed without producing plan_ref",
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


def handle_plan_failure(
    issue_number: int,
    reason: str,
) -> None:
    """Handle planner execution failure."""
    from vibe3.services.issue_failure_service import fail_planner_issue

    fail_planner_issue(issue_number=issue_number, reason=reason)


def snapshot_plan_progress(
    *,
    issue_number: int,
    branch: str,
    store: SQLiteClient,
    config: OrchestraConfig,
) -> dict[str, object]:
    """Capture planner progress snapshot."""
    return snapshot_progress(
        issue_number=issue_number,
        branch=branch,
        store=store,
        github=GitHubClient(),
        repo=config.repo,
    )


def build_plan_actor(config: OrchestraConfig) -> tuple[Any, str]:
    """Resolve planner options and actor string together."""
    options = resolve_plan_options(config)
    return options, format_agent_actor(options)


PLAN_SYNC_SPEC = IssueRoleSyncSpec(
    role_name="planner",
    resolve_options=resolve_plan_options,
    resolve_branch=resolve_plan_branch,
    build_async_request=lambda config, issue, actor: build_plan_request(
        config,
        issue,
        actor=actor,
    ),
    build_sync_request=build_plan_sync_request,
    snapshot_progress=lambda issue_number, branch, store, config: (
        snapshot_plan_progress(
            issue_number=issue_number,
            branch=branch,
            store=store,
            config=config,
        )
    ),
    post_sync_hook=handle_plan_post_sync,
    failure_handler=lambda issue_number, reason: handle_plan_failure(
        issue_number=issue_number,
        reason=reason,
    ),
)
