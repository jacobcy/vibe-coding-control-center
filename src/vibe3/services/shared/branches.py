"""Branch resolution utilities for CLI commands.

Consolidates branch argument resolution, PR-to-branch mapping, and
issue number resolution with conflict detection.
"""

import shutil
from collections.abc import Iterable, Mapping
from typing import Any

import typer

from vibe3.clients.github_client import GitHubClient
from vibe3.exceptions import UserError
from vibe3.services.convention_resolver import ConventionResolver
from vibe3.services.flow_service import FlowService


# ============================================================================
# Issue Branch Resolution
# ============================================================================


def iter_issue_branch_candidates(issue_number: int) -> Iterable[str]:
    """Yield supported branch candidates for an issue number."""
    resolver = ConventionResolver.from_repo()
    convention = resolver.resolve()
    yield convention.branch.canonical_branch(issue_number)
    yield convention.branch.dev_branch(issue_number)


def resolve_issue_branch_input(
    branch: str | None,
    flow_service: Any,
    *,
    allow_no_flow: bool = False,
) -> str | None:
    """Resolve numeric issue input with conflict detection.

    Changes from original:
    - Uses get_flows_by_issue() for bound flows first
    - Conflict detection for multiple active flows
    - Smart warnings for unbound or aborted candidates

    Args:
        branch: User input (branch name or issue number)
        flow_service: FlowService instance
        allow_no_flow: If True, return None instead of raising UserError
            when no flows exist at all (Step 5). All other error paths
            (conflict, all-aborted, unbound-candidates) still raise.

    Returns:
        Resolved branch name, or None if allow_no_flow=True and no flows exist

    Raises:
        UserError: When conflicts or missing flows detected
    """
    # Step 1: Check input type and normalize
    if branch is None:
        return None

    stripped = branch.strip()
    if not stripped.isdigit():
        return stripped

    issue_number = int(stripped)
    store = getattr(flow_service, "store")

    # Step 2: Query flows with issue binding
    candidates = store.get_flows_by_issue(issue_number, role="task")

    if candidates:
        # Step 3: Resolve with conflict detection
        return _resolve_best_flow_from_candidates(candidates, issue_number)

    # Step 4: Check unbound candidates (smart warning)
    unbound_candidates = []
    for candidate in iter_issue_branch_candidates(issue_number):
        state = store.get_flow_state(candidate)
        if isinstance(state, Mapping):
            unbound_candidates.append(state)

    if unbound_candidates:
        # Smart warning: has candidates but no binding
        details = "\n  - ".join(_format_flow_details(f) for f in unbound_candidates)
        raise UserError(
            f"Found flow(s) for issue #{issue_number} "
            f"candidates but without task binding:\n"
            f"  - {details}\n\n"
            f"Use 'vibe3 flow bind {issue_number} --role task' to link the issue."
        )

    # Step 5: No flows at all
    if allow_no_flow:
        return None
    raise UserError(
        f"No flow found for issue #{issue_number}. "
        f"Use '/vibe-new issue {issue_number}' to create a flow.\n"
        f"提示：如果是 PR 号，请使用 --pr {issue_number}"
    )


def _format_flow_details(flow: Mapping[str, Any]) -> str:
    """Format single flow details: branch (status: X, pr: Y).

    Args:
        flow: Flow state dict from database

    Returns:
        Human-readable string like "dev/issue-976 (status: active, pr: #990)"
    """
    branch = flow.get("branch", "unknown")
    status = flow.get("flow_status", "unknown")

    # PR info: check pr_ref or derive from pr_number
    pr_ref = flow.get("pr_ref")
    if isinstance(pr_ref, str) and pr_ref:
        # Extract PR number from URL (e.g., "https://github.com/.../pull/990")
        pr_number = pr_ref.split("/")[-1]
        pr_info = f"pr: #{pr_number}"
    else:
        pr_info = "pr: none"

    return f"{branch} (status: {status}, {pr_info})"


def _resolve_best_flow_from_candidates(
    candidates: list[dict[str, Any]],
    issue_number: int,
) -> str:
    """Select best flow or raise UserError for conflicts.

    Args:
        candidates: List of flow dicts from get_flows_by_issue()
        issue_number: Issue number being resolved
    Returns:
        Selected branch name

    Raises:
        UserError: When multiple active flows conflict or all aborted
    """
    # Priority 1: Non-aborted flows
    non_aborted = [f for f in candidates if f["flow_status"] != "aborted"]

    if len(non_aborted) == 1:
        # Auto-select the only non-aborted flow
        return str(non_aborted[0]["branch"])

    # Priority 2: Check for multiple active flows (conflict)
    active = [f for f in candidates if f["flow_status"] == "active"]

    if len(active) > 1:
        # Conflict: multiple active flows
        details = "\n  - ".join(_format_flow_details(f) for f in active)
        raise UserError(
            f"Multiple active flows detected for issue #{issue_number}:\n"
            f"  - {details}\n\n"
            f"Use 'vibe3 flow abort <branch>' to resolve the conflict."
        )

    # Priority 3: Single active flow among multiple non-aborted
    if len(active) == 1:
        return str(active[0]["branch"])

    # Priority 4: All flows are aborted
    if not non_aborted and candidates:
        details = "\n  - ".join(_format_flow_details(f) for f in candidates)
        raise UserError(
            f"All flows for issue #{issue_number} are aborted:\n"
            f"  - {details}\n\n"
            f"Use 'vibe3 flow restore <branch>' to reactivate a flow."
        )

    # Fallback: Should not reach here if candidates is non-empty
    return str(candidates[0]["branch"])


# ============================================================================
# PR Branch Resolution
# ============================================================================


