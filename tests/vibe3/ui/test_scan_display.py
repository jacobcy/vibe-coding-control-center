"""Tests for scan display UI functions."""

from unittest.mock import MagicMock, patch

from rich.console import Console

from vibe3.models import ExecutionLaunchResult
from vibe3.ui.scan_display import (
    display_execution_result,
    display_material_list,
    display_supervisor_dry_run,
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


class TestDisplayCodeagentResult:
    """Tests for CodeagentResult display (plan/run/review commands)."""

    def test_display_codeagent_result_shows_backend_and_model(self):
        """display_codeagent_result shows backend/model when present."""
        from vibe3.agents import CodeagentResult

        console = MagicMock()
        result = CodeagentResult(
            success=True,
            backend="claude",
            model="sonnet",
            log_path="temp/logs/plan/test.log",
            tmux_session="vibe3-plan-test",
        )
        from vibe3.ui.scan_display import display_codeagent_result

        display_codeagent_result(console, result, "Plan")
        # Verify backend and model were printed
        calls = [str(c) for c in console.print.call_args_list]
        assert any("Backend:" in c and "claude" in c for c in calls)
        assert any("Model:" in c and "sonnet" in c for c in calls)
        assert any("Log path:" in c for c in calls)
        assert any("Tmux session:" in c for c in calls)

    def test_display_codeagent_result_handles_missing_backend_model(self):
        """display_codeagent_result handles missing backend/model gracefully."""
        from vibe3.agents import CodeagentResult

        console = MagicMock()
        result = CodeagentResult(
            success=True,
            log_path="temp/logs/plan/test.log",
            tmux_session="vibe3-plan-test",
        )
        from vibe3.ui.scan_display import display_codeagent_result

        display_codeagent_result(console, result, "Run")
        # Should not crash, and should still show log/tmux
        calls = [str(c) for c in console.print.call_args_list]
        assert any("Log path:" in c for c in calls)
        assert any("Tmux session:" in c for c in calls)
        # Should not have Backend/Model labels
        assert not any("Backend:" in c for c in calls)
        assert not any("Model:" in c for c in calls)

    def test_display_codeagent_result_handles_failure(self):
        """display_codeagent_result shows stderr on failure."""
        from vibe3.agents import CodeagentResult

        console = MagicMock()
        result = CodeagentResult(
            success=False,
            exit_code=1,
            stderr="Error: something went wrong",
            backend="claude",
            model="sonnet",
        )
        from vibe3.ui.scan_display import display_codeagent_result

        display_codeagent_result(console, result, "Review")
        # Should show failure and stderr
        calls = [str(c) for c in console.print.call_args_list]
        assert any("Failed" in c for c in calls)
        assert any("Error: something went wrong" in c for c in calls)


class TestDisplayExecutionResult:
    """Tests for execution result display."""

    def test_display_execution_result_shows_backend_and_model(self):
        """display_execution_result shows backend/model when present."""
        console = MagicMock()
        result = ExecutionLaunchResult(
            launched=True,
            tmux_session="vibe3-governance-20260615-123456-t0",
            log_path="/tmp/gov.log",
            backend="claude",
            model="sonnet",
        )
        display_execution_result(console, result)
        # Verify backend and model were printed
        calls = [str(c) for c in console.print.call_args_list]
        assert any("Backend:" in c and "claude" in c for c in calls)
        assert any("Model:" in c and "sonnet" in c for c in calls)
        assert any("Tmux session:" in c for c in calls)
        assert any("Log path:" in c for c in calls)

    def test_display_execution_result_handles_missing_backend_model(self):
        """display_execution_result handles missing backend/model gracefully."""
        console = MagicMock()
        result = ExecutionLaunchResult(
            launched=True,
            tmux_session="vibe3-governance-20260615-123456-t0",
            log_path="/tmp/gov.log",
        )
        display_execution_result(console, result)
        # Should not crash, and should still show tmux/log
        calls = [str(c) for c in console.print.call_args_list]
        assert any("Tmux session:" in c for c in calls)
        assert any("Log path:" in c for c in calls)
        # Should not have Backend/Model labels
        assert not any("Backend:" in c for c in calls)
        assert not any("Model:" in c for c in calls)
