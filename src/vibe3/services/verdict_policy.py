"""Re-export shim — verdict policy has moved to vibe3.services.pr.verdict_policy."""

from vibe3.services.pr.verdict_policy import (
    ALL_VERDICTS,
    blocks_merge,
    passes_review,
    requires_audit_ref,
)

__all__ = ["ALL_VERDICTS", "blocks_merge", "passes_review", "requires_audit_ref"]
