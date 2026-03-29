"""Inspect command helper functions."""

from pathlib import Path
from typing import Union

from loguru import logger

from vibe3.commands.inspect_pr_helpers import (
    _analyze_critical_files,
    _calculate_risk_score,
    _filter_critical_files,
    _get_pr_changed_files,
    _get_pr_commit_count,
    _get_recent_commits,
    build_pr_analysis,
)
from vibe3.commands.inspect_types import (
    CommitInfo,
    CriticalFileInfo,
    PRCriticalAnalysis,
)
from vibe3.config.loader import get_config
from vibe3.models.change_source import (
    BranchSource,
    CommitSource,
    PRSource,
    UncommittedSource,
)
from vibe3.services import dag_service
from vibe3.services.pr_scoring_service import PRDimensions, generate_score_report
from vibe3.services.serena_service import SerenaService

__all__ = [
    "CriticalFileInfo",
    "CommitInfo",
    "PRCriticalAnalysis",
    "build_change_analysis",
    "validate_pr_number",
    "build_pr_analysis",
    "_get_pr_changed_files",
    "_filter_critical_files",
    "_analyze_critical_files",
    "_calculate_risk_score",
    "_get_recent_commits",
    "_get_pr_commit_count",
]


def build_change_analysis(source_type: str, identifier: str) -> dict[str, object]:
    """Run change analysis pipeline and return impact/dag/score."""
    import sys
    from io import StringIO

    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient

    log = logger.bind(
        domain="inspect", action="change_analysis", source_type=source_type
    )
    log.info("Running change analysis pipeline")

    source: Union[PRSource, CommitSource, BranchSource, UncommittedSource]
    if source_type == "pr":
        source = PRSource(pr_number=int(identifier))
    elif source_type == "commit":
        source = CommitSource(sha=identifier)
    elif source_type == "uncommit":
        source = UncommittedSource()
    else:
        source = BranchSource(branch=identifier)

    old_stderr = sys.stderr
    sys.stderr = StringIO()

    try:
        git_client = GitClient(
            github_client=GitHubClient() if source_type == "pr" else None
        )
        svc = SerenaService(git_client=git_client)
        impact = svc.analyze_changes(source)
        untracked_files: set[str] = set()
        if source_type == "uncommit":
            try:
                untracked_files = set(git_client.get_untracked_files())
            except Exception as e:
                logger.debug(f"Skipping: {e}")
                untracked_files = set()

        sys.stderr = old_stderr

        all_changed_files = impact.get("changed_files", [])
        assert isinstance(all_changed_files, list)

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

        if skipped_count > 0:
            impact["skipped_files"] = [
                f for f in all_changed_files if not Path(f).exists()
            ]

        changed_symbols_by_file: dict[str, list[str]] = {}
        skipped_tests = 0

        for file in changed_files:
            is_test = (
                file.startswith("tests/")
                or file.startswith("test/")
                or "/tests/" in file
                or "/test/" in file
                or file.startswith("test_")
                or file.endswith("_test.py")
            )
            if is_test:
                skipped_tests += 1
                continue

            if file.endswith(".py"):
                changed_funcs = svc.get_changed_functions(file, source=source)
                if changed_funcs:
                    changed_symbols_by_file[file] = changed_funcs

        if skipped_tests > 0:
            log.bind(skipped_test_files=skipped_tests).info(
                "Skipped test files for AST analysis"
            )

        log.bind(
            files_with_changes=len(changed_symbols_by_file),
            total_symbols=sum(len(syms) for syms in changed_symbols_by_file.values()),
        ).info("Extracted changed symbols from diff")

        dag = dag_service.expand_impacted_modules(changed_files)
        changed_lines = sum(
            1
            for line in git_client.get_diff(source).splitlines()
            if (line.startswith("+") or line.startswith("-"))
            and not line.startswith("+++")
            and not line.startswith("---")
        )
        if untracked_files:
            for file in changed_files:
                if file not in untracked_files:
                    continue
                try:
                    changed_lines += max(
                        1, len(Path(file).read_text(encoding="utf-8").splitlines())
                    )
                except OSError:
                    log.bind(file=file).warning(
                        "Failed to count lines for untracked file"
                    )

        config = get_config()
        critical_paths = config.review_scope.critical_paths
        public_api_paths = config.review_scope.public_api_paths

        dims = PRDimensions(
            changed_files=len(changed_files),
            impacted_modules=len(dag.impacted_modules),
            changed_lines=changed_lines,
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
            "changed_symbols": changed_symbols_by_file,
            "dag": dag.model_dump(),
            "score": score,
        }
    except Exception:
        sys.stderr = old_stderr
        raise


# ========== PR Validation Functions ==========


def validate_pr_number(pr_number: int) -> None:
    """Validate that an identifier refers to an existing PR."""
    from vibe3.clients.github_client import GitHubClient
    from vibe3.exceptions import UserError

    gh = GitHubClient()

    pr = gh.get_pr(pr_number)
    if pr is not None:
        return

    issue = gh.view_issue(pr_number)
    if issue == "network_error":
        raise UserError(
            f"Cannot verify #{pr_number}: network or authentication error.\n"
            f"  Please check your network connection and GitHub authentication."
        )
    if isinstance(issue, dict):
        raise UserError(
            f"#{pr_number} is an issue, not a PR.\n"
            f"  Use 'vibe inspect pr <number>' only for pull requests.\n"
            f"  Issue title: {issue.get('title', 'N/A')}"
        )

    raise UserError(
        f"#{pr_number} does not exist or is not accessible.\n"
        f"  Please verify the number and ensure you have access to this repository."
    )
