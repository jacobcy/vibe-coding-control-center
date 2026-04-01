"""Inspect base command helpers."""

from typing import Any

from loguru import logger

from vibe3.analysis import dag_service
from vibe3.analysis.change_scope_service import (
    collect_changed_symbols,
    count_changed_lines,
)
from vibe3.analysis.serena_service import SerenaService
from vibe3.clients.git_client import GitClient
from vibe3.config.loader import get_config
from vibe3.exceptions import GitError, UserError
from vibe3.models.change_source import BranchSource
from vibe3.services.pr_scoring_service import PRDimensions, generate_score_report


def _code_paths() -> list[str]:
    config = get_config()
    return (
        config.code_limits.code_paths.v2_shell + config.code_limits.code_paths.v3_python
    )


def _is_code_file(filepath: str, code_paths: list[str]) -> bool:
    return any(filepath.startswith(path.rstrip("/")) for path in code_paths)


def validate_base_branch(git_client: GitClient, base_branch: str) -> None:
    """Validate that base branch exists."""

    def ref_exists(ref: str) -> bool:
        try:
            git_client._run(["rev-parse", "--verify", ref])
            return True
        except GitError:
            return False

    base_exists = (
        ref_exists(base_branch)
        or ref_exists(f"refs/heads/{base_branch}")
        or ref_exists(f"refs/remotes/{base_branch}")
        or ref_exists(f"refs/remotes/origin/{base_branch}")
    )

    if not base_exists:
        raise UserError(
            f"Base branch '{base_branch}' not found or invalid.\n\n"
            "Please provide a valid branch name or commit SHA.\n\n"
            "Examples:\n"
            "  vibe inspect base\n"
            "  vibe inspect base main\n"
            "  vibe inspect base develop\n"
            "  vibe inspect base HEAD~5"
        ) from None


def count_changed_lines_in_code_paths(git: GitClient, source: BranchSource) -> int:
    """Count changed lines only in configured code paths."""
    code_paths = _code_paths()
    return count_changed_lines(git.get_diff(source), code_paths=code_paths)


def build_json_output(
    git: GitClient,
    source: BranchSource,
    current_branch: str,
    base_branch: str,
    all_changed_files: list[str],
    existing_files: list[str],
    deleted_files: list[str],
    core_files: list[dict[str, Any]],
    changed_lines: int,
) -> dict[str, Any]:
    """Build JSON output for inspect base command."""
    code_paths = _code_paths()

    code_changed_files = [f for f in all_changed_files if _is_code_file(f, code_paths)]

    changed_symbols_by_file: dict[str, list[str]] = {}
    if existing_files:
        svc = SerenaService(git_client=git)
        changed_symbols_by_file, skipped_tests = collect_changed_symbols(
            svc,
            source,
            existing_files,
        )
        if skipped_tests > 0:
            logger.bind(skipped_test_files=skipped_tests).info(
                "Skipped test files for AST analysis"
            )

    has_critical = any(f["critical_path"] for f in core_files)
    has_public_api = any(f["public_api"] for f in core_files)

    impacted_modules = []
    if core_files:
        core_paths = [f["path"] for f in core_files if not f.get("deleted", False)]
        if core_paths:
            dag = dag_service.expand_impacted_modules(core_paths)
            impacted_modules = dag.impacted_modules

    dims = PRDimensions(
        changed_files=len(code_changed_files),
        changed_lines=changed_lines,
        impacted_modules=len(impacted_modules),
        critical_path_touch=has_critical,
        public_api_touch=has_public_api,
    )
    score_report = generate_score_report(dims)

    result = {
        "current_branch": current_branch,
        "base_branch": base_branch,
        "core_files": core_files,
        "total_changed": len(all_changed_files),
        "code_changed": len(code_changed_files),
        "existing_changed": len(existing_files),
        "deleted_files": len(deleted_files),
        "core_changed": len(core_files),
        "score": score_report,
    }
    if core_files:
        result["impacted_modules"] = impacted_modules
    if changed_symbols_by_file:
        result["changed_symbols"] = changed_symbols_by_file

    return result


def print_human_output(
    current_branch: str,
    base_branch: str,
    all_changed_files: list[str],
    existing_files: list[str],
    deleted_files: list[str],
    core_files: list[dict[str, Any]],
) -> None:
    """Print human-readable output for inspect base command."""
    import typer

    typer.echo(f"=== Branch Analysis: {current_branch} vs {base_branch} ===\n")

    if deleted_files:
        typer.echo(f"⚠️  Deleted files: {len(deleted_files)}")
        for f in deleted_files[:5]:
            typer.echo(f"    - {f}")
        if len(deleted_files) > 5:
            typer.echo(f"    ... and {len(deleted_files) - 5} more")
        typer.echo()

    if not core_files:
        typer.echo("✅ No core files changed")
        typer.echo(f"\n  Total files changed: {len(all_changed_files)}")
        typer.echo(f"  Existing files: {len(existing_files)}")
        typer.echo(f"  Deleted files: {len(deleted_files)}")
        typer.echo("  Core files changed: 0")
        return

    typer.echo(f"Core files changed ({len(core_files)}):")
    for file_info in core_files:
        tags = []
        if file_info["critical_path"]:
            tags.append("critical")
        if file_info["public_api"]:
            tags.append("public-api")
        if file_info.get("deleted"):
            tags.append("deleted")
        tag_str = ", ".join(tags)
        typer.echo(f"  - {file_info['path']} ({tag_str})")

    existing_core_paths = [f["path"] for f in core_files if not f.get("deleted", False)]
    if existing_core_paths:
        dag = dag_service.expand_impacted_modules(existing_core_paths)

        typer.echo(f"\nImpact scope ({len(dag.impacted_modules)} modules):")
        for module in dag.impacted_modules[:10]:
            typer.echo(f"  - {module}")
        if len(dag.impacted_modules) > 10:
            typer.echo(f"  ... and {len(dag.impacted_modules) - 10} more")
    else:
        typer.echo("\nImpact scope: No existing core files to analyze")

    typer.echo("\nSummary:")
    typer.echo(f"  Total files changed: {len(all_changed_files)}")
    typer.echo(f"  Existing files: {len(existing_files)}")
    typer.echo(f"  Deleted files: {len(deleted_files)}")
    typer.echo(f"  Core files changed: {len(core_files)}")

    critical_count = sum(1 for f in core_files if f["critical_path"])
    if critical_count > 0:
        typer.echo(f"  ⚠️  {critical_count} critical file(s) changed")
    else:
        typer.echo("  ℹ️  Only public API files changed")
