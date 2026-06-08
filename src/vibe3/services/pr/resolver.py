"""PR to Branch resolution with conflict detection."""

import shutil

import typer

from vibe3.clients import GitHubClient
from vibe3.exceptions import UserError
from vibe3.services.convention_resolver import get_convention
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_branch_resolver import resolve_issue_branch_input


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
            convention = get_convention()
            return convention.branch.canonical_branch(int(branch_opt))  # type: ignore[no-any-return]
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
            convention = get_convention()
            return convention.branch.canonical_branch(int(position_arg))  # type: ignore[no-any-return]
        return position_arg

    # Step 5: Priority 4 - Current branch (fallback)
    return flow_service.get_current_branch()
