"""PR analysis service.

Provides reusable PR analysis logic for both commands and services.
"""

from pathlib import Path
from typing import cast

from loguru import logger

from vibe3.analysis import dag_service
from vibe3.analysis.serena_service import SerenaService
from vibe3.config.loader import get_config
from vibe3.models.change_source import PRSource
from vibe3.models.pr_analysis import (
    CommitInfo,
    CriticalFileInfo,
    PRCriticalAnalysis,
)
from vibe3.services.pr_scoring_service import PRDimensions, generate_score_report


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
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient

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
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient

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


def _get_recent_commits(pr_number: int, limit: int = 5) -> list[CommitInfo]:
    """Return latest commit messages for a PR."""
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
            continue

    return commits_info


def _get_pr_commit_count(pr_number: int) -> int:
    """Return total commit count for a PR."""
    from vibe3.clients.github_client import GitHubClient

    gh = GitHubClient()

    try:
        commits = gh.get_pr_commits(pr_number)
        return len(commits)
    except Exception as e:
        logger.warning(f"Failed to get commit count for PR {pr_number}: {e}")
        return 0