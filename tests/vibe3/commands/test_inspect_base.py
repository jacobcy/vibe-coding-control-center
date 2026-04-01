"""Tests for vibe inspect base subcommand.

Tests CLI surface: argument validation, help output, exit codes.
All external services are mocked.
"""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.inspect import app

runner = CliRunner()


def test_inspect_base_default_parent():
    """Test inspect base defaults to parent policy."""
    mock_git = MagicMock()
    mock_git.get_changed_files.return_value = ["tests/test_foo.py", "docs/README.md"]

    with patch("vibe3.clients.git_client.GitClient") as mock_git_client:
        mock_git_client.return_value = mock_git
        with patch("vibe3.utils.git_helpers.get_current_branch") as mock_branch:
            mock_branch.return_value = "feature/test"
            with patch("vibe3.config.loader.get_config") as mock_config:
                mock_config.return_value.review_scope.critical_paths = ["src/core/"]
                mock_config.return_value.review_scope.public_api_paths = ["src/api/"]
                with patch(
                    "vibe3.commands.pr_helpers.BaseResolutionUsecase.resolve_inspect_base",
                    return_value=MagicMock(base_branch="feature/root"),
                ):
                    result = runner.invoke(app, ["base"])

    assert result.exit_code == 0
    assert "feature/test vs feature/root" in result.output
    assert "No core files changed" in result.output


def test_inspect_base_custom_base_branch():
    """Test inspect base with custom base branch."""
    mock_git = MagicMock()
    mock_git.get_changed_files.return_value = ["tests/test_foo.py", "docs/README.md"]

    with patch("vibe3.clients.git_client.GitClient") as mock_git_client:
        mock_git_client.return_value = mock_git
        with patch("vibe3.utils.git_helpers.get_current_branch") as mock_branch:
            mock_branch.return_value = "feature/test"
            with patch("vibe3.config.loader.get_config") as mock_config:
                mock_config.return_value.review_scope.critical_paths = ["src/core/"]
                mock_config.return_value.review_scope.public_api_paths = ["src/api/"]

                result = runner.invoke(app, ["base", "develop"])

    assert result.exit_code == 0
    assert "feature/test vs develop" in result.output
    assert "No core files changed" in result.output


def test_inspect_base_with_core_files():
    """Test inspect base with core files changed."""
    mock_git = MagicMock()
    mock_git.get_changed_files.return_value = [
        "src/core/important.py",
        "src/api/public.py",
        "tests/test_foo.py",
    ]

    mock_dag = MagicMock()
    mock_dag.impacted_modules = ["vibe3.core", "vibe3.api", "vibe3.utils"]

    with patch("vibe3.clients.git_client.GitClient") as mock_git_client:
        mock_git_client.return_value = mock_git
        with patch("vibe3.utils.git_helpers.get_current_branch") as mock_branch:
            mock_branch.return_value = "feature/test"
            with patch("vibe3.config.loader.get_config") as mock_config:
                mock_config.return_value.review_scope.critical_paths = ["src/core/"]
                mock_config.return_value.review_scope.public_api_paths = ["src/api/"]
                dag_mod = "vibe3.analysis.dag_service"
                with patch(f"{dag_mod}.expand_impacted_modules") as mock_expand:
                    mock_expand.return_value = mock_dag
                    with patch("pathlib.Path.exists", return_value=True):
                        with patch(
                            "vibe3.commands.pr_helpers.BaseResolutionUsecase.resolve_inspect_base",
                            return_value=MagicMock(base_branch="feature/root"),
                        ):
                            result = runner.invoke(app, ["base"])

    assert result.exit_code == 0
    assert "Core files changed (2)" in result.output
    assert "src/core/important.py" in result.output
    assert "src/api/public.py" in result.output
    assert "Impact scope (3 modules)" in result.output


