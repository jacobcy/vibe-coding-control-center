"""Planner role definition and request builders."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from vibe3.agents import (
    CodeagentResult,
    build_plan_prompt_body,
    create_codeagent_command,
    describe_plan_sections,
    make_plan_context_builder,
)
from vibe3.clients import GitHubClient
from vibe3.config import (
    PLANNER_GATE_CONFIG,
    VibeConfig,
    get_convention,
    load_orchestra_config,
    load_runtime_config,
)
from vibe3.execution import (
    CodeagentExecutionService,
    ExecutionCoordinator,
    build_prompt_meta,
    build_role_async_request,
    build_role_sync_request,
    build_self_invocation,
    build_task_flow_branch_resolver,
    resolve_env_overridable_agent_options,
)
from vibe3.models import (
    AgentOptions,
    ExecutionRequest,
    IssueInfo,
    IssueState,
    OrchestraConfig,
    PlanRequest,
    PlanScope,
    PlanSpecInput,
    WorktreeRequirement,
)
from vibe3.observability import write_prompt_provenance
from vibe3.prompts import (
    PromptManifest,
    collect_dry_run_provenance,
    discover_project_scope_overlays,
)
from vibe3.roles.definitions import (
    IssueRoleSyncSpec,
    RoleOutputContract,
    TriggerableRoleDefinition,
)
from vibe3.services.issue import fail_planner_issue
from vibe3.services.orchestra import record_dispatch_failure_if_unexpected

PLANNER_ROLE = TriggerableRoleDefinition(
    name="planner",
    registry_role="planner",
    worktree=PLANNER_GATE_CONFIG,
    trigger_name="plan",
    trigger_state=IssueState.CLAIMED,
    output_contract=RoleOutputContract(required_ref="plan_ref"),
)


def resolve_plan_options(
    config: OrchestraConfig,
    cli_overrides: dict[str, str] | None = None,
) -> Any:
    """Resolve planner agent options with env override support."""
    runtime_config = load_runtime_config(cli_overrides=cli_overrides)
    return resolve_env_overridable_agent_options(
        backend_env_key="VIBE3_PLANNER_BACKEND",
        model_env_key="VIBE3_PLANNER_MODEL",
        fallback_resolver=lambda: AgentOptions(
            agent=runtime_config.plan.agent_config.agent,
            backend=(
                runtime_config.plan.agent_config.backend
                if not runtime_config.plan.agent_config.agent
                else None
            ),
            model=(
                runtime_config.plan.agent_config.model
                if not runtime_config.plan.agent_config.agent
                else None
            ),
            timeout_seconds=runtime_config.plan.agent_config.timeout_seconds,
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
    from vibe3.services.flow import FlowService
    from vibe3.services.shared import SpecRefService

    flow_service = FlowService()
    flow = flow_service.get_flow_status(branch)
    if not flow:
        return None

    sections: list[str] = []

    # Issue context
    from vibe3.clients import GITHUB_FIELDS_BODY_COMMENTS

    issue_payload = GitHubClient().view_issue(
        issue.number, repo=config.repo, fields=list(GITHUB_FIELDS_BODY_COMMENTS)  # type: ignore[call-overload]
    )
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
        spec_content = spec_service.get_spec_content_for_prompt(
            spec_info, branch=branch
        )
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
    prompts_path: Path | None = None,
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
        prompts_path=prompts_path,
    )
    fallback_prompt = None
    if meta.fallback_context_mode is not None:
        fallback_prompt = build_plan_prompt_body(
            plan_request,
            VibeConfig.get_defaults(),
            mode=meta.prompt_mode,  # type: ignore[arg-type]
            context_mode=meta.fallback_context_mode,
            prompts_path=prompts_path,
        )
    sections = describe_plan_sections(
        meta.prompt_mode,  # type: ignore[arg-type]
        meta.context_mode,
        prompts_path=prompts_path,
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
    tick_id: int = 0,
) -> ExecutionRequest:
    """Build the planner async execution request for dispatch."""
    convention = get_convention()
    target_branch = branch or convention.branch.canonical_branch(issue.number)
    return build_role_async_request(
        role="planner",
        config=config,
        issue=issue,
        command_args=[
            "plan",
            "--branch",
            target_branch,
            "--no-async",
        ],
        worktree_requirement=PLANNER_ROLE.worktree,
        branch=branch,
        repo_path=repo_path,
        actor=actor,
        tick_id=tick_id,
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
    tick_id: int = 0,
    prompts_path: Path | None = None,
) -> ExecutionRequest:
    """Build the planner sync execution request."""
    from vibe3.clients import SQLiteClient

    flow_state = SQLiteClient().get_flow_state(branch) if branch else None
    (
        prompt,
        extra_refs,
        dry_run_summary,
        include_global_notice,
        fallback_prompt,
    ) = build_plan_prompt(
        config,
        issue,
        branch,
        flow_state,
        session_id=session_id,
        prompts_path=prompts_path,
    )

    # Collect and write provenance for dry-run audit
    if dry_run:
        meta = build_prompt_meta(
            flow_state,
            ref_keys=("plan_ref",),
            retry_ref_keys=("plan_ref",),
            session_id=session_id,
            default_mode="first",
        )
        # Determine variant_key: {mode}.{context_mode}
        # e.g., "first.bootstrap", "retry.bootstrap", "retry.resume"
        variant_key = f"{meta.prompt_mode}.{meta.context_mode}"

        manifest = PromptManifest.load_for_prompts_path(prompts_path)
        provenance = collect_dry_run_provenance(
            manifest=manifest,
            recipe_key="plan.default",
            variant_key=variant_key,
            rendered_text=prompt,
        )
        provenance_path = write_prompt_provenance(
            provenance, role="planner", issue_number=issue.number
        )
        # Add provenance path and project-scope overlays to dry_run_summary
        if dry_run_summary:
            dry_run_summary["provenance_path"] = str(provenance_path)
            overlays = discover_project_scope_overlays()
            if overlays:
                dry_run_summary["project_scope_overlays"] = overlays

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
        tick_id=tick_id,
    )


PLAN_SYNC_SPEC = IssueRoleSyncSpec(
    role_name="planner",
    resolve_options=resolve_plan_options,
    resolve_branch=PLAN_BRANCH_RESOLVER,
    build_async_request=lambda config, issue, actor, branch: build_plan_request(
        config,
        issue,
        branch=branch,
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
    from vibe3.services.flow import FlowService
    from vibe3.services.shared import SpecRefService

    # Case 1: Explicit file provided
    if file:
        if not file.exists():
            raise FileNotFoundError(f"File not found: {file}")
        description = file.read_text(encoding="utf-8")
        spec_path: str | None = str(file.resolve())
        request = PlanRequest(
            scope=PlanScope.for_spec(description),
            task_guidance=(
                "Create an implementation plan for this specification:\n\n"
                f"{description}"
            ),
        )
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
        is_valid, error = spec_service.validate_spec_ref(flow.spec_ref, branch=branch)
        if not is_valid:
            raise ValueError(f"Flow spec_ref invalid: {error}")

        # Get spec content
        spec_content = spec_service.get_spec_content_for_prompt(
            spec_info, branch=branch
        )
        if not spec_content:
            raise ValueError(f"Failed to read spec content from {flow.spec_ref}")

        # Determine spec_path based on kind
        spec_path = (
            spec_info.file_path if spec_info.kind == "file" else None
        )  # Already defined with str | None type in Case 1

        request = PlanRequest(
            scope=PlanScope.for_spec(spec_content),
            task_guidance=(
                "Create an implementation plan for this specification:\n\n"
                f"{spec_content}"
            ),
        )
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
        "  vibe3 plan --spec <path>          # Override flow spec_ref with file\n"
        "Or ensure flow has an existing spec_ref."
    )


def _resolve_spec_ref(branch: str) -> str | None:
    """Get spec_ref from flow state, or None if unavailable."""
    from vibe3.services.flow import FlowService

    try:
        flow = FlowService().get_flow_status(branch)
        if flow and flow.spec_ref:
            return flow.spec_ref
    except Exception:
        pass
    return None


def execute_spec_plan_async(
    *,
    request: PlanRequest,
    issue_number: int | None,
    branch: str,
    cli_args: list[str],
    agent: str | None = None,
    backend: str | None = None,
    model: str | None = None,
    fresh_session: bool = False,
    config: VibeConfig | None = None,
) -> CodeagentResult:
    """Execute spec plan in async mode (tmux wrapper).

    ``request`` and ``config`` are intentionally unused: async mode re-invokes
    the CLI via ``cli_args`` inside a tmux session, so all configuration is
    re-resolved from scratch by the child process. Passing a custom ``request``
    or ``config`` here has no effect.

    ``agent``, ``backend``, ``model``, and ``fresh_session`` are also unused here
    because they should already be included in ``cli_args`` by the caller.
    """
    _ = request, config, agent, backend, model, fresh_session
    from vibe3.clients import SQLiteClient

    # Resolve repo path from git common dir (main repo root)
    from vibe3.execution import resolve_orchestra_repo_root

    repo_root = resolve_orchestra_repo_root()

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
            cwd=None,  # Let coordinator resolve worktree path
            repo_path=str(repo_root),
            worktree_requirement=WorktreeRequirement.PERMANENT,
            env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
            refs=(
                {"issue_number": str(issue_number)} if issue_number is not None else {}
            ),
            actor="agent:plan",
            mode="async",
        )
    )
    record_dispatch_failure_if_unexpected(
        result=launch,
        role="planner",
        issue_number=issue_number,
        branch=branch,
    )

    spec_ref = _resolve_spec_ref(branch)

    return CodeagentResult(
        success=launch.launched,
        stderr=launch.reason or "",
        tmux_session=launch.tmux_session,
        log_path=launch.log_path,
        backend=launch.backend,
        model=launch.model,
        issue_number=issue_number,
        spec_ref=spec_ref,
    )


def execute_spec_plan_sync(
    *,
    request: PlanRequest,
    issue_number: int | None,
    branch: str,
    agent: str | None = None,
    backend: str | None = None,
    model: str | None = None,
    fresh_session: bool = False,
    config: VibeConfig | None = None,
    dry_run: bool = False,
    show_prompt: bool = False,
) -> CodeagentResult:
    """Execute spec plan in sync mode (direct execution)."""
    from vibe3.execution import build_prompt_meta, load_session_id

    cfg = config or VibeConfig.get_defaults()
    session_id = None if fresh_session else load_session_id("planner", branch)

    dry_run_summary: dict[str, Any] | None = None
    if dry_run:
        meta = build_prompt_meta(
            None,
            ref_keys=("plan_ref",),
            retry_ref_keys=("plan_ref",),
            session_id=session_id,
            default_mode="first",
        )
        sections = describe_plan_sections(
            meta.prompt_mode,  # type: ignore[arg-type]
            meta.context_mode,  # type: ignore[arg-type]
        )
        dry_run_summary = meta.summary(sections)
        overlays = discover_project_scope_overlays()
        if overlays:
            dry_run_summary["project_scope_overlays"] = overlays

    # In dry_run without show_prompt, use a short task label to avoid
    # cluttering the output with the full issue body.
    task_label: str | None
    if dry_run and not show_prompt and issue_number is not None:
        task_label = f"issue: #{issue_number}"
    else:
        task_label = request.task_guidance

    command = create_codeagent_command(
        role="planner",
        context_builder=make_plan_context_builder(
            request, cfg, annotate_sections=dry_run
        ),
        task=task_label,
        dry_run=dry_run,
        show_prompt=show_prompt,
        handoff_kind="plan",
        branch=branch,
        issue_number=issue_number,
        cwd=None,  # Sync execution uses agent's built-in cwd resolution
        config=cfg,
        agent=agent,
        backend=backend,
        model=model,
        session_id=session_id,
        dry_run_summary=dry_run_summary,
    )
    result = CodeagentExecutionService(cfg).execute_sync(command)

    result.spec_ref = _resolve_spec_ref(branch)

    return result
