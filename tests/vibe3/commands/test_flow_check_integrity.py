"""Tests for flow check-integrity CLI command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


def test_check_integrity_dry_run_clean() -> None:
    """Dry-run with no invalid rows should report clean and exit 0."""
    with patch("vibe3.clients.SQLiteClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.list_invalid_branch_links.return_value = []
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["flow", "check-integrity"])

        assert result.exit_code == 0
        assert "No invalid branch links found" in result.output
        mock_client.list_invalid_branch_links.assert_called_once()
        mock_client.delete_invalid_branch_links.assert_not_called()


def test_check_integrity_dry_run_found() -> None:
    """Dry-run with invalid rows should show rows but NOT delete."""
    with patch("vibe3.clients.SQLiteClient") as mock_client_class:
        mock_client = MagicMock()
        invalid_rows = [
            {
                "branch": "main",
                "issue_number": 100,
                "issue_role": "task",
                "created_at": "2025-01-01T00:00:00Z",
            },
        ]
        mock_client.list_invalid_branch_links.return_value = invalid_rows
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["flow", "check-integrity"])

        assert result.exit_code == 0
        assert "Invalid Branch Links" in result.output
        assert "main" in result.output
        assert "100" in result.output
        assert "Use --repair to delete them" in result.output
        mock_client.delete_invalid_branch_links.assert_not_called()


def test_check_integrity_repair_with_yes() -> None:
    """--repair --yes should delete rows without confirmation."""
    with patch("vibe3.clients.SQLiteClient") as mock_client_class:
        mock_client = MagicMock()
        invalid_rows = [
            {
                "branch": "main",
                "issue_number": 100,
                "issue_role": "task",
                "created_at": "2025-01-01T00:00:00Z",
            },
        ]
        mock_client.list_invalid_branch_links.return_value = invalid_rows
        mock_client.delete_invalid_branch_links.return_value = 1
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["flow", "check-integrity", "--repair", "--yes"])

        assert result.exit_code == 0
        assert "Deleted 1 invalid branch links" in result.output
        mock_client.delete_invalid_branch_links.assert_called_once_with(invalid_rows)


def test_check_integrity_repair_declined() -> None:
    """--repair with declined confirmation should NOT delete."""
    with patch("vibe3.clients.SQLiteClient") as mock_client_class:
        mock_client = MagicMock()
        invalid_rows = [
            {
                "branch": "main",
                "issue_number": 100,
                "issue_role": "task",
                "created_at": "2025-01-01T00:00:00Z",
            },
        ]
        mock_client.list_invalid_branch_links.return_value = invalid_rows
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app, ["flow", "check-integrity", "--repair"], input="N\n"
        )

        assert result.exit_code == 0
        assert "Repair aborted" in result.output
        mock_client.delete_invalid_branch_links.assert_not_called()


def test_check_integrity_format_json() -> None:
    """--format json should output valid JSON."""
    with patch("vibe3.clients.SQLiteClient") as mock_client_class:
        mock_client = MagicMock()
        invalid_rows = [
            {
                "branch": "main",
                "issue_number": 100,
                "issue_role": "task",
                "created_at": "2025-01-01T00:00:00Z",
            },
        ]
        mock_client.list_invalid_branch_links.return_value = invalid_rows
        mock_client_class.return_value = mock_client

        result = runner.invoke(app, ["flow", "check-integrity", "--format", "json"])

        assert result.exit_code == 0
        import json

        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert len(output_data) == 1
        assert output_data[0]["branch"] == "main"
