"""Tests for task resume command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


class TestTaskResumeCommand:
    """Tests for task resume CLI command."""

    def test_task_resume_dry_run_with_all(self) -> None:
        """vibe3 task resume --all --reason "quota resumed" 走 dry-run。"""
        mock_usecase = MagicMock()
        mock_usecase.resume_failed_issues.return_value = {
            "resumed": [],
            "skipped": [],
            "requested": 2,
            "candidates": [
                {
                    "number": 439,
                    "title": "Manager backend regression",
                    "state": "failed",
                    "failed_reason": "quota exhausted",
                },
                {
                    "number": 441,
                    "title": "Another failed issue",
                    "state": "failed",
                    "failed_reason": "network error",
                },
            ],
        }

        # Mock fetch_failed_resume_candidates
        mock_usecase.status_service.fetch_failed_resume_candidates.return_value = [
            {"number": 439, "title": "Manager backend regression"},
            {"number": 441, "title": "Another failed issue"},
        ]

        with patch(
            "vibe3.commands.task._build_resume_usecase",
            return_value=mock_usecase,
        ):
            result = runner.invoke(
                app,
                [
                    "task",
                    "resume",
                    "--all",
                    "--reason",
                    "quota resumed",
                ],
            )

            assert result.exit_code == 0
            assert "439" in result.stdout
            assert "441" in result.stdout
            assert "dry-run" in result.stdout.lower()

            # dry-run 模式不调用 apply
            mock_usecase.resume_failed_issues.assert_called_once_with(
                issue_numbers=[439, 441],
                reason="quota resumed",
                dry_run=True,
            )

    def test_task_resume_apply_with_explicit_issue_numbers(self) -> None:
        """vibe3 task resume 340 410 --yes --reason "quota resumed" 会执行恢复。"""
        mock_usecase = MagicMock()
        mock_usecase.resume_failed_issues.return_value = {
            "resumed": [340, 410],
            "skipped": [],
            "requested": 2,
        }

        with patch(
            "vibe3.commands.task._build_resume_usecase",
            return_value=mock_usecase,
        ):
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

            mock_usecase.resume_failed_issues.assert_called_once_with(
                issue_numbers=[340, 410],
                reason="quota resumed",
                dry_run=False,
            )

    def test_task_resume_requires_all_or_issue_list(self) -> None:
        """没有 --all 且没有 issue 列表时，命令报错退出。"""
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
                "--all",
            ],
        )

        assert result.exit_code != 0
