"""GitHub Flow adapter — lightweight skill distribution from global runtime."""

from pathlib import Path

from vibe3.models import AdapterManifest, AdapterResource


def _build_github_flow_manifest(global_skills: Path | None = None) -> AdapterManifest:
    """Build GitHub Flow adapter manifest from global ~/.vibe/skills resources.

    Args:
        global_skills: Path to global skills directory (from runtime_assets_root)

    Returns:
        AdapterManifest with all GitHub Flow skills
    """
    resources: list[AdapterResource] = []
    if global_skills and global_skills.exists():
        for skill_path in global_skills.iterdir():
            if skill_path.is_dir():
                skill_md = skill_path / "SKILL.md"
                if skill_md.exists():
                    rel_path = skill_md.relative_to(global_skills.parent)
                    resources.append(
                        AdapterResource(
                            type="skill",
                            name=skill_path.name,
                            path=str(rel_path),
                        )
                    )
    return AdapterManifest(
        name="github-flow",
        version="1.0.0",
        description="Lightweight skill distribution from global ~/.vibe runtime",
        resources=resources,
    )
