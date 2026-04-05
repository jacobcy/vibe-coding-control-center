"""Tests for task resume command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


class TestTaskResumeCommand:
    """Tests for task resume CLI command."""

    def test_task_resume_dry_run_with_failed_flag(self) -> None:
        """vibe3 task resume --failed --reason "quota resumed" 走 dry-run。"""
        mock_usecase = MagicMock()
        mock_usecase.resume_issues.return_value = {
            "resumed": [],
            "skipped": [],
            "requested": [439, 441],
            "candidates": [
                {
                    "number": 439,
                    "title": "Manager backend regression",
                    "state": "failed",
                    "resume_kind": "failed",
                    "failed_reason": "quota exhausted",
                },
                {
                    "number": 441,
                    "title": "Another failed issue",
                    "state": "failed",
                    "resume_kind": "failed",
                    "failed_reason": "network error",
                },
            ],
        }

        # Mock fetch_resume_candidates
        mock_usecase.status_service.fetch_resume_candidates.return_value = [
            {
                "number": 439,
                "title": "Manager backend regression",
                "resume_kind": "failed",
            },
            {
                "number": 441,
                "title": "Another failed issue",
                "resume_kind": "failed",
            },
        ]

        # Mock FlowService to return empty lists
        with (
            patch(
                "vibe3.commands.task._build_resume_usecase",
                return_value=mock_usecase,
            ),
            patch("vibe3.commands.task.FlowService") as mock_flow_service,
        ):
            mock_flow_service_instance = MagicMock()
            mock_flow_service.return_value = mock_flow_service_instance
            mock_flow_service_instance.list_flows.return_value = []

            result = runner.invoke(
                app,
                [
                    "task",
                    "resume",
                    "--failed",
                    "--reason",
                    "quota resumed",
                ],
            )

            assert result.exit_code == 0
            assert "439" in result.stdout
            assert "441" in result.stdout
            assert "dry-run" in result.stdout.lower()

            # Verify resume_issues was called with flows parameter
            mock_usecase.resume_issues.assert_called_once()
            call_kwargs = mock_usecase.resume_issues.call_args[1]
            assert call_kwargs["issue_numbers"] == [439, 441]
            assert call_kwargs["reason"] == "quota resumed"
            assert call_kwargs["dry_run"] is True
            assert "flows" in call_kwargs
            assert "stale_flows" in call_kwargs

    def test_task_resume_dry_run_with_blocked_flag(self) -> None:
        """vibe3 task resume --blocked --reason "dependency available" 走 dry-run。"""
        mock_usecase = MagicMock()
        mock_usecase.resume_issues.return_value = {
            "resumed": [],
            "skipped": [],
            "requested": [301],
            "candidates": [
                {
                    "number": 301,
                    "title": "Dependency available",
                    "state": "blocked",
                    "resume_kind": "blocked",
                },
            ],
        }

        # Mock fetch_resume_candidates
        mock_usecase.status_service.fetch_resume_candidates.return_value = [
            {
                "number": 301,
                "title": "Dependency available",
                "resume_kind": "blocked",
            },
        ]

        with (
            patch(
                "vibe3.commands.task._build_resume_usecase",
                return_value=mock_usecase,
            ),
            patch("vibe3.commands.task.FlowService") as mock_flow_service,
        ):
            mock_flow_service_instance = MagicMock()
            mock_flow_service.return_value = mock_flow_service_instance
            mock_flow_service_instance.list_flows.return_value = []

            result = runner.invoke(
                app,
                [
                    "task",
                    "resume",
                    "--blocked",
                    "--reason",
                    "dependency available",
                ],
            )

            assert result.exit_code == 0
            assert "301" in result.stdout
            assert "dry-run" in result.stdout.lower()

            # Verify resume_issues was called with flows parameter
            mock_usecase.resume_issues.assert_called_once()
            call_kwargs = mock_usecase.resume_issues.call_args[1]
            assert call_kwargs["issue_numbers"] == [301]
            assert call_kwargs["reason"] == "dependency available"
            assert call_kwargs["dry_run"] is True
            assert "flows" in call_kwargs
            assert "stale_flows" in call_kwargs

    def test_task_resume_apply_with_explicit_issue_numbers(self) -> None:
        """vibe3 task resume 340 410 --yes --reason "quota resumed" 会执行恢复。"""
        mock_usecase = MagicMock()
        mock_usecase.resume_issues.return_value = {
            "resumed": [
                {"number": 340, "resume_kind": "failed"},
                {"number": 410, "resume_kind": "failed"},
            ],
            "skipped": [],
            "requested": [340, 410],
        }

        with (
            patch(
                "vibe3.commands.task._build_resume_usecase",
                return_value=mock_usecase,
            ),
            patch("vibe3.commands.task.FlowService") as mock_flow_service,
        ):
            mock_flow_service_instance = MagicMock()
            mock_flow_service.return_value = mock_flow_service_instance
            mock_flow_service_instance.list_flows.return_value = []

            result = runner.invoke(
                app,
                [
                    "task",
                    "resume",
                    "340",
                    "410",
                    "--yes",
                    "--reason",
                    "quota resumed",
                ],
            )

            assert result.exit_code == 0
            assert "resumed" in result.stdout.lower()

            # Verify resume_issues was called with flows parameter
            mock_usecase.resume_issues.assert_called_once()
            call_kwargs = mock_usecase.resume_issues.call_args[1]
            assert call_kwargs["issue_numbers"] == [340, 410]
            assert call_kwargs["reason"] == "quota resumed"
            assert call_kwargs["dry_run"] is False
            assert "flows" in call_kwargs
            assert "stale_flows" in call_kwargs

    def test_task_resume_requires_all_or_issue_list(self) -> None:
        """没有 --failed/--blocked 且没有 issue 列表时，命令报错退出。"""
        result = runner.invoke(
            app,
            [
                "task",
                "resume",
                "--reason",
                "quota resumed",
            ],
        )

        assert result.exit_code != 0
        # Typer exits with code 2 and error message
        assert result.exit_code == 2 or "error" in result.output.lower()

    def test_task_resume_requires_reason(self) -> None:
        """没有 --reason 时，命令报错退出。"""
        result = runner.invoke(
            app,
            [
                "task",
                "resume",
                "--failed",
            ],
        )

        assert result.exit_code != 0

    def test_task_resume_cannot_specify_both_failed_and_blocked(self) -> None:
        """不能同时指定 --failed 和 --blocked。"""
        result = runner.invoke(
            app,
            [
                "task",
                "resume",
                "--failed",
                "--blocked",
                "--reason",
                "test",
            ],
        )

        assert result.exit_code != 0
        assert "both" in result.output.lower() or "cannot" in result.output.lower()
