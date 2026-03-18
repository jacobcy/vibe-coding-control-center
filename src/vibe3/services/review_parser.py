"""Review parser - 解析 Codex 输出的审核结果."""

import re

from loguru import logger
from pydantic import BaseModel

from vibe3.exceptions import VibeError


class ReviewParserError(VibeError):
    """解析失败."""

    def __init__(self, details: str) -> None:
        super().__init__(f"Review parse failed: {details}", recoverable=False)


class ReviewComment(BaseModel):
    """单条审核意见."""

    path: str
    line: int
    severity: str  # CRITICAL | MAJOR | MINOR
    body: str


class ParsedReview(BaseModel):
    """解析后的完整审核结果."""

    comments: list[ReviewComment]
    verdict: str  # PASS | MAJOR | BLOCK
    raw: str


# 匹配 "path/to/file.py:42 [MAJOR] description"
_COMMENT_RE = re.compile(
    r"^([^\s:]+):(\d+)\s+\[(CRITICAL|MAJOR|MINOR)\]\s+(.+)$",
    re.MULTILINE,
)
_VERDICT_RE = re.compile(r"VERDICT:\s*(PASS|MAJOR|BLOCK)", re.IGNORECASE)


def parse_codex_review(raw: str) -> ParsedReview:
    """解析 Codex 输出的审核结果.

    Args:
        raw: Codex 原始输出

    Returns:
        解析后的审核结果
    """
    log = logger.bind(domain="review_parser", action="parse_codex_review")
    log.info("Parsing Codex review output")

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


def convert_to_github_format(review: ParsedReview) -> list[dict[str, object]]:
    """将解析结果转换为 GitHub API review comments 格式.

    Args:
        review: 解析后的审核结果

    Returns:
        GitHub API 格式的 comment 列表
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
