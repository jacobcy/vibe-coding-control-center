"""Central verdict policy for review and merge behavior."""

from typing import Final

from vibe3.models.verdict_types import VerdictValue

ALL_VERDICTS: Final[tuple[VerdictValue, ...]] = (
    "PASS",
    "MINOR",
    "MAJOR",
    "BLOCK",
    "REFUSE",
    "UNKNOWN",
)

PASSING_VERDICTS: Final[frozenset[VerdictValue]] = frozenset({"PASS", "MINOR"})
AUDIT_REQUIRED_VERDICTS: Final[frozenset[VerdictValue]] = frozenset(
    {"MINOR", "MAJOR", "BLOCK"}
)
MERGE_BLOCKING_VERDICTS: Final[frozenset[VerdictValue]] = frozenset(
    {"MAJOR", "BLOCK", "REFUSE", "UNKNOWN"}
)


def passes_review(verdict: VerdictValue) -> bool:
    return verdict in PASSING_VERDICTS


def requires_audit_ref(verdict: VerdictValue) -> bool:
    return verdict in AUDIT_REQUIRED_VERDICTS


def blocks_merge(verdict: VerdictValue) -> bool:
    return verdict in MERGE_BLOCKING_VERDICTS
