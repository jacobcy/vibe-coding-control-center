"""Tests for TaskLabelService."""

from unittest.mock import MagicMock, patch

from vibe3.services.task_label_service import TaskLabelService


class TestTaskLabelService:
    """Tests for vibe-task label operations."""

    @patch("vibe3.services.task_label_service.subprocess.run")
    def test_ensure_vibe_task_label_already_present(self, mock_run: MagicMock) -> None:
        """When label already present, should return True without adding."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"labels": [{"name": "vibe-task"}]}',
        )

        svc = TaskLabelService()
        result = svc.ensure_vibe_task_label(123)

        assert result is True
        assert mock_run.call_count == 1

    @patch("vibe3.services.task_label_service.subprocess.run")
    def test_ensure_vibe_task_label_adds_when_missing(
        self, mock_run: MagicMock
    ) -> None:
        """When label missing, should add it and return True."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout='{"labels": []}'),
            MagicMock(returncode=0, stdout=""),
        ]

        svc = TaskLabelService()
        result = svc.ensure_vibe_task_label(123)

        assert result is True
        assert mock_run.call_count == 2

    @patch("vibe3.services.task_label_service.subprocess.run")
    def test_ensure_vibe_task_label_handles_get_failure(
        self, mock_run: MagicMock
    ) -> None:
        """When get labels fails, should try to add anyway."""
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout="", stderr="error"),
            MagicMock(returncode=0, stdout=""),
        ]

        svc = TaskLabelService()
        result = svc.ensure_vibe_task_label(123)

        assert result is True

    @patch("vibe3.services.task_label_service.subprocess.run")
    def test_ensure_vibe_task_label_handles_add_failure(
        self, mock_run: MagicMock
    ) -> None:
        """When add label fails, should return False."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout='{"labels": []}'),
            MagicMock(returncode=1, stdout="", stderr="error"),
        ]

        svc = TaskLabelService()
        result = svc.ensure_vibe_task_label(123)

        assert result is False

    @patch("vibe3.services.task_label_service.subprocess.run")
    def test_has_vibe_task_label_returns_true(self, mock_run: MagicMock) -> None:
        """Should return True when vibe-task label exists."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"labels": [{"name": "other"}, {"name": "vibe-task"}]}',
        )

        svc = TaskLabelService()
        result = svc._has_vibe_task_label(123)

        assert result is True

    @patch("vibe3.services.task_label_service.subprocess.run")
    def test_has_vibe_task_label_returns_false(self, mock_run: MagicMock) -> None:
        """Should return False when vibe-task label does not exist."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"labels": [{"name": "other"}]}',
        )

        svc = TaskLabelService()
        result = svc._has_vibe_task_label(123)

        assert result is False
