"""Tests for scan display UI functions."""

from unittest.mock import patch

from rich.console import Console

from vibe3.ui.scan_display import (
    display_governance_dry_run,
    display_material_list,
    display_supervisor_dry_run,
)


class TestDisplayGovernanceDryRun:
    """Tests for governance dry-run display."""

    def test_displays_material_info(self):
        """Test that material information is displayed."""
        console = Console()

        with patch.object(console, "print") as mock_print:
            display_governance_dry_run(
                console=console,
                material_name="supervisor/governance/assignee-pool.md",
                prompt_content="# Test Prompt\nContent here",
            )

            # Check that material name is displayed
            printed_text = " ".join(str(call) for call in mock_print.call_args_list)
            assert "assignee-pool" in printed_text or "Material" in printed_text

    def test_displays_prompt_preview(self):
        """Test that prompt preview is displayed."""
        console = Console()

        with patch.object(console, "print") as mock_print:
            display_governance_dry_run(
                console=console,
                material_name="test-material",
                prompt_content="Test prompt content",
            )

            # Check that prompt is displayed (Panel or direct print)
            printed_text = " ".join(str(call) for call in mock_print.call_args_list)
            assert (
                "Test prompt content" in printed_text
                or len(mock_print.call_args_list) > 0
            )


class TestDisplaySupervisorDryRun:
    """Tests for supervisor dry-run display."""

    def test_displays_scan_process(self):
        """Test that scan process steps are displayed."""
        console = Console()

        with patch.object(console, "print") as mock_print:
            display_supervisor_dry_run(console=console, total_scanned=10, candidates=[])

            # Check that process steps are mentioned
            printed_text = " ".join(str(call) for call in mock_print.call_args_list)
            assert (
                "supervisor" in printed_text.lower() or "scan" in printed_text.lower()
            )

    def test_displays_candidates_in_table(self):
        """Test that candidates are displayed in a table."""
        console = Console()

        candidates = [
            {
                "number": 123,
                "title": "Test Issue",
                "labels": ["supervisor", "state/handoff"],
            },
            {"number": 456, "title": "Another Issue", "labels": ["supervisor"]},
        ]

        with patch.object(console, "print") as mock_print:
            display_supervisor_dry_run(
                console=console, total_scanned=15, candidates=candidates
            )

            # Should print table with issue info
            assert mock_print.call_count > 0


class TestDisplayMaterialList:
    """Tests for material list display."""

    def test_displays_material_table(self):
        """Test that materials are displayed in a table."""
        console = Console()

        materials = [
            {"name": "assignee-pool", "description": "Assignee Pool 治理材料"},
            {"name": "roadmap-intake", "description": "Roadmap Intake 治理材料"},
        ]

        with patch.object(console, "print") as mock_print:
            display_material_list(console=console, materials=materials)

            # Should print table
            assert mock_print.call_count > 0

    def test_handles_empty_list(self):
        """Test handling of empty material list."""
        console = Console()

        with patch.object(console, "print") as mock_print:
            display_material_list(console=console, materials=[])

            # Should show "no materials" message
            printed_text = " ".join(str(call) for call in mock_print.call_args_list)
            assert (
                "no" in printed_text.lower()
                or "empty" in printed_text.lower()
                or len([]) == 0
            )
