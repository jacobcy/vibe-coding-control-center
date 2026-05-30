"""Scan service functions - business logic for scan commands."""

from pathlib import Path
from typing import Any

from loguru import logger


def extract_material_description(material_path: str) -> str:
    """Extract description from material markdown file.

    Reads the first markdown header (# Title) as description.
    Falls back to filename if no title found.

    Args:
        material_path: Path to material file

    Returns:
        Material description or filename as fallback
    """
    try:
        path = Path(material_path)
        if not path.exists():
            return material_path

        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("# "):
                    # Extract title without '# ' prefix
                    return line[2:].strip()
                # Stop at first non-empty, non-title line
                if line and not line.startswith("#"):
                    break
    except Exception as e:
        logger.debug(f"Could not extract description from {material_path}: {e}")

    # Fallback to filename
    return material_path


def dispatch_governance_execution(
    tick_count: int = 0, material_override: str | None = None
) -> None:
    """Execute governance scan (execution-only entry point).

    Entry point for internal governance command, calling execution layer directly.

    Args:
        tick_count: Tick number for governance material rotation
        material_override: Optional governance role to override material rotation
    """
    from vibe3.execution.governance_sync_runner import run_governance_sync
    from vibe3.orchestra.logging import append_governance_event
    from vibe3.roles.governance_factory import build_default_governance_fns

    run_governance_sync(
        tick_count=tick_count,
        material_override=material_override,
        dry_run=False,  # Execution-only, no dry-run
        show_prompt=False,
        session_id=None,
        governance_fns=build_default_governance_fns(),
        append_event=append_governance_event,
    )


def dispatch_supervisor_execution(issue_number: int, no_async: bool = False) -> None:
    """Execute supervisor apply for a single issue (execution-only entry point).

    Entry point for internal apply command, calling execution layer directly.

    Args:
        issue_number: Issue to apply supervisor handoff
        no_async: Run synchronously instead of async tmux session
    """
    from vibe3.execution.issue_role_sync_runner import (
        run_issue_role_async,
        run_issue_role_sync,
    )
    from vibe3.roles.supervisor import SUPERVISOR_CLI_SYNC_SPEC

    if no_async:
        run_issue_role_sync(
            issue_number=issue_number,
            dry_run=False,
            fresh_session=True,
            show_prompt=False,
            spec=SUPERVISOR_CLI_SYNC_SPEC,
        )
    else:
        run_issue_role_async(
            issue_number=issue_number,
            dry_run=False,
            spec=SUPERVISOR_CLI_SYNC_SPEC,
        )


def fetch_supervisor_candidates(
    github_client: Any, repo: str | None
) -> tuple[int, list[dict]]:
    """Fetch supervisor candidate issues from GitHub.

    Filters for issues with both 'supervisor' and 'state/handoff' labels.

    Args:
        github_client: GitHubClient instance
        repo: Repository in "owner/repo" format

    Returns:
        Tuple of (total_issues_scanned, matching_candidates)
        - total_issues_scanned: Total number of open issues queried
        - matching_candidates: List of candidate issues (number, title, labels)
    """
    from vibe3.services.label_utils import normalize_labels

    try:
        raw_issues = github_client.list_issues(limit=100, state="open", repo=repo)
        total_scanned = len(raw_issues)

        # Filter for supervisor + state/handoff labels
        matching = []
        for item in raw_issues:
            labels = normalize_labels(item.get("labels"))
            if "supervisor" in labels and "state/handoff" in labels:
                matching.append(
                    {
                        "number": item.get("number"),
                        "title": item.get("title", "")[:60],  # Truncate
                        "labels": labels,
                    }
                )

        return total_scanned, matching

    except Exception as e:
        logger.error(f"Failed to fetch supervisor candidates: {e}")
        return 0, []


def get_available_governance_materials() -> list[str]:
    """Fetch available governance materials from catalog.

    Returns list of short material names (without path/suffix).

    Returns:
        List of material short names (e.g., ["assignee-pool", "roadmap-intake"])
    """
    try:
        from vibe3.roles.governance import load_governance_material_catalog

        catalog = load_governance_material_catalog()
        materials = []
        for material in catalog:
            # Extract short name:
            # "supervisor/governance/roadmap-intake.md" → "roadmap-intake"
            name = material.name
            if name.startswith("supervisor/governance/"):
                short_name = name.split("/")[-1]
                short_name = (
                    short_name[:-3] if short_name.endswith(".md") else short_name
                )
                materials.append(short_name)
        return sorted(set(materials))
    except Exception:
        # Fallback if catalog cannot be loaded
        return []


