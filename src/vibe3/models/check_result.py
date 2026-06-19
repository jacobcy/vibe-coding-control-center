"""Check result data model."""

from dataclasses import dataclass, field


@dataclass
class CheckResult:
    """Result of consistency check for a single branch."""

    is_valid: bool
    issues: list[str]
    warnings: list[str] = field(default_factory=list)
    branch: str = ""
