"""Tests for pre-push review gate logic.

Tests the inspect-score trigger mechanism for local review.
"""

import json
from unittest.mock import MagicMock, patch

from vibe3.services.review_runner import AgentOptions


class TestInspectScoreTrigger:
    """Tests for inspect-score based review trigger."""

    def test_should_not_trigger_review_on_high_risk_without_block(self) -> None:
        """High risk alone should not auto-trigger review."""
        inspect_data = {"score": {"score": 8, "risk_level": "HIGH", "block": False}}
        assert self._should_trigger_review(inspect_data) is False

    def test_should_trigger_review_on_critical_risk(self) -> None:
        """Critical risk with block should trigger review."""
        inspect_data = {"score": {"score": 10, "risk_level": "CRITICAL", "block": True}}
        assert self._should_trigger_review(inspect_data) is True

    def test_should_not_trigger_review_on_low_risk(self) -> None:
        """Low risk score should not trigger review."""
        inspect_data = {"score": {"score": 3, "risk_level": "LOW", "block": False}}
        assert self._should_trigger_review(inspect_data) is False

    def test_should_not_trigger_review_on_medium_risk(self) -> None:
        """Medium risk score should not trigger review."""
        inspect_data = {"score": {"score": 5, "risk_level": "MEDIUM", "block": False}}
        assert self._should_trigger_review(inspect_data) is False

    def test_handles_missing_score_gracefully(self) -> None:
        """Missing score should default to no trigger."""
        inspect_data: dict[str, dict[str, object]] = {}
        assert self._should_trigger_review(inspect_data) is False

    def _should_trigger_review(self, inspect_data: dict) -> bool:
        """Determine if review should be triggered based on inspect score."""
        score_data = inspect_data.get("score", {})
        return bool(score_data.get("block", False))


class TestAgentOptionsForPrePush:
    """Tests for AgentOptions in pre-push context."""

    def test_default_options_suitable_for_pre_push(self) -> None:
        """Default options should be suitable for pre-push review."""
        options = AgentOptions()
        assert options.agent is None
        assert options.backend is None
        assert options.model is None
        assert options.timeout_seconds == 600  # 10 minutes

    def test_can_override_model_for_pre_push(self) -> None:
        """Can override model for pre-push review."""
        options = AgentOptions(model="gpt-5.4")
        assert options.model == "gpt-5.4"


class TestInspectJsonOutput:
    """Tests for inspect --json output structure."""

    def test_inspect_json_contains_score(self) -> None:
        """Inspect JSON output should contain score section."""
        from vibe3.services.review_pipeline_helpers import run_inspect_json

        with patch("vibe3.services.review_pipeline_helpers.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps(
                {
                    "impact": {"changed_files": ["a.py"]},
                    "dag": {"nodes": []},
                    "score": {"score": 5, "risk_level": "MEDIUM"},
                }
            )
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = run_inspect_json(["base", "main"])

        assert "score" in result
        assert "risk_level" in result["score"]


class TestPrePushCompileCheck:
    """Tests for compile check in pre-push."""

    def test_compile_check_detects_syntax_error(self, tmp_path) -> None:
        """Compile check should detect Python syntax errors."""
        # Create a file with syntax error
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def foo(\n")  # Missing closing paren

        import subprocess

        result = subprocess.run(
            ["python", "-m", "compileall", str(tmp_path), "-q"],
            capture_output=True,
        )
        assert result.returncode != 0

    def test_compile_check_passes_valid_code(self, tmp_path) -> None:
        """Compile check should pass valid Python code."""
        good_file = tmp_path / "good.py"
        good_file.write_text("def foo(): pass\n")

        import subprocess

        result = subprocess.run(
            ["python", "-m", "compileall", str(tmp_path), "-q"],
            capture_output=True,
        )
        assert result.returncode == 0
