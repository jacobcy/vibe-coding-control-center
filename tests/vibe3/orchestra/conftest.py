"""Shared fixtures for orchestra tests."""

from __future__ import annotations


class CompletedProcess:
    """Minimal mock for subprocess.CompletedProcess."""

    def __init__(
        self,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
