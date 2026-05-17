"""Tests for parse_projection_with_fallback helper."""

from vibe3.services.issue_body_service import parse_projection_with_fallback


def test_parse_projection_with_fallback_parses_managed_section():
    """parse_projection_with_fallback reads managed section from issue body."""
    body = """User content here.

<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked by**: #456
- **Blocked reason**: Waiting for dependency

<!-- vibe3-flow-state-end -->

More user content."""

    projection = parse_projection_with_fallback(body)

    assert projection.state == "blocked"
    assert projection.blocked_by == [456]
    assert projection.blocked_reason == "Waiting for dependency"


def test_parse_projection_with_fallback_returns_empty_if_no_managed_section():
    """parse_projection_with_fallback returns empty projection if no managed section."""
    body = "User content only, no managed section."

    projection = parse_projection_with_fallback(body)

    # Empty projection (defaults to active state)
    assert projection.state == "active"
    assert projection.blocked_by == []
    assert projection.blocked_reason is None
