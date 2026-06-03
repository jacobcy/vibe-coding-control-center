"""Tests for run_command skill resolution and dispatch."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.agents.models import CodeagentResult
from vibe3.config.convention_resolver import ConventionResolver
from vibe3.models.adapter_manifest import AdapterManifest, AdapterResource
from vibe3.roles.run_command import execute_manual_run, resolve_skill_path


def _get_adapter_for_profile(profile_config):
    """Return a focused adapter stub for profile lookup tests."""
    if profile_config.profile != "vibe-center":
        return None
    return AdapterManifest(
        name="vibe-center",
        version="3.0.0",
        description="Focused adapter stub for run command tests",
        resources=[
            AdapterResource(
                type="skill",
                name="vibe-commit",
                path="skills/vibe-commit/SKILL.md",
            )
        ],
    )


def test_skill_path_uses_profile():
    """Test skill lookup uses profile resolution."""
    with patch(
        "vibe3.config.profile_config.ProfileConfig._get_adapter",
        _get_adapter_for_profile,
    ):
        resolver = ConventionResolver(profile="vibe-center")
        path = resolve_skill_path("vibe-commit", resolver)
        resolver_minimal = ConventionResolver(profile="minimal")
        path_minimal = resolve_skill_path("vibe-commit", resolver_minimal)

    assert path is not None
    assert "skills/vibe-commit/SKILL.md" in path
    assert path_minimal is None


def test_skill_path_returns_none_for_missing():
    """Test that missing skills return None."""
    resolver = ConventionResolver(profile="minimal")
    path = resolve_skill_path("nonexistent-skill", resolver)
    assert path is None


def test_skill_path_without_resolver_uses_default(monkeypatch):
    """Test that omitting resolver uses default from_repo().

    In vibe-center repo (detected via git remote), should find vibe-commit.
    In external repos, should return None (minimal profile).
    """
    # Force vibe-center profile to make test deterministic
    monkeypatch.setenv("VIBE_PROFILE", "vibe-center")
    with patch(
        "vibe3.config.profile_config.ProfileConfig._get_adapter",
        _get_adapter_for_profile,
    ):
        path = resolve_skill_path("vibe-commit")
    assert path is not None
    assert "skills/vibe-commit/SKILL.md" in path


def test_execute_manual_run_reads_skill_from_real_repo_root_under_git_isolation(
    monkeypatch,
) -> None:
    """Skill execution should not trust an isolated git common dir for resources."""
    monkeypatch.chdir(Path.cwd() / "src")

    captured_prompt: dict[str, str] = {}

    def fake_execute_sync(command):
        captured_prompt["text"] = command.context_builder()
        return CodeagentResult(success=True)

    with (
        patch(
            "vibe3.roles.run_command.resolve_skill_path",
            return_value="skills/vibe-commit/SKILL.md",
        ),
        patch("vibe3.roles.run_command.CodeagentExecutionService") as mock_service_cls,
    ):
        mock_service_cls.return_value.execute_sync.side_effect = fake_execute_sync

        result = execute_manual_run(
            config=MagicMock(),
            branch="task/issue-1885",
            issue_number=1885,
            instructions=None,
            plan_file=None,
            skill="vibe-commit",
            summary=MagicMock(),
            dry_run=False,
            no_async=True,
            show_prompt=False,
            agent=None,
            backend=None,
            model=None,
        )

    assert result == CodeagentResult(success=True)
    assert "vibe-commit" in captured_prompt["text"]


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
