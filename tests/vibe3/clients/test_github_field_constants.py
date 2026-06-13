"""Tests for GitHub field constants."""

from vibe3.clients.github_field_constants import (
    GITHUB_DEFAULT_LIST_FIELDS,
    GITHUB_DEFAULT_VIEW_FIELDS,
    GITHUB_FIELDS_ISSUE_META,
    GITHUB_KNOWN_ISSUE_FIELDS,
)


def test_meta_fields_definition() -> None:
    """GITHUB_FIELDS_ISSUE_META should contain shared metadata fields."""
    assert "number" in GITHUB_FIELDS_ISSUE_META
    assert "title" in GITHUB_FIELDS_ISSUE_META
    assert "state" in GITHUB_FIELDS_ISSUE_META
    assert "updatedAt" in GITHUB_FIELDS_ISSUE_META
    assert "labels" in GITHUB_FIELDS_ISSUE_META
    assert "assignees" in GITHUB_FIELDS_ISSUE_META
    assert "milestone" in GITHUB_FIELDS_ISSUE_META
    # Should NOT contain body or url
    assert "body" not in GITHUB_FIELDS_ISSUE_META
    assert "url" not in GITHUB_FIELDS_ISSUE_META


def test_view_fields_definition() -> None:
    """GITHUB_DEFAULT_VIEW_FIELDS should include body and url."""
    # Should include all meta fields
    for field in GITHUB_FIELDS_ISSUE_META:
        assert field in GITHUB_DEFAULT_VIEW_FIELDS

    # Should include body and url
    assert "body" in GITHUB_DEFAULT_VIEW_FIELDS
    assert "url" in GITHUB_DEFAULT_VIEW_FIELDS


def test_list_fields_definition() -> None:
    """GITHUB_DEFAULT_LIST_FIELDS should exclude body and url."""
    # Should be exactly equal to meta fields
    assert GITHUB_DEFAULT_LIST_FIELDS == GITHUB_FIELDS_ISSUE_META

    # Should NOT contain body or url
    assert "body" not in GITHUB_DEFAULT_LIST_FIELDS
    assert "url" not in GITHUB_DEFAULT_LIST_FIELDS


def test_all_fields_are_known() -> None:
    """All defined fields should be in GITHUB_KNOWN_ISSUE_FIELDS."""
    known_set = set(GITHUB_KNOWN_ISSUE_FIELDS)

    for field in GITHUB_FIELDS_ISSUE_META:
        assert field in known_set, f"Field {field} not in known fields"

    for field in GITHUB_DEFAULT_VIEW_FIELDS:
        assert field in known_set, f"Field {field} not in known fields"

    for field in GITHUB_DEFAULT_LIST_FIELDS:
        assert field in known_set, f"Field {field} not in known fields"


def test_no_duplicate_fields() -> None:
    """Field constants should not contain duplicates."""
    assert len(GITHUB_FIELDS_ISSUE_META) == len(set(GITHUB_FIELDS_ISSUE_META))
    assert len(GITHUB_DEFAULT_VIEW_FIELDS) == len(set(GITHUB_DEFAULT_VIEW_FIELDS))
    assert len(GITHUB_DEFAULT_LIST_FIELDS) == len(set(GITHUB_DEFAULT_LIST_FIELDS))
