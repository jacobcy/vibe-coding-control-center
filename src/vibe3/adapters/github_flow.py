"""GitHub Flow adapter — lightweight skill distribution from global runtime."""

from vibe3.adapters import register_adapter
from vibe3.clients import runtime_assets_root
from vibe3.models.adapter_manifest import AdapterManifest, AdapterResource


def _build_github_flow_manifest() -> AdapterManifest:
    """Build GitHub Flow adapter manifest from global ~/.vibe/skills resources."""
    resources: list[AdapterResource] = []
    global_skills = runtime_assets_root() / "skills"
    if global_skills.exists():
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


GITHUB_FLOW_ADAPTER = _build_github_flow_manifest()
register_adapter(GITHUB_FLOW_ADAPTER)
