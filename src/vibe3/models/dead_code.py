"""Dead code detection models."""

from typing import Literal

from pydantic import BaseModel, Field


class DeadCodeFinding(BaseModel):
    """Single dead code finding."""

    symbol: str
    file: str
    line: int
    loc: int
    confidence: Literal["high", "medium", "low"]
    category: Literal[
        "unused_function",
        "unused_class",
        "unused_method",
        "potential_dynamic",
    ]
    reason: str  # Why it's classified as dead code


class DeadCodeReport(BaseModel):
    """Dead code scan report."""

    total_symbols: int = 0
    dead_code_count: int = 0
    findings: list[DeadCodeFinding] = Field(default_factory=list)
    excluded: list[str] = Field(
        default_factory=list
    )  # Excluded symbols (CLI commands, etc.)
    excluded_count: int = 0