def test_inspect_base_json_output():
    """Test inspect base with JSON output."""
    mock_git = MagicMock()
    mock_git.get_changed_files.return_value = ["src/core/important.py"]

    mock_dag = MagicMock()
    mock_dag.impacted_modules = ["vibe3.core"]

    with patch("vibe3.clients.git_client.GitClient") as mock_git_client:
        mock_git_client.return_value = mock_git
        with patch("vibe3.utils.git_helpers.get_current_branch") as mock_branch:
            mock_branch.return_value = "feature/test"
            with patch("vibe3.config.loader.get_config") as mock_config:
                mock_config.return_value.review_scope.critical_paths = ["src/core/"]
                mock_config.return_value.review_scope.public_api_paths = []
                dag_mod = "vibe3.analysis.dag_service"
                with patch(f"{dag_mod}.expand_impacted_modules") as mock_expand:
                    mock_expand.return_value = mock_dag
                    with patch("pathlib.Path.exists", return_value=True):
                        # Mock score generation to avoid config loading
                        with patch(
                            "vibe3.services.pr_scoring_service.generate_score_report"
                        ) as mock_score:
                            mock_score.return_value = {
                                "score": 5,
                                "level": "MEDIUM",
                                "block": False,
                            }
                            with patch(
                                "vibe3.commands.pr_helpers.BaseResolutionUsecase.resolve_inspect_base",
                                return_value=MagicMock(base_branch="feature/root"),
                            ):
                                result = runner.invoke(app, ["base", "--json"])

    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert data["current_branch"] == "feature/test"
    assert data["base_branch"] == "feature/root"
    assert data["core_changed"] == 1
    assert data["total_changed"] == 1
    assert len(data["core_files"]) == 1
    assert data["core_files"][0]["critical_path"] is True


def test_inspect_base_json_custom_branch():
    """Test inspect base JSON output with custom base branch."""
    mock_git = MagicMock()
    mock_git.get_changed_files.return_value = ["src/core/important.py"]

    mock_dag = MagicMock()
    mock_dag.impacted_modules = ["vibe3.core"]

    with patch("vibe3.clients.git_client.GitClient") as mock_git_client:
        mock_git_client.return_value = mock_git
        with patch("vibe3.utils.git_helpers.get_current_branch") as mock_branch:
            mock_branch.return_value = "feature/test"
            with patch("vibe3.config.loader.get_config") as mock_config:
                mock_config.return_value.review_scope.critical_paths = ["src/core/"]
                mock_config.return_value.review_scope.public_api_paths = []
                dag_mod = "vibe3.analysis.dag_service"
                with patch(f"{dag_mod}.expand_impacted_modules") as mock_expand:
                    mock_expand.return_value = mock_dag
                    with patch("pathlib.Path.exists", return_value=True):
                        # Mock score generation to avoid config loading
                        with patch(
                            "vibe3.services.pr_scoring_service.generate_score_report"
                        ) as mock_score:
                            mock_score.return_value = {
                                "score": 5,
                                "level": "MEDIUM",
                                "block": False,
                            }
                            result = runner.invoke(app, ["base", "develop", "--json"])

    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert data["current_branch"] == "feature/test"
    assert data["base_branch"] == "develop"


def test_inspect_base_help():
    """Test inspect base help output."""
    result = runner.invoke(app, ["base", "--help"])
    assert result.exit_code == 0
    assert "core" in result.output.lower() or "critical" in result.output.lower()


def test_inspect_base_uses_shared_base_resolver():
    """inspect base should resolve branch through shared base resolver."""
    mock_git = MagicMock()
    mock_git.get_changed_files.return_value = []

    with patch("vibe3.clients.git_client.GitClient", return_value=mock_git):
        with patch(
            "vibe3.utils.git_helpers.get_current_branch", return_value="feature/test"
        ):
            with patch("vibe3.config.loader.get_config") as mock_config:
                mock_config.return_value.review_scope.critical_paths = ["src/core/"]
                mock_config.return_value.review_scope.public_api_paths = ["src/api/"]
                with patch(
                    "vibe3.commands.pr_helpers.BaseResolutionUsecase.resolve_inspect_base",
                    return_value=MagicMock(base_branch="feature/root"),
                ) as mock_resolve:
                    result = runner.invoke(app, ["base"])

    assert result.exit_code == 0
    mock_resolve.assert_called_once_with(None, current_branch="feature/test")
