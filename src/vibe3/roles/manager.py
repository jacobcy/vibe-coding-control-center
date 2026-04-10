"""Manager role definition and request builder."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from vibe3.agents.review_runner import format_agent_actor
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.environment.session_naming import get_manager_session_name
from vibe3.environment.session_registry import SessionRegistryService
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.flow_dispatch import FlowManager
from vibe3.execution.gates import apply_request_completion_gate, source_state_from_label
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
)

HANDOFF_MANAGER_ROLE = TriggerableRoleDefinition(
    name="manager-handoff",
    registry_role="manager",
    gate_config=MANAGER_GATE_CONFIG,
    trigger_name="manager",
    trigger_state=IssueState.HANDOFF,
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

    from vibe3.runtime.agent_resolver import resolve_manager_agent_options

    return resolve_manager_agent_options(config, VibeConfig.get_defaults())


def resolve_manager_branch(
    store: SQLiteClient,
    issue_number: int,
    current_branch: str,
) -> str:
    """Resolve target branch for manager execution."""
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
    except Exception:
        return None

    flow_branch = str(flow.get("branch") or "").strip()
    if not flow_branch:
        return None

    root = (repo_path or resolve_orchestra_repo_root()).resolve()
    env = dict(os.environ)
    env["VIBE3_ASYNC_CHILD"] = "1"
    if not env.get("VIBE3_MANAGER_BACKEND"):
        from vibe3.config.settings import VibeConfig
        from vibe3.runtime.agent_resolver import resolve_manager_agent_options

        try:
            options = resolve_manager_agent_options(config, VibeConfig.get_defaults())
            if options.backend:
                env["VIBE3_MANAGER_BACKEND"] = options.backend
            if options.model:
                env["VIBE3_MANAGER_MODEL"] = options.model
        except Exception:
            pass

    return ExecutionRequest(
        role="manager",
        target_branch=flow_branch,
        target_id=issue.number,
        execution_name=get_manager_session_name(issue.number),
        cmd=[
            "uv",
            "run",
            "--project",
            str(root),
            "python",
            "-I",
            str((root / "src" / "vibe3" / "cli.py").resolve()),
            "internal",
            "manager",
            str(issue.number),
            "--no-async",
        ],
        repo_path=str(root),
        env=env,
        refs={"issue_title": issue.title},
        actor=actor,
        mode="async",
        worktree_requirement=MANAGER_ROLE.gate_config.worktree,
        completion_gate=MANAGER_ROLE.gate_config.completion_contract,
    )


def resolve_manager_launch_cwd(*, session_id: str | None) -> Path:
    """Resolve launch CWD for manager execution."""
    if session_id:
        return Path.cwd()
    git_common_dir = Path(GitClient().get_git_common_dir())
    return git_common_dir.parent


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
    return ExecutionRequest(
        role="manager",
        target_branch=branch,
        target_id=issue.number,
        execution_name=get_manager_session_name(issue.number),
        prompt=prompt,
        options=options,
        cwd=str(Path.cwd()) if session_id else None,
        repo_path=str(resolve_manager_launch_cwd(session_id=session_id)),
        refs={
            "task": manager_task,
            **({"session_id": session_id} if session_id else {}),
        },
        actor=actor,
        mode="sync",
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
    """Apply manager-specific post-sync hooks and completion gates."""
    if handle_closed_issue_post_run(
        store=store,
        issue_number=issue_number,
        branch=branch,
        actor=actor,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    ):
        return True

    return apply_request_completion_gate(
        request=request,
        store=store,
        repo=config.repo,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )


def build_manager_actor(config: OrchestraConfig) -> tuple[object, str]:
    """Resolve manager options and actor string together."""
    options = resolve_manager_options(config)
    return options, format_agent_actor(options)


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
    resolve_branch=resolve_manager_branch,
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
    failure_handler=fail_manager_issue,
)
