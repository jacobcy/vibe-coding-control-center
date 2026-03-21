"""Inspect base command helpers - 核心文件改动分析的辅助函数."""

from typing import Any

from vibe3.clients.git_client import GitClient
from vibe3.config.loader import get_config
from vibe3.exceptions import GitError, UserError
from vibe3.models.change_source import BranchSource
from vibe3.services import dag_service
from vibe3.services.pr_scoring_service import PRDimensions, generate_score_report
from vibe3.services.serena_service import SerenaService


def validate_base_branch(git_client: GitClient, base_branch: str) -> None:
    """Validate that base branch exists.

    Args:
        git_client: Git client instance
        base_branch: Base branch name or ref

    Raises:
        UserError: If base branch doesn't exist
    """

    def ref_exists(ref: str) -> bool:
        try:
            git_client._run(["rev-parse", "--verify", ref])
            return True
        except GitError:
            return False

    # Check various ref formats
    base_exists = (
        ref_exists(base_branch)  # As provided (could be SHA, HEAD~5, etc.)
        or ref_exists(f"refs/heads/{base_branch}")  # Local branch
        or ref_exists(f"refs/remotes/{base_branch}")  # Remote ref (origin/main)
        or ref_exists(f"refs/remotes/origin/{base_branch}")  # Shorthand remote
    )

    if not base_exists:
        raise UserError(
            f"Base branch '{base_branch}' not found or invalid.\n\n"
            "Please provide a valid branch name or commit SHA.\n\n"
            "Examples:\n"
            "  vibe inspect base              # Use default: origin/main\n"
            "  vibe inspect base main         # Compare vs local main\n"
            "  vibe inspect base develop      # Compare vs develop branch\n"
            "  vibe inspect base HEAD~5       # Compare vs 5 commits ago"
        ) from None


def count_changed_lines_in_code_paths(git: GitClient, source: BranchSource) -> int:
    """Count changed lines only in core code paths.

    Exclude docs, configs, scripts, tests to avoid inflating risk scores.

    Args:
        git: Git client instance
        source: Branch source

    Returns:
        Number of changed lines in code paths
    """
    config = get_config()
    code_paths = (
        config.code_limits.code_paths.v2_shell + config.code_limits.code_paths.v3_python
    )

    def is_code_file(filepath: str) -> bool:
        """Check if file is in code paths (not docs/configs)."""
        return any(filepath.startswith(path.rstrip("/")) for path in code_paths)

    # Parse diff to track which file each line belongs to
    full_diff = git.get_diff(source)
    changed_lines = 0
    current_file = None

    for line in full_diff.splitlines():
        # Track which file we're in (diff format: "diff --git a/file b/file")
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                # Extract filename from "a/file" (remove a/ prefix)
                current_file = parts[2][2:]
        elif current_file and is_code_file(current_file):
            # Count +/- lines only in code files
            if (
                line.startswith(("+", "-"))
                and not line.startswith("+++")
                and not line.startswith("---")
            ):
                changed_lines += 1

    return changed_lines


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
    """Build JSON output for inspect base command.

    Args:
        git: Git client instance
        source: Branch source
        current_branch: Current branch name
        base_branch: Base branch name
        all_changed_files: All changed files
        existing_files: Existing files
        deleted_files: Deleted files
        core_files: Core files with critical/public_api flags
        changed_lines: Changed lines count

    Returns:
        JSON-serializable result dict
    """
    # Get AST-level analysis: changed functions
    # Skip test files - they don't need AST analysis
    changed_symbols_by_file: dict[str, list[str]] = {}
    if existing_files:
        svc = SerenaService(git_client=git)
        for file in existing_files:
            # Skip test files to save tokens
            is_test = (
                file.startswith("tests/")
                or file.startswith("test/")
                or "/tests/" in file
                or "/test/" in file
                or file.startswith("test_")
                or file.endswith("_test.py")
            )
            if is_test:
                continue

            if file.endswith(".py"):
                try:
                    changed_funcs = svc.get_changed_functions(file, source=source)
                    if changed_funcs:
                        changed_symbols_by_file[file] = changed_funcs
                except Exception:
                    # Skip files that can't be analyzed
                    pass

    # Calculate score
    has_critical = any(f["critical_path"] for f in core_files)
    has_public_api = any(f["public_api"] for f in core_files)

    # Get impacted modules for scoring
    impacted_modules = []
    if core_files:
        # Only use existing files for DAG analysis
        core_paths = [f["path"] for f in core_files if not f.get("deleted", False)]
        if core_paths:
            dag = dag_service.expand_impacted_modules(core_paths)
            impacted_modules = dag.impacted_modules

    dims = PRDimensions(
        changed_files=len(all_changed_files),  # Include deleted files in count
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
        "total_changed": len(all_changed_files),  # Include deleted files
        "existing_changed": len(existing_files),
        "deleted_files": len(deleted_files),
        "core_changed": len(core_files),
        "score": score_report,  # Add score for pre-push hook
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
    """Print human-readable output for inspect base command.

    Args:
        current_branch: Current branch name
        base_branch: Base branch name
        all_changed_files: All changed files
        existing_files: Existing files
        deleted_files: Deleted files
        core_files: Core files with critical/public_api flags
    """
    import typer

    typer.echo(f"=== Branch Analysis: {current_branch} vs {base_branch} ===\n")

    if deleted_files:
        typer.echo(f"⚠️  Deleted files: {len(deleted_files)}")
        for f in deleted_files[:5]:  # Show first 5
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

    # Only analyze existing files for DAG impact
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
