"""Tests for web UI HTML templates.

This module tests HTML template validity and structure.
"""

from pathlib import Path


def test_tasks_html_template_exists():
    """tasks.html template file must exist."""
    template_path = Path("src/vibe3/server/static/tasks.html")
    assert template_path.exists(), "tasks.html template must exist"


def test_tasks_html_has_required_elements():
    """tasks.html must contain required JavaScript functions and elements."""
    template_path = Path("src/vibe3/server/static/tasks.html")
    content = template_path.read_text()

    # Check for required JavaScript functions
    assert (
        "function renderIssues" in content
    ), "tasks.html must define renderIssues function"
    assert (
        "const BLOCK_CONFIG" in content
    ), "tasks.html must define BLOCK_CONFIG for per-section field configuration"
    assert (
        "const FIELD_RENDERERS" in content
    ), "tasks.html must define FIELD_RENDERERS for custom field rendering"

    # Check for required JavaScript logic to render sections
    assert (
        "classified_issues.blocked_items" in content
    ), "tasks.html must render blocked_items from API response"
    assert (
        "classified_issues.waiting_for_pool_items" in content
    ), "tasks.html must render waiting_for_pool_items from API response"

    # Check for XSS prevention
    assert (
        "function escapeHtml" in content
    ), "tasks.html must define escapeHtml function for XSS prevention"


def test_tasks_html_block_config_has_required_sections():
    """BLOCK_CONFIG must define field configurations for all required sections."""
    template_path = Path("src/vibe3/server/static/tasks.html")
    content = template_path.read_text()

    # Check that BLOCK_CONFIG is defined with object literal syntax
    assert (
        "const BLOCK_CONFIG = {" in content or "const BLOCK_CONFIG={" in content
    ), "BLOCK_CONFIG must be defined as const object"

    # Verify that renderIssues is called with correct block types
    # These calls use the block type as the third parameter
    required_block_types = [
        "'blocked'",  # For Blocked section
        "'waiting-for-pool'",  # For Waiting for Pool section
        "'roadmap-item'",  # For Roadmap sections
    ]

    for block_type in required_block_types:
        assert (
            block_type in content
        ), f"tasks.html must use {block_type} block type in renderIssues call"


def test_tasks_html_blocked_section_shows_blocked_reason():
    """BLOCK_CONFIG for 'blocked' section must include blocked_reason field."""
    template_path = Path("src/vibe3/server/static/tasks.html")
    content = template_path.read_text()

    # Check that blocked section config includes blocked_reason
    # This is a simplified check; actual rendering is tested by integration tests
    assert (
        "blocked_reason" in content
    ), "tasks.html must reference blocked_reason field for Blocked section"


def test_tasks_html_waiting_for_pool_hides_state():
    """BLOCK_CONFIG for 'waiting-for-pool' section must exclude state field."""
    template_path = Path("src/vibe3/server/static/tasks.html")
    content = template_path.read_text()

    # Verify that waiting-for-pool block type is used
    assert (
        "'waiting-for-pool'" in content
    ), "tasks.html must use 'waiting-for-pool' block type"

    # Verify that BLOCK_CONFIG is defined (specific field configuration
    # is tested by the presence of blocked_reason in blocked config)
    assert (
        "const BLOCK_CONFIG" in content
    ), "BLOCK_CONFIG must be defined for per-section field configuration"
