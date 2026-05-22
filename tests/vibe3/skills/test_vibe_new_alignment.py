from pathlib import Path


def test_vibe_new_skill_uses_layered_pseudocode_sections() -> None:
    """Test that vibe-new SKILL.md has clear bootstrap structure."""
    content = Path("skills/vibe-new/SKILL.md").read_text(encoding="utf-8")

    # Simplified structure: numbered steps instead of explicit section headers
    assert "## 1. 强制前置检查" in content
    assert "## 3. Bootstrap flow scene" in content
    assert "## 停止条件" in content


def test_vibe_new_skill_does_not_introduce_vibe3_new_command() -> None:
    content = Path("skills/vibe-new/SKILL.md").read_text(encoding="utf-8")

    assert "vibe3 new" not in content
    assert "bootstrap_full_workflow" not in content


def test_vibe_new_workflow_no_longer_routes_to_vibe_start() -> None:
    workflow = Path(".agent/workflows/vibe:new.md").read_text(encoding="utf-8")

    assert "/vibe-start" not in workflow
    assert "/vibe-continue" in workflow or "workflow selector" in workflow
