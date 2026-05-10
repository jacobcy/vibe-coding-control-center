"""Tests for TickDispatcher service."""

from unittest.mock import MagicMock, patch

from vibe3.models.tick import TickPlan
from vibe3.services.tick_dispatcher import TickDispatcher


class TestTickDispatcher:
    """Test suite for TickDispatcher."""

    def test_dispatcher_calls_internal_governance(self) -> None:
        """Test that dispatcher calls run_governance_sync with correct params."""
        plan = TickPlan(
            governance_enabled=True,
            governance_material="architecture",
            supervisor_enabled=False,
            dry_run=False,
        )

        dispatcher = TickDispatcher()

        with patch(
            "vibe3.execution.governance_sync_runner.run_governance_sync"
        ) as mock_governance:
            dispatcher.dispatch(plan)

            mock_governance.assert_called_once_with(
                tick_count=0,
                material_override="architecture",
                dry_run=False,
                show_prompt=False,
                session_id=None,
            )

    def test_dispatcher_calls_internal_governance_auto_material(self) -> None:
        """Test dispatcher handles auto material (None)."""
        plan = TickPlan(
            governance_enabled=True,
            governance_material=None,  # Auto-rotate
            supervisor_enabled=False,
            dry_run=False,
        )

        dispatcher = TickDispatcher()

        with patch(
            "vibe3.execution.governance_sync_runner.run_governance_sync"
        ) as mock_governance:
            dispatcher.dispatch(plan)

            mock_governance.assert_called_once_with(
                tick_count=0,
                material_override=None,
                dry_run=False,
                show_prompt=False,
                session_id=None,
            )

    def test_dispatcher_calls_internal_apply_for_supervisor(self) -> None:
        """Test that dispatcher calls run_supervisor_apply for each issue."""
        plan = TickPlan(
            governance_enabled=False,
            supervisor_enabled=True,
            supervisor_issues=[123, 456],
            dry_run=False,
        )

        dispatcher = TickDispatcher()

        with patch(
            "vibe3.execution.supervisor_apply_runner.run_supervisor_apply"
        ) as mock_apply:
            dispatcher.dispatch(plan)

            assert mock_apply.call_count == 2
            mock_apply.assert_any_call(
                issue_number=123,
                dry_run=False,
                fresh_session=True,
            )
            mock_apply.assert_any_call(
                issue_number=456,
                dry_run=False,
                fresh_session=True,
            )

    def test_dispatcher_dry_run_prints_plan(self) -> None:
        """Test dry-run mode prints plan without executing."""
        plan = TickPlan(
            governance_enabled=True,
            governance_material="architecture",
            supervisor_enabled=True,
            supervisor_issues=[123],
            dry_run=True,
        )

        dispatcher = TickDispatcher()

        with (
            patch(
                "vibe3.execution.governance_sync_runner.run_governance_sync"
            ) as mock_governance,
            patch(
                "vibe3.execution.supervisor_apply_runner.run_supervisor_apply"
            ) as mock_apply,
            patch("vibe3.services.tick_dispatcher.Console") as mock_console,
        ):
            mock_console_instance = MagicMock()
            mock_console.return_value = mock_console_instance

            dispatcher.dispatch(plan)

            # Verify no actual execution
            mock_governance.assert_not_called()
            mock_apply.assert_not_called()

            # Verify plan was printed
            assert mock_console_instance.print.called

    def test_dispatcher_scans_supervisor_candidates(self) -> None:
        """Test that dispatcher scans for supervisor candidates when issues empty."""
        plan = TickPlan(
            governance_enabled=False,
            supervisor_enabled=True,
            supervisor_issues=[],  # Empty list triggers scan
            dry_run=False,
        )

        dispatcher = TickDispatcher()

        with (
            patch.object(
                dispatcher, "_scan_supervisor_candidates", return_value=[111, 222]
            ) as mock_scan,
            patch(
                "vibe3.execution.supervisor_apply_runner.run_supervisor_apply"
            ) as mock_apply,
        ):
            dispatcher.dispatch(plan)

            # Verify scan was called
            mock_scan.assert_called_once()

            # Verify apply was called for each scanned issue
            assert mock_apply.call_count == 2
            mock_apply.assert_any_call(
                issue_number=111,
                dry_run=False,
                fresh_session=True,
            )
            mock_apply.assert_any_call(
                issue_number=222,
                dry_run=False,
                fresh_session=True,
            )

    def test_dispatcher_skips_supervisor_when_disabled(self) -> None:
        """Test that dispatcher skips supervisor when disabled in plan."""
        plan = TickPlan(
            governance_enabled=True,
            governance_material="architecture",
            supervisor_enabled=False,  # Disabled
            dry_run=False,
        )

        dispatcher = TickDispatcher()

        with (
            patch(
                "vibe3.execution.governance_sync_runner.run_governance_sync"
            ) as mock_governance,
            patch(
                "vibe3.execution.supervisor_apply_runner.run_supervisor_apply"
            ) as mock_apply,
            patch.object(dispatcher, "_scan_supervisor_candidates") as mock_scan,
        ):
            dispatcher.dispatch(plan)

            mock_governance.assert_called_once()
            mock_apply.assert_not_called()
            mock_scan.assert_not_called()

    def test_dispatcher_handles_both_phases(self) -> None:
        """Test dispatcher executes both governance and supervisor."""
        plan = TickPlan(
            governance_enabled=True,
            governance_material="testing",
            supervisor_enabled=True,
            supervisor_issues=[789],
            dry_run=False,
        )

        dispatcher = TickDispatcher()

        with (
            patch(
                "vibe3.execution.governance_sync_runner.run_governance_sync"
            ) as mock_governance,
            patch(
                "vibe3.execution.supervisor_apply_runner.run_supervisor_apply"
            ) as mock_apply,
        ):
            dispatcher.dispatch(plan)

            mock_governance.assert_called_once_with(
                tick_count=0,
                material_override="testing",
                dry_run=False,
                show_prompt=False,
                session_id=None,
            )
            mock_apply.assert_called_once_with(
                issue_number=789,
                dry_run=False,
                fresh_session=True,
            )

    def test_dispatcher_dry_run_format_with_explicit_issues(self) -> None:
        """Test dry-run output format with explicit issue list."""
        plan = TickPlan(
            governance_enabled=True,
            governance_material="architecture",
            supervisor_enabled=True,
            supervisor_issues=[123, 456],
            dry_run=True,
        )

        dispatcher = TickDispatcher()

        with patch("vibe3.services.tick_dispatcher.Console") as mock_console:
            mock_console_instance = MagicMock()
            mock_console.return_value = mock_console_instance

            dispatcher.dispatch(plan)

            # Check that print was called with formatted output
            print_calls = mock_console_instance.print.call_args_list
            assert len(print_calls) > 0

            # Verify the output contains expected sections
            all_output = str(print_calls)
            assert "Governance" in all_output
            assert "Supervisor" in all_output
            assert "architecture" in all_output
            assert "123" in all_output
            assert "456" in all_output

    def test_dispatcher_dry_run_format_with_scan_mode(self) -> None:
        """Test dry-run output format indicates scan mode when issues empty."""
        plan = TickPlan(
            governance_enabled=False,
            supervisor_enabled=True,
            supervisor_issues=[],  # Empty triggers scan mode
            dry_run=True,
        )

        dispatcher = TickDispatcher()

        with patch("vibe3.services.tick_dispatcher.Console") as mock_console:
            mock_console_instance = MagicMock()
            mock_console.return_value = mock_console_instance

            dispatcher.dispatch(plan)

            # Check output indicates scan mode
            print_calls = mock_console_instance.print.call_args_list
            all_output = str(print_calls)
            assert "scan" in all_output.lower()


