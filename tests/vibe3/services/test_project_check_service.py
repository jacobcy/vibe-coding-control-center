"""Tests for project check service."""

import subprocess
from pathlib import Path
from unittest.mock import patch

from vibe3.services.project_check_service import (
    CheckCategory,
    CheckItem,
    ProjectCheckResult,
    ProjectCheckService,
)


class TestProjectCheckService:
    """Tests for ProjectCheckService."""

    def test_get_git_root_from_repo_root(self, tmp_path: Path) -> None:
        """Test _get_git_root works correctly from repo root."""
        # Create a real git repo
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        subprocess.run(["git", "init"], cwd=repo_root, check=True)

        # Test from repo root
        service = ProjectCheckService(project_root=repo_root)
        git_root = service._get_git_root()
        assert git_root == repo_root, f"Expected {repo_root}, got {git_root}"

    def test_get_git_root_from_subdirectory(self, tmp_path: Path) -> None:
        """Test _get_git_root works correctly from a subdirectory."""
        # Create a real git repo
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        subprocess.run(["git", "init"], cwd=repo_root, check=True)

        # Create a subdirectory
        subdir = repo_root / "subdir"
        subdir.mkdir()

        # Test from subdirectory
        service = ProjectCheckService(project_root=subdir)
        git_root = service._get_git_root()
        assert git_root == repo_root, f"Expected {repo_root}, got {git_root}"

    def test_get_git_root_not_a_repo(self, tmp_path: Path) -> None:
        """Test _get_git_root returns None when not in a git repo."""
        service = ProjectCheckService(project_root=tmp_path)
        git_root = service._get_git_root()
        assert git_root is None

    def test_check_git_not_a_repo(self, tmp_path: Path) -> None:
        """Test git checks fail when not in a git repo."""
        service = ProjectCheckService(project_root=tmp_path)
        category = service.check_git_repository()

        # First item should fail
        assert category.items[0].name == "In git repository"
        assert category.items[0].status == "fail"

        # Remaining items should be skipped
        assert all(item.status == "skip" for item in category.items[1:])

    def test_check_vibe3_config_missing(self, tmp_path: Path) -> None:
        """Test vibe3 config checks when directories don't exist."""
        service = ProjectCheckService(project_root=tmp_path)

        # Mock git root to return tmp_path
        with patch.object(service, "_get_git_root", return_value=tmp_path):
            category = service.check_vibe3_config()

            # .git/vibe3/ should be missing
            vibe3_dir_item = next(
                item for item in category.items if "vibe3/ directory" in item.name
            )
            assert vibe3_dir_item.status == "fail"
            assert vibe3_dir_item.fixable is True

    def test_check_vibe3_config_complete(self, tmp_path: Path) -> None:
        """Test vibe3 config checks when all directories exist."""
        # Create required directories
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        vibe3_dir = git_dir / "vibe3"
        vibe3_dir.mkdir()
        handoff_db = vibe3_dir / "handoff.db"
        handoff_db.touch()  # Create empty db file

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        settings_file = claude_dir / "settings.json"
        settings_file.touch()

        service = ProjectCheckService(project_root=tmp_path)

        with patch.object(service, "_get_git_root", return_value=tmp_path):
            category = service.check_vibe3_config()

            # All items should pass
            for item in category.items:
                if item.status != "warning":  # handoff.db may show warning if empty
                    assert item.status in ("pass", "warning")

    def test_fix_create_missing_directories(self, tmp_path: Path) -> None:
        """Test --fix creates missing directories."""
        # Create .git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        service = ProjectCheckService(project_root=tmp_path)

        with patch.object(service, "_get_git_root", return_value=tmp_path):
            result = service.run_checks(fix=True)

            # Directories should be created
            assert (git_dir / "vibe3").exists()
            assert (tmp_path / ".claude").exists()

            # Items should be fixed
            vibe3_category = next(
                cat for cat in result.categories if cat.name == "vibe3 Configuration"
            )
            vibe3_dir_item = next(
                item for item in vibe3_category.items if "vibe3/ directory" in item.name
            )
            assert vibe3_dir_item.status == "pass"

    def test_check_dependencies_python_version(self, tmp_path: Path) -> None:
        """Test Python version check."""
        service = ProjectCheckService(project_root=tmp_path)
        category = service.check_dependencies()

        # Python version check should pass (we're running on 3.11+)
        python_item = next(item for item in category.items if "Python" in item.name)
        assert python_item.status == "pass"

    def test_check_dependencies_project_manifest(self, tmp_path: Path) -> None:
        """Test project manifest detection."""
        # Create pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        pyproject.touch()

        service = ProjectCheckService(project_root=tmp_path)
        category = service.check_dependencies()

        manifest_item = next(item for item in category.items if "manifest" in item.name)
        assert manifest_item.status == "pass"

    def test_check_orchestra_config_missing(self, tmp_path: Path) -> None:
        """Test Orchestra config check when missing."""
        service = ProjectCheckService(project_root=tmp_path)

        with patch.object(service, "_get_git_root", return_value=tmp_path):
            category = service.check_orchestra_config()

            # Should show warning for missing config
            config_item = next(
                item for item in category.items if "config" in item.name.lower()
            )
            assert config_item.status in ("pass", "warning")

    def test_overall_result(self, tmp_path: Path) -> None:
        """Test overall result calculation."""
        service = ProjectCheckService(project_root=tmp_path)

        # Run checks in non-git directory
        result = service.run_checks()

        # Should have failures
        assert result.overall is False

        # Count should have failures
        counts = result.count_results()
        assert counts["fail"] > 0

    def test_count_results(self) -> None:
        """Test result counting."""
        result = ProjectCheckResult()
        category = CheckCategory(
            name="Test",
            items=[
                CheckItem(name="Pass", status="pass", message=""),
                CheckItem(name="Fail", status="fail", message=""),
                CheckItem(name="Warning", status="warning", message=""),
                CheckItem(name="Skip", status="skip", message=""),
            ],
        )
        result.categories.append(category)

        counts = result.count_results()
        assert counts["pass"] == 1
        assert counts["fail"] == 1
        assert counts["warning"] == 1
        assert counts["skip"] == 1
