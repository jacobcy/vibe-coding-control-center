"""Vibe Center adapter definition.

This module declares all resources that belong to the Vibe Center
distribution, making it an explicit adapter instead of implicit
"because it's in this repo" assumption.
"""

from pathlib import Path

from vibe3.adapters.resource_root import resolve_resource_root
from vibe3.models import AdapterManifest, AdapterResource

_SOURCE_REPO_ROOT = Path(__file__).resolve().parents[3]


def _build_vibe_center_manifest(
    git_common_dir: str | None = None,
    global_skills: Path | None = None,
) -> AdapterManifest:
    """Build Vibe Center adapter manifest from actual repo resources.

    Args:
        git_common_dir: Git common directory path (from GitClient)
        global_skills: Path to global skills directory (from runtime_assets_root)

    Returns:
        AdapterManifest with all Vibe Center resources
    """

    repo_root = resolve_resource_root(
        required_marker="skills",
        git_common_dir=git_common_dir,
        additional_roots=(_SOURCE_REPO_ROOT,),
    )

    resources: list[AdapterResource] = []

    # Core policies (always present in vibe-center)
    resources.extend(
        [
            AdapterResource(
                type="policy", name="common", path="supervisor/policies/common.md"
            ),
            AdapterResource(
                type="policy",
                name="common-develop",
                path="supervisor/policies/common-develop.md",
            ),
            AdapterResource(
                type="policy", name="plan", path="supervisor/policies/plan.md"
            ),
            AdapterResource(
                type="policy", name="run", path="supervisor/policies/run.md"
            ),
            AdapterResource(
                type="policy", name="review", path="supervisor/policies/review.md"
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
            AdapterResource(
                type="supervisor",
                name="code-auditor",
                path="supervisor/governance/code-auditor.md",
            ),
            AdapterResource(
                type="supervisor",
                name="audit-observation",
                path="supervisor/governance/audit-observation.md",
            ),
        ]
    )

    # Skills (scan directory)
    skills_dirs = [repo_root / "skills"]
    if (
        global_skills
        and global_skills.exists()
        and global_skills.resolve()
        not in [d.resolve() for d in skills_dirs if d.exists()]
    ):
        skills_dirs.append(global_skills)

    for skills_dir in skills_dirs:
        if not skills_dir.exists():
            continue
        base = repo_root if skills_dir == repo_root / "skills" else skills_dir.parent
        for skill_path in skills_dir.iterdir():
            if skill_path.is_dir():
                skill_md = skill_path / "SKILL.md"
                if skill_md.exists():
                    rel_path = skill_md.relative_to(base)
                    # Avoid duplicates
                    existing_names = {r.name for r in resources if r.type == "skill"}
                    if skill_path.name not in existing_names:
                        resources.append(
                            AdapterResource(
                                type="skill",
                                name=skill_path.name,
                                path=str(rel_path),
                            )
                        )

    # Workflows (from .agent/workflows)
    workflows_dir = repo_root / ".agent/workflows"
    if workflows_dir.exists():
        for workflow_path in workflows_dir.glob("*.md"):
            # Store relative path for portability
            rel_path = workflow_path.relative_to(repo_root)
            resources.append(
                AdapterResource(
                    type="workflow",
                    name=workflow_path.stem,
                    path=str(rel_path),
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
