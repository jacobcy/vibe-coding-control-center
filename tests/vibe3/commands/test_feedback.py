"""Tests for feedback CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from vibe3.commands.feedback import app

runner = CliRunner()


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database."""
    import sqlite3

    from vibe3.clients.sqlite_schema import init_schema

    db_path = tmp_path / "feedback.db"
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    conn.close()
    return db_path


VALID_YAML = """
audit_observation:
  created_at: "2026-06-20T00:00:00Z"
  created_by: "cli_test"
  source_material: "test/material.md"
  subject:
    issue_number: 123
    branch: "test/branch"
  observation:
    title: "CLI Test Observation"
    symptom: "CLI test symptom"
    observed_failure_mode: "scope_mismatch"
    confidence: "high"
  source_watermark: "cli_test_watermark_123"
"""


@patch("vibe3.commands.feedback.FeedbackWriteService")
def test_write_command(mock_write_service, temp_db_path: Path, tmp_path: Path) -> None:
    """Test write command with valid YAML file."""
    from vibe3.models.audit_observation import AuditObservation, ObservationSourceWindow

    # Setup mock
    mock_service = mock_write_service.return_value
    obs = AuditObservation.create(
        observation_type="test",
        source_window=ObservationSourceWindow(branch="test"),
        symptom="Test",
        observed_failure_mode="scope_mismatch",
        confidence="high",
        created_by="test",
    )
    mock_service.write_from_file.return_value = obs

    yaml_file = tmp_path / "obs.yaml"
    yaml_file.write_text(VALID_YAML, encoding="utf-8")

    result = runner.invoke(app, ["write", str(yaml_file)])

    assert result.exit_code == 0
    assert "✓" in result.output or "Wrote" in result.output


@patch("vibe3.commands.feedback.FeedbackWriteService")
def test_write_command_stdin(mock_write_service, temp_db_path: Path) -> None:
    """Test write command from stdin."""
    from vibe3.models.audit_observation import AuditObservation, ObservationSourceWindow

    mock_service = mock_write_service.return_value
    obs = AuditObservation.create(
        observation_type="test",
        source_window=ObservationSourceWindow(branch="test"),
        symptom="Test",
        observed_failure_mode="scope_mismatch",
        confidence="high",
        created_by="test",
    )
    mock_service.write_from_stdin.return_value = obs

    result = runner.invoke(app, ["write", "--stdin"], input=VALID_YAML)

    assert result.exit_code == 0


@patch("vibe3.commands.feedback.FeedbackWriteService")
def test_write_command_file_not_found(
    mock_write_service, temp_db_path: Path, tmp_path: Path
) -> None:
    """Test write command with missing file."""
    mock_service = mock_write_service.return_value
    mock_service.write_from_file.side_effect = FileNotFoundError("not found")

    result = runner.invoke(app, ["write", "nonexistent.yaml"])

    # Should complete but show error message
    assert "File not found" in result.output or "Error" in result.output


@patch("vibe3.commands.feedback.FeedbackWriteService")
def test_validate_command_valid(
    mock_write_service, temp_db_path: Path, tmp_path: Path
) -> None:
    """Test validate command with valid YAML."""
    mock_service = mock_write_service.return_value
    mock_service.validate_file.return_value = (True, None)

    yaml_file = tmp_path / "obs.yaml"
    yaml_file.write_text(VALID_YAML, encoding="utf-8")

    result = runner.invoke(app, ["validate", str(yaml_file)])

    assert result.exit_code == 0
    assert "Valid" in result.output


@patch("vibe3.commands.feedback.FeedbackWriteService")
def test_validate_command_invalid(
    mock_write_service, temp_db_path: Path, tmp_path: Path
) -> None:
    """Test validate command with invalid YAML."""
    mock_service = mock_write_service.return_value
    mock_service.validate_file.return_value = (
        False,
        "audit_observation key missing",
    )

    yaml_file = tmp_path / "obs.yaml"
    yaml_file.write_text("invalid: yaml", encoding="utf-8")

    result = runner.invoke(app, ["validate", str(yaml_file)])

    # Should complete but show error message
    assert "audit_observation" in result.output


@patch("vibe3.commands.feedback.FeedbackReadService")
def test_list_command(mock_read_service, temp_db_path: Path) -> None:
    """Test list command."""
    mock_service = mock_read_service.return_value
    mock_service.list_observations.return_value = [
        {
            "observation_id": "obs-123",
            "observation_type": "test",
            "symptom": "Test symptom",
            "observed_failure_mode": "scope_mismatch",
            "confidence": "high",
            "created_at": "2026-06-20T00:00:00Z",
        }
    ]

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "Observations" in result.output or "test" in result.output


@patch("vibe3.commands.feedback.FeedbackReadService")
def test_show_command(mock_read_service, temp_db_path: Path) -> None:
    """Test show command."""
    mock_service = mock_read_service.return_value
    mock_service.show_observation.return_value = {
        "observation_id": "obs-123",
        "observation_type": "show_test",
        "symptom": "Show test symptom",
        "observed_failure_mode": "missing_output",
        "confidence": "medium",
        "source_material": "test.md",
        "flow_status": "blocked",
        "subject_issue_number": 123,
        "subject_branch": "test",
        "subject_pr_number": None,
        "interpretation_reasoning": "Test reasoning",
        "interpretation_likely_agent_failure": "Test failure",
        "suitable_for_clustering": True,
        "suggested_cluster_key": "test-cluster",
        "requires_human_review": True,
        "created_at": "2026-06-20T00:00:00Z",
    }

    result = runner.invoke(app, ["show", "obs-123"])

    assert result.exit_code == 0
    assert "show_test" in result.output or "obs-123" in result.output


@patch("vibe3.commands.feedback.FeedbackReadService")
def test_show_command_not_found(mock_read_service, temp_db_path: Path) -> None:
    """Test show command with nonexistent ID."""
    mock_service = mock_read_service.return_value
    mock_service.show_observation.return_value = None

    result = runner.invoke(app, ["show", "nonexistent-id"])

    assert result.exit_code == 1
    assert "not found" in result.output


@patch("vibe3.commands.feedback.FeedbackReadService")
def test_stats_command(mock_read_service, temp_db_path: Path) -> None:
    """Test stats command."""
    mock_service = mock_read_service.return_value
    mock_service.get_stats.return_value = {
        "scope_mismatch": 2,
        "missing_output": 1,
    }

    result = runner.invoke(app, ["stats"])

    assert result.exit_code == 0
    assert "scope_mismatch" in result.output


@patch("vibe3.commands.feedback.FeedbackImportService")
def test_import_command(
    mock_import_service, temp_db_path: Path, tmp_path: Path
) -> None:
    """Test import command."""
    mock_service = mock_import_service.return_value
    mock_service.import_from_directory.return_value = (1, 0)

    # Create test directory with YAML file
    import_dir = tmp_path / "observations"
    import_dir.mkdir()
    yaml_file = import_dir / "obs.yaml"
    yaml_file.write_text(VALID_YAML, encoding="utf-8")

    result = runner.invoke(app, ["import", "--from", str(import_dir)])

    assert result.exit_code == 0
    assert "Imported" in result.output


@patch("vibe3.commands.feedback.FeedbackImportService")
def test_import_command_nonexistent_dir(
    mock_import_service, temp_db_path: Path
) -> None:
    """Test import command with nonexistent directory."""
    mock_service = mock_import_service.return_value
    mock_service.import_from_directory.side_effect = FileNotFoundError("not found")

    result = runner.invoke(app, ["import", "--from", "/nonexistent/dir"])

    assert result.exit_code == 1
    assert "not found" in result.output
