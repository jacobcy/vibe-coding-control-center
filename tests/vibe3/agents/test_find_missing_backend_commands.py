"""Tests for backend command availability checking."""

import json
from pathlib import Path
from unittest.mock import patch

from vibe3.agents.backends.codeagent_config import find_missing_backend_commands


def test_find_missing_backend_commands_only_reports_configured_backends(
    tmp_path: Path,
) -> None:
    repo_models = tmp_path / "models.json"
    repo_models.write_text(
        json.dumps(
            {
                "default_backend": "opencode",
                "agents": {
                    "vibe-manager": {"backend": "gemini"},
                    "vibe-reviewer": {"backend": "claude"},
                },
            }
        )
    )

    def fake_which(command: str, path: str | None = None) -> str | None:
        return None if command in {"opencode", "gemini"} else f"/usr/bin/{command}"

    with patch("vibe3.agents.backends.codeagent_config.shutil.which", fake_which):
        missing = find_missing_backend_commands(repo_models)

    assert missing == {"gemini": "gemini", "opencode": "opencode"}
