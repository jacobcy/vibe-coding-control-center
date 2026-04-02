"""Tests for ManagerExecutor error category tracking."""

from pathlib import Path
from unittest.mock import patch

from tests.vibe3.conftest import CompletedProcess
from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.orchestra.config import CircuitBreakerConfig, OrchestraConfig


class TestManagerErrorCategoryTracking:
    """Tests for error category tracking in ManagerExecutor."""

    def test_error_category_reset_on_each_run(self):
        """Error category should be reset before each command run."""
        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))

        # Set error category manually
        manager._last_error_category = "previous_error"

        with patch(
            "subprocess.run",
            return_value=CompletedProcess(returncode=0),
        ):
            result = manager._run_command(["echo", "test"], Path("/tmp"), "Test")

        assert result is True
        # Error category should be reset to None on success
        assert manager._last_error_category is None

    def test_error_category_set_on_failure(self):
        """Error category should be set when command fails."""
        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))

        with patch(
            "subprocess.run",
            return_value=CompletedProcess(
                returncode=1, stderr="Error: rate limit exceeded"
            ),
        ):
            result = manager._run_command(["echo", "test"], Path("/tmp"), "Test")

        assert result is False
        # Error category should be set
        assert manager._last_error_category is not None

    def test_error_category_classified_without_circuit_breaker(self):
        """Classification should still run when circuit breaker is disabled."""
        config = OrchestraConfig(
            circuit_breaker=CircuitBreakerConfig(enabled=False),
        )
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))

        with patch(
            "subprocess.run",
            return_value=CompletedProcess(
                returncode=1, stderr="Error: rate limit exceeded"
            ),
        ):
            result = manager._run_command(
                ["echo", "test"], Path("/tmp"), "Test without CB"
            )

        assert result is False
        assert manager._last_error_category == "api_error"
