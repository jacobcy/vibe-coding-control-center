"""Tests for FeedbackWriteService."""

from __future__ import annotations

from pathlib import Path

import pytest

from vibe3.clients.feedback_store import FeedbackStore
from vibe3.services.feedback.write_service import FeedbackWriteService


@pytest.fixture
def temp_store_path(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    import sqlite3

    from vibe3.clients.sqlite_schema import init_schema

    db_path = tmp_path / "feedback.db"
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    conn.close()
    return db_path


@pytest.fixture
def write_service(temp_store_path: Path) -> FeedbackWriteService:
    """Create a write service with temporary store."""
    store = FeedbackStore(db_path=str(temp_store_path))
    return FeedbackWriteService(store=store)


VALID_YAML = """
audit_observation:
  schema_version: 1
  created_at: "2026-06-20T00:00:00Z"
  created_by: "test_suite"
  source_material: "test/material.md"

  subject:
    issue_number: 123
    branch: "test/branch"
    pr_number: 456

  observation:
    title: "Test observation"
    symptom: "Test symptom description"
    observed_failure_mode: "scope_mismatch"
    confidence: "high"

  facts:
    - kind: "test"
      ref: "ref1"
      summary: "Test fact"

  interpretation:
    reasoning: "Test reasoning"
    likely_agent_failure: "Test failure"
    affected_material_candidates:
      - "material1"

  limitations:
    - "Test limitation"

  next_stage_input:
    suitable_for_clustering: true
    suggested_cluster_key: "test-cluster"
    requires_human_review: true

  source_watermark: "abcd1234efgh5678"
"""

INVALID_YAML_MISSING_KEY = """
some_other_key:
  value: "test"
"""

INVALID_YAML_BAD_FIELD = """
audit_observation:
  created_at: "2026-06-20T00:00:00Z"
  created_by: "test_suite"
  observation:
    symptom: "Test"
    observed_failure_mode: "invalid_mode"
    confidence: "invalid_confidence"
"""


def test_write_from_valid_yaml(
    write_service: FeedbackWriteService, tmp_path: Path
) -> None:
    """Test writing a valid YAML observation."""
    yaml_file = tmp_path / "obs.yaml"
    yaml_file.write_text(VALID_YAML, encoding="utf-8")

    obs = write_service.write_from_file(yaml_file)

    assert obs.observation_id is not None
    assert obs.observation_type == "Test observation"
    assert obs.symptom == "Test symptom description"
    assert obs.observed_failure_mode == "scope_mismatch"
    assert obs.confidence == "high"
    assert obs.source_window.issue_number == 123
    assert obs.source_window.branch == "test/branch"
    assert obs.source_window.pr_number == 456


def test_write_from_stdin(write_service: FeedbackWriteService) -> None:
    """Test writing from stdin (YAML string)."""
    obs = write_service.write_from_stdin(VALID_YAML)

    assert obs.observation_id is not None
    assert obs.observation_type == "Test observation"


def test_validate_valid_yaml(
    write_service: FeedbackWriteService, tmp_path: Path
) -> None:
    """Test validation of valid YAML."""
    yaml_file = tmp_path / "obs.yaml"
    yaml_file.write_text(VALID_YAML, encoding="utf-8")

    is_valid, error = write_service.validate_file(yaml_file)

    assert is_valid is True
    assert error is None


def test_validate_missing_file(
    write_service: FeedbackWriteService, tmp_path: Path
) -> None:
    """Test validation of missing file."""
    yaml_file = tmp_path / "nonexistent.yaml"

    is_valid, error = write_service.validate_file(yaml_file)

    assert is_valid is False
    assert "File not found" in error


def test_validate_missing_key(
    write_service: FeedbackWriteService, tmp_path: Path
) -> None:
    """Test validation of YAML missing audit_observation key."""
    yaml_file = tmp_path / "obs.yaml"
    yaml_file.write_text(INVALID_YAML_MISSING_KEY, encoding="utf-8")

    is_valid, error = write_service.validate_file(yaml_file)

    assert is_valid is False
    assert "audit_observation" in error


def test_validate_invalid_enum(
    write_service: FeedbackWriteService, tmp_path: Path
) -> None:
    """Test validation of YAML with invalid enum value."""
    yaml_file = tmp_path / "obs.yaml"
    yaml_file.write_text(INVALID_YAML_BAD_FIELD, encoding="utf-8")

    is_valid, error = write_service.validate_file(yaml_file)

    assert is_valid is False


def test_dedup_on_same_watermark(
    write_service: FeedbackWriteService, tmp_path: Path
) -> None:
    """Test that duplicate watermarks are skipped."""
    yaml_file = tmp_path / "obs.yaml"
    yaml_file.write_text(VALID_YAML, encoding="utf-8")

    # First write
    obs1 = write_service.write_from_file(yaml_file)

    # Second write with same watermark should skip
    obs2 = write_service.write_from_stdin(VALID_YAML)

    # Should return the same observation ID (existing)
    assert obs2.observation_id == obs1.observation_id


def test_file_not_found(write_service: FeedbackWriteService, tmp_path: Path) -> None:
    """Test that missing file raises FileNotFoundError."""
    yaml_file = tmp_path / "nonexistent.yaml"

    with pytest.raises(FileNotFoundError):
        write_service.write_from_file(yaml_file)


def test_yaml_to_model_nested_mapping(
    write_service: FeedbackWriteService, tmp_path: Path
) -> None:
    """Test that nested YAML fields are correctly mapped to flat model."""
    yaml_content = """
audit_observation:
  created_at: "2026-06-20T00:00:00Z"
  created_by: "test"
  source_material: "custom/material.md"
  flow_status: "blocked"

  subject:
    issue_number: 789
    branch: "custom/branch"
    commit_shas: ["sha1", "sha2"]

  observation:
    title: "Custom observation type"
    symptom: "Custom symptom"
    observed_failure_mode: "missing_output"
    confidence: "low"

  interpretation:
    reasoning: "Custom reasoning"
    likely_agent_failure: "Custom failure"

  source_watermark: "custom_watermark_123"
"""
    yaml_file = tmp_path / "custom.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")

    obs = write_service.write_from_file(yaml_file)

    assert obs.observation_type == "Custom observation type"
    assert obs.source_material == "custom/material.md"
    assert obs.flow_status == "blocked"
    assert obs.source_window.issue_number == 789
    assert obs.source_window.branch == "custom/branch"
    assert obs.source_window.commit_shas == ["sha1", "sha2"]
    assert obs.observed_failure_mode == "missing_output"
    assert obs.confidence == "low"
