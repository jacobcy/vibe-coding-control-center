"""Vibe Center adapter definition.

This module declares all resources that belong to the Vibe Center
distribution, making it an explicit adapter instead of implicit
"because it's in this repo" assumption.
"""

from pathlib import Path

from vibe3.adapters import register_adapter
from vibe3.config.adapter_manifest import AdapterManifest, AdapterResource


def _build_vibe_center_manifest() -> AdapterManifest:
    """Build Vibe Center adapter manifest from actual repo resources."""

    resources: list[AdapterResource] = []

    # Core policies (always present in vibe-center)
    resources.extend(
        [
            AdapterResource(
                type="policy", name="common", path=".agent/policies/common.md"
            ),
            AdapterResource(type="policy", name="plan", path=".agent/policies/plan.md"),
            AdapterResource(type="policy", name="run", path=".agent/policies/run.md"),
            AdapterResource(
                type="policy", name="review", path=".agent/policies/review.md"
            ),
        ]
    )

    # Supervisor templates
    resources.extend(
        [
            AdapterResource(
                type="supervisor", name="apply", path="supervisor/apply.md"
            ),
            AdapterResource(
                type="supervisor", name="manager", path="supervisor/manager.md"
            ),
            AdapterResource(
                type="supervisor",
                name="issue-cleanup",
                path="supervisor/issue-cleanup.md",
            ),
            AdapterResource(
                type="supervisor",
                name="project-explorer",
                path="supervisor/project-explorer.md",
            ),
            # Governance templates
            AdapterResource(
                type="supervisor",
                name="roadmap-intake",
                path="supervisor/governance/roadmap-intake.md",
            ),
            AdapterResource(
                type="supervisor",
                name="assignee-pool",
                path="supervisor/governance/assignee-pool.md",
            ),
            AdapterResource(
                type="supervisor",
                name="cron-supervisor",
                path="supervisor/governance/cron-supervisor.md",
            ),
        ]
    )

    # Skills (scan directory)
    skills_dir = Path("skills")
    if skills_dir.exists():
        for skill_path in skills_dir.iterdir():
            if skill_path.is_dir():
                skill_md = skill_path / "SKILL.md"
                if skill_md.exists():
                    resources.append(
                        AdapterResource(
                            type="skill",
                            name=skill_path.name,
                            path=str(skill_md.relative_to(".")),
                        )
                    )

    # Workflows (from .agent/workflows)
    workflows_dir = Path(".agent/workflows")
    if workflows_dir.exists():
        for workflow_path in workflows_dir.glob("*.md"):
            resources.append(
                AdapterResource(
                    type="workflow",
                    name=workflow_path.stem,
                    path=str(workflow_path.relative_to(".")),
                )
            )

    return AdapterManifest(
        name="vibe-center",
        version="3.0.0",
        description=(
            "Vibe Center opinionated distribution with"
            " full governance and orchestration"
        ),
        resources=resources,
    )


# Build and register
VIBE_CENTER_ADAPTER = _build_vibe_center_manifest()
register_adapter(VIBE_CENTER_ADAPTER)
