"""Inspect command helper functions."""

from pathlib import Path
from typing import Union

from loguru import logger

# Re-export PR helpers for backward compatibility
from vibe3.commands.inspect_pr_helpers import (
    _analyze_critical_files,
    _calculate_risk_score,
    _filter_critical_files,
    _get_pr_changed_files,
    _get_pr_commit_count,
    _get_recent_commits,
    build_pr_analysis,
)

# Re-export types for backward compatibility
from vibe3.commands.inspect_types import (
    CommitInfo,
    CriticalFileInfo,
    PRCriticalAnalysis,
)
from vibe3.config.loader import get_config
from vibe3.models.change_source import BranchSource, CommitSource, PRSource
from vibe3.services import dag_service
from vibe3.services.pr_scoring_service import PRDimensions, generate_score_report
from vibe3.services.serena_service import SerenaService

__all__ = [
    # Types
    "CriticalFileInfo",
    "CommitInfo",
    "PRCriticalAnalysis",
    # Change analysis
    "build_change_analysis",
    # PR validation
    "validate_pr_number",
    # PR analysis
    "build_pr_analysis",
    "_get_pr_changed_files",
    "_filter_critical_files",
    "_analyze_critical_files",
    "_calculate_risk_score",
    "_get_recent_commits",
    "_get_pr_commit_count",
]


def build_change_analysis(source_type: str, identifier: str) -> dict[str, object]:
    """执行改动分析流程（serena → dag → scoring）.

    Args:
        source_type: "pr" | "commit" | "branch"
        identifier: PR 编号、commit SHA 或分支名

    Returns:
        包含 impact / dag / score 的分析结果 dict
    """
    import sys
    from io import StringIO

    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient

    log = logger.bind(
        domain="inspect", action="change_analysis", source_type=source_type
    )
    log.info("Running change analysis pipeline")

    # 构建 ChangeSource
    source: Union[PRSource, CommitSource, BranchSource]
    if source_type == "pr":
        source = PRSource(pr_number=int(identifier))
    elif source_type == "commit":
        source = CommitSource(sha=identifier)
    else:
        source = BranchSource(branch=identifier)

    # Suppress Serena warnings
    old_stderr = sys.stderr
    sys.stderr = StringIO()

    try:
        # 1. Serena 符号分析
        # 注入 GitHubClient 如果是 PR source
        git_client = GitClient(
            github_client=GitHubClient() if source_type == "pr" else None
        )
        svc = SerenaService(git_client=git_client)
        impact = svc.analyze_changes(source)

        # Restore stderr for our output
        sys.stderr = old_stderr

        # 2. DAG 影响范围
        all_changed_files = impact.get("changed_files", [])
        assert isinstance(all_changed_files, list)

        # Filter out files that no longer exist
        changed_files = [f for f in all_changed_files if Path(f).exists()]
        skipped_count = len(all_changed_files) - len(changed_files)

        if skipped_count > 0:
            log.bind(
                total_files=len(all_changed_files),
                existing_files=len(changed_files),
                skipped_files=skipped_count,
            ).warning(
                f"Skipping {skipped_count} files that no longer exist in repository"
            )

        # Add skipped files info to impact for display
        if skipped_count > 0:
            impact["skipped_files"] = [
                f for f in all_changed_files if not Path(f).exists()
            ]

        # Try to extract changed functions for each file (only existing files)
        changed_symbols_by_file: dict[str, list[str]] = {}

        for file in changed_files:
            if file.endswith(".py"):
                changed_funcs = svc.get_changed_functions(file, source=source)
                if changed_funcs:
                    changed_symbols_by_file[file] = changed_funcs

        log.bind(
            files_with_changes=len(changed_symbols_by_file),
            total_symbols=sum(len(syms) for syms in changed_symbols_by_file.values()),
        ).info("Extracted changed symbols from diff")

        dag = dag_service.expand_impacted_modules(changed_files)

        # 3. 风险评分
        # Read critical and public API paths from config
        config = get_config()
        critical_paths = config.review_scope.critical_paths
        public_api_paths = config.review_scope.public_api_paths

        dims = PRDimensions(
            changed_files=len(changed_files),
            impacted_modules=len(dag.impacted_modules),
            changed_lines=0,  # 需要从 diff 计算
            critical_path_touch=any(
                any(p in str(f) for p in critical_paths) for f in changed_files
            ),
            public_api_touch=any(
                any(p in str(f) for p in public_api_paths) for f in changed_files
            ),
        )
        score = generate_score_report(dims)

        return {
            "impact": impact,
            "changed_symbols": changed_symbols_by_file,  # 新增：改动的符号
            "dag": dag.model_dump(),
            "score": score,
        }
    except Exception:
        # Always restore stderr on error
        sys.stderr = old_stderr
        raise


# ========== PR Validation Functions ==========


def validate_pr_number(pr_number: int) -> None:
    """Validate that a PR number refers to an actual PR.

    Args:
        pr_number: PR number to validate

    Raises:
        UserError: If the number refers to an issue instead of PR
        PRNotFoundError: If neither PR nor issue exists with this number
    """
    from vibe3.clients.github_client import GitHubClient
    from vibe3.exceptions import UserError

    gh = GitHubClient()

    # Check if it's a PR
    pr = gh.get_pr(pr_number)
    if pr is not None:
        return  # Valid PR

    # Not a PR, check if it's an issue
    issue = gh.view_issue(pr_number)
    if issue is not None:
        raise UserError(
            f"#{pr_number} is an issue, not a PR.\n"
            f"  Use 'vibe inspect pr <number>' only for pull requests.\n"
            f"  Issue title: {issue.get('title', 'N/A')}"
        )

    # Neither PR nor issue
    raise UserError(
        f"#{pr_number} does not exist or is not accessible.\n"
        f"  Please verify the number and ensure you have access to this repository."
    )
