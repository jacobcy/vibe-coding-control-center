"""Tests for issue body managed section service."""

from vibe3.models.issue_body import FlowStateProjection
from vibe3.services.issue.body import (
    MANAGED_SECTION_END,
    MANAGED_SECTION_START,
    merge_projection,
    parse_projection,
    render_projection,
)


def test_parse_projection_parses_managed_section():
    """parse_projection reads managed section from issue body."""
    body = """User content here.

<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked by**: #456
- **Blocked reason**: Waiting for dependency

<!-- vibe3-flow-state-end -->

More user content."""

    projection = parse_projection(body)

    assert projection.state == "blocked"
    assert projection.blocked_by == [456]
    assert projection.blocked_reason == "Waiting for dependency"


def test_parse_projection_returns_empty_if_no_managed_section():
    """parse_projection returns empty projection if no managed section."""
    body = "User content only, no managed section."

    projection = parse_projection(body)

    # Empty projection (defaults to active state)
    assert projection.state == "active"
    assert projection.blocked_by == []
    assert projection.blocked_reason is None


class TestParseProjection:
    """Tests for parse_projection function."""

    def test_parse_empty_body(self):
        """Parse empty body returns default projection."""
        result = parse_projection("")
        assert result == FlowStateProjection()

    def test_parse_no_managed_section(self):
        """Parse body without managed section returns default."""
        body = "# Some issue\n\nThis is content."
        result = parse_projection(body)
        assert result == FlowStateProjection()

    def test_parse_empty_managed_section(self):
        """Parse empty managed section returns default."""
        body = f"# Issue\n\n{MANAGED_SECTION_START}\n\n{MANAGED_SECTION_END}"
        result = parse_projection(body)
        assert result == FlowStateProjection()

    def test_parse_blocked_state(self):
        """Parse complete projection with all fields."""
        body = f"""# Issue

Some content.

{MANAGED_SECTION_START}

**Vibe3 Flow State**

- **State**: blocked
- **Blocked by**: #123, #456
- **Blocked reason**: Waiting for dependencies
- **Dependencies**: #789

{MANAGED_SECTION_END}

More content."""
        result = parse_projection(body)
        assert result.state == "blocked"
        assert result.blocked_by == [123, 456, 789]
        assert result.blocked_reason == "Waiting for dependencies"

    def test_parse_partial_projection(self):
        """Parse projection with only some fields."""
        body = f"""# Issue

{MANAGED_SECTION_START}

**Vibe3 Flow State**

- **State**: done
- **Dependencies**: #100

{MANAGED_SECTION_END}"""
        result = parse_projection(body)
        assert result.state == "done"
        assert result.blocked_by == [100]
        assert result.blocked_reason is None


class TestRenderProjection:
    """Tests for render_projection function."""

    def test_render_empty_projection(self):
        """Render empty projection returns empty string."""
        proj = FlowStateProjection()
        result = render_projection(proj)
        assert result == ""

    def test_render_active_state(self):
        """Render active state (default) returns empty."""
        proj = FlowStateProjection(state="active")
        result = render_projection(proj)
        assert result == ""

    def test_render_blocked_projection(self):
        """Render blocked state with full info."""
        proj = FlowStateProjection(
            state="blocked",
            blocked_by=[123, 456],
            blocked_reason="Waiting for deps",
        )
        result = render_projection(proj)

        assert MANAGED_SECTION_START in result
        assert MANAGED_SECTION_END in result
        assert "**State**: blocked" in result
        assert "#123" in result
        assert "#456" in result
        assert "Waiting for deps" in result

    def test_render_done_state(self):
        """Render done state."""
        proj = FlowStateProjection(state="done")
        result = render_projection(proj)
        assert "**State**: done" in result


class TestMergeProjection:
    """Tests for merge_projection function."""

    def test_merge_into_empty_body(self):
        """Merge projection into empty body."""
        proj = FlowStateProjection(state="done")
        result = merge_projection("", proj)
        assert MANAGED_SECTION_START in result
        assert "**State**: done" in result

    def test_merge_preserves_user_content(self):
        """Merge preserves existing user content."""
        body = "# My Issue\n\nThis is important.\n\n- Item 1\n- Item 2"
        proj = FlowStateProjection(state="blocked", blocked_by=[123])
        result = merge_projection(body, proj)

        assert "# My Issue" in result
        assert "This is important." in result
        assert "- Item 1" in result
        assert "- Item 2" in result
        assert "**State**: blocked" in result

    def test_merge_replaces_managed_section(self):
        """Merge replaces existing managed section."""
        body = f"""# Issue

{MANAGED_SECTION_START}

**Vibe3 Flow State**

- **State**: active

{MANAGED_SECTION_END}

User content."""

        proj = FlowStateProjection(state="done", blocked_by=[100])
        result = merge_projection(body, proj)

        # Should have new state
        assert "**State**: done" in result
        assert "#100" in result

        # Should NOT have old state
        assert result.count("**State**:") == 1

        # Should preserve user content
        assert "User content." in result

    def test_merge_removes_empty_section(self):
        """Merge empty projection removes managed section."""
        body = f"""# Issue

{MANAGED_SECTION_START}

**Vibe3 Flow State**

- **State**: blocked

{MANAGED_SECTION_END}

User content."""

        proj = FlowStateProjection()  # Empty/default
        result = merge_projection(body, proj)

        # Should remove managed section
        assert MANAGED_SECTION_START not in result
        assert MANAGED_SECTION_END not in result

        # Should preserve user content
        assert "# Issue" in result
        assert "User content." in result

    def test_merge_idempotent(self):
        """Merging twice produces same result."""
        body = "# Issue\n\nContent."
        proj = FlowStateProjection(state="done")

        result1 = merge_projection(body, proj)
        result2 = merge_projection(result1, proj)

        assert result1 == result2
