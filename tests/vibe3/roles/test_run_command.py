"""Tests for run_command skill resolution and dispatch."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.adapters import register_adapter
from vibe3.models.adapter_manifest import AdapterManifest, AdapterResource
from vibe3.roles.run_command import resolve_skill_path
from vibe3.services.convention_resolver import ConventionResolver


@pytest.fixture(autouse=True)
def ensure_vibe_center_adapter():
    """Ensure vibe-center adapter is registered with correct repo root.

    The isolate_database fixture in tests/vibe3/conftest.py patches
    GitClient.get_git_common_dir() to return a temp directory, which
    breaks the adapter's skill discovery. This fixture ensures the
    adapter is registered with the correct paths for tests that need it.
    """
    # Get the real repo root (not the tempdir from isolate_database)
    # Use the actual git common dir (not patched)
    import subprocess

    result = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        git_common_dir = Path(result.stdout.strip())
        repo_root = (
            git_common_dir.parent
            if git_common_dir.name == ".git"
            else git_common_dir.parent
        )
    else:
        # Fallback to cwd
        repo_root = Path.cwd()

    # Build and register adapter with correct repo root
    resources = []

    # Add skills from real repo
    skills_dir = repo_root / "skills"
    if skills_dir.exists():
        for skill_path in skills_dir.iterdir():
            if skill_path.is_dir():
                skill_md = skill_path / "SKILL.md"
                if skill_md.exists():
                    rel_path = skill_md.relative_to(repo_root)
                    resources.append(
                        AdapterResource(
                            type="skill",
                            name=skill_path.name,
                            path=str(rel_path),
                        )
                    )

    # Add policies (required for vibe-center profile)
    resources.extend(
        [
            AdapterResource(
                type="policy", name="common", path="supervisor/policies/common.md"
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

    adapter = AdapterManifest(
        name="vibe-center",
        version="3.0.0",
        description="Vibe Center adapter for tests",
        resources=resources,
    )
    register_adapter(adapter)

    yield


def test_skill_path_uses_profile(ensure_vibe_center_adapter):
    """Test skill lookup uses profile resolution."""
    resolver = ConventionResolver(profile="vibe-center")
    path = resolve_skill_path("vibe-commit", resolver)
    assert path is not None
    assert "skills/vibe-commit/SKILL.md" in path

    resolver_minimal = ConventionResolver(profile="minimal")
    path_minimal = resolve_skill_path("vibe-commit", resolver_minimal)
    assert path_minimal is None


def test_skill_path_returns_none_for_missing():
    """Test that missing skills return None."""
    resolver = ConventionResolver(profile="minimal")
    path = resolve_skill_path("nonexistent-skill", resolver)
    assert path is None


def test_skill_path_without_resolver_uses_default(
    monkeypatch, ensure_vibe_center_adapter
):
    """Test that omitting resolver uses default from_repo().

    In vibe-center repo (detected via git remote), should find vibe-commit.
    In external repos, should return None (minimal profile).
    """
    # Force vibe-center profile to make test deterministic
    monkeypatch.setenv("VIBE_PROFILE", "vibe-center")
    path = resolve_skill_path("vibe-commit")
    assert path is not None
    assert "skills/vibe-commit/SKILL.md" in path


class TestDispatchRunCommandAsyncWorktreeRequirement:
    """dispatch_run_command_async must set worktree_requirement=PERMANENT."""

    def test_sets_worktree_requirement_permanent(self) -> None:
        """ExecutionRequest must include worktree_requirement=PERMANENT."""
        from vibe3.execution.role_contracts import WorktreeRequirement

        with (
            patch(
                "vibe3.execution.issue_role_support.resolve_orchestra_repo_root",
                return_value=Path("/fake/repo"),
            ),
            patch("vibe3.roles.run_command.load_orchestra_config"),
            patch("vibe3.roles.run_command.SQLiteClient"),
            patch("vibe3.roles.run_command.ExecutionCoordinator") as mock_coord_cls,
        ):
            mock_coord = MagicMock()
            mock_coord_cls.return_value = mock_coord

            from vibe3.roles.run_command import dispatch_run_command_async

            dispatch_run_command_async(
                branch="dev/issue-42",
                cli_args=["run", "--plan", "plan.md"],
                issue_number=42,
                execution_name="vibe3-executor-issue-42",
                handoff_metadata={"plan_ref": "plan.md"},
            )

            exec_request = mock_coord.dispatch_execution.call_args[0][0]
            assert exec_request.worktree_requirement == WorktreeRequirement.PERMANENT
            assert exec_request.cwd is None
            assert exec_request.repo_path == "/fake/repo"

    def test_sets_worktree_requirement_permanent_no_issue(self) -> None:
        """Even without issue_number, worktree_requirement must be PERMANENT."""
        from vibe3.execution.role_contracts import WorktreeRequirement

        with (
            patch(
                "vibe3.execution.issue_role_support.resolve_orchestra_repo_root",
                return_value=Path("/fake/repo"),
            ),
            patch("vibe3.roles.run_command.load_orchestra_config"),
            patch("vibe3.roles.run_command.SQLiteClient"),
            patch("vibe3.roles.run_command.ExecutionCoordinator") as mock_coord_cls,
        ):
            mock_coord = MagicMock()
            mock_coord_cls.return_value = mock_coord

            from vibe3.roles.run_command import dispatch_run_command_async

            dispatch_run_command_async(
                branch="dev/issue-99",
                cli_args=["run"],
                issue_number=None,
                execution_name="vibe3-executor-issue-0",
                handoff_metadata=None,
            )

            exec_request = mock_coord.dispatch_execution.call_args[0][0]
            assert exec_request.worktree_requirement == WorktreeRequirement.PERMANENT
            assert exec_request.target_id == 0
