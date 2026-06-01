"""Tests for RFC/Epic label handling in task status dashboard."""

from typer.testing import CliRunner

from tests.vibe3.test_rfc_epic_utils import make_issue
from vibe3.cli import app
from vibe3.models.orchestration import IssueState

runner = CliRunner(env={"NO_COLOR": "1"})


def test_task_status_shows_rfc_and_epic_in_separate_sections(
    mock_services,
) -> None:
    """task status should show RFC and Epic issues in their own sections."""
    mock_services["status_service"].fetch_orchestrated_issues.return_value = [
        make_issue(777, "RFC design needed", labels=["roadmap/rfc"]),
        make_issue(888, "Epic container issue", labels=["roadmap/epic"]),
    ]

    result = runner.invoke(app, ["task", "status"])

    assert result.exit_code == 0
    output = result.output
    # RFC section should appear
    assert "Roadmap RFC:" in output
    assert "# 777" in output
    assert "RFC design needed" in output
    # Epic section should appear
    assert "Roadmap Epic:" in output
    assert "# 888" in output
    assert "Epic container issue" in output


def test_task_status_blocked_issues_excludes_rfc_and_epic(
    mock_services,
) -> None:
    """Blocked Issues section should exclude RFC/Epic labeled items."""
    mock_services["status_service"].fetch_orchestrated_issues.return_value = [
        make_issue(
            999,
            "Regular blocked issue",
            blocked_reason="dependency missing",
        ),
        make_issue(
            777,
            "RFC blocked issue",
            blocked_reason="needs design input",
            labels=["roadmap/rfc"],
        ),
    ]

    result = runner.invoke(app, ["task", "status"])

    assert result.exit_code == 0
    output = result.output
    # Regular blocked issue should be in Blocked Issues section
    assert "Blocked Issues:" in output
    blocked_section_start = output.index("Blocked Issues:")
    blocked_section_end = output.find("\n\n", blocked_section_start)
    if blocked_section_end == -1:
        blocked_section_end = len(output)
    blocked_section = output[blocked_section_start:blocked_section_end]
    assert "# 999" in blocked_section
    assert "Regular blocked issue" in blocked_section
    # RFC issue should NOT be in Blocked Issues section
    assert "# 777" not in blocked_section
    # RFC issue should be in Roadmap RFC section
    assert "Roadmap RFC:" in output
    rfc_section_start = output.index("Roadmap RFC:")
    rfc_section_end = output.find("\n\n", rfc_section_start)
    if rfc_section_end == -1:
        rfc_section_end = len(output)
    rfc_section = output[rfc_section_start:rfc_section_end]
    assert "# 777" in rfc_section


def test_epic_shows_dependency_ready(mock_services) -> None:
    """Epic should show ✓ READY when all dependencies are completed."""
    # Epic with dependencies #457 and #458, both NOT in open issues (completed)
    mock_services["status_service"].fetch_orchestrated_issues.return_value = [
        make_issue(
            888,
            "Epic with completed dependencies",
            labels=["roadmap/epic"],
            body="## Dependencies\n\n- Blocked by #457 (API)\n- Blocked by #458 (DB)\n",
        ),
    ]

    result = runner.invoke(app, ["task", "status"])

    assert result.exit_code == 0
    output = result.output
    assert "Roadmap Epic:" in output
    assert "# 888" in output
    assert "✓ READY" in output


def test_epic_shows_dependency_waiting(mock_services) -> None:
    """Epic should show ⏳ WAITING when some dependencies are still open."""
    # Epic with dependencies #457 (still open) and #458 (completed)
    mock_services["status_service"].fetch_orchestrated_issues.return_value = [
        make_issue(
            457,
            "Still open dependency",
            state=IssueState.IN_PROGRESS,
            assignee="developer",
        ),
        make_issue(
            888,
            "Epic with partial dependencies",
            labels=["roadmap/epic"],
            body="## Dependencies\n\n- Blocked by #457 (API)\n- Blocked by #458 (DB)\n",
        ),
    ]

    result = runner.invoke(app, ["task", "status"])

    assert result.exit_code == 0
    output = result.output
    assert "Roadmap Epic:" in output
    assert "# 888" in output
    assert "⏳ WAITING" in output
    assert "(1/2)" in output


def test_epic_no_dependencies(mock_services) -> None:
    """Epic without dependencies section should not show dependency status."""
    mock_services["status_service"].fetch_orchestrated_issues.return_value = [
        make_issue(
            888,
            "Epic without dependencies",
            labels=["roadmap/epic"],
            body="## Summary\n\nThis epic has no dependencies section.\n",
        ),
    ]

    result = runner.invoke(app, ["task", "status"])

    assert result.exit_code == 0
    output = result.output
    assert "Roadmap Epic:" in output
    assert "# 888" in output
    # Should NOT show any dependency status line
    assert "✓ READY" not in output
    assert "⏳ WAITING" not in output


def test_epic_parser_rejects_partial_header_match(mock_services) -> None:
    """Parser should not match '## Dependencies Overview' as '## Dependencies'."""
    # Epic with "## Dependencies Overview" section containing #123,
    # followed by actual "## Dependencies" section containing #456
    mock_services["status_service"].fetch_orchestrated_issues.return_value = [
        make_issue(
            888,
            "Epic with similarly-named sections",
            labels=["roadmap/epic"],
            body=(
                "## Dependencies Overview\n\n"
                "- #123 (API)\n\n"
                "## Dependencies\n\n"
                "- #456 (DB)\n"
            ),
        ),
    ]

    result = runner.invoke(app, ["task", "status"])

    assert result.exit_code == 0
    output = result.output
    assert "Roadmap Epic:" in output
    assert "# 888" in output
    # Should show READY for #456 (correct), not WAITING for #123 (wrong)
    assert "✓ READY" in output


def test_epic_ignores_done_dependencies(mock_services) -> None:
    """Epic should show ✓ READY when dependencies are DONE."""
    # Epic with dependency #457 that is DONE
    mock_services["status_service"].fetch_orchestrated_issues.return_value = [
        make_issue(
            457,
            "Completed dependency",
            state=IssueState.DONE,
            assignee="developer",
        ),
        make_issue(
            888,
            "Epic with DONE dependency",
            labels=["roadmap/epic"],
            body="## Dependencies\n\n- Blocked by #457 (API)\n",
        ),
    ]

    result = runner.invoke(app, ["task", "status"])

    assert result.exit_code == 0
    output = result.output
    assert "Roadmap Epic:" in output
    assert "# 888" in output
    # Should show READY because #457 is DONE (not blocking)
    assert "✓ READY" in output
    assert "⏳ WAITING" not in output
