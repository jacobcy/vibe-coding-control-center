"""PR-specific helper functions for inspect command."""

from pathlib import Path
from typing import cast

from loguru import logger

from vibe3.commands.inspect_types import (
    CommitInfo,
    CriticalFileInfo,
    PRCriticalAnalysis,
)
from vibe3.config.loader import get_config
from vibe3.models.change_source import PRSource
from vibe3.services import dag_service
from vibe3.services.pr_scoring_service import PRDimensions, generate_score_report
from vibe3.services.serena_service import SerenaService


def build_pr_analysis(pr_number: int, verbose: bool = False) -> PRCriticalAnalysis:
    """Analyze PR focusing on critical files.

    Flow:
    1. Get all changed files in PR
    2. Filter critical files (touching critical/public-api paths)
    3. Analyze only critical files once
    4. Output comprehensive report

    Args:
        pr_number: PR number to analyze
        verbose: Include detailed information

    Returns:
        PRCriticalAnalysis: Analysis result

    Raises:
        GitError: Unable to get PR information
        GitHubError: GitHub API call failed
    """

    log = logger.bind(domain="inspect", action="pr_analysis", pr_number=pr_number)
    log.info("Analyzing PR")

    # 1. Get changed files
    all_changed_files = _get_pr_changed_files(pr_number)
    log.info(f"PR has {len(all_changed_files)} changed files")

    # 2. Filter critical files
    critical_files = _filter_critical_files(all_changed_files)
    log.info(
        f"Found {len(critical_files)} critical files out of {len(all_changed_files)}"
    )

    # 3. Analyze critical files
    critical_symbols, critical_file_dags = _analyze_critical_files(
        critical_files, pr_number
    )

    # 4. Overall DAG analysis
    overall_dag = dag_service.expand_impacted_modules(all_changed_files)

    # 5. Risk scoring
    score = _calculate_risk_score(
        all_changed_files, critical_files, overall_dag.impacted_modules
    )

    # 6. Get commits info (only if verbose)
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
    """Get list of changed files in a PR (including deleted files).

    Args:
        pr_number: PR number

    Returns:
        List of all file paths changed in the PR

    Raises:
        GitError: Unable to get PR files
        GitHubError: GitHub API error
    """
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient

    # Get raw file list from git (without Serena analysis)
    git = GitClient(github_client=GitHubClient())
    all_changed_files = git.get_changed_files(PRSource(pr_number=pr_number))

    # Log deleted files but keep them in the list for counting/scoring
    deleted_files = [f for f in all_changed_files if not Path(f).exists()]
    if deleted_files:
        logger.bind(
            domain="inspect",
            action="get_pr_changed_files",
            pr_number=pr_number,
            deleted_count=len(deleted_files),
            deleted_files=deleted_files,
        ).info(f"{len(deleted_files)} deleted files included in PR analysis")

    return all_changed_files


def _filter_critical_files(files: list[str]) -> list[CriticalFileInfo]:
    """Filter critical files based on configuration.

    Args:
        files: List of file paths

    Returns:
        List of CriticalFileInfo for matching files
    """
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
    """Analyze critical files for symbols and dependencies.

    Args:
        critical_files: List of critical file info
        pr_number: PR number for source reference

    Returns:
        Tuple of (critical_symbols, critical_file_dags)
    """
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient

    git = GitClient(github_client=GitHubClient())
    svc = SerenaService(git_client=git)

    critical_symbols: dict[str, list[str]] = {}
    critical_file_dags: dict[str, list[str]] = {}

    for file_info in critical_files:
        file = file_info["path"]
        if not file.endswith(".py"):
            continue

        # Skip AST/symbol analysis for deleted files
        if not Path(file).exists():
            continue

        # Extract changed functions
        changed_funcs = svc.get_changed_functions(
            file, source=PRSource(pr_number=pr_number)
        )
        if changed_funcs:
            critical_symbols[file] = changed_funcs

        # DAG impact scope
        dag = dag_service.expand_impacted_modules([file])
        if dag.impacted_modules:
            critical_file_dags[file] = dag.impacted_modules

    return critical_symbols, critical_file_dags


def _calculate_risk_score(
    all_files: list[str],
    critical_files: list[CriticalFileInfo],
    impacted_modules: list[str],
) -> dict:
    """Calculate risk score for the PR.

    Args:
        all_files: All changed files
        critical_files: Critical files list
        impacted_modules: List of impacted modules

    Returns:
        Risk score report dict
    """
    dims = PRDimensions(
        changed_files=len(all_files),
        impacted_modules=len(impacted_modules),
        changed_lines=0,  # TODO: Calculate from diff
        critical_path_touch=any(f["critical_path"] for f in critical_files),
        public_api_touch=any(f["public_api"] for f in critical_files),
    )
    return generate_score_report(dims)


def _get_recent_commits(pr_number: int, limit: int = 5) -> list[CommitInfo]:
    """Get recent commit information for a PR.

    Args:
        pr_number: PR number
        limit: Maximum number of commits to return

    Returns:
        List of CommitInfo

    Raises:
        GitHubError: Unable to get PR commits
    """
    from vibe3.clients.github_client import GitHubClient
    from vibe3.utils.git_helpers import get_commit_message

    gh = GitHubClient()

    try:
        commit_shas = gh.get_pr_commits(pr_number)
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
            continue  # Skip failed commits, don't fail the whole analysis

    return commits_info


def _get_pr_commit_count(pr_number: int) -> int:
    """Get total commit count for a PR.

    Args:
        pr_number: PR number

    Returns:
        Number of commits (0 if failed)
    """
    from vibe3.clients.github_client import GitHubClient

    gh = GitHubClient()

    try:
        commits = gh.get_pr_commits(pr_number)
        return len(commits)
    except Exception as e:
        logger.warning(f"Failed to get commit count for PR {pr_number}: {e}")
        return 0
