"""Integration tests for PR create command with AI support."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from tests.vibe3.pr_patch_constants import PR_CREATE, PR_PACKAGE
from vibe3.cli import app
from vibe3.config.settings import AIConfig
from vibe3.models import BranchSource
from vibe3.models.pr import UpdatePRRequest
from vibe3.services.pr.create import _build_inspect_summary, _enrich_changed_files
from vibe3.utils.branch_compare import BranchBehindInfo


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


class TestPRCreateCommandAI:
    """Tests for PR create command with --ai flag."""

    def test_pr_create_confirms_existing_pr(self, runner: CliRunner) -> None:
        """Existing PR should be confirmed without requiring title."""
        with patch("vibe3.commands.pr_create.PRService") as mock_service:
            existing_pr = MagicMock(
                number=456,
                title="Existing PR",
                body="",
                model_dump=lambda: {"number": 456, "title": "Existing PR"},
            )
            mock_service.return_value.get_open_pr_for_branch.return_value = existing_pr

            result = runner.invoke(app, ["pr", "create", "--json", "--yes"])

        assert result.exit_code == 0
        assert json.loads(result.output)["number"] == 456
        mock_service.return_value.sync_pr_state_from_remote.assert_called_once_with(
            existing_pr, actor=None
        )
        mock_service.return_value.create_pr.assert_not_called()

    def test_pr_create_existing_pr_shows_confirmed_status(
        self, runner: CliRunner
    ) -> None:
        """Non-JSON output should report existing PR status instead of created."""
        with patch("vibe3.commands.pr_create.PRService") as mock_service:
            existing_pr = MagicMock(
                number=456,
                title="Existing PR",
                body="",
                state=MagicMock(value="MERGED"),
                draft=False,
                url="https://github.com/org/repo/pull/456",
                head_branch="task/311",
                base_branch="main",
            )
            mock_service.return_value.get_open_pr_for_branch.return_value = existing_pr

            result = runner.invoke(app, ["pr", "create", "--yes"])

        assert result.exit_code == 0
        assert "already exists and is merged" in result.output.lower()

    def test_pr_create_requires_yes_flag(self, runner: CliRunner) -> None:
        """PR create should exit with a warning if --yes is not provided."""
        result = runner.invoke(app, ["pr", "create"])
        assert result.exit_code == 0
        assert "此命令需要明确确认" in result.output

    def test_pr_create_without_ai(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test PR create without --ai flag works normally."""
        with (
            patch(
                "vibe3.commands.pr_create.FlowService.get_current_branch",
                return_value="task/demo",
            ),
            patch(
                "vibe3.commands.pr_helpers.BaseResolutionUsecase.resolve_pr_create_base",
                return_value="main",
            ),
            patch(f"{PR_PACKAGE}.PRCreateUsecase.check_flow_task"),
            patch("vibe3.commands.pr_create.PRService") as mock_service,
            patch(
                "vibe3.commands.pr_create.check_branch_behind", return_value=None
            ),  # Mock branch behind check
        ):
            mock_service.return_value.get_open_pr_for_branch.return_value = None
            mock_service.return_value.create_pr.return_value = MagicMock(
                number=123,
                title="Test PR",
                body="Test body",
                model_dump=lambda: {"number": 123, "title": "Test PR"},
            )
            result = runner.invoke(app, ["pr", "create", "-t", "Test PR", "--yes"])
        assert result.exit_code == 0
        mock_service.return_value.create_pr.assert_called_once_with(
            title="Test PR",
            body="",
            base_branch="main",
            actor=None,
        )

    def test_pr_create_ai_disabled(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test PR create with --ai when AI is disabled."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("vibe3.commands.pr_create.PRService") as mock_service:
                mock_service.return_value.get_open_pr_for_branch.return_value = None
                mock_service.return_value.create_pr.return_value = MagicMock(
                    number=123,
                    title="Test PR",
                    body="Test body",
                    model_dump=lambda: {"number": 123},
                )
                with patch(f"{PR_CREATE}.VibeConfig.get_defaults") as mock_config:
                    mock_config.return_value.ai.enabled = False
                    result = runner.invoke(app, ["pr", "create", "--ai", "--yes"])
                    # Should fail because title missing and AI disabled
                    assert result.exit_code != 0

    def test_pr_create_ai_json_uses_suggestions_without_prompt(
        self, runner: CliRunner
    ) -> None:
        """Test pr create --ai --json uses AI result without prompting."""
        with patch(
            "vibe3.commands.pr_create.FlowService.get_current_branch",
            return_value="task/refactor/v3-thin-commands-19k",
        ):
            with patch(
                "vibe3.commands.pr_helpers.BaseResolutionUsecase.resolve_pr_create_base",
                return_value="origin/main",
            ):
                with patch(
                    f"{PR_PACKAGE}.BaseResolutionUsecase.collect_branch_material"
                ) as mock_material:
                    mock_material.return_value = MagicMock(
                        commits=["feat: add feature"],
                        changed_files=["src/file.py"],
                    )
                    with patch(f"{PR_CREATE}.VibeConfig.get_defaults") as mock_config:
                        mock_config.return_value.ai = AIConfig()
                        with patch(
                            f"{PR_CREATE}.AISuggestionClient.suggest_pr_content"
                        ) as mock_suggest:
                            mock_suggest.return_value = (
                                "feat: ai title",
                                "Summary\n\n- change",
                            )
                            with (
                                patch(f"{PR_PACKAGE}.PRCreateUsecase.check_flow_task"),
                                patch(
                                    f"{PR_CREATE}._build_inspect_summary",
                                    return_value="",
                                ),
                                patch(
                                    "vibe3.commands.pr_create.PRService"
                                ) as mock_service,
                                patch(
                                    "vibe3.commands.pr_create.check_branch_behind",
                                    return_value=None,
                                ),  # Mock branch behind check
                            ):
                                pr_service = mock_service.return_value
                                pr_service.get_open_pr_for_branch.return_value = None
                                mock_pr = MagicMock(
                                    number=123,
                                    title="feat: ai title",
                                    body="Summary\n\n- change",
                                    model_dump=lambda: {
                                        "number": 123,
                                        "title": "feat: ai title",
                                        "body": "Summary\n\n- change",
                                    },
                                )
                                mock_service.return_value.create_pr.return_value = (
                                    mock_pr
                                )
                                result = runner.invoke(
                                    app,
                                    ["pr", "create", "--ai", "--json", "--yes"],
                                )

        assert result.exit_code == 0
        assert json.loads(result.output)["title"] == "feat: ai title"

    def test_pr_create_ai_requires_commits_for_suggestions(
        self, runner: CliRunner
    ) -> None:
        """Test --ai mode fails with clear error when no commits available."""
        with patch(
            "vibe3.commands.pr_create.FlowService.get_current_branch",
            return_value="main",
        ):
            with patch(
                "vibe3.commands.pr_helpers.BaseResolutionUsecase.resolve_pr_create_base",
                return_value="main",
            ):
                with patch(f"{PR_PACKAGE}.PRCreateUsecase.check_flow_task"):
                    with patch("vibe3.commands.pr_create.PRService") as mock_service:
                        pr_service = mock_service.return_value
                        pr_service.get_open_pr_for_branch.return_value = None
                        # Mock collect_branch_material to return empty commits
                        with patch(
                            f"{PR_PACKAGE}.BaseResolutionUsecase.collect_branch_material"
                        ) as mock_material:
                            mock_material.return_value = MagicMock(
                                commits=[],  # No commits
                                changed_files=[],
                            )
                            result = runner.invoke(
                                app, ["pr", "create", "--ai", "--yes"]
                            )

        assert result.exit_code == 1
        assert "requires commits to generate suggestions" in result.output
        assert "Commit your changes first" in result.output


def test_build_inspect_summary_uses_explicit_base_branch() -> None:
    """Inspect summary should analyze against the caller's base branch."""
    with patch("vibe3.analysis.build_change_analysis") as mock_analysis:
        mock_analysis.return_value = {
            "score": {
                "level": "LOW",
                "score": 1,
                "recommendations": [],
                "dimensions": {},
            }
        }

        _build_inspect_summary("feature/child", "feature/parent")

    mock_analysis.assert_called_once_with("branch", "feature/child", "feature/parent")


def test_enrich_changed_files_uses_numstat_loc_deltas() -> None:
    """Changed file enrichment should parse LOC from numstat, not patch diff."""
    mock_git = MagicMock()
    mock_git.get_numstat.return_value = (
        "12\t3\tsrc/vibe3/services/pr/create.py\n"
        "7\t0\tsrc/vibe3/analysis/snapshot_service.py"
    )

    with patch("vibe3.clients.GitClient", return_value=mock_git):
        result = _enrich_changed_files(
            [
                "src/vibe3/services/pr/create.py",
                "src/vibe3/analysis/snapshot_service.py",
            ],
            "feature/child",
            "feature/parent",
        )

    mock_git.get_numstat.assert_called_once_with(
        BranchSource(branch="feature/child", base="feature/parent")
    )
    assert "- src/vibe3/services/pr/create.py (+9 LOC)" in result
    assert "- src/vibe3/analysis/snapshot_service.py (+7 LOC)" in result


class TestPRCreateBranchBehind:
    """Tests for branch-behind PR body update path."""

    def test_pr_create_branch_behind_updates_body(self, runner: CliRunner) -> None:
        """When branch is behind base, PR body should be updated with warning."""
        with (
            patch(
                "vibe3.commands.pr_create.FlowService.get_current_branch",
                return_value="task/demo",
            ),
            patch(
                "vibe3.commands.pr_helpers.BaseResolutionUsecase.resolve_pr_create_base",
                return_value="main",
            ),
            patch(f"{PR_PACKAGE}.PRCreateUsecase.check_flow_task"),
            patch("vibe3.commands.pr_create.PRService") as mock_service,
            patch("vibe3.commands.pr_create.check_branch_behind") as mock_check_behind,
            patch(
                "vibe3.commands.pr_create.format_branch_behind_body"
            ) as mock_format_body,
        ):
            # Mock branch behind check to return behind info
            behind_info = BranchBehindInfo(
                head_branch="task/demo", base_branch="main", behind_count=3
            )
            mock_check_behind.return_value = behind_info

            # Mock format function to return predictable warning
            mock_format_body.return_value = "__WARNING_PREFIX__"

            # Mock PR service
            pr_service = mock_service.return_value
            pr_service.get_open_pr_for_branch.return_value = None

            # Mock created PR
            created_pr = MagicMock(
                number=123,
                title="Test PR",
                body="Test body",
                head_branch="task/demo",
                base_branch="main",
                model_dump=lambda: {
                    "number": 123,
                    "title": "Test PR",
                    "body": "__WARNING_PREFIX__\n\n---\n\nTest body",
                },
            )
            pr_service.create_pr.return_value = created_pr

            # Mock updated PR
            updated_pr = MagicMock(
                number=123,
                title="Test PR",
                body="__WARNING_PREFIX__\n\n---\n\nTest body",
                head_branch="task/demo",
                base_branch="main",
                model_dump=lambda: {
                    "number": 123,
                    "title": "Test PR",
                    "body": "__WARNING_PREFIX__\n\n---\n\nTest body",
                },
            )
            pr_service.github_client.update_pr.return_value = updated_pr

            result = runner.invoke(
                app, ["pr", "create", "-t", "Test PR", "--json", "--yes"]
            )

        # Verify exit code
        assert result.exit_code == 0

        # Verify format_branch_behind_body was called with correct info
        mock_format_body.assert_called_once_with(behind_info)

        # Verify update_pr was called with updated body
        pr_service.github_client.update_pr.assert_called_once()
        call_args = pr_service.github_client.update_pr.call_args[0][0]
        assert isinstance(call_args, UpdatePRRequest)
        assert call_args.number == 123
        assert call_args.title is None
        assert call_args.body == "__WARNING_PREFIX__\n\n---\n\nTest body"
        assert call_args.draft is None
        assert call_args.base_branch is None

        # Verify create_pr was called (PR created before body update)
        pr_service.create_pr.assert_called_once()

        # Verify JSON output contains updated body
        output = json.loads(result.output)
        assert output["number"] == 123
        assert output["body"] == "__WARNING_PREFIX__\n\n---\n\nTest body"