def resolve_branch_from_pr(
    pr_number: int,
    *,
    github_client: GitHubClient | None = None,
) -> str:
    """Resolve branch name from PR number.

    Args:
        pr_number: PR number (e.g., 1183)
        github_client: Optional GitHub client (for testing)

    Returns:
        Branch name (e.g., "dev/issue-476")

    Raises:
        UserError: If PR not found or inaccessible
    """
    if not shutil.which("gh"):
        raise UserError(
            "gh CLI 未安装或不在 PATH 中，无法查询 PR。\n"
            "请安装 GitHub CLI: https://cli.github.com"
        )

    client = github_client or GitHubClient()

    try:
        pr = client.get_pr(pr_number)
    except FileNotFoundError as e:
        raise UserError(
            f"无法获取 PR #{pr_number}: gh CLI 不可用。\n"
            f"请确认 GitHub CLI 已正确安装。"
        ) from e
    except Exception as e:
        raise UserError(
            f"无法获取 PR #{pr_number}: {e}\n"
            f"请检查 PR 编号是否正确或网络连接是否正常。"
        ) from e

    if not pr:
        raise UserError(
            f"PR #{pr_number} 不存在或无法访问。\n"
            f"请确认 PR 编号是否正确，以及是否有仓库访问权限。"
        )

    branch = pr.head_branch
    if not branch:
        raise UserError(f"无法从 PR #{pr_number} 获取分支名。")

    return branch


# ============================================================================
# Unified Command Branch Resolution
# ============================================================================


def resolve_command_branch(
    *,
    branch_opt: str | None = None,
    pr_opt: int | None = None,
    position_arg: str | None = None,
    flow_service: FlowService,
    github_client: GitHubClient | None = None,
    allow_no_flow: bool = False,
    canonical_fallback: bool = False,
) -> str:
    """Unified branch resolution for flow/handoff/task commands.

    Priority order:
    1. --branch <value> (explicit, highest priority)
    2. --pr <number> (resolve PR → branch)
    3. <position-arg> (may be issue number or branch name)
    4. current branch (fallback)

    Args:
        branch_opt: Value from --branch option
        pr_opt: Value from --pr option
        position_arg: Positional argument (issue/branch)
        flow_service: FlowService for issue resolution
        github_client: Optional GitHub client (for testing)
        allow_no_flow: If True, return raw numeric string instead of raising
            UserError when no flows exist for an issue number. Only affects
            --branch and <position-arg> paths.
        canonical_fallback: If True, return canonical branch name for issue
            numbers without flows (e.g., "1234" → "task/issue-1234") instead
            of raising UserError. Only applies when input is a pure issue
            number (digits only). Takes precedence over allow_no_flow.

    Returns:
        Resolved branch name

    Raises:
        UserError: If resolution fails or conflicts detected
        typer.Exit: Parameter conflict
    """
    # Step 1: Check parameter conflicts
    provided = [
        name
        for opt, name in [
            (branch_opt, "--branch"),
            (pr_opt, "--pr"),
            (position_arg, "<arg>"),
        ]
        if opt is not None
    ]

    if len(provided) > 1:
        typer.echo(
            f"错误：不能同时使用 {', '.join(provided)}，请只指定一个目标。",
            err=True,
        )
        raise typer.Exit(1)

    # Step 2: Priority 1 - Explicit --branch
    if branch_opt is not None:
        # When canonical_fallback is enabled, allow_no_flow should also be True
        # so resolve_issue_branch_input returns None instead of raising
        effective_allow_no_flow = allow_no_flow or canonical_fallback
        resolved = resolve_issue_branch_input(
            branch_opt, flow_service, allow_no_flow=effective_allow_no_flow
        )
        if resolved is not None:
            return resolved
        # If unresolved and canonical_fallback enabled for issue numbers
        if canonical_fallback and branch_opt.isdigit():
            resolver = ConventionResolver.from_repo()
            convention = resolver.resolve()
            return convention.branch.canonical_branch(int(branch_opt))
        return branch_opt

    # Step 3: Priority 2 - --pr option
    if pr_opt is not None:
        return resolve_branch_from_pr(
            pr_opt,
            github_client=github_client,
        )

    # Step 4: Priority 3 - Positional argument
    if position_arg is not None:
        # When canonical_fallback is enabled, allow_no_flow should also be True
        # so resolve_issue_branch_input returns None instead of raising
        effective_allow_no_flow = allow_no_flow or canonical_fallback
        resolved = resolve_issue_branch_input(
            position_arg, flow_service, allow_no_flow=effective_allow_no_flow
        )
        if resolved is not None:
            return resolved
        # If unresolved and canonical_fallback enabled for issue numbers
        if canonical_fallback and position_arg.isdigit():
            resolver = ConventionResolver.from_repo()
            convention = resolver.resolve()
            return convention.branch.canonical_branch(int(position_arg))
        return position_arg

    # Step 5: Priority 4 - Current branch (fallback)
    return flow_service.get_current_branch()


# ============================================================================
# Legacy Wrapper for Backward Compatibility
# ============================================================================


def resolve_branch_arg(branch_arg: str | None) -> str:
    """Resolve --branch argument to a canonical branch name.

    This is a thin wrapper around resolve_command_branch for backward
    compatibility with existing command imports.

    Rules:
    - None → current git branch
    - digits only → canonical task branch (task/issue-N) if no flow exists
    - otherwise → return as-is (explicit branch name)

    Args:
        branch_arg: Branch argument from CLI (may be None, digits, or branch name)

    Returns:
        Resolved branch name
    """
    return resolve_command_branch(
        position_arg=branch_arg,
        flow_service=FlowService(),
        allow_no_flow=False,
        canonical_fallback=True,
    )
