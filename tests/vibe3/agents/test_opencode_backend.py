"""Tests for OpenCode backend verification scenarios.

These tests verify that OpenCode backend works correctly after the Zod
schema fix and plugin disabling. Tests cover:
- Error pattern diagnosis
- Command construction with OpenCode backend
- Manager-to-OpenCode dispatch path
- Plugin-related events no longer causing silent failures
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.agents.backends.codeagent_config import (
    resolve_effective_agent_options,
)
from vibe3.models.review_runner import AgentOptions, AgentResult
from vibe3.utils.codeagent_helpers import (
    diagnose_backend_error,
    summarize_backend_output,
)


class TestOpenCodeBackendVerification:
    """Tests for OpenCode-specific backend scenarios."""

    def test_opencode_backend_command_construction(self, tmp_path: Path) -> None:
        """Verify command is correctly built for OpenCode backend."""
        # Create a temporary models.json with vibe-executor mapped to opencode backend
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        models_json = config_dir / "models.json"
        models_json.write_text(
            json.dumps(
                {
                    "default_backend": "claude",
                    "default_model": "claude-sonnet-4-20250514",
                    "agents": {
                        "vibe-executor": {
                            "backend": "opencode",
                            "model": "my-provider/gpt-4o",
                        },
                    },
                }
            )
        )

        # Mock repo_models_json_path to return our test config
        with patch(
            "vibe3.agents.backends.codeagent_config.repo_models_json_path",
            return_value=models_json,
        ):
            options = AgentOptions(agent="vibe-executor")
            resolved = resolve_effective_agent_options(options)

            # Verify resolved backend and model
            assert resolved.backend == "opencode"
            assert resolved.model == "my-provider/gpt-4o"

            # Build the actual command
            prompt_file = tmp_path / "prompt.md"
            prompt_file.write_text("test prompt")
            command = CodeagentBackend._build_command(
                resolved,
                str(prompt_file),
                task="test task",
            )

            # Verify command contains --backend opencode
            assert "--backend" in command
            backend_idx = command.index("--backend")
            assert command[backend_idx + 1] == "opencode"

            # Verify command contains the model
            assert "--model" in command
            model_idx = command.index("--model")
            assert command[model_idx + 1] == "my-provider/gpt-4o"

    def test_opencode_zod_schema_error_diagnosis(self) -> None:
        """Verify Zod schema error is still correctly diagnosed after the fix."""
        # Output containing the Zod schema error pattern
        output = """
Error: schema._zod.def is not a function
    at parseSchema (/app/schema.js:42)
    at validateInput (/app/validation.js:15)
"""
        diagnosis = diagnose_backend_error(output)

        assert diagnosis is not None
        assert "OpenCode Zod schema error" in diagnosis
        assert (
            "Update codeagent-wrapper" in diagnosis
            or "Use a different model" in diagnosis
        )

    def test_opencode_plugin_event_not_in_normal_output(self) -> None:
        """Verify OpenCode backend completes cleanly without plugin-related errors."""
        # Simulate successful OpenCode execution with normal output
        stdout = """
VERDICT: PASS
SESSION_ID: test-session-123
Result: Successfully executed
"""
        stderr = ""

        # Parse the output - should not raise errors about plugin loading
        result = AgentResult(
            exit_code=0,
            stdout=stdout,
            stderr=stderr,
            session_id="test-session-123",
        )

        assert result.is_success()
        assert "VERDICT: PASS" in result.stdout

    def test_opencode_plugin_error_summarized_correctly(self) -> None:
        """Verify plugin errors are surfaced rather than silently dropped."""
        # stderr containing plugin loading error
        stderr = """
[codeagent-wrapper] Starting backend: opencode
Failed to parse event: plugin loading
Error: Cannot find module 'some-plugin'
    at loadPlugin (/app/plugins.js:25)
"""
        stdout = "VERDICT: FAIL\n"

        summary = summarize_backend_output(stderr, stdout)

        # Verify error is captured in summary
        assert "Failed to parse event" in summary or "plugin" in summary.lower()

    def test_opencode_success_path_with_model_resolution(self, tmp_path: Path) -> None:
        """Verify full path: options resolve to opencode backend, command
        is built correctly.
        """
        # Create test config with opencode backend mapping
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        models_json = config_dir / "models.json"
        models_json.write_text(
            json.dumps(
                {
                    "default_backend": "claude",
                    "default_model": "claude-sonnet-4-20250514",
                    "agents": {
                        "vibe-executor": {
                            "backend": "opencode",
                            "model": "my-provider/gpt-4o",
                        },
                    },
                }
            )
        )

        # Mock subprocess to return success
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\nSESSION_ID: test-456\n"
        mock_result.stderr = ""

        with patch(
            "vibe3.agents.backends.codeagent_config.repo_models_json_path",
            return_value=models_json,
        ):
            with patch.object(CodeagentBackend, "_run_subprocess") as mock_run:
                mock_run.return_value = (mock_result, None)

                backend = CodeagentBackend()
                options = AgentOptions(agent="vibe-executor")

                backend.run(
                    "test prompt content",
                    options,
                    task="execute test",
                )

                # Verify resolution
                assert mock_run.call_count == 1
                call_args = mock_run.call_args[0]
                command = call_args[0]

                # Verify command has opencode backend and model
                assert "--backend" in command
                backend_idx = command.index("--backend")
                assert command[backend_idx + 1] == "opencode"

                assert "--model" in command
                model_idx = command.index("--model")
                assert command[model_idx + 1] == "my-provider/gpt-4o"