def governance_material_exists(material_name: str) -> bool:
    """Check whether a governance material exists in catalog.

    Accepts either short names like ``roadmap-intake`` or full material paths.
    """
    try:
        from vibe3.roles.governance import load_governance_material_catalog
        from vibe3.roles.governance_utils import find_material_in_catalog

        catalog = load_governance_material_catalog()
        return find_material_in_catalog(catalog, material_name) is not None
    except Exception:
        return False


def validate_governance_material_consistency(
    adapter: Any | None = None,
    recipes_path: Path | None = None,
    repo_root: Path | None = None,
) -> list[dict]:
    """Cross-check adapter manifest, recipe catalog, and file system.

    Checks performed:
    1. Adapter availability: vibe-center adapter must be importable
    2. Recipe availability: governance.scan recipe must load with definition
    3. material_catalog -> adapter: every catalog entry has an adapter resource
    4. material_catalog -> file system: every catalog entry's file exists
    5. adapter -> material_catalog: every governance adapter resource is in catalog

    Parameters accept overrides for testability; when None, load defaults.

    Returns:
        List of dicts with keys: type, message, detail.
        Possible types: missing_adapter, missing_recipe, missing_file, orphaned_adapter.
    """
    from vibe3.adapters import get_adapter
    from vibe3.prompts.manifest import PromptManifest

    issues: list[dict] = []

    # Load defaults when not provided
    if adapter is None:
        adapter = get_adapter("vibe-center")
        if adapter is None:
            issues.append(
                {
                    "type": "missing_adapter",
                    "message": "vibe-center adapter not found",
                    "detail": "Ensure vibe-center adapter module is importable",
                }
            )
            return issues
    if repo_root is None:
        from vibe3.clients import GitClient

        git_client = GitClient()
        git_common_dir = git_client.get_git_common_dir()
        repo_root = Path(git_common_dir).parent if git_common_dir else Path.cwd()

    # Load material catalog from prompt manifest
    try:
        if recipes_path is not None:
            manifest = PromptManifest.load(recipes_path)
        else:
            manifest = PromptManifest.load_default()
        recipe_def = manifest.recipe("governance.scan")
        if not recipe_def or not recipe_def.loaded_definition:
            issues.append(
                {
                    "type": "missing_recipe",
                    "message": "governance.scan recipe not found or not loaded",
                    "detail": "Cannot validate without recipe definition",
                }
            )
            return issues
        material_catalog = recipe_def.loaded_definition.material_catalog
    except Exception as exc:
        issues.append(
            {
                "type": "missing_recipe",
                "message": f"Failed to load governance.scan recipe: {exc}",
                "detail": "Cannot validate without recipe definition",
            }
        )
        return issues

    catalog_paths = {m.name for m in material_catalog}

    # Check 1: material_catalog -> adapter
    adapter_supervisor_paths = {
        r.path for r in adapter.get_resources_by_type("supervisor")
    }
    for material in material_catalog:
        if material.name not in adapter_supervisor_paths:
            issues.append(
                {
                    "type": "missing_adapter",
                    "message": (
                        f"Material '{material.name}' in catalog but not"
                        " registered in adapter"
                    ),
                    "detail": (
                        f"Add AdapterResource for '{material.name}'"
                        " to adapter manifest"
                    ),
                }
            )

    # Check 2: material_catalog -> file system
    for material in material_catalog:
        file_path = repo_root / material.name
        if not file_path.exists():
            issues.append(
                {
                    "type": "missing_file",
                    "message": (
                        f"Material '{material.name}' in catalog but file"
                        f" not found at {file_path}"
                    ),
                    "detail": f"File does not exist at {file_path}",
                }
            )

    # Check 3: adapter -> material_catalog
    for resource in adapter.get_resources_by_type("supervisor"):
        if (
            resource.path.startswith("supervisor/governance/")
            and resource.path not in catalog_paths
        ):
            issues.append(
                {
                    "type": "orphaned_adapter",
                    "message": (
                        f"Adapter has governance resource '{resource.path}'"
                        " not in material catalog"
                    ),
                    "detail": (
                        f"Add '{resource.path}' to material_catalog"
                        " or remove from adapter manifest"
                    ),
                }
            )

    return issues


def list_governance_materials(console: Any) -> None:
    """List available governance materials with descriptions.

    Loads catalog, extracts descriptions, and displays via UI layer.

    Args:
        console: Rich Console instance for display
    """
    import typer

    from vibe3.roles.governance import load_governance_material_catalog
    from vibe3.ui.scan_display import display_material_list

    # Load catalog
    try:
        catalog = load_governance_material_catalog()
    except Exception as exc:
        console.print(f"[red]Error loading material catalog: {exc}[/red]")
        raise typer.Exit(1)

    # Build materials list with descriptions
    materials = []
    for material in catalog:
        description = extract_material_description(material.name)
        materials.append({"name": material.name, "description": description})

    # Display via UI layer
    display_material_list(console, materials)
