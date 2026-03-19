"""Review parser - Parse output from codeagent-wrapper.

This module parses the output from codeagent-wrapper review agent.
It is designed to be robust against wrapper output noise such as:
- Session/log preamble
- Markdown headers
- Extra newlines
- Timestamp logs

Output format expected:
    path/to/file.py:42 [MAJOR] concise issue description
    VERDICT: PASS | MAJOR | BLOCK
"""

import re

from loguru import logger
from pydantic import BaseModel

from vibe3.exceptions import VibeError


class ReviewParserError(VibeError):
    """Parse failed."""

    def __init__(self, details: str) -> None:
        super().__init__(f"Review parse failed: {details}", recoverable=False)


class ReviewComment(BaseModel):
    """Single review comment."""

    path: str
    line: int
    severity: str  # CRITICAL | MAJOR | MINOR
    body: str


class ParsedReview(BaseModel):
    """Parsed review result."""

    comments: list[ReviewComment]
    verdict: str  # PASS | MAJOR | BLOCK
    raw: str


# Match "path/to/file.py:42 [MAJOR] description"
_COMMENT_RE = re.compile(
    r"^([^\s:]+):(\d+)\s+\[(CRITICAL|MAJOR|MINOR)\]\s+(.+)$",
    re.MULTILINE,
)
_VERDICT_RE = re.compile(r"VERDICT:\s*(PASS|MAJOR|BLOCK)", re.IGNORECASE)


def parse_codex_review(raw: str) -> ParsedReview:
    """Parse codeagent-wrapper review output.

    This function is robust against output noise and will:
    - Ignore preamble/log lines from wrapper
    - Extract findings matching the expected format
    - Default to PASS verdict if none found

    Args:
        raw: Raw output from codeagent-wrapper

    Returns:
        Parsed review result
    """
    log = logger.bind(domain="review_parser", action="parse_codex_review")
    log.info("Parsing review output")

    comments = [
        ReviewComment(
            path=m.group(1), line=int(m.group(2)), severity=m.group(3), body=m.group(4)
        )
        for m in _COMMENT_RE.finditer(raw)
    ]

    verdict_match = _VERDICT_RE.search(raw)
    verdict = verdict_match.group(1).upper() if verdict_match else "PASS"

    skipped = sum(
        1
        for line in raw.splitlines()
        if line.strip() and not _COMMENT_RE.match(line) and not _VERDICT_RE.search(line)
    )
    if skipped > 0:
        log.bind(
            domain="review_parser", action="parse_codex_review", skipped_lines=skipped
        ).debug("Skipped non-matching lines")

    log.bind(comments=len(comments), verdict=verdict).success("Review parsed")
    return ParsedReview(comments=comments, verdict=verdict, raw=raw)


# Alias for clarity - same function, more descriptive name
parse_review_output = parse_codex_review


def convert_to_github_format(review: ParsedReview) -> list[dict[str, object]]:
    """Convert parsed review to GitHub API review comments format.

    Args:
        review: Parsed review result

    Returns:
        List of GitHub API format comments
    """
    return [
        {
            "path": c.path,
            "line": c.line,
            "body": f"**[{c.severity}]** {c.body}",
            "side": "RIGHT",
        }
        for c in review.comments
    ]
