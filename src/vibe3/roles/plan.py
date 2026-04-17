"""Planner role definition and request builders."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from vibe3.agents.models import CodeagentResult, create_codeagent_command
from vibe3.agents.plan_prompt import build_plan_prompt_body, make_plan_context_builder
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.execution.codeagent_runner import CodeagentExecutionService
from vibe3.execution.codeagent_support import build_self_invocation
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.execution.issue_role_support import (
    build_issue_async_cli_request,
    build_issue_sync_prompt_request,
    build_required_ref_sync_spec,
    build_task_flow_branch_resolver,
    resolve_env_overridable_agent_options,
)
from vibe3.execution.role_contracts import PLANNER_GATE_CONFIG
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.models.plan import PlanRequest, PlanScope, PlanSpecInput
from vibe3.roles.definitions import TriggerableRoleDefinition
from vibe3.services.issue_failure_service import (
    block_planner_noop_issue,
    fail_planner_issue,
)

PLANNER_ROLE = TriggerableRoleDefinition(
    name="planner",
    registry_role="planner",
    gate_config=PLANNER_GATE_CONFIG,
    trigger_name="plan",
    trigger_state=IssueState.CLAIMED,
    status_field="planner_status",
    dispatch_predicate=lambda fs, live: not fs.get("plan_ref") and not live,
)


def resolve_plan_options(config: OrchestraConfig) -> Any:
    """Resolve planner agent options with env override support."""
    from vibe3.execution.agent_resolver import resolve_planner_agent_options

    return resolve_env_overridable_agent_options(
        backend_env_key="VIBE3_PLANNER_BACKEND",
        model_env_key="VIBE3_PLANNER_MODEL",
        fallback_resolver=lambda: resolve_planner_agent_options(
            config, VibeConfig.get_defaults()
        ),
    )


PLAN_BRANCH_RESOLVER = build_task_flow_branch_resolver(
    fallback_branch=lambda _issue_number, current_branch: current_branch
)


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
    target_branch = branch or f"task/issue-{issue.number}"
    return build_issue_async_cli_request(
        role="planner",
        issue=issue,
        target_branch=target_branch,
        command_args=["plan", "--issue", str(issue.number), "--no-async"],
        actor=actor,
        execution_name=f"vibe3-planner-issue-{issue.number}",
        refs={"issue_number": str(issue.number)},
        worktree_requirement=PLANNER_ROLE.gate_config.worktree,
        completion_gate=PLANNER_ROLE.gate_config.completion_contract,
        repo_path=repo_path,
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

    return build_issue_sync_prompt_request(
        role="planner",
        issue=issue,
        target_branch=branch,
        prompt=prompt,
        options=options,
        task=task,
        actor=actor,
        execution_name=f"vibe3-planner-issue-{issue.number}",
        session_id=session_id,
        dry_run=dry_run,
        worktree_requirement=PLANNER_ROLE.gate_config.worktree,
        completion_gate=PLANNER_ROLE.gate_config.completion_contract,
    )


PLAN_SYNC_SPEC = build_required_ref_sync_spec(
    role_name="planner",
    resolve_options=resolve_plan_options,
    resolve_branch=PLAN_BRANCH_RESOLVER,
    build_async_request=lambda config, issue, actor: build_plan_request(
        config,
        issue,
        actor=actor,
    ),
    build_sync_request=build_plan_sync_request,
    required_ref="plan_ref",
    missing_reason="Planner completed without producing plan_ref",
    missing_ref_handler=block_planner_noop_issue,
    failure_handler=lambda issue_number, reason: fail_planner_issue(
        issue_number=issue_number, reason=reason
    ),
    # No success_handler: agent must transition state or get blocked.
    # See docs/standards/vibe3-noop-gate-boundary-standard.md
)


def resolve_spec_plan_input(
    branch: str,
    *,
    file: Path | None = None,
    msg: str | None = None,
) -> PlanSpecInput:
    """Resolve spec planning input from file or inline message."""
    if file and msg:
        raise ValueError("Provide either --file or --msg, not both.")
    if not file and not msg:
        raise ValueError("Provide either --file or --msg.")

    if file:
        if not file.exists():
            raise FileNotFoundError(f"File not found: {file}")
        description = file.read_text(encoding="utf-8")
        spec_path = str(file.resolve())
    else:
        description = msg or ""
        spec_path = None

    request = PlanRequest(scope=PlanScope.for_spec(description))
    return PlanSpecInput(
        branch=branch,
        request=request,
        description=description,
        spec_path=spec_path,
    )


def bind_plan_spec(branch: str, spec_path: str) -> None:
    """Bind resolved spec path to current flow."""
    from vibe3.services.flow_service import FlowService

    FlowService().bind_spec(branch, spec_path, "user")


def execute_spec_plan(
    *,
    request: PlanRequest,
    issue_number: int | None,
    branch: str,
    async_mode: bool = True,
    cli_args: list[str] | None = None,
    config: VibeConfig | None = None,
) -> CodeagentResult:
    """Execute spec-mode planning using the shared execution shell."""
    cfg = config or VibeConfig.get_defaults()
    command = create_codeagent_command(
        role="planner",
        context_builder=make_plan_context_builder(request, cfg),
        task=request.task_guidance,
        handoff_kind="plan",
        branch=branch,
        cwd=Path.cwd(),
        config=cfg,
    )

    if async_mode:
        if cli_args is None:
            raise ValueError("Async plan execution requires explicit cli_args")
        launch = ExecutionCoordinator(
            OrchestraConfig.from_settings(),
            SQLiteClient(),
        ).dispatch_execution(
            ExecutionRequest(
                role="planner",
                target_branch=branch,
                target_id=issue_number or 0,
                execution_name=(
                    f"vibe3-planner-issue-{issue_number}"
                    if issue_number is not None
                    else f"vibe3-planner-{branch.replace('/', '-')}"
                ),
                cmd=build_self_invocation(cli_args),
                cwd=str(Path.cwd()),
                env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
                refs=(
                    {"issue_number": str(issue_number)}
                    if issue_number is not None
                    else {}
                ),
                actor="agent:plan",
                mode="async",
            )
        )
        return CodeagentResult(
            success=launch.launched,
            stderr=launch.reason or "",
            tmux_session=launch.tmux_session,
            log_path=Path(launch.log_path) if launch.log_path else None,
        )

    result = CodeagentExecutionService(cfg).execute_sync(command)
    if issue_number is None:
        return result
    if result.success:
        publish_plan_command_success(issue_number=issue_number, branch=branch)
    else:
        publish_plan_command_failure(
            issue_number=issue_number,
            reason=result.stderr or "Plan execution failed",
        )
    return result


def publish_plan_command_success(*, issue_number: int, branch: str) -> None:
    """Publish plan completion event for command-mode execution."""
    from vibe3.domain.events import PlanCompleted
    from vibe3.domain.publisher import publish

    publish(
        PlanCompleted(
            issue_number=issue_number,
            branch=branch,
            actor="agent:plan",
        )
    )


def publish_plan_command_failure(*, issue_number: int, reason: str) -> None:
    """Publish plan failure event for command-mode execution."""
    from vibe3.domain.events import IssueFailed
    from vibe3.domain.publisher import publish

    publish(
        IssueFailed(
            issue_number=issue_number,
            reason=reason,
            actor="agent:plan",
        )
    )
