"""PR utilities - merged from pr_utils.py, pr_status_checker.py, and pr_analysis_service.py.

This module provides:
- PR metadata and body construction utilities
- Authoritative PR status checking (merged PR detection)
- PR analysis and risk scoring
"""

import subprocess
from pathlib import Path
from typing import Any, cast

from loguru import logger

from vibe3.analysis import dag_service
from vibe3.analysis.pr_scoring import PRDimensions
from vibe3.analysis.serena_service import SerenaService
from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_issues_ops import parse_linked_issues
from vibe3.clients.merged_pr_cache import MergedPRCache
from vibe3.config.loader import get_config
from vibe3.exceptions import GitError, UserError
from vibe3.models.change_source import PRSource
from vibe3.models.flow import IssueLink
from vibe3.models.pr import PRMetadata
from vibe3.models.pr_analysis import (
    CommitInfo,
    CriticalFileInfo,
    PRCriticalAnalysis,
)
from vibe3.services.git_path_client import get_git_common_dir
from vibe3.services.shared.scoring import generate_score_report

# =============================================================================
# PR Metadata Utilities (from pr_utils.py)
# =============================================================================


def get_metadata_from_flow(store: SQLiteClient, branch: str) -> PRMetadata | None:
    """Read metadata from flow state.

    Args:
        store: SQLiteClient instance
        branch: Branch name

    Returns:
        PR metadata from flow state, or None if flow not found
    """
    flow_data = store.get_flow_state(branch)
    if not flow_data:
        logger.bind(branch=branch).debug("No flow found for branch")
        return None

    metadata = PRMetadata(
        branch=branch,
        task_issue=None,
        flow_slug=flow_data.get("flow_slug"),
        spec_ref=flow_data.get("spec_ref"),
        planner=flow_data.get("planner_actor"),
        executor=flow_data.get("executor_actor"),
        reviewer=flow_data.get("reviewer_actor"),
        latest=flow_data.get("latest_actor"),
    )

    try:
        links = store.get_issue_links(branch)
    except Exception:
        links = []

    metadata.task_issue = IssueLink.resolve_task_number(links)

    logger.bind(
        branch=branch,
        task_issue=metadata.task_issue,
        flow_slug=metadata.flow_slug,
    ).debug("Loaded metadata from flow")

    return metadata


def _has_issue_linked(body: str, issue_number: int) -> bool:
    """Check if body already contains a GitHub auto-close keyword for the issue.

    Args:
        body: PR body text
        issue_number: Issue number to check

    Returns:
        True if a linking keyword (Closes/Fixes/Resolves #<n>) already exists
    """
    return issue_number in parse_linked_issues(body)


def _build_linked_section(metadata: PRMetadata, body: str) -> str:
    """Build the GitHub auto-link section for the bound task issue.

    Injects ``Closes #<n>`` at the top of the body unless the body already
    references the same issue with a linking keyword.

    Args:
        metadata: PR metadata (may contain task_issue)
        body: Original PR body

    Returns:
        Linking line with trailing blank line, or empty string
    """
    if not metadata.task_issue:
        return ""
    if _has_issue_linked(body, metadata.task_issue):
        return ""
    return f"Closes #{metadata.task_issue}\n\n"


def build_pr_body(body: str, metadata: PRMetadata | None = None) -> str:
    """Build PR body with issue linkage and contributor signature.

    - If a task issue is bound, prepends ``Closes #<n>`` to trigger GitHub's
      native issue-PR linkage (unless already present).
    - If flow_state contains non-placeholder actors, appends a Contributors
      section with normalized, deduplicated signatures.
    """
    if not metadata:
        return body

    linked_section = _build_linked_section(metadata, body)

    contributors = metadata.contributors
    if not contributors:
        return linked_section + body

    signature = "\n\n---\n\n" + "## Contributors\n\n" + ", ".join(contributors) + "\n"
    return linked_section + body + signature


def check_upstream_conflicts(
    git_client: GitClient,
    action: str,
    base_branch: str = "main",
    remote: str = "origin",
) -> None:
    """Fetch base branch and dry-run merge to detect conflicts.

    On conflict: raise UserError to halt the calling command.
    On network/fetch failure: log warning and continue (non-blocking).

    Args:
        git_client: GitClient instance for fetch and merge operations
        action: Context label for log/error messages (e.g. "create", "ready")
        base_branch: Target base branch for the PR (branch name or remote ref)
        remote: Remote name to fetch from

    Raises:
        UserError: When merge conflicts are detected
    """
    prefixed = base_branch.startswith(f"{remote}/")
    target = base_branch if prefixed else f"{remote}/{base_branch}"
    fetch_ref = base_branch.removeprefix(f"{remote}/") if prefixed else base_branch
    try:
        git_client.fetch(remote, fetch_ref)
    except GitError:
        logger.bind(domain="pr", action=action).warning(
            f"Failed to fetch {target}, skipping conflict check"
        )
        return

    if git_client.check_merge_conflicts(target):
        raise UserError(
            f"Merge conflict detected between current branch and {target}\n"
            f"Resolve before {action}:\n"
            f"  1. git rebase {target}\n"
            f"  2. Resolve any conflicts\n"
            f"  3. Re-run vibe3 pr {action}"
        )


