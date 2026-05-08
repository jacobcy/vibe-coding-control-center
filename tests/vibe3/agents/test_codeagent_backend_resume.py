import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.models.review_runner import AgentOptions


@patch.object(CodeagentBackend, "_run_subprocess")
@patch("vibe3.utils.codeagent_helpers.tempfile.NamedTemporaryFile")
def test_codeagent_backend_resume_mode(mock_tempfile, mock_run):
    mock_file = MagicMock()
    mock_file.name = "/Users/test/.codeagent/agents/fake-prompt.md"
    mock_tempfile.return_value.__enter__.return_value = mock_file

    mock_cp = MagicMock(spec=subprocess.CompletedProcess)
    mock_cp.returncode = 0
    mock_cp.stdout = "SESSION_ID: 262f0fea-eacb-4223-b842-b5b5097f94e8\nSuccess"
    mock_cp.stderr = ""
    mock_run.return_value = (mock_cp, None)

    options = AgentOptions(agent="vibe-planner")
    session_id = "262f0fea-eacb-4223-b842-b5b5097f94e8"

    backend = CodeagentBackend()
    result = backend.run(
        prompt="context",
        options=options,
        task="continue work",
        session_id=session_id,
    )

    mock_tempfile.assert_called_once()
    called_dir = mock_tempfile.call_args[1].get("dir")
    assert called_dir == Path.home() / ".codeagent" / "agents"

    called_command = mock_run.call_args[0][0]
    assert "--backend" in called_command
    assert "--prompt-file" in called_command
    assert "resume" in called_command
    assert session_id in called_command
    assert "continue work" in called_command

    assert result.session_id == "262f0fea-eacb-4223-b842-b5b5097f94e8"
    assert result.exit_code == 0


@patch.object(CodeagentBackend, "_run_subprocess")
@patch("vibe3.utils.codeagent_helpers.tempfile.NamedTemporaryFile")
def test_codeagent_backend_new_session(mock_tempfile, mock_run):
    mock_file = MagicMock()
    mock_file.name = "/Users/test/.codeagent/agents/fake-prompt.md"
    mock_tempfile.return_value.__enter__.return_value = mock_file

    mock_cp = MagicMock(spec=subprocess.CompletedProcess)
    mock_cp.returncode = 0
    mock_cp.stdout = "SESSION_ID: 12345678-1234-1234-1234-1234567890ab\nSuccess"
    mock_cp.stderr = ""
    mock_run.return_value = (mock_cp, None)

    options = AgentOptions(agent="vibe-planner")

    backend = CodeagentBackend()
    result = backend.run(prompt="context", options=options, task="start work")

    mock_tempfile.assert_called_once()
    called_dir = mock_tempfile.call_args[1].get("dir")
    assert called_dir == Path.home() / ".codeagent" / "agents"

    called_command = mock_run.call_args[0][0]
    assert "resume" not in called_command
    assert "--backend" in called_command
    assert "--prompt-file" in called_command
    assert "start work" in called_command

    assert result.session_id == "12345678-1234-1234-1234-1234567890ab"
