"""Spec reference service for handling file and issue-based spec references."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from loguru import logger


@dataclass
class SpecRefInfo:
    """Parsed spec reference information."""

    raw: str
    kind: str
    issue_number: int | None = None
    issue_title: str | None = None
    issue_body: str | None = None
    file_path: str | None = None
    display: str | None = None


class SpecRefService:
    """Service for parsing and resolving spec references."""

    def parse_spec_ref(self, spec_ref: str) -> SpecRefInfo:
        """Parse a spec reference into structured info.

        Args:
            spec_ref: Spec reference (file path, issue number, or issue URL)

        Returns:
            SpecRefInfo with parsed details
        """
        issue_number = self._try_parse_issue_number(spec_ref)

        if issue_number is not None:
            return self._resolve_issue_spec(spec_ref, issue_number)

        return SpecRefInfo(
            raw=spec_ref, kind="file", file_path=spec_ref, display=spec_ref
        )

    def _try_parse_issue_number(self, spec_ref: str) -> int | None:
        stripped = spec_ref.strip()

        if stripped.isdigit():
            return int(stripped)

        if stripped.startswith("#"):
            remainder = stripped[1:]
            digits = []
            for ch in remainder:
                if ch.isdigit():
                    digits.append(ch)
                else:
                    break
            if digits:
                return int("".join(digits))

        if "github.com" in stripped and "/issues/" in stripped:
            parts = stripped.split("/issues/")
            if len(parts) == 2:
                num_part = parts[1].split("?")[0].split("#")[0]
                if num_part.isdigit():
                    return int(num_part)

        return None

    def _resolve_issue_spec(self, spec_ref: str, issue_number: int) -> SpecRefInfo:
        issue_data = self._fetch_issue_data(issue_number)

        if issue_data is None:
            return SpecRefInfo(
                raw=spec_ref,
                kind="issue",
                issue_number=issue_number,
                display=f"#{issue_number}",
            )

        title = issue_data.get("title", "")
        body = issue_data.get("body", "")
        display = f"#{issue_number}:{title}" if title else f"#{issue_number}"

        return SpecRefInfo(
            raw=spec_ref,
            kind="issue",
            issue_number=issue_number,
            issue_title=title,
            issue_body=body,
            display=display,
        )

    def _fetch_issue_data(self, issue_number: int) -> dict | None:
        try:
            result = subprocess.run(
                [
                    "gh",
                    "issue",
                    "view",
                    str(issue_number),
                    "--json",
                    "number,title,body",
                ],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            logger.bind(
                external="github",
                operation="fetch_issue_data",
                issue_number=issue_number,
            ).warning("GitHub CLI not found, fallback to issue number only")
            return None

        if result.returncode != 0:
            logger.bind(
                external="github",
                operation="fetch_issue_data",
                issue_number=issue_number,
                error=result.stderr,
            ).warning("Failed to fetch issue data")
            return None

        return cast(dict, json.loads(result.stdout))

    def get_spec_content_for_prompt(self, info: SpecRefInfo) -> str | None:
        """Get spec content suitable for prompt injection.

        Args:
            info: Parsed spec reference info

        Returns:
            Formatted spec content or None if unavailable
        """
        if info.kind == "issue":
            parts = []
            if info.issue_number:
                parts.append(f"Issue: #{info.issue_number}")
            if info.issue_title:
                parts.append(f"Title: {info.issue_title}")
            if info.issue_body:
                parts.append(f"\n{info.issue_body}")
            return "\n".join(parts) if parts else None

        if info.kind == "file" and info.file_path:
            path = Path(info.file_path)
            if path.exists():
                try:
                    return path.read_text(encoding="utf-8")
                except OSError:
                    return None
        return None

    def validate_spec_ref(self, spec_ref: str) -> tuple[bool, str]:
        """Validate a spec reference.

        Args:
            spec_ref: Spec reference to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        issue_number = self._try_parse_issue_number(spec_ref)
        if issue_number is not None:
            return True, ""

        path = Path(spec_ref)
        if path.exists() and path.is_file():
            return True, ""

        return False, f"Spec reference not found: {spec_ref}"

    def resolve_spec_ref(self, spec_ref: str) -> str:
        """Resolve a spec reference to its canonical form.

        Args:
            spec_ref: Spec reference to resolve

        Returns:
            Resolved spec reference
        """
        issue_number = self._try_parse_issue_number(spec_ref)
        if issue_number is not None:
            # If it's an issue number, return as issue URL or number
            return f"#{issue_number}"

        # Otherwise, return as file path
        return spec_ref

    def get_spec_display(
        self, spec_ref: str | None, issue_number: int | None = None
    ) -> str:
        """Get display string for spec reference.

        Args:
            spec_ref: Spec reference
            issue_number: Task issue number (for fallback when spec_ref is None)

        Returns:
            Display string
        """
        if spec_ref:
            info = self.parse_spec_ref(spec_ref)
            return info.display or spec_ref
        elif issue_number:
            # Fallback to issue URL when spec_ref is None
            return f"https://github.com/{self._get_repo_owner()}/{self._get_repo_name()}/issues/{issue_number}"
        return "None"

    def _get_repo_owner(self) -> str:
        """Get GitHub repo owner from git config."""
        try:
            result = subprocess.run(
                ["git", "config", "remote.origin.url"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            url = result.stdout.strip()

            # Handle SSH format: git@github.com:user/repo.git
            if url.startswith("git@github.com:"):
                repo_part = url.split(":")[-1]
                parts = repo_part.split("/")
                if len(parts) >= 2:
                    return parts[0]

            # Handle HTTPS format: https://github.com/user/repo.git
            if "github.com" in url:
                parts = url.split("/")
                if len(parts) >= 2:
                    return parts[-2].rstrip(".git")

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.bind(
                external="git",
                operation="get_repo_owner",
                error=str(e),
            ).warning("Failed to get repo owner from git config")
        return "owner"

    def _get_repo_name(self) -> str:
        """Get GitHub repo name from git config."""
        try:
            result = subprocess.run(
                ["git", "config", "remote.origin.url"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            url = result.stdout.strip()

            # Handle SSH format: git@github.com:user/repo.git
            if url.startswith("git@github.com:"):
                repo_part = url.split(":")[-1]
                parts = repo_part.split("/")
                if len(parts) >= 2:
                    return parts[-1].rstrip(".git")

            # Handle HTTPS format: https://github.com/user/repo.git
            if "github.com" in url:
                parts = url.split("/")
                if len(parts) >= 1:
                    return parts[-1].rstrip(".git")

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.bind(
                external="git",
                operation="get_repo_name",
                error=str(e),
            ).warning("Failed to get repo name from git config")
        return "repo"
