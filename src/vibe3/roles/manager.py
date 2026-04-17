"""Manager role definition and request builder."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.environment.session_naming import get_manager_session_name
from vibe3.environment.session_registry import SessionRegistryService
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.flow_dispatch import FlowManager
from vibe3.execution.gates import apply_request_completion_gate, source_state_from_label
from vibe3.execution.issue_role_support import (
    build_issue_async_cli_request,
    build_issue_sync_prompt_request,
    build_task_flow_branch_resolver,
    resolve_orchestra_repo_root,
)
from vibe3.execution.role_contracts import MANAGER_GATE_CONFIG
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.prompts.assembler import PromptAssembler
from vibe3.prompts.models import (
    PromptRecipe,
    PromptRenderResult,
    PromptVariableSource,
    VariableSourceKind,
)
from vibe3.prompts.provider_registry import ProviderRegistry
from vibe3.prompts.template_loader import DEFAULT_PROMPTS_PATH
from vibe3.roles.definitions import IssueRoleSyncSpec, TriggerableRoleDefinition
from vibe3.runtime.no_progress_policy import snapshot_progress
from vibe3.services.abandon_flow_service import AbandonFlowService
from vibe3.services.issue_failure_service import fail_manager_issue

MANAGER_ROLE = TriggerableRoleDefinition(
    name="manager",
    registry_role="manager",
    gate_config=MANAGER_GATE_CONFIG,
    trigger_name="manager",
    trigger_state=IssueState.READY,
    status_field=None,
    dispatch_predicate=lambda _fs, has_live: not has_live,
)

HANDOFF_MANAGER_ROLE = TriggerableRoleDefinition(
    name="manager-handoff",
    registry_role="manager",
    gate_config=MANAGER_GATE_CONFIG,
    trigger_name="manager",
    trigger_state=IssueState.HANDOFF,
    status_field=None,
    dispatch_predicate=lambda _fs, has_live: not has_live,
)


def render_manager_prompt(
    config: OrchestraConfig,
    issue: IssueInfo,
    prompts_path: Path | None = None,
) -> PromptRenderResult:
    """Render manager task instructions via PromptAssembler."""
    prompts_path = prompts_path or DEFAULT_PROMPTS_PATH
    registry = ProviderRegistry()
    registry.register("manager.issue_number", lambda ctx: str(issue.number))
    registry.register("manager.issue_title", lambda ctx: issue.title)

    recipe = build_manager_recipe(config)
    assembler = PromptAssembler(prompts_path=prompts_path, registry=registry)
    return assembler.render(recipe, runtime_context={})


def build_manager_recipe(config: OrchestraConfig) -> PromptRecipe:
    """Build the PromptRecipe for manager dispatch."""
    ad = config.assignee_dispatch
    variables: dict[str, PromptVariableSource] = {
        "issue_number": PromptVariableSource(
            kind=VariableSourceKind.PROVIDER, provider="manager.issue_number"
        ),
        "issue_title": PromptVariableSource(
            kind=VariableSourceKind.PROVIDER, provider="manager.issue_title"
        ),
    }
    if ad.include_supervisor_content and ad.supervisor_file:
        variables["supervisor_content"] = PromptVariableSource(
            kind=VariableSourceKind.FILE, path=ad.supervisor_file
        )
    return PromptRecipe(
        template_key=ad.prompt_template,
        variables=variables,
        description="Manager task dispatch",
    )


def build_manager_command(
    config: OrchestraConfig,
    rendered_text: str,
) -> list[str]:
    """Build executable manager command for an issue."""
    _ = config
    cmd = ["uv", "run", "python", "-m", "vibe3", "run"]
    cmd.append("--async")
    cmd.append(rendered_text)
    return cmd


def resolve_manager_options(config: OrchestraConfig) -> Any:
    """Resolve manager agent options with env override support."""
    _backend_override = os.environ.get("VIBE3_MANAGER_BACKEND")
    _model_override = os.environ.get("VIBE3_MANAGER_MODEL") or None
    if _backend_override:
        from vibe3.models.review_runner import AgentOptions

        return AgentOptions(
            backend=_backend_override,
            model=_model_override,
        )

    from vibe3.execution.agent_resolver import resolve_manager_agent_options

    return resolve_manager_agent_options(config, VibeConfig.get_defaults())


MANAGER_BRANCH_RESOLVER = build_task_flow_branch_resolver(
    fallback_branch=lambda issue_number, _current_branch: f"task/issue-{issue_number}"
)


def build_manager_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    *,
    registry: SessionRegistryService | None = None,
    repo_path: Path | None = None,
    actor: str = "orchestra:manager",
) -> ExecutionRequest | None:
    """Build the manager execution request from declarative role policy."""
    flow_manager = FlowManager(config, registry=registry)
    try:
        flow = flow_manager.create_flow_for_issue(issue)
    except Exception as exc:
        logger.bind(
            domain="manager",
            issue_number=issue.number,
        ).warning(f"create_flow_for_issue failed: {exc}")
        return None

    if not flow:
        return None

    flow_branch = str(flow.get("branch") or "").strip()
    if not flow_branch:
        return None

    refs = {"issue_title": issue.title}
    env = dict(os.environ)
    if not env.get("VIBE3_MANAGER_BACKEND"):
        from vibe3.config.settings import VibeConfig
        from vibe3.execution.agent_resolver import resolve_manager_agent_options

        try:
            options = resolve_manager_agent_options(config, VibeConfig.get_defaults())
            if options.backend:
                env["VIBE3_MANAGER_BACKEND"] = options.backend
            if options.model:
                env["VIBE3_MANAGER_MODEL"] = options.model
        except Exception:
            pass

    request = build_issue_async_cli_request(
        role="manager",
        issue=issue,
        target_branch=flow_branch,
        command_args=["internal", "manager", str(issue.number), "--no-async"],
        actor=actor,
        execution_name=get_manager_session_name(issue.number),
        refs=refs,
        worktree_requirement=MANAGER_ROLE.gate_config.worktree,
        completion_gate=MANAGER_ROLE.gate_config.completion_contract,
        repo_path=repo_path,
    )
    if request.env is not None:
        request.env.update(env)
    return request


def build_manager_sync_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    branch: str,
    session_id: str | None,
    options: Any,
    actor: str,
    dry_run: bool,
) -> ExecutionRequest:
    """Build the manager sync execution request."""
    rendered = render_manager_prompt(config, issue)
    prompt = rendered.rendered_text
    manager_task = (
        f"Manage issue #{issue.number}: {issue.title}\n"
        "Act as the manager state controller for this issue. "
        "Inspect the scene, read issue comments and handoff, update labels/comments/"
        "handoff when allowed, and stop when the current state rule requires exit."
    )
    repo_root = Path.cwd() if session_id else Path(resolve_orchestra_repo_root())
    return build_issue_sync_prompt_request(
        role="manager",
        issue=issue,
        target_branch=branch,
        prompt=prompt,
        options=options,
        task=manager_task,
        actor=actor,
        execution_name=get_manager_session_name(issue.number),
        repo_path=repo_root,
        session_id=session_id,
        dry_run=dry_run,
        worktree_requirement=MANAGER_ROLE.gate_config.worktree,
        completion_gate=MANAGER_ROLE.gate_config.completion_contract,
    )


def handle_closed_issue_post_run(
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
    source_state = source_state_from_label(before_state_label)

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


def handle_manager_post_sync(
    store: SQLiteClient,
    issue_number: int,
    branch: str,
    actor: str,
    config: OrchestraConfig,
    before_snapshot: dict[str, object],
    after_snapshot: dict[str, object],
    request: ExecutionRequest,
) -> bool:
    """Apply manager-specific post-sync hooks and completion gates.

    Manager's responsibilities:
    1. Check if issue was closed during execution
    2. Verify MUST_CHANGE_LABEL completion gate (manager must change state label)

    Checking agent artifacts (plan_ref, report_ref, audit_ref, pr_ref) is NOT
    manager's job - each agent checks its own output via build_required_ref_sync_spec:

    - planner checks plan_ref, blocks if missing (no automatic state transition)
    - executor checks report_ref, blocks if missing (no automatic state transition)
    - reviewer checks audit_ref, blocks if missing (no automatic state transition)

    Manager checking these refs has a timing bug: manager just transitioned the state
    (e.g., handoff -> in-progress) and immediately checks the ref that the next agent
    (executor) hasn't had time to produce yet. This causes false BLOCK.

    The correct check happens in each agent's apply_required_ref_post_sync, which runs
    right after that agent completes and has the ref available.
    """

    # Record state transition if it occurred
    from vibe3.utils.constants import (
        EVENT_STATE_TRANSITIONED,
        EVENT_STATE_UNCHANGED,
    )

    before_state = before_snapshot.get("state_label")
    after_state = after_snapshot.get("state_label")
    if before_state != after_state:
        store.add_event(
            branch,
            EVENT_STATE_TRANSITIONED,
            actor,
            detail=f"State changed: {before_state} → {after_state}",
            refs={
                "before_state": str(before_state or ""),
                "after_state": str(after_state or ""),
                "issue": str(issue_number),
            },
        )
    else:
        store.add_event(
            branch,
            EVENT_STATE_UNCHANGED,
            actor,
            detail=f"State unchanged after manager: still {before_state}",
            refs={
                "state": str(before_state or ""),
                "issue": str(issue_number),
            },
        )

    # Check if issue was closed during execution
    if handle_closed_issue_post_run(
        store=store,
        issue_number=issue_number,
        branch=branch,
        actor=actor,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    ):
        return True

    # Apply completion gate (MUST_CHANGE_LABEL)
    return apply_request_completion_gate(
        request=request,
        store=store,
        repo=config.repo,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )


def snapshot_manager_progress(
    *,
    issue_number: int,
    branch: str,
    store: SQLiteClient,
    config: OrchestraConfig,
) -> dict[str, object]:
    """Capture manager progress snapshot."""
    return snapshot_progress(
        issue_number=issue_number,
        branch=branch,
        store=store,
        github=GitHubClient(),
        repo=config.repo,
    )


MANAGER_SYNC_SPEC = IssueRoleSyncSpec(
    role_name="manager",
    resolve_options=resolve_manager_options,
    resolve_branch=MANAGER_BRANCH_RESOLVER,
    build_async_request=lambda config, issue, actor: build_manager_request(
        config,
        issue,
        repo_path=resolve_orchestra_repo_root(),
        actor=actor,
    ),
    build_sync_request=build_manager_sync_request,
    snapshot_progress=lambda issue_number, branch, store, config: (
        snapshot_manager_progress(
            issue_number=issue_number,
            branch=branch,
            store=store,
            config=config,
        )
    ),
    post_sync_hook=handle_manager_post_sync,
    failure_handler=lambda issue_number, reason: fail_manager_issue(
        issue_number=issue_number,
        reason=reason,
    ),
)