# =============================================================================
# PR Status Checker (from pr_status_checker.py)
# =============================================================================


def get_merged_pr_for_issue(
    issue_number: int, repo: str | None = None
) -> dict[str, Any] | None:
    """Get the merged PR associated with an issue (if any).

    This is the ONLY source of truth for determining if work is complete.
    Use this instead of checking state/done labels or flow_status.

    Args:
        issue_number: GitHub issue number
        repo: Repository (owner/repo format, optional, for future use)

    Returns:
        PR dict with keys: number, headRefName, body, mergedAt
        Returns None if no merged PR found or query failed

    Example:
        >>> pr = get_merged_pr_for_issue(123)
        >>> if pr:
        ...     print(f"Issue #123 has merged PR #{pr['number']}")
    """
    # Step 1: Resolve repo path for cache
    try:
        git_common_dir = get_git_common_dir()
        if git_common_dir:
            repo_path = Path(git_common_dir).parent
        else:
            # Fallback to cwd if git common dir unavailable
            repo_path = Path.cwd()
    except Exception:
        repo_path = Path.cwd()

    # Step 2: Check cache first
    cache = MergedPRCache(repo_path)
    cached_pr = cache.get_merged_pr_for_issue(issue_number)
    if cached_pr:
        logger.bind(
            domain="pr_status",
            issue_number=issue_number,
            pr_number=cached_pr.get("number"),
            source="cache",
        ).debug("Found merged PR for issue in cache")
        return cached_pr

    # Step 3: Cache miss - sync cache with latest merged PRs
    github_client = GitHubClient()
    logger.bind(
        domain="pr_status",
        issue_number=issue_number,
    ).debug("Cache miss, syncing cache")

    try:
        cache.sync(github_client, limit=200)

        cached_pr = cache.get_merged_pr_for_issue(issue_number)
        if cached_pr:
            logger.bind(
                domain="pr_status",
                issue_number=issue_number,
                pr_number=cached_pr.get("number"),
                source="sync",
            ).debug("Found merged PR for issue after sync")
            return cached_pr

        logger.bind(domain="pr_status", issue_number=issue_number).debug(
            "No merged PR found for issue"
        )
        return None

    except Exception as exc:
        logger.bind(
            domain="pr_status",
            issue_number=issue_number,
            error=str(exc),
            exc_info=True,  # Record full exception
        ).error("Failed to check merged PR status")
        return None


def has_merged_pr_for_issue(issue_number: int, repo: str | None = None) -> bool:
    """Check if an issue has a merged PR (authoritative truth).

    This is the ONLY source of truth for determining if work is complete.
    Use this instead of checking state/done labels or flow_status.

    Args:
        issue_number: GitHub issue number
        repo: Repository (owner/repo format, optional, for future use)

    Returns:
        True if issue has at least one merged PR, False otherwise

    Example:
        >>> has_merged_pr_for_issue(123)
        True  # Issue #123 has a merged PR, cannot be resumed
    """
    return get_merged_pr_for_issue(issue_number, repo) is not None


# =============================================================================
# PR Analysis Service (from pr_analysis_service.py)
# =============================================================================


def build_pr_analysis(pr_number: int, verbose: bool = False) -> PRCriticalAnalysis:
    """Analyze PR and return structured critical-file report.

    This is the main entry point for PR analysis, used by:
    - inspect command (CLI)
    - pr_review_briefing_service (service)

    Args:
        pr_number: GitHub PR number
        verbose: Whether to include recent commits

    Returns:
        Structured PR analysis result
    """
    log = logger.bind(domain="pr_analysis", action="analyze", pr_number=pr_number)
    log.info("Analyzing PR")

    git = GitClient(github_client=GitHubClient())

    all_changed_files = _get_pr_changed_files(pr_number)
    log.info(f"PR has {len(all_changed_files)} changed files")

    critical_files = _filter_critical_files(all_changed_files)
    log.info(
        f"Found {len(critical_files)} critical files out of {len(all_changed_files)}"
    )

    critical_symbols, critical_file_dags = _analyze_critical_files(
        critical_files, pr_number
    )

    overall_dag = dag_service.expand_impacted_modules(all_changed_files)
    changed_lines = sum(
        1
        for line in git.get_diff(PRSource(pr_number=pr_number)).splitlines()
        if (line.startswith("+") or line.startswith("-"))
        and not line.startswith("+++")
        and not line.startswith("---")
    )

    score = _calculate_risk_score(
        all_changed_files,
        critical_files,
        overall_dag.impacted_modules,
        changed_lines=changed_lines,
    )

    commits_info = _get_recent_commits(pr_number, limit=5) if verbose else []

    return PRCriticalAnalysis(
        pr_number=pr_number,
        total_commits=_get_pr_commit_count(pr_number),
        total_files=len(all_changed_files),
        critical_files=critical_files,
        critical_symbols=critical_symbols,
        impacted_modules=overall_dag.impacted_modules,
        critical_file_dags=critical_file_dags,
        score=score,
        recent_commits=commits_info,
    )


