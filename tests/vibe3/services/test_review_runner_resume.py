import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.models.review_runner import AgentOptions
from vibe3.services.review_runner import run_review_agent


@patch("subprocess.run")
@patch("tempfile.NamedTemporaryFile")
def test_run_review_agent_resume_mode(mock_tempfile, mock_run):
    mock_file = MagicMock()
    mock_file.name = "/Users/test/.codeagent/agents/fake-prompt.md"
    mock_tempfile.return_value.__enter__.return_value = mock_file

    mock_cp = MagicMock(spec=subprocess.CompletedProcess)
    mock_cp.returncode = 0
    mock_cp.stdout = "SESSION_ID: 262f0fea-eacb-4223-b842-b5b5097f94e8\nSuccess"
    mock_cp.stderr = ""
    mock_run.return_value = mock_cp

    options = AgentOptions(agent="planner")
    session_id = "262f0fea-eacb-4223-b842-b5b5097f94e8"

    result = run_review_agent(
        prompt_file_content="context",
        options=options,
        task="continue work",
        session_id=session_id,
    )

    mock_tempfile.assert_called_once()
    called_dir = mock_tempfile.call_args[1].get("dir")
    assert called_dir == Path.home() / ".codeagent" / "agents"

    called_command = mock_run.call_args[0][0]
    assert "--agent" in called_command
    assert "planner" in called_command
    assert "--prompt-file" in called_command
    assert "resume" in called_command
    assert session_id in called_command
    assert "continue work" in called_command

    assert result.session_id == "262f0fea-eacb-4223-b842-b5b5097f94e8"
    assert result.exit_code == 0


@patch("subprocess.run")
@patch("tempfile.NamedTemporaryFile")
def test_run_review_agent_new_session(mock_tempfile, mock_run):
    mock_file = MagicMock()
    mock_file.name = "/Users/test/.codeagent/agents/fake-prompt.md"
    mock_tempfile.return_value.__enter__.return_value = mock_file

    mock_cp = MagicMock(spec=subprocess.CompletedProcess)
    mock_cp.returncode = 0
    mock_cp.stdout = "SESSION_ID: 12345678-1234-1234-1234-1234567890ab\nSuccess"
    mock_cp.stderr = ""
    mock_run.return_value = mock_cp

    options = AgentOptions(agent="planner")

    result = run_review_agent(
        prompt_file_content="context", options=options, task="start work"
    )

    mock_tempfile.assert_called_once()
    called_dir = mock_tempfile.call_args[1].get("dir")
    assert called_dir == Path.home() / ".codeagent" / "agents"

    called_command = mock_run.call_args[0][0]
    assert "resume" not in called_command
    assert "--agent" in called_command
    assert "planner" in called_command
    assert "--prompt-file" in called_command
    assert "start work" in called_command

    assert result.session_id == "12345678-1234-1234-1234-1234567890ab"
