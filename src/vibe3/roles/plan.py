"""Planner role definition and request builders."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from vibe3.agents.models import CodeagentResult, create_codeagent_command
from vibe3.agents.plan_prompt import (
    build_plan_prompt_body,
    describe_plan_sections,
    make_plan_context_builder,
)
from vibe3.clients.github_client import GitHubClient
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.config.settings import VibeConfig
from vibe3.execution.codeagent_runner import CodeagentExecutionService
from vibe3.execution.codeagent_support import build_self_invocation
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.execution.issue_role_support import (
    build_issue_sync_spec,
    build_task_flow_branch_resolver,
    resolve_env_overridable_agent_options,
)
from vibe3.execution.prompt_meta import build_prompt_meta
from vibe3.execution.role_contracts import PLANNER_GATE_CONFIG
from vibe3.execution.role_request_factory import (
    build_role_async_request,
    build_role_sync_request,
)
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.models.plan import PlanRequest, PlanScope, PlanSpecInput
from vibe3.roles.definitions import TriggerableRoleDefinition
from vibe3.services.issue_failure_service import fail_planner_issue

PLANNER_ROLE = TriggerableRoleDefinition(
    name="planner",
    registry_role="planner",
    worktree=PLANNER_GATE_CONFIG,
    trigger_name="plan",
    trigger_state=IssueState.CLAIMED,
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
    flow_state: dict[str, object] | None,
    session_id: str | None = None,
) -> tuple[str, dict[str, str], dict[str, object], bool, str | None]:
    """Build the plan prompt body for an issue.

    Returns prompt plus refs/summary/global-notice decision for sync execution.
    """
    guidance = _build_plan_task_guidance(config, issue, branch)
    meta = build_prompt_meta(
        flow_state,
        ref_keys=("plan_ref",),
        retry_ref_keys=("plan_ref",),
        session_id=session_id,
        default_mode="first",
    )

    plan_request = PlanRequest(
        scope=PlanScope.for_task(issue.number),
        task_guidance=guidance,
    )
    prompt = build_plan_prompt_body(
        plan_request,
        VibeConfig.get_defaults(),
        mode=meta.prompt_mode,  # type: ignore[arg-type]
        context_mode=meta.context_mode,
    )
    fallback_prompt = None
    if meta.fallback_context_mode is not None:
        fallback_prompt = build_plan_prompt_body(
            plan_request,
            VibeConfig.get_defaults(),
            mode=meta.prompt_mode,  # type: ignore[arg-type]
            context_mode=meta.fallback_context_mode,
        )
    sections = describe_plan_sections(
        meta.prompt_mode,  # type: ignore[arg-type]
        meta.context_mode,
    )
    summary = meta.summary(sections)
    return prompt, meta.refs, summary, meta.include_global_notice, fallback_prompt


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
    return build_role_async_request(
        role="planner",
        config=config,
        issue=issue,
        command_args=["plan", "--branch", target_branch, "--no-async"],
        worktree_requirement=PLANNER_ROLE.worktree,
        branch=branch,
        repo_path=repo_path,
        actor=actor,
    )


def build_plan_sync_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    branch: str,
    flow_state: dict[str, object] | None,
    session_id: str | None,
    options: Any,
    actor: str,
    dry_run: bool,
    show_prompt: bool,
) -> ExecutionRequest:
    """Build the planner sync execution request."""
    from vibe3.clients.sqlite_client import SQLiteClient

    flow_state = SQLiteClient().get_flow_state(branch) if branch else None
    (
        prompt,
        extra_refs,
        dry_run_summary,
        include_global_notice,
        fallback_prompt,
    ) = build_plan_prompt(config, issue, branch, flow_state, session_id=session_id)
    task = f"Create implementation plan for issue #{issue.number}: {issue.title}"

    return build_role_sync_request(
        role="planner",
        config=config,
        issue=issue,
        branch=branch,
        prompt=prompt,
        task=task,
        options=options,
        worktree_requirement=PLANNER_ROLE.worktree,
        session_id=session_id,
        actor=actor,
        dry_run=dry_run,
        show_prompt=show_prompt,
        include_global_notice=include_global_notice,
        fallback_prompt=fallback_prompt,
        fallback_include_global_notice=True,
        extra_refs=extra_refs,
        dry_run_summary=dry_run_summary,
    )


PLAN_SYNC_SPEC = build_issue_sync_spec(
    role_name="planner",
    resolve_options=resolve_plan_options,
    resolve_branch=PLAN_BRANCH_RESOLVER,
    build_async_request=lambda config, issue, actor: build_plan_request(
        config,
        issue,
        actor=actor,
    ),
    build_sync_request=build_plan_sync_request,
    failure_handler=lambda issue_number, reason: fail_planner_issue(
        issue_number=issue_number, reason=reason
    ),
)


def resolve_spec_plan_input(
    branch: str,
    *,
    file: Path | None = None,
) -> PlanSpecInput:
    """Resolve spec planning input from file or flow spec_ref.

    Priority:
    1. Explicit --file from CLI
    2. Flow's existing spec_ref (if available)
    3. Error if none available
    """
    from vibe3.services.flow_service import FlowService
    from vibe3.services.spec_ref_service import SpecRefService

    # Case 1: Explicit file provided
    if file:
        if not file.exists():
            raise FileNotFoundError(f"File not found: {file}")
        description = file.read_text(encoding="utf-8")
        spec_path: str | None = str(file.resolve())
        request = PlanRequest(scope=PlanScope.for_spec(description))
        return PlanSpecInput(
            branch=branch,
            request=request,
            description=description,
            spec_path=spec_path,
        )

    # Case 2: Try flow's spec_ref as default
    flow_service = FlowService()
    flow = flow_service.get_flow_status(branch)

    if flow and flow.spec_ref:
        spec_service = SpecRefService()
        spec_info = spec_service.parse_spec_ref(flow.spec_ref)

        # Validate spec_ref exists
        is_valid, error = spec_service.validate_spec_ref(flow.spec_ref)
        if not is_valid:
            raise ValueError(f"Flow spec_ref invalid: {error}")

        # Get spec content
        spec_content = spec_service.get_spec_content_for_prompt(spec_info)
        if not spec_content:
            raise ValueError(f"Failed to read spec content from {flow.spec_ref}")

        # Determine spec_path based on kind
        spec_path = (
            spec_info.file_path if spec_info.kind == "file" else None
        )  # Already defined with str | None type in Case 1

        request = PlanRequest(scope=PlanScope.for_spec(spec_content))
        return PlanSpecInput(
            branch=branch,
            request=request,
            description=spec_content,
            spec_path=spec_path,
        )

    # Case 3: No spec available
    raise ValueError(
        "No spec provided.\n"
        "Use one of:\n"
        "  vibe flow bind <issue> --role task # Bind issue as spec\n"
        "  vibe flow update --spec <file>    # Bind spec file to flow\n"
        "  vibe3 plan spec --file <path>     # From spec file (replaces current spec)\n"
        "Or ensure flow has an existing spec_ref."
    )


def execute_spec_plan_async(
    *,
    request: PlanRequest,
    issue_number: int | None,
    branch: str,
    cli_args: list[str],
    config: VibeConfig | None = None,
) -> CodeagentResult:
    """Execute spec plan in async mode (tmux wrapper).

    ``request`` and ``config`` are intentionally unused: async mode re-invokes
    the CLI via ``cli_args`` inside a tmux session, so all configuration is
    re-resolved from scratch by the child process. Passing a custom ``request``
    or ``config`` here has no effect.
    """
    _ = request, config
    from vibe3.clients.sqlite_client import SQLiteClient

    launch = ExecutionCoordinator(
        load_orchestra_config(),
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
                {"issue_number": str(issue_number)} if issue_number is not None else {}
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


def execute_spec_plan_sync(
    *,
    request: PlanRequest,
    issue_number: int | None,
    branch: str,
    config: VibeConfig | None = None,
) -> CodeagentResult:
    """Execute spec plan in sync mode (direct execution)."""
    cfg = config or VibeConfig.get_defaults()
    command = create_codeagent_command(
        role="planner",
        context_builder=make_plan_context_builder(request, cfg),
        task=request.task_guidance,
        handoff_kind="plan",
        branch=branch,
        issue_number=issue_number,
        cwd=Path.cwd(),
        config=cfg,
    )
    return CodeagentExecutionService(cfg).execute_sync(command)
