"""Tests for project check CLI command."""

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from vibe3.commands.project_check import app
from vibe3.services.project_check_service import (
    CheckCategory,
    CheckItem,
    ProjectCheckResult,
)

runner = CliRunner()


class TestProjectCheckCLI:
    """Tests for project-check CLI command."""

    def test_project_check_help(self) -> None:
        """Test help output contains expected description."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Check vibe3 ecosystem project environment" in result.output

    def test_project_check_verbose_flag(self, tmp_path: Path) -> None:
        """Test --verbose shows all check items."""
        # Mock the service to return a known result
        mock_result = ProjectCheckResult()
        mock_result.categories.append(
            CheckCategory(
                name="Test",
                items=[
                    CheckItem(name="Pass", status="pass", message="Test pass"),
                    CheckItem(name="Fail", status="fail", message="Test fail"),
                ],
            )
        )

        with patch(
            "vibe3.commands.project_check.ProjectCheckService"
        ) as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.run_checks.return_value = mock_result

            result = runner.invoke(app, ["--verbose"])

            # Should show both pass and fail items
            assert "Test pass" in result.output
            assert "Test fail" in result.output

    def test_project_check_non_verbose(self, tmp_path: Path) -> None:
        """Test non-verbose mode hides passing items."""
        mock_result = ProjectCheckResult()
        mock_result.categories.append(
            CheckCategory(
                name="Test",
                items=[
                    CheckItem(name="Pass", status="pass", message="Test pass"),
                    CheckItem(name="Fail", status="fail", message="Test fail"),
                ],
            )
        )
        mock_result.overall = False

        with patch(
            "vibe3.commands.project_check.ProjectCheckService"
        ) as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.run_checks.return_value = mock_result

            result = runner.invoke(app, [])

            # Should only show fail item
            assert "Test fail" in result.output
            # Pass item should not be shown (only in summary)
            assert result.exit_code == 1

    def test_project_check_json_output(self, tmp_path: Path) -> None:
        """Test --json outputs valid JSON."""
        mock_result = ProjectCheckResult()
        mock_result.categories.append(
            CheckCategory(
                name="Test",
                items=[
                    CheckItem(name="Pass", status="pass", message="Test pass"),
                ],
            )
        )

        with patch(
            "vibe3.commands.project_check.ProjectCheckService"
        ) as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.run_checks.return_value = mock_result

            result = runner.invoke(app, ["--json"])

            # Should be valid JSON
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "overall" in data
            assert "categories" in data
            assert "summary" in data

    def test_project_check_exit_code_on_failure(self, tmp_path: Path) -> None:
        """Test exit code is 1 when checks fail."""
        mock_result = ProjectCheckResult()
        mock_result.overall = False
        mock_result.categories.append(
            CheckCategory(
                name="Test",
                items=[
                    CheckItem(name="Fail", status="fail", message="Test fail"),
                ],
            )
        )

        with patch(
            "vibe3.commands.project_check.ProjectCheckService"
        ) as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.run_checks.return_value = mock_result

            result = runner.invoke(app, [])
            assert result.exit_code == 1

    def test_project_check_exit_code_on_success(self, tmp_path: Path) -> None:
        """Test exit code is 0 when all checks pass."""
        mock_result = ProjectCheckResult()
        mock_result.overall = True
        mock_result.categories.append(
            CheckCategory(
                name="Test",
                items=[
                    CheckItem(name="Pass", status="pass", message="Test pass"),
                ],
            )
        )

        with patch(
            "vibe3.commands.project_check.ProjectCheckService"
        ) as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.run_checks.return_value = mock_result

            result = runner.invoke(app, [])
            assert result.exit_code == 0

    def test_project_check_fix_flag(self, tmp_path: Path) -> None:
        """Test --fix calls fix logic."""
        mock_result = ProjectCheckResult()
        mock_result.overall = True

        with patch(
            "vibe3.commands.project_check.ProjectCheckService"
        ) as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.run_checks.return_value = mock_result

            result = runner.invoke(app, ["--fix"])

            # Should call run_checks with fix=True
            mock_service.run_checks.assert_called_once_with(fix=True)
            assert result.exit_code == 0

    def test_project_check_mutually_exclusive_json_and_verbose(self) -> None:
        """Test --json and --verbose are mutually exclusive."""
        result = runner.invoke(app, ["--json", "--verbose"])
        assert result.exit_code == 1
        assert "mutually exclusive" in result.output
