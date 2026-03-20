"""Tests for review_gate command.

Tests the pre-push review gate logic.
"""

from unittest.mock import MagicMock, patch

import pytest
import typer

from vibe3.commands.review_gate import review_gate


class TestReviewGate:
    """Tests for review_gate command."""

    def test_review_gate_passes_on_low_risk(self) -> None:
        """Low risk should pass without review."""
        mock_config = MagicMock()
        mock_config.review.agent_config.agent = "code-reviewer"

        with (
            patch("vibe3.commands.review_gate.run_inspect_json") as mock_inspect,
            patch(
                "vibe3.commands.review_gate.VibeConfig.get_defaults"
            ) as mock_get_config,
        ):
            mock_inspect.return_value = {"score": {"risk_level": "LOW", "score": 3}}
            mock_get_config.return_value = mock_config

            # Should not raise any exception
            review_gate(check_block=False)

    def test_review_gate_passes_on_medium_risk(self) -> None:
        """Medium risk should pass without review."""
        mock_config = MagicMock()
        mock_config.review.agent_config.agent = "code-reviewer"

        with (
            patch("vibe3.commands.review_gate.run_inspect_json") as mock_inspect,
            patch(
                "vibe3.commands.review_gate.VibeConfig.get_defaults"
            ) as mock_get_config,
        ):
            mock_inspect.return_value = {"score": {"risk_level": "MEDIUM", "score": 5}}
            mock_get_config.return_value = mock_config

            # Should not raise any exception
            review_gate(check_block=False)

    def test_review_gate_triggers_review_on_high_risk(self) -> None:
        """HIGH risk should trigger review."""
        mock_config = MagicMock()
        mock_config.review.agent_config.agent = "code-reviewer"
        mock_config.review.agent_config.backend = None
        mock_config.review.agent_config.model = None

        with (
            patch("vibe3.commands.review_gate.run_inspect_json") as mock_inspect,
            patch("vibe3.commands.review_gate.run_review_agent") as mock_review,
            patch("vibe3.commands.review_gate.build_review_context") as mock_build,
            patch(
                "vibe3.commands.review_gate.VibeConfig.get_defaults"
            ) as mock_get_config,
        ):
            mock_inspect.return_value = {
                "score": {"risk_level": "HIGH", "score": 8},
                "changed_symbols": None,
            }
            mock_build.return_value = "context"
            mock_review.return_value = MagicMock(stdout="VERDICT: PASS", exit_code=0)
            mock_get_config.return_value = mock_config

            # Should not raise any exception
            review_gate(check_block=False)

    def test_review_gate_blocks_on_verdict_block(self) -> None:
        """BLOCK verdict should return exit code 1."""
        mock_config = MagicMock()
        mock_config.review.agent_config.agent = "code-reviewer"
        mock_config.review.agent_config.backend = None
        mock_config.review.agent_config.model = None

        mock_review_result = MagicMock()
        mock_review_result.stdout = "path/to/file.py:42 [MAJOR] Issue\nVERDICT: BLOCK"
        mock_review_result.exit_code = 0

        with (
            patch("vibe3.commands.review_gate.run_inspect_json") as mock_inspect,
            patch("vibe3.commands.review_gate.run_review_agent") as mock_review,
            patch("vibe3.commands.review_gate.build_review_context") as mock_build,
            patch(
                "vibe3.commands.review_gate.VibeConfig.get_defaults"
            ) as mock_get_config,
        ):
            mock_inspect.return_value = {
                "score": {"risk_level": "HIGH", "score": 9},
                "changed_symbols": None,
            }
            mock_build.return_value = "context"
            mock_review.return_value = mock_review_result
            mock_get_config.return_value = mock_config

            with pytest.raises(typer.Exit) as exc_info:
                review_gate(check_block=True)

            assert exc_info.value.exit_code == 1

    def test_review_gate_handles_inspect_failure(self) -> None:
        """Inspect failure should return exit code 2."""
        mock_config = MagicMock()
        mock_config.review.agent_config.agent = "code-reviewer"

        with (
            patch("vibe3.commands.review_gate.run_inspect_json") as mock_inspect,
            patch(
                "vibe3.commands.review_gate.VibeConfig.get_defaults"
            ) as mock_get_config,
        ):
            mock_inspect.side_effect = Exception("Inspect failed")
            mock_get_config.return_value = mock_config

            with pytest.raises(typer.Exit) as exc_info:
                review_gate(check_block=False)

            assert exc_info.value.exit_code == 2

    def test_review_gate_critical_blocks_on_review_failure(self) -> None:
        """CRITICAL risk should block on review failure."""
        mock_config = MagicMock()
        mock_config.review.agent_config.agent = "code-reviewer"
        mock_config.review.agent_config.backend = None
        mock_config.review.agent_config.model = None

        with (
            patch("vibe3.commands.review_gate.run_inspect_json") as mock_inspect,
            patch("vibe3.commands.review_gate.run_review_agent") as mock_review,
            patch("vibe3.commands.review_gate.build_review_context") as mock_build,
            patch(
                "vibe3.commands.review_gate.VibeConfig.get_defaults"
            ) as mock_get_config,
        ):
            mock_inspect.return_value = {
                "score": {"risk_level": "CRITICAL", "score": 10},
                "changed_symbols": None,
            }
            mock_build.return_value = "context"
            mock_review.side_effect = Exception("Review failed")
            mock_get_config.return_value = mock_config

            with pytest.raises(typer.Exit) as exc_info:
                review_gate(check_block=True)

            assert exc_info.value.exit_code == 1
