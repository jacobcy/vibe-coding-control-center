"""Tests for review_pipeline_helpers module."""

import unittest
from unittest.mock import patch

from vibe3.agents.review_pipeline_helpers import run_inspect_json
from vibe3.exceptions import SystemError


class TestRunInspectJson(unittest.TestCase):
    """Test cases for run_inspect_json function."""

    @patch("vibe3.agents.review_pipeline_helpers.build_change_analysis")
    def test_pr_dispatch(self, mock_build_change_analysis: unittest.mock.Mock) -> None:
        """Test PR dispatch calls build_change_analysis with correct arguments."""
        mock_build_change_analysis.return_value = {
            "impact": {},
            "changed_symbols": {},
            "dag": {},
            "score": {},
        }

        result = run_inspect_json(["pr", "123"])

        mock_build_change_analysis.assert_called_once_with("pr", "123")
        assert isinstance(result, dict)
        assert "score" in result
        assert "changed_symbols" in result

    @patch("vibe3.agents.review_pipeline_helpers.build_change_analysis")
    def test_base_dispatch(
        self, mock_build_change_analysis: unittest.mock.Mock
    ) -> None:
        """Test base dispatch calls build_change_analysis with 'branch' source_type."""
        mock_build_change_analysis.return_value = {
            "impact": {},
            "changed_symbols": {},
            "dag": {},
            "score": {},
        }

        result = run_inspect_json(["base", "main"])

        mock_build_change_analysis.assert_called_once_with("branch", "main")
        assert isinstance(result, dict)
        assert "score" in result
        assert "changed_symbols" in result

    def test_unknown_subcommand(self) -> None:
        """Test unknown subcommand raises SystemError."""
        with self.assertRaises(SystemError) as context:
            run_inspect_json(["unknown"])

        self.assertIn("Unknown inspect subcommand: unknown", str(context.exception))

    def test_missing_identifier(self) -> None:
        """Test missing identifier raises SystemError."""
        with self.assertRaises(SystemError) as context:
            run_inspect_json(["pr"])

        self.assertIn("Missing identifier for inspect pr", str(context.exception))

    def test_empty_args(self) -> None:
        """Test empty args raises SystemError."""
        with self.assertRaises(SystemError) as context:
            run_inspect_json([])

        self.assertIn("Missing inspect subcommand", str(context.exception))


if __name__ == "__main__":
    unittest.main()