class TestTickDispatcherScanCandidates:
    """Test suite for _scan_supervisor_candidates method."""

    def test_scan_returns_issue_numbers(self) -> None:
        """Test that scan returns list of issue numbers."""
        dispatcher = TickDispatcher()

        mock_candidates = [
            {
                "number": 111,
                "title": "Issue 111",
                "labels": ["supervisor", "state/handoff"],
            },
            {
                "number": 222,
                "title": "Issue 222",
                "labels": ["supervisor", "state/handoff"],
            },
        ]

        with patch(
            "vibe3.services.scan_service.fetch_supervisor_candidates",
            return_value=mock_candidates,
        ):
            result = dispatcher._scan_supervisor_candidates()

            assert result == [111, 222]

    def test_scan_returns_empty_list_on_error(self) -> None:
        """Test that scan handles errors gracefully."""
        dispatcher = TickDispatcher()

        with patch(
            "vibe3.services.scan_service.fetch_supervisor_candidates",
            side_effect=Exception("GitHub API error"),
        ):
            result = dispatcher._scan_supervisor_candidates()

            assert result == []

    def test_scan_handles_empty_candidates(self) -> None:
        """Test that scan handles no candidates found."""
        dispatcher = TickDispatcher()

        with patch(
            "vibe3.services.scan_service.fetch_supervisor_candidates",
            return_value=[],
        ):
            result = dispatcher._scan_supervisor_candidates()

            assert result == []
