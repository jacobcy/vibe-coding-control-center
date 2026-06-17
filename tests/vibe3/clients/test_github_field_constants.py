"""Tests for GitHub field constants."""

import json
import subprocess

import pytest

from vibe3.clients.github_field_constants import (
    GITHUB_DEFAULT_LIST_FIELDS,
    GITHUB_DEFAULT_VIEW_FIELDS,
    GITHUB_FIELDS_ISSUE_META,
    GITHUB_KNOWN_ISSUE_FIELDS,
    GITHUB_KNOWN_PR_FIELDS,
    GITHUB_PR_LIST_MERGED_FIELDS,
)


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


@pytest.mark.integration
def test_known_fields_work_with_gh_cli() -> None:
    """GITHUB_KNOWN_ISSUE_FIELDS entries should be recognized by gh CLI."""
    # Filter out projectCards which is deprecated and causes gh CLI to fail
    fields_to_test = [f for f in GITHUB_KNOWN_ISSUE_FIELDS if f != "projectCards"]

    # Use current issue #2896 as test subject
    fields_arg = ",".join(sorted(fields_to_test))
    result = subprocess.run(
        ["gh", "issue", "view", "2896", "--json", fields_arg],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"gh CLI failed: {result.stderr}"

    # Verify response is valid JSON with expected fields
    response = json.loads(result.stdout)
    for field in fields_to_test:
        assert field in response, f"Field {field} not in response"


@pytest.mark.integration
def test_project_cards_field_deprecated() -> None:
    """projectCards field triggers deprecation warning but should still be tracked."""
    result = subprocess.run(
        ["gh", "issue", "view", "2896", "--json", "projectCards"],
        capture_output=True,
        text=True,
    )

    # Should fail with deprecation warning
    assert result.returncode != 0
    assert "deprecated" in result.stderr.lower()


@pytest.mark.integration
def test_default_field_sets_work_with_gh_cli() -> None:
    """Default field sets should produce valid API calls."""
    # Test GITHUB_DEFAULT_VIEW_FIELDS with issue view
    view_fields_arg = ",".join(GITHUB_DEFAULT_VIEW_FIELDS)
    view_result = subprocess.run(
        ["gh", "issue", "view", "2896", "--json", view_fields_arg],
        capture_output=True,
        text=True,
    )

    assert view_result.returncode == 0, f"View fields failed: {view_result.stderr}"

    view_response = json.loads(view_result.stdout)
    # View fields should include body and url
    assert "body" in view_response, "body not in view response"
    assert "url" in view_response, "url not in view response"

    # Test GITHUB_DEFAULT_LIST_FIELDS with issue list
    list_fields_arg = ",".join(GITHUB_DEFAULT_LIST_FIELDS)
    list_result = subprocess.run(
        ["gh", "issue", "list", "--limit", "1", "--json", list_fields_arg],
        capture_output=True,
        text=True,
    )

    assert list_result.returncode == 0, f"List fields failed: {list_result.stderr}"

    list_response = json.loads(list_result.stdout)
    # List response is an array
    assert isinstance(list_response, list), "List response should be an array"
    if len(list_response) > 0:
        # List fields should NOT include body or url (for performance)
        assert "body" not in list_response[0], "body should not be in list response"
        assert "url" not in list_response[0], "url should not be in list response"


def test_all_pr_fields_are_known() -> None:
    """All defined PR fields should be in GITHUB_KNOWN_PR_FIELDS."""
    known_set = set(GITHUB_KNOWN_PR_FIELDS)

    for field in GITHUB_PR_LIST_MERGED_FIELDS:
        assert field in known_set, f"PR field {field} not in known PR fields"


def test_pr_list_merged_fields() -> None:
    """GITHUB_PR_LIST_MERGED_FIELDS should have correct structure."""
    assert GITHUB_PR_LIST_MERGED_FIELDS == (
        "number",
        "headRefName",
        "body",
        "mergedAt",
    )
    assert len(GITHUB_PR_LIST_MERGED_FIELDS) == 4


@pytest.mark.integration
def test_known_pr_fields_work_with_gh_cli() -> None:
    """GITHUB_KNOWN_PR_FIELDS entries should be recognized by gh CLI."""
    # Filter out projectCards which is deprecated and causes gh CLI to fail
    fields_to_test = [f for f in GITHUB_KNOWN_PR_FIELDS if f != "projectCards"]

    # Use all fields at once to verify they're all valid
    fields_arg = ",".join(sorted(fields_to_test))
    result = subprocess.run(
        ["gh", "pr", "list", "--limit", "1", "--json", fields_arg],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"gh CLI failed: {result.stderr}"

    # Verify response is valid JSON
    response = json.loads(result.stdout)
    assert isinstance(response, list), "PR list response should be an array"
    # If there are PRs, verify fields are present
    if len(response) > 0:
        for field in fields_to_test:
            assert field in response[0], f"PR field {field} not in response"
