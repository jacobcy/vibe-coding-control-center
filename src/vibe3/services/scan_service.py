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


def run_manual_governance_scan(material_override: str | None = None) -> None:
    """Execute manual governance scan (no heartbeat facade).

    Entry point for scan governance command, calling execution layer directly.

    Args:
        material_override: Optional governance role to override material rotation
    """
    from vibe3.execution.governance_sync_runner import run_governance_sync

    run_governance_sync(
        tick_count=0,  # Manual scan uses tick=0 for default material selection
        material_override=material_override,
        dry_run=False,  # Manual scan is execution (dry-run handled by scan layer)
        show_prompt=False,
        session_id=None,
    )


def run_manual_supervisor_apply(
    issue_number: int, dry_run: bool = False, no_async: bool = False
) -> None:
    """Execute manual supervisor apply for a single issue.

    Entry point for scan supervisor command, calling execution layer directly.

    Args:
        issue_number: Issue to apply supervisor handoff
        dry_run: Preview mode (no execution)
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
            dry_run=dry_run,
            fresh_session=True,
            show_prompt=False,
            spec=SUPERVISOR_CLI_SYNC_SPEC,
        )
    else:
        run_issue_role_async(
            issue_number=issue_number,
            dry_run=dry_run,
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
    from vibe3.utils.label_utils import normalize_labels

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