def _get_pr_changed_files(pr_number: int) -> list[str]:
    """Return changed file paths for a PR, including deleted files."""
    git = GitClient(github_client=GitHubClient())
    all_changed_files = git.get_changed_files(PRSource(pr_number=pr_number))

    deleted_files = [f for f in all_changed_files if not Path(f).exists()]
    if deleted_files:
        logger.bind(
            domain="pr_analysis",
            action="get_changed_files",
            pr_number=pr_number,
            deleted_count=len(deleted_files),
            deleted_files=deleted_files,
        ).info(f"{len(deleted_files)} deleted files included in PR analysis")

    return all_changed_files


def _filter_critical_files(files: list[str]) -> list[CriticalFileInfo]:
    """Filter files touching configured critical/public-api paths."""
    config = get_config()
    critical_paths = config.review_scope.critical_paths
    public_api_paths = config.review_scope.public_api_paths

    critical_files: list[CriticalFileInfo] = []
    for file in files:
        is_critical = any(p in str(file) for p in critical_paths)
        is_public_api = any(p in str(file) for p in public_api_paths)

        if is_critical or is_public_api:
            critical_files.append(
                cast(
                    CriticalFileInfo,
                    {
                        "path": file,
                        "critical_path": is_critical,
                        "public_api": is_public_api,
                    },
                )
            )

    return critical_files


def _analyze_critical_files(
    critical_files: list[CriticalFileInfo],
    pr_number: int,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Extract changed symbols and DAG impact for critical Python files."""
    git = GitClient(github_client=GitHubClient())
    svc = SerenaService(git_client=git)

    critical_symbols: dict[str, list[str]] = {}
    critical_file_dags: dict[str, list[str]] = {}

    for file_info in critical_files:
        file = file_info["path"]
        if not file.endswith(".py"):
            continue

        if not Path(file).exists():
            continue

        changed_funcs = svc.get_changed_functions(
            file, source=PRSource(pr_number=pr_number)
        )
        if changed_funcs:
            critical_symbols[file] = changed_funcs

        dag = dag_service.expand_impacted_modules([file])
        if dag.impacted_modules:
            critical_file_dags[file] = dag.impacted_modules

    return critical_symbols, critical_file_dags


def _calculate_risk_score(
    all_files: list[str],
    critical_files: list[CriticalFileInfo],
    impacted_modules: list[str],
    changed_lines: int = 0,
) -> dict:
    """Calculate PR risk score."""
    dims = PRDimensions(
        changed_files=len(all_files),
        impacted_modules=len(impacted_modules),
        changed_lines=changed_lines,
        critical_path_touch=any(f["critical_path"] for f in critical_files),
        public_api_touch=any(f["public_api"] for f in critical_files),
    )
    return generate_score_report(dims)


def _fetch_pr_commit_shas(pr_number: int) -> list[str]:
    """Fetch commit SHAs for a PR via direct gh CLI call."""
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--json",
            "commits",
            "--jq",
            ".commits[].oid",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]


def _get_recent_commits(pr_number: int, limit: int = 5) -> list[CommitInfo]:
    """Return latest commit messages for a PR via direct gh CLI call."""
    from vibe3.utils.git_helpers import get_commit_message

    try:
        commit_shas = _fetch_pr_commit_shas(pr_number)
    except Exception as e:
        logger.warning(f"Failed to get commits for PR {pr_number}: {e}")
        return []

    commits_info: list[CommitInfo] = []
    for sha in commit_shas[:limit]:
        try:
            message = get_commit_message(sha)
            commits_info.append(
                cast(
                    CommitInfo,
                    {
                        "sha": sha[:7],
                        "message": message,
                    },
                )
            )
        except Exception as e:
            logger.warning(f"Failed to get commit message for {sha}: {e}")
            continue

    return commits_info


def _get_pr_commit_count(pr_number: int) -> int:
    """Return total commit count for a PR via direct gh CLI call."""
    try:
        commits = _fetch_pr_commit_shas(pr_number)
        return len(commits)
    except Exception as e:
        logger.warning(f"Failed to get commit count for PR {pr_number}: {e}")
        return 0
