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


def fetch_supervisor_candidates(github_client: Any, repo: str | None) -> list[dict]:
    """Fetch supervisor candidate issues from GitHub.

    Filters for issues with both 'supervisor' and 'state/handoff' labels.

    Args:
        github_client: GitHubClient instance
        repo: Repository in "owner/repo" format

    Returns:
        List of candidate issues (number, title, labels)
    """
    from vibe3.utils.label_utils import normalize_labels

    try:
        raw_issues = github_client.list_issues(limit=100, state="open", repo=repo)

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

        return matching

    except Exception as e:
        logger.error(f"Failed to fetch supervisor candidates: {e}")
        return []


def render_governance_prompt_preview(
    config: Any, tick_count: int, material_override: str | None
) -> str:
    """Render governance prompt for preview.

    Args:
        config: Orchestra config
        tick_count: Tick count for material rotation
        material_override: Optional material override

    Returns:
        Rendered prompt text
    """
    from vibe3.roles.governance import (
        build_governance_dry_run_context,
        render_governance_prompt,
    )

    # Build minimal snapshot context for dry-run
    snapshot_context = build_governance_dry_run_context()

    # Render prompt
    render_result = render_governance_prompt(
        config,
        snapshot_context,
        tick_count=tick_count,
        material_override=material_override,
    )

    return render_result.rendered_text
