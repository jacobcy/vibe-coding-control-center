"""Tests for CLI override forwarding in async dispatch paths."""

from unittest.mock import MagicMock, patch

from vibe3.roles.run_command import execute_manual_run


class TestAsyncOverrideForwarding:
    """Tests for CLI override forwarding in async dispatch paths."""

    def test_skill_path_forwards_overrides(self):
        """Test that skill-path async dispatch forwards CLI overrides."""
        captured_cli_args: dict[str, list[str]] = {}

        def capture_cli_args(*, cli_args, **kwargs):
            captured_cli_args["args"] = cli_args
            # Return AsyncDispatchResult to match new return type
            from vibe3.roles.run_command import AsyncDispatchResult

            return AsyncDispatchResult(tmux_session=None, log_path=None)

        with (
            patch(
                "vibe3.roles.run_command.dispatch_run_command_async",
                side_effect=capture_cli_args,
            ),
            patch(
                "vibe3.roles.run_command.resolve_skill_path",
                return_value="skills/test-skill/SKILL.md",
            ),
            patch("vibe3.roles.run_command.resolve_runtime_asset") as mock_asset,
            patch("vibe3.roles.run_command.SQLiteClient"),
            patch("vibe3.roles.run_command.CodeagentExecutionService"),
        ):
            # Mock the skill file content
            mock_path = MagicMock()
            mock_path.read_text.return_value = "# Test Skill"
            mock_asset.return_value = mock_path

            execute_manual_run(
                config=MagicMock(),
                branch="task/issue-2117",
                issue_number=2117,
                instructions=None,
                plan_file=None,
                skill="test-skill",
                summary=MagicMock(),
                dry_run=False,
                no_async=False,
                show_prompt=False,
                agent="custom-agent",
                backend="custom-backend",
                model="custom-model",
                fresh_session=True,
            )

        cli_args = captured_cli_args["args"]
        assert "--agent" in cli_args
        assert "custom-agent" in cli_args
        assert "--backend" in cli_args
        assert "custom-backend" in cli_args
        assert "--model" in cli_args
        assert "custom-model" in cli_args
        assert "--fresh-session" in cli_args

    def test_run_path_forwards_overrides(self):
        """Test that run-path async dispatch forwards CLI overrides."""
        captured_cli_args: dict[str, list[str]] = {}

        def capture_cli_args(*, cli_args, **kwargs):
            captured_cli_args["args"] = cli_args
            # Return AsyncDispatchResult to match new return type
            from vibe3.roles.run_command import AsyncDispatchResult

            return AsyncDispatchResult(tmux_session=None, log_path=None)

        with (
            patch(
                "vibe3.roles.run_command.dispatch_run_command_async",
                side_effect=capture_cli_args,
            ),
            patch("vibe3.roles.run_command.SQLiteClient") as mock_sqlite_cls,
            patch("vibe3.roles.run_command.CodeagentExecutionService"),
        ):
            mock_sqlite = MagicMock()
            mock_sqlite_cls.return_value = mock_sqlite
            mock_sqlite.get_flow_state.return_value = None

            execute_manual_run(
                config=MagicMock(run=MagicMock(run_prompt="test")),
                branch="task/issue-2117",
                issue_number=2117,
                instructions="test instructions",
                plan_file="/tmp/plan.md",
                skill=None,
                summary=MagicMock(mode="plan"),
                dry_run=False,
                no_async=False,
                show_prompt=False,
                agent="custom-agent",
                backend="custom-backend",
                model="custom-model",
                fresh_session=True,
            )

        cli_args = captured_cli_args["args"]
        assert "--agent" in cli_args
        assert "custom-agent" in cli_args
        assert "--backend" in cli_args
        assert "custom-backend" in cli_args
        assert "--model" in cli_args
        assert "custom-model" in cli_args
        assert "--fresh-session" in cli_args

    def test_no_overrides_produces_clean_args(self):
        """Test that absence of overrides produces no override flags."""
        captured_cli_args: dict[str, list[str]] = {}

        def capture_cli_args(*, cli_args, **kwargs):
            captured_cli_args["args"] = cli_args
            # Return AsyncDispatchResult to match new return type
            from vibe3.roles.run_command import AsyncDispatchResult

            return AsyncDispatchResult(tmux_session=None, log_path=None)

        with (
            patch(
                "vibe3.roles.run_command.dispatch_run_command_async",
                side_effect=capture_cli_args,
            ),
            patch(
                "vibe3.roles.run_command.resolve_skill_path",
                return_value="skills/test-skill/SKILL.md",
            ),
            patch("vibe3.roles.run_command.resolve_runtime_asset") as mock_asset,
            patch("vibe3.roles.run_command.SQLiteClient"),
            patch("vibe3.roles.run_command.CodeagentExecutionService"),
        ):
            # Mock the skill file content
            mock_path = MagicMock()
            mock_path.read_text.return_value = "# Test Skill"
            mock_asset.return_value = mock_path

            execute_manual_run(
                config=MagicMock(),
                branch="task/issue-2117",
                issue_number=2117,
                instructions=None,
                plan_file=None,
                skill="test-skill",
                summary=MagicMock(),
                dry_run=False,
                no_async=False,
                show_prompt=False,
                agent=None,
                backend=None,
                model=None,
                fresh_session=False,
            )

        cli_args = captured_cli_args["args"]
        assert "--agent" not in cli_args
        assert "--backend" not in cli_args
        assert "--model" not in cli_args
        assert "--fresh-session" not in cli_args
