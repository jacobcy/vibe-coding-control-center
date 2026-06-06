"""Orchestra instance information management.

Moved from runtime/ to utils/ to break services→runtime circular dependency.
Services layer imports these utilities without depending on the runtime layer.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class OrchestraInstanceInfo:
    """Serve instance information stored in global PID file."""

    pid: int
    cwd: Path
    port: int
    started_at: datetime

    def to_dict(self) -> dict:
        """Serialize instance info to JSON-compatible dict."""
        return {
            "pid": self.pid,
            "cwd": str(self.cwd),
            "port": self.port,
            "started_at": self.started_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> OrchestraInstanceInfo:
        """Deserialize instance info from JSON dict."""
        return cls(
            pid=data["pid"],
            cwd=Path(data["cwd"]),
            port=data["port"],
            started_at=datetime.fromisoformat(data["started_at"]),
        )


def read_instance_info(pid_file: Path) -> OrchestraInstanceInfo | None:
    """Read instance info from PID file.

    Returns None if:
    - File doesn't exist
    - File has invalid JSON
    - File has invalid format
    - File has non-object JSON (TypeError)
    """
    if not pid_file.exists():
        return None

    try:
        data = json.loads(pid_file.read_text())
        return OrchestraInstanceInfo.from_dict(data)
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None


def write_instance_info(pid_file: Path, info: OrchestraInstanceInfo) -> None:
    """Write instance info to PID file.

    Creates parent directories if needed.
    """
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(json.dumps(info.to_dict(), indent=2))


def validate_instance(info: OrchestraInstanceInfo) -> bool:
    """Validate that instance is still running and is an orchestra process.

    Returns False if:
    - Process is dead (os.kill raises ProcessLookupError)
    - Process is not orchestra (wrong command line)
    """
    try:
        os.kill(info.pid, 0)
    except (ProcessLookupError, PermissionError):
        return False

    # Check command line matches orchestra process
    import subprocess

    try:
        result = subprocess.run(
            ["ps", "-p", str(info.pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return False

        cmdline = result.stdout.strip().lower()
        return "vibe3" in cmdline and "serve" in cmdline
    except Exception:
        return False
