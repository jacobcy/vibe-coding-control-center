"""Tests for CodeagentBackend - codeagent-wrapper runner.

Tests the core runner functionality with extensible interface design.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.config.settings import AgentPromptConfig, VibeConfig
from vibe3.exceptions import AgentExecutionError
from vibe3.models.review_runner import (
    AgentOptions,
)


class TestCodeagentBackend:
    """Tests for CodeagentBackend.run method."""

    def test_build_prompt_file_content_prepends_global_notice(self) -> None:
        config = VibeConfig(
            agent_prompt=AgentPromptConfig(global_notice="## Debug Stop Rule\nStop now")
        )

        with patch(
            "vibe3.agents.backends.codeagent.VibeConfig.get_defaults",
            return_value=config,
        ):
            content = CodeagentBackend._build_prompt_file_content("prompt body")

        assert content.startswith("## Debug Stop Rule\nStop now\n\n---\n\n")
        assert content.endswith("prompt body")

    def test_build_prompt_file_content_keeps_prompt_when_notice_empty(self) -> None:
        with patch(
            "vibe3.agents.backends.codeagent.VibeConfig.get_defaults",
            return_value=VibeConfig(),
        ):
            content = CodeagentBackend._build_prompt_file_content("prompt body")

        assert content == "prompt body"

    def test_default_log_dir_uses_env_override(self, monkeypatch) -> None:
        """Async log dir should honor orchestra-provided override."""
        monkeypatch.setenv("VIBE3_ASYNC_LOG_DIR", "/tmp/orchestra-logs")

        assert (
            CodeagentBackend._default_log_dir() == Path("/tmp/orchestra-logs").resolve()
        )

    def test_resolve_async_log_path_routes_plan_issue_logs_into_issue_dir(self) -> None:
        """Plan issue async logs should live under temp/logs/issues/issue-N."""
        log_path = CodeagentBackend._resolve_async_log_path(
            Path("/tmp/logs"),
            "vibe3-plan-issue-419",
        )

        assert log_path == Path("/tmp/logs/issues/issue-419/plan.async.log")

    def test_run_uses_repo_models_mapping_for_agent_preset(
        self, tmp_path: Path
    ) -> None:
        """Agent preset should resolve through repo-local config/models.json."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""
        repo_models = tmp_path / "models.json"
        repo_models.write_text(
            '{"agents":{"code-reviewer":{"backend":"claude","model":"claude-sonnet-4-6"}}}'
        )

        with (
            patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run,
            patch(
                "vibe3.agents.backends.codeagent_config.REPO_MODELS_JSON_PATH",
                repo_models,
            ),
        ):
            mock_run.return_value = mock_result
            options = AgentOptions(
                agent="code-reviewer",
            )
            backend = CodeagentBackend()
            result = backend.run("prompt body", options)

        assert result.exit_code == 0
        assert "VERDICT: PASS" in result.stdout

        call_args = mock_run.call_args
        command = call_args[0][0]
        assert "codeagent-wrapper" in command[0]
        assert "--agent" not in command
        assert "--backend" in command
        assert "claude" in command
        assert "--model" in command
        assert "claude-sonnet-4-6" in command

    def test_run_falls_back_to_agent_flag_when_repo_mapping_missing(
        self, tmp_path: Path
    ) -> None:
        """Unknown repo-local preset mapping should fall back to raw --agent mode."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""
        repo_models = tmp_path / "models.json"
        repo_models.write_text('{"agents":{"other":{"backend":"claude"}}}')

        with (
            patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run,
            patch(
                "vibe3.agents.backends.codeagent_config.REPO_MODELS_JSON_PATH",
                repo_models,
            ),
        ):
            mock_run.return_value = mock_result
            backend = CodeagentBackend()
            result = backend.run("prompt body", AgentOptions(agent="code-reviewer"))

        assert result.exit_code == 0
        command = mock_run.call_args[0][0]
        assert "--agent" in command
        assert "code-reviewer" in command

    def test_run_without_model_when_repo_mapping_missing(self, tmp_path: Path) -> None:
        """Fallback agent mode should omit --model when repo mapping is absent."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""
        repo_models = tmp_path / "models.json"
        repo_models.write_text("{}")

        with (
            patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run,
            patch(
                "vibe3.agents.backends.codeagent_config.REPO_MODELS_JSON_PATH",
                repo_models,
            ),
        ):
            mock_run.return_value = mock_result
            options = AgentOptions(agent="code-reviewer")
            backend = CodeagentBackend()
            result = backend.run("prompt body", options)

        assert result.exit_code == 0

        # Verify no --model flag when model is None
        call_args = mock_run.call_args
        command = call_args[0][0]
        assert "--model" not in command

    def test_run_uses_explicit_cwd_when_provided(self) -> None:
        """Runner should execute in the provided cwd when specified."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            backend = CodeagentBackend()
            backend.run(
                "prompt body",
                AgentOptions(agent="code-reviewer"),
                cwd=Path("/tmp/worktree-430"),
            )

        assert mock_run.call_args.kwargs["cwd"] == "/tmp/worktree-430"

    def test_run_writes_global_notice_into_prompt_file(self, tmp_path: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""
        config = VibeConfig(
            agent_prompt=AgentPromptConfig(
                global_notice="## Debug Stop Rule\nStop current task after two retries."
            )
        )
        captured_prompt: dict[str, str] = {}

        def fake_run_subprocess(command, *, project_root, timeout_seconds):
            prompt_file = Path(command[command.index("--prompt-file") + 1])
            captured_prompt["content"] = prompt_file.read_text()
            return mock_result

        with (
            patch(
                "vibe3.agents.backends.codeagent.VibeConfig.get_defaults",
                return_value=config,
            ),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            backend = CodeagentBackend()
            with patch.object(
                backend, "_run_subprocess", side_effect=fake_run_subprocess
            ):
                backend.run("prompt body", AgentOptions(agent="code-reviewer"))

        assert captured_prompt["content"].startswith(
            "## Debug Stop Rule\nStop current task after two retries.\n\n---\n\n"
        )
        assert captured_prompt["content"].endswith("prompt body")

    def test_run_non_zero_exit_raises_error(self) -> None:
        """Runner should raise error on non-zero exit code."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "Error: something failed\n"
        mock_result.stderr = ""

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            options = AgentOptions(agent="code-reviewer")
            backend = CodeagentBackend()

            with pytest.raises(AgentExecutionError) as exc_info:
                backend.run("prompt body", options)

        assert "codeagent-wrapper failed" in str(exc_info.value)
        assert "something failed" in str(exc_info.value)

    def test_run_non_zero_exit_prefers_stderr_in_message(self) -> None:
        """Runner should surface stderr details when available."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "stdout ignored\n"
        mock_result.stderr = "wrapper stderr details\n"

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            options = AgentOptions(agent="code-reviewer")
            backend = CodeagentBackend()

            with pytest.raises(AgentExecutionError) as exc_info:
                backend.run("prompt body", options)

        assert "wrapper stderr details" in str(exc_info.value)

    def test_run_retries_without_session_when_resume_session_is_invalid(self) -> None:
        """Invalid resume session should fall back to a fresh session once."""
        invalid_resume = subprocess.CompletedProcess(
            args=["codeagent-wrapper"],
            returncode=42,
            stdout="session not found\n",
            stderr="Error: session not found for resume\n",
        )
        fresh_success = subprocess.CompletedProcess(
            args=["codeagent-wrapper"],
            returncode=0,
            stdout=(
                "VERDICT: PASS\n" "SESSION_ID: 262f0fea-eacb-4223-b842-b5b5097f94e8\n"
            ),
            stderr="",
        )

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.side_effect = [invalid_resume, fresh_success]
            backend = CodeagentBackend()

            result = backend.run(
                "prompt body",
                AgentOptions(agent="code-reviewer"),
                task="custom task",
                session_id="11111111-1111-1111-1111-111111111111",
            )

        assert result.exit_code == 0
        assert result.session_id == "262f0fea-eacb-4223-b842-b5b5097f94e8"
        assert mock_run.call_count == 2
        first_command = mock_run.call_args_list[0].args[0]
        second_command = mock_run.call_args_list[1].args[0]
        assert "resume" in first_command
        assert "11111111-1111-1111-1111-111111111111" in first_command
        assert "resume" not in second_command

    def test_run_does_not_retry_without_session_for_non_resume_error(self) -> None:
        """Non-resume failures should still fail fast without a fresh retry."""
        hard_failure = subprocess.CompletedProcess(
            args=["codeagent-wrapper"],
            returncode=1,
            stdout="fatal error\n",
            stderr="fatal error\n",
        )

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.return_value = hard_failure
            backend = CodeagentBackend()

            with pytest.raises(AgentExecutionError):
                backend.run(
                    "prompt body",
                    AgentOptions(agent="code-reviewer"),
                    session_id="11111111-1111-1111-1111-111111111111",
                )

        assert mock_run.call_count == 1

    def test_run_wrapper_not_found(self) -> None:
        """Runner should give clear error when wrapper not found."""
        from vibe3.exceptions import AgentExecutionError

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("codeagent-wrapper not found")
            options = AgentOptions(agent="code-reviewer")
            backend = CodeagentBackend()

            with pytest.raises(AgentExecutionError) as exc_info:
                backend.run("prompt body", options)

        assert "codeagent-wrapper not found" in str(exc_info.value)

    def test_run_timeout(self) -> None:
        """Runner should timeout after specified seconds."""
        import subprocess

        from vibe3.exceptions import AgentExecutionError

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["codeagent-wrapper"], timeout=300
            )
            options = AgentOptions(
                agent="code-reviewer",
                timeout_seconds=300,
            )
            backend = CodeagentBackend()

            with pytest.raises(AgentExecutionError) as exc_info:
                backend.run("prompt body", options)

        assert "timed out" in str(exc_info.value)

    def test_run_uses_prompt_file(self) -> None:
        """Runner should pass prompt via temporary file."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Result\n"
        mock_result.stderr = ""

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            options = AgentOptions(agent="code-reviewer")
            backend = CodeagentBackend()
            backend.run("my prompt file content", options, task="custom task")

        # Check that command includes --prompt-file
        call_args = mock_run.call_args[0]
        command = call_args[0]
        assert "--prompt-file" in command
        # The prompt file path should be created under ~/.codeagent/agents
        prompt_file_idx = command.index("--prompt-file") + 1
        expected_dir = Path.home() / ".codeagent" / "agents"
        assert Path(command[prompt_file_idx]).parent == expected_dir
        # The last argument should be the custom task
        assert command[-1] == "custom task"

    def test_run_no_worktree_flag_after_refactor(self) -> None:
        """After refactoring, --worktree flag is no longer used.

        Worktree is now self-managed.
        """
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            backend = CodeagentBackend()
            backend.run(
                "prompt body",
                AgentOptions(agent="code-reviewer"),
            )

        command = mock_run.call_args[0][0]
        # After refactoring, --worktree flag is removed (vibe3 self-manages worktrees)
        assert "--worktree" not in command

    def test_run_skips_worktree_flag_for_resume_session(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            backend = CodeagentBackend()
            backend.run(
                "prompt body",
                AgentOptions(agent="code-reviewer"),
                session_id="262f0fea-eacb-4223-b842-b5b5097f94e8",
            )

        command = mock_run.call_args[0][0]
        assert "--worktree" not in command
