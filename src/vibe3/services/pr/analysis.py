"""PR analysis service.

Provides reusable PR analysis logic for both commands and services.
"""

import subprocess
from pathlib import Path
from typing import cast

from loguru import logger

from vibe3.analysis import (
    PRDimensions,
    SerenaService,
    count_changed_lines,
    dag_service,
    generate_score_report,
)
from vibe3.config import get_config
from vibe3.models import CommitInfo, CriticalFileInfo, PRCriticalAnalysis, PRSource


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
    from vibe3.clients import GitClient, GitHubClient

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
    changed_lines = count_changed_lines(git.get_diff(PRSource(pr_number=pr_number)))

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


def get_pr_changed_files(pr_number: int) -> list[str]:
    """Return changed file paths for a PR, including deleted files."""
    from vibe3.clients import GitClient, GitHubClient

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


def filter_critical_files(files: list[str]) -> list[CriticalFileInfo]:
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


def analyze_critical_files(
    critical_files: list[CriticalFileInfo],
    pr_number: int,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Extract changed symbols and DAG impact for critical Python files."""
    from vibe3.clients import GitClient, GitHubClient

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


def calculate_pr_risk_score(
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


def get_recent_commits(pr_number: int, limit: int = 5) -> list[CommitInfo]:
    """Return latest commit messages for a PR via direct gh CLI call."""
    from vibe3.utils import get_commit_message

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


def get_pr_commit_count(pr_number: int) -> int:
    """Return total commit count for a PR via direct gh CLI call."""
    try:
        commits = _fetch_pr_commit_shas(pr_number)
        return len(commits)
    except Exception as e:
        logger.warning(f"Failed to get commit count for PR {pr_number}: {e}")
        return 0


_get_pr_changed_files = get_pr_changed_files
_filter_critical_files = filter_critical_files
_analyze_critical_files = analyze_critical_files
_calculate_risk_score = calculate_pr_risk_score
_get_recent_commits = get_recent_commits
_get_pr_commit_count = get_pr_commit_count
