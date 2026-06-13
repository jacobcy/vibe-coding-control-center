"""Tests for TimelineCommentPolicy YAML loading."""

from pathlib import Path

from vibe3.config.timeline_comment_policy import TimelineCommentPolicy


def test_yaml_load_success(tmp_path: Path) -> None:
    """Test successful YAML loading with all fields."""
    yaml_content = """
no_comment:
  state_sync:
    - flow_blocked
    - custom_event
  runtime_error:
    - flow_failed
  artifact_ref:
    - handoff_plan
write_comment:
  milestone:
    - handoff_append
  human_readable:
    - user_notification
"""
    yaml_file = tmp_path / "timeline.yaml"
    yaml_file.write_text(yaml_content)

    policy = TimelineCommentPolicy.from_yaml(yaml_file)
    assert "custom_event" in policy.state_sync_events
    assert policy.should_write_comment("custom_event") is False
    assert policy.should_write_comment("handoff_append") is True


def test_yaml_load_missing_file(tmp_path: Path) -> None:
    """Test fallback to defaults when YAML file doesn't exist."""
    policy = TimelineCommentPolicy.from_yaml(tmp_path / "nonexistent.yaml")
    # Should fallback to defaults
    default = TimelineCommentPolicy()
    assert policy.state_sync_events == default.state_sync_events
    assert policy.runtime_error_events == default.runtime_error_events
    assert policy.artifact_ref_events == default.artifact_ref_events
    assert policy.milestone_events == default.milestone_events
    assert policy.human_readable_events == default.human_readable_events


def test_yaml_load_invalid_yaml(tmp_path: Path) -> None:
    """Test fallback to defaults when YAML is invalid."""
    yaml_file = tmp_path / "invalid.yaml"
    yaml_file.write_text("invalid: yaml: content: [")

    policy = TimelineCommentPolicy.from_yaml(yaml_file)
    # Should fallback to defaults
    default = TimelineCommentPolicy()
    assert policy.state_sync_events == default.state_sync_events


def test_yaml_load_partial_config(tmp_path: Path) -> None:
    """Test loading YAML with only partial configuration."""
    yaml_content = """
no_comment:
  state_sync:
    - flow_blocked
    - custom_event
"""
    yaml_file = tmp_path / "partial.yaml"
    yaml_file.write_text(yaml_content)

    policy = TimelineCommentPolicy.from_yaml(yaml_file)
    # Custom event should be loaded
    assert "custom_event" in policy.state_sync_events
    # Missing fields should use defaults
    default = TimelineCommentPolicy()
    assert policy.runtime_error_events == default.runtime_error_events
    assert policy.milestone_events == default.milestone_events


def test_yaml_load_custom_events(tmp_path: Path) -> None:
    """Test loading YAML with custom event types."""
    yaml_content = """
no_comment:
  state_sync:
    - custom_sync_event
  runtime_error:
    - custom_error_event
  artifact_ref:
    - custom_artifact_event
write_comment:
  milestone:
    - custom_milestone_event
  human_readable:
    - custom_human_event
"""
    yaml_file = tmp_path / "custom.yaml"
    yaml_file.write_text(yaml_content)

    policy = TimelineCommentPolicy.from_yaml(yaml_file)
    assert "custom_sync_event" in policy.state_sync_events
    assert "custom_error_event" in policy.runtime_error_events
    assert "custom_artifact_event" in policy.artifact_ref_events
    assert "custom_milestone_event" in policy.milestone_events
    assert "custom_human_event" in policy.human_readable_events


def test_should_write_comment_with_yaml_policy(tmp_path: Path) -> None:
    """Test should_write_comment behavior with YAML-loaded policy."""
    yaml_content = """
no_comment:
  state_sync:
    - flow_blocked
    - custom_no_comment_event
write_comment:
  milestone:
    - handoff_append
    - custom_comment_event
"""
    yaml_file = tmp_path / "timeline.yaml"
    yaml_file.write_text(yaml_content)

    policy = TimelineCommentPolicy.from_yaml(yaml_file)
    # Events in no_comment categories should return False
    assert policy.should_write_comment("flow_blocked") is False
    assert policy.should_write_comment("custom_no_comment_event") is False
    # Events in write_comment categories should return True
    assert policy.should_write_comment("handoff_append") is True
    assert policy.should_write_comment("custom_comment_event") is True
    # Unknown events should default to False
    assert policy.should_write_comment("unknown_event") is False


def test_backward_compatibility() -> None:
    """Test that hardcoded defaults still work without YAML."""
    # Create policy with defaults (no YAML)
    default_policy = TimelineCommentPolicy()

    # Verify expected behavior matches hardcoded values
    # State sync events - no comments
    assert default_policy.should_write_comment("flow_blocked") is False
    assert default_policy.should_write_comment("resumed") is False
    assert default_policy.should_write_comment("flow_aborted") is False

    # Runtime error events - no comments
    assert default_policy.should_write_comment("flow_failed") is False

    # Artifact ref events - no comments
    assert default_policy.should_write_comment("handoff_plan") is False
    assert default_policy.should_write_comment("handoff_report") is False
    assert default_policy.should_write_comment("handoff_audit") is False
    assert default_policy.should_write_comment("handoff_indicate") is False
    assert default_policy.should_write_comment("plan_recorded") is False
    assert default_policy.should_write_comment("report_recorded") is False

    # Handoff append events - configured via YAML (default: unknown event = no comment)
    assert default_policy.should_write_comment("handoff_append") is False

    # Milestone events - write comments
    assert default_policy.should_write_comment("flow_rebuild") is True
    assert default_policy.should_write_comment("milestone_recorded") is True

    # Human-readable events - write comments
    assert default_policy.should_write_comment("user_notification") is True

    # Unknown events - default to no comment
    assert default_policy.should_write_comment("unknown_event") is False


def test_yaml_empty_file(tmp_path: Path) -> None:
    """Test fallback when YAML file is empty."""
    yaml_file = tmp_path / "empty.yaml"
    yaml_file.write_text("")

    policy = TimelineCommentPolicy.from_yaml(yaml_file)
    # Should fallback to defaults
    default = TimelineCommentPolicy()
    assert policy.state_sync_events == default.state_sync_events


def test_yaml_empty_sections(tmp_path: Path) -> None:
    """Test YAML with empty sections."""
    yaml_content = """
no_comment: {}
write_comment: {}
"""
    yaml_file = tmp_path / "empty_sections.yaml"
    yaml_file.write_text(yaml_content)

    policy = TimelineCommentPolicy.from_yaml(yaml_file)
    # Should use defaults for all fields
    default = TimelineCommentPolicy()
    assert policy.state_sync_events == default.state_sync_events
    assert policy.milestone_events == default.milestone_events
