"""Tests for 'vibe3 prompt check' command."""

import json

from typer.testing import CliRunner

from vibe3.cli import app as cli_app

runner = CliRunner(env={"NO_COLOR": "1"})


class TestPromptCheckCommand:
    def test_help_shows_template_key_argument(self) -> None:
        result = runner.invoke(cli_app, ["prompt", "check", "--help"])
        assert result.exit_code == 0
        assert "TEMPLATE_KEY" in result.output or "template" in result.output.lower()

    def test_known_template_key_exits_0(self) -> None:
        result = runner.invoke(cli_app, ["prompt", "check", "run.plan"])
        assert result.exit_code == 0

    def test_known_template_key_shows_required_variables(self) -> None:
        result = runner.invoke(cli_app, ["prompt", "check", "run.plan"])
        assert result.exit_code == 0
        assert "run_prompt_body" in result.output

    def test_unknown_template_key_exits_1(self) -> None:
        result = runner.invoke(cli_app, ["prompt", "check", "does.not.exist"])
        assert result.exit_code == 1

    def test_unknown_template_key_shows_error(self) -> None:
        result = runner.invoke(cli_app, ["prompt", "check", "does.not.exist"])
        assert "does.not.exist" in result.output or "not found" in result.output.lower()

    def test_json_flag_outputs_valid_json(self) -> None:
        result = runner.invoke(cli_app, ["prompt", "check", "run.plan", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "template_key" in data
        assert data["template_key"] == "run.plan"
        assert "is_valid" in data
        assert "required_variables" in data

    def test_governance_template_key(self) -> None:
        result = runner.invoke(
            cli_app, ["prompt", "check", "orchestra.governance.plan"]
        )
        assert result.exit_code == 0
        assert (
            "supervisor_name" in result.output or "supervisor_content" in result.output
        )

    def test_manager_template_key(self) -> None:
        result = runner.invoke(
            cli_app, ["prompt", "check", "orchestra.assignee_dispatch.manager"]
        )
        assert result.exit_code == 0


class TestPromptCheckList:
    def test_list_all_template_keys(self) -> None:
        result = runner.invoke(cli_app, ["prompt", "check", "--list"])
        assert result.exit_code == 0
        assert "run.plan" in result.output

    def test_list_json_flag(self) -> None:
        result = runner.invoke(cli_app, ["prompt", "check", "--list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert "run.plan" in data
