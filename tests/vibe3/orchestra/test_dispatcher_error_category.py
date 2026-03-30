"""Tests for Dispatcher error category tracking - Phase 3."""

from pathlib import Path
from unittest.mock import patch

from tests.vibe3.orchestra.conftest import CompletedProcess
from vibe3.orchestra.config import CircuitBreakerConfig, OrchestraConfig
from vibe3.orchestra.dispatcher import Dispatcher


class TestDispatcherErrorCategoryTracking:
    """Tests for error category tracking."""

    def test_error_category_reset_on_each_run(self):
        """Error category should be reset before each command run."""
        config = OrchestraConfig()
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))

        # Set error category manually
        dispatcher._last_error_category = "previous_error"

        with patch(
            "subprocess.run",
            return_value=CompletedProcess(returncode=0),
        ):
            result = dispatcher._run_command(["echo", "test"], Path("/tmp"), "Test")

        assert result is True
        # Error category should be reset to None on success
        assert dispatcher._last_error_category is None

    def test_error_category_set_on_failure(self):
        """Error category should be set when command fails."""
        config = OrchestraConfig()
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))

        with patch(
            "subprocess.run",
            return_value=CompletedProcess(
                returncode=1, stderr="Error: rate limit exceeded"
            ),
        ):
            result = dispatcher._run_command(["echo", "test"], Path("/tmp"), "Test")

        assert result is False
        # Error category should be set
        assert dispatcher._last_error_category is not None

    def test_error_category_classified_without_circuit_breaker(self):
        """Classification should still run when circuit breaker is disabled."""
        config = OrchestraConfig(
            circuit_breaker=CircuitBreakerConfig(enabled=False),
        )
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))

        with patch(
            "subprocess.run",
            return_value=CompletedProcess(
                returncode=1, stderr="Error: rate limit exceeded"
            ),
        ):
            result = dispatcher._run_command(
                ["echo", "test"], Path("/tmp"), "Test without CB"
            )

        assert result is False
        assert dispatcher._last_error_category == "api_error"
