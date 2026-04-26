"""Artifact parsing and detail building logic."""

import re
from pathlib import Path


class ArtifactParser:
    """Parser for handoff artifacts."""

    _RESERVED_REF_KEYS = {
        "ref",
        "backend",
        "model",
        "session_id",
        "modified_files",
        "modified_count",
        "verdict",
        "comment_count",  # Special handling in detail building
    }

    _AGENT_PROMPT_BLOCK_RE = re.compile(
        r"<agent-prompt>.*?</agent-prompt>\s*", re.DOTALL
    )

    @classmethod
    def sanitize_handoff_content(cls, content: str) -> str:
        """Strip prompt-provenance blocks from persisted shared artifacts."""
        return cls._AGENT_PROMPT_BLOCK_RE.sub("", content)

    @classmethod
    def parse_modified_files(cls, content: str) -> list[str]:
        """Extract modified files from a run artifact body."""
        match = re.search(
            r"### Modified Files\s*([\s\S]*?)(?:\n###|\Z)",
            content,
            re.IGNORECASE,
        )
        if not match:
            return []

        files_section = match.group(1)
        file_matches = re.findall(
            r"^-\s*([^:\]\n]+)(?::|\])?",
            files_section,
            re.MULTILINE,
        )
        return [path.strip() for path in file_matches if path.strip()]

    @classmethod
    def parse_review_verdict(cls, content: str) -> str | None:
        """Extract verdict token from review content."""
        match = re.search(r"VERDICT:\s*(PASS|MAJOR|BLOCK)", content, re.IGNORECASE)
        return match.group(1).upper() if match else None

    @classmethod
    def build_artifact_detail(
        cls,
        kind: str,
        content: str,
        artifact_file: Path,
        metadata: dict[str, str] | None = None,
    ) -> tuple[str, dict[str, str]]:
        """Build event detail and refs from artifact content."""
        refs: dict[str, str] = {}
        detail_parts = [f"{kind.capitalize()} completed: {artifact_file.name}"]

        metadata = metadata or {}

        if kind == "run":
            modified_files = cls.parse_modified_files(content)
            if modified_files:
                refs["modified_files"] = ",".join(modified_files)
                refs["modified_count"] = str(len(modified_files))
                detail_parts.append(f"Modified {len(modified_files)} files:")
                for file_path in modified_files[:3]:
                    detail_parts.append(f"  - {file_path}")
                if len(modified_files) > 3:
                    detail_parts.append(f"  ... and {len(modified_files) - 3} more")

        if kind == "review":
            verdict = cls.parse_review_verdict(content) or metadata.get("verdict")
            if verdict:
                refs["verdict"] = verdict
                comment_count = metadata.get("comment_count")
                if comment_count:
                    detail_parts.append(f"Verdict: {verdict}, {comment_count} comments")
                else:
                    detail_parts.append(f"Verdict: {verdict}")

        for key, value in metadata.items():
            if key != "comment_count" and key not in cls._RESERVED_REF_KEYS:
                refs[key] = value

        return "\n".join(detail_parts), refs
