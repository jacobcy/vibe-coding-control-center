"""Tests for run_command skill resolution and dispatch."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.agents.models import CodeagentResult
from vibe3.config.convention_resolver import ConventionResolver
from vibe3.exceptions import SkillNotAvailableError
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


def test_skill_not_available_error_includes_profile():
    """Test SkillNotAvailableError includes current profile in error message."""
    with patch("vibe3.roles.run_command.resolve_skill_path", return_value=None):
        with patch(
            "vibe3.roles.run_command.ConventionResolver._detect_profile",
            return_value="minimal",
        ):
            with pytest.raises(SkillNotAvailableError) as exc_info:
                execute_manual_run(
                    config=MagicMock(),
                    branch="test/branch",
                    issue_number=123,
                    instructions=None,
                    plan_file=None,
                    skill="nonexistent-skill",
                    summary=MagicMock(),
                    dry_run=True,
                    no_async=True,
                    show_prompt=False,
                    agent=None,
                    backend=None,
                    model=None,
                )

    error_msg = str(exc_info.value)
    assert "nonexistent-skill" in error_msg
    assert "minimal" in error_msg
    assert "VIBE_PROFILE" in error_msg


def test_execute_manual_run_uses_resolve_runtime_asset():
    """Test execute_manual_run uses resolve_runtime_asset for skill file reading."""
    with patch(
        "vibe3.roles.run_command.resolve_skill_path",
        return_value="skills/vibe-commit/SKILL.md",
    ):
        with patch("vibe3.roles.run_command.resolve_runtime_asset") as mock_resolve:
            # Mock resolve_runtime_asset to return a path with skill content
            mock_skill_path = MagicMock(spec=Path)
            mock_skill_path.read_text.return_value = "# Test Skill\n"
            mock_resolve.return_value = mock_skill_path

            with patch(
                "vibe3.roles.run_command.CodeagentExecutionService"
            ) as mock_service_cls:
                mock_service_cls.return_value.execute_sync.return_value = (
                    CodeagentResult(success=True)
                )

                execute_manual_run(
                    config=MagicMock(),
                    branch="test/branch",
                    issue_number=123,
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

            # Verify resolve_runtime_asset was called with skill path
            mock_resolve.assert_called_once_with("skills/vibe-commit/SKILL.md")
            # Verify skill content was read from resolved path
            mock_skill_path.read_text.assert_called_once_with(encoding="utf-8")


def test_execute_manual_run_resolves_github_flow_skill_from_global_runtime(
    monkeypatch, tmp_path: Path
) -> None:
    """External repos using github-flow should discover and read global skills."""
    external_repo = tmp_path / "external-repo"
    external_repo.mkdir()
    git_dir = external_repo / ".git"
    git_dir.mkdir()
    config_dir = external_repo / ".vibe"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text("profile: github-flow\n", encoding="utf-8")

    runtime_root = tmp_path / "runtime"
    skill_dir = runtime_root / "skills" / "ship-it"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Ship It\n\nDo the work.\n", encoding="utf-8")

    monkeypatch.chdir(external_repo)
    monkeypatch.setenv("VIBE3_RUNTIME_ASSETS_ROOT", str(runtime_root))

    import vibe3.adapters as adapter_registry
    from vibe3.adapters import github_flow

    previous_adapter = adapter_registry._ADAPTERS.pop("github-flow", None)
    was_loaded = "github-flow" in adapter_registry._LOADED
    adapter_registry._LOADED.discard("github-flow")
    adapter_registry.register_adapter(github_flow._build_github_flow_manifest())

    captured_prompt: dict[str, str] = {}

    def fake_execute_sync(command):
        captured_prompt["text"] = command.context_builder()
        return CodeagentResult(success=True)

    try:
        with (
            patch(
                "vibe3.clients.git_client.GitClient.get_git_common_dir",
                return_value=str(git_dir),
            ),
            patch("vibe3.roles.run_command.CodeagentExecutionService") as service_cls,
        ):
            service_cls.return_value.execute_sync.side_effect = fake_execute_sync

            assert resolve_skill_path("ship-it") == "skills/ship-it/SKILL.md"

            result = execute_manual_run(
                config=MagicMock(),
                branch="issue-123",
                issue_number=123,
                instructions=None,
                plan_file=None,
                skill="ship-it",
                summary=MagicMock(),
                dry_run=False,
                no_async=True,
                show_prompt=False,
                agent=None,
                backend=None,
                model=None,
            )
    finally:
        adapter_registry._ADAPTERS.pop("github-flow", None)
        if previous_adapter is not None:
            adapter_registry._ADAPTERS["github-flow"] = previous_adapter
        if was_loaded:
            adapter_registry._LOADED.add("github-flow")
        else:
            adapter_registry._LOADED.discard("github-flow")

    assert result == CodeagentResult(success=True)
    assert "# Ship It" in captured_prompt["text"]
