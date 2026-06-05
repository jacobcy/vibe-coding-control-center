from pathlib import Path


def _skill_content() -> str:
    return Path("skills/vibe-project-check/SKILL.md").read_text(encoding="utf-8")


def test_project_check_documents_internal_manager_prompt_readiness_command() -> None:
    content = _skill_content()

    assert "internal manager 命令缺少 --dry-run/--show-prompt" not in content
    assert "vibe3 internal manager" in content
    assert "--dry-run --show-prompt --branch" in content


def test_project_check_covers_prompt_recipe_runtime_assets() -> None:
    content = _skill_content()

    required_assets = [
        "supervisor/apply.md",
        "supervisor/governance/assignee-pool.md",
        "supervisor/governance/roadmap-intake.md",
        "supervisor/governance/cron-supervisor.md",
        "supervisor/governance/code-auditor.md",
    ]
    for asset in required_assets:
        assert asset in content

    assert "Global runtime assets: 14/14 present" in content
