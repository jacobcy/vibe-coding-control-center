"""Regression tests for run_command behavior that must not drift."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from vibe3.agents.models import CodeagentResult
from vibe3.exceptions import SkillNotAvailableError
from vibe3.roles.run_command import execute_manual_run, resolve_skill_path


@pytest.fixture(autouse=True)
def clear_repo_context_caches():
    """Keep profile/repo cache mutations from leaking across tests."""
    from vibe3.config.convention_resolver import get_convention, get_resolver
    from vibe3.utils.git_helpers import find_repo_root as _find_repo_root_impl

    get_convention.cache_clear()
    get_resolver.cache_clear()
    _find_repo_root_impl.cache_clear()
    yield
    get_convention.cache_clear()
    get_resolver.cache_clear()
    _find_repo_root_impl.cache_clear()


def test_skill_not_available_error_includes_profile() -> None:
    """SkillNotAvailableError includes the current profile in the message."""
    with (
        patch("vibe3.roles.run_command.resolve_skill_path", return_value=None),
        patch(
            "vibe3.config.convention_resolver.ConventionResolver._detect_profile",
            return_value="minimal",
        ),
        pytest.raises(SkillNotAvailableError) as exc_info,
    ):
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


def test_execute_manual_run_uses_resolve_runtime_asset() -> None:
    """execute_manual_run reads skill content through runtime asset resolution."""
    with (
        patch(
            "vibe3.roles.run_command.resolve_skill_path",
            return_value="skills/vibe-commit/SKILL.md",
        ),
        patch("vibe3.roles.run_command.resolve_runtime_asset") as mock_resolve,
        patch("vibe3.roles.run_command.CodeagentExecutionService") as mock_service_cls,
    ):
        mock_skill_path = MagicMock(spec=Path)
        mock_skill_path.read_text.return_value = "# Test Skill\n"
        mock_resolve.return_value = mock_skill_path
        mock_service_cls.return_value.execute_sync.return_value = CodeagentResult(
            success=True
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

    mock_resolve.assert_called_once_with("skills/vibe-commit/SKILL.md")
    mock_skill_path.read_text.assert_called_once_with(encoding="utf-8")


def test_execute_manual_run_resolves_github_flow_skill_from_global_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """External repos using github-flow discover and read global skills."""
    # Clear resolver cache to ensure fresh resolver for custom test environment
    from vibe3.config.convention_resolver import get_resolver
    from vibe3.utils.git_helpers import find_repo_root as _find_repo_root_impl

    get_resolver.cache_clear()
    _find_repo_root_impl.cache_clear()

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
    adapter_registry.register_adapter(
        github_flow._build_github_flow_manifest(global_skills=runtime_root / "skills")
    )

    captured_prompt: dict[str, str] = {}

    def fake_execute_sync(command: Any) -> CodeagentResult:
        captured_prompt["text"] = command.context_builder()
        return CodeagentResult(success=True)

    try:
        with (
            patch(
                "vibe3.utils.git_helpers.get_git_common_dir",
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


def test_async_publish_dispatch_preserves_publish_cli_mode() -> None:
    """Default async publish dispatch must re-enter the child as run --publish."""
    captured: dict[str, object] = {}

    def fake_dispatch(**kwargs: object):
        captured.update(kwargs)
        # Return AsyncDispatchResult to match new return type
        from vibe3.roles.run_command import AsyncDispatchResult

        return AsyncDispatchResult(tmux_session=None, log_path=None)

    with (
        patch(
            "vibe3.roles.run_command.resolve_skill_path",
            return_value="skills/vibe-commit/SKILL.md",
        ),
        patch("vibe3.roles.run_command.resolve_runtime_asset") as mock_resolve,
        patch(
            "vibe3.roles.run_command.dispatch_run_command_async",
            side_effect=fake_dispatch,
        ),
    ):
        mock_skill_path = MagicMock(spec=Path)
        mock_skill_path.read_text.return_value = "# Commit Skill\n"
        mock_resolve.return_value = mock_skill_path

        result = execute_manual_run(
            config=MagicMock(),
            branch="task/issue-42",
            issue_number=42,
            instructions=None,
            plan_file=None,
            skill="vibe-commit",
            summary=MagicMock(),
            dry_run=False,
            no_async=False,
            show_prompt=False,
            agent=None,
            backend=None,
            model=None,
            publish=True,
        )

    assert result is not None
    assert result.success is True
    assert result.plan_ref is None
    assert captured["cli_args"] == ["run", "--publish"]
    assert captured["handoff_metadata"] == {"skill": "vibe-commit", "publish": True}


def test_async_plan_dispatch_returns_codeagent_result() -> None:
    """Async run dispatch should return displayable launch metadata."""
    from vibe3.roles.run_command import AsyncDispatchResult

    with (
        patch(
            "vibe3.roles.run_command.dispatch_run_command_async",
            return_value=AsyncDispatchResult(
                tmux_session="vibe3-run-issue-42",
                log_path="temp/logs/run.log",
                backend="claude",
                model="haiku",
                launched=True,
            ),
        ),
        patch("vibe3.roles.run_command.SQLiteClient") as mock_sqlite_cls,
    ):
        mock_sqlite_cls.return_value.get_flow_state.return_value = None
        result = execute_manual_run(
            config=MagicMock(run=MagicMock(run_prompt="run prompt")),
            branch="task/issue-42",
            issue_number=42,
            instructions=None,
            plan_file="docs/plans/cleanup-v2.md",
            skill=None,
            summary=MagicMock(mode="flow"),
            dry_run=False,
            no_async=False,
            show_prompt=False,
            agent=None,
            backend=None,
            model=None,
        )

    assert result is not None
    assert result.success is True
    assert result.backend == "claude"
    assert result.model == "haiku"
    assert result.plan_ref == "docs/plans/cleanup-v2.md"
    assert result.tmux_session == "vibe3-run-issue-42"
    assert result.log_path == "temp/logs/run.log"


def test_async_plan_dispatch_fills_backend_model_from_run_config() -> None:
    """Async run result metadata should not depend on launcher-populated fields."""
    from vibe3.roles.run_command import AsyncDispatchResult

    config = SimpleNamespace(
        run=SimpleNamespace(
            run_prompt="run prompt",
            agent_config=SimpleNamespace(
                agent=None,
                backend="claude",
                model="haiku",
                timeout_seconds=3600,
            ),
        )
    )

    with (
        patch(
            "vibe3.roles.run_command.dispatch_run_command_async",
            return_value=AsyncDispatchResult(
                tmux_session="vibe3-run-issue-42",
                log_path="temp/logs/run.log",
                backend=None,
                model=None,
                launched=True,
            ),
        ),
        patch("vibe3.roles.run_command.SQLiteClient") as mock_sqlite_cls,
    ):
        mock_sqlite_cls.return_value.get_flow_state.return_value = None
        result = execute_manual_run(
            config=config,
            branch="task/issue-42",
            issue_number=42,
            instructions=None,
            plan_file="docs/plans/cleanup-v2.md",
            skill=None,
            summary=MagicMock(mode="flow"),
            dry_run=False,
            no_async=False,
            show_prompt=False,
            agent=None,
            backend=None,
            model=None,
        )

    assert result is not None
    assert result.backend == "claude"
    assert result.model == "haiku"
