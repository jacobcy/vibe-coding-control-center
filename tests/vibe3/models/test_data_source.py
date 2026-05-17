"""Tests for DataSource provenance enum."""

from vibe3.models.data_source import DataSource


def test_data_source_enum_values():
    """DataSource has expected values for source tracking."""
    assert DataSource.LOCAL_SQLITE == "local"
    assert DataSource.GITHUB_API == "github"
    assert DataSource.ISSUE_BODY_FALLBACK == "fallback"
    assert DataSource.ORCHESTRA_SERVER == "server"


def test_data_source_enum_str():
    """DataSource can be used as string for display."""
    # str enum allows direct comparison
    assert DataSource.LOCAL_SQLITE == "local"
    # .value returns the string value
    assert DataSource.GITHUB_API.value == "github"
