"""GitHub label operations — issue label CRUD via gh CLI."""

from __future__ import annotations

import json
import subprocess
from typing import Protocol

from loguru import logger

GH_LABEL_CMD_TIMEOUT_SECONDS = 30


class IssueLabelPort(Protocol):
    """Port for issue label read/write operations."""

    def get_issue_labels(self, issue_number: int) -> list[str] | None:
        """Return issue labels; None means labels cannot be fetched."""
        ...

    def add_issue_label(self, issue_number: int, label: str) -> bool:
        """Add one label to issue."""
        ...

    def remove_issue_label(self, issue_number: int, label: str) -> bool:
        """Remove one label from issue."""
        ...

    def ensure_label_exists(
        self,
        label: str,
        *,
        color: str,
        description: str,
    ) -> bool:
        """Ensure a repository label exists."""
        ...


class GhIssueLabelPort:
    """Default issue label port backed by `gh issue`."""

    def __init__(self, repo: str | None = None) -> None:
        self.repo = repo
        if self.repo is None:
            from vibe3.config.settings import VibeConfig

            config = VibeConfig.get_defaults()
            self.repo = getattr(getattr(config, "orchestra", None), "repo", None)

    def _build_cmd(self, base: list[str]) -> list[str]:
        cmd = list(base)
        if self.repo:
            cmd.extend(["--repo", self.repo])
        return cmd

    def _run_command(
        self,
        base: list[str],
        *,
        issue_number: int | None = None,
        label: str | None = None,
    ) -> subprocess.CompletedProcess[str] | None:
        cmd = self._build_cmd(base)
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=GH_LABEL_CMD_TIMEOUT_SECONDS,
            )
        except FileNotFoundError:
            logger.bind(
                external="github",
                issue_number=issue_number,
                label=label,
            ).warning("gh command not found")
            return None
        except subprocess.TimeoutExpired:
            logger.bind(
                external="github",
                issue_number=issue_number,
                label=label,
                timeout=GH_LABEL_CMD_TIMEOUT_SECONDS,
                cmd=" ".join(cmd),
            ).warning("gh label command timed out")
            return None

    def get_issue_labels(self, issue_number: int) -> list[str] | None:
        result = self._run_command(
            ["gh", "issue", "view", str(issue_number), "--json", "labels"],
            issue_number=issue_number,
        )
        if result is None:
            return None

        if result.returncode != 0:
            logger.bind(
                external="github",
                issue_number=issue_number,
                error=result.stderr,
            ).warning("Failed to fetch issue labels")
            return None

        data = json.loads(result.stdout)
        labels = data.get("labels", [])
        return [label.get("name", "") for label in labels if label.get("name")]

    def add_issue_label(self, issue_number: int, label: str) -> bool:
        result = self._run_command(
            ["gh", "issue", "edit", str(issue_number), "--add-label", label],
            issue_number=issue_number,
            label=label,
        )
        if result is None:
            return False
        return result.returncode == 0

    def remove_issue_label(self, issue_number: int, label: str) -> bool:
        result = self._run_command(
            ["gh", "issue", "edit", str(issue_number), "--remove-label", label],
            issue_number=issue_number,
            label=label,
        )
        if result is None:
            return False
        return result.returncode == 0

    def ensure_label_exists(
        self,
        label: str,
        *,
        color: str,
        description: str,
    ) -> bool:
        result = self._run_command(
            [
                "gh",
                "label",
                "create",
                label,
                "--color",
                color,
                "--description",
                description,
                "--force",
            ],
            label=label,
        )
        if result is None:
            return False
        return result.returncode == 0
