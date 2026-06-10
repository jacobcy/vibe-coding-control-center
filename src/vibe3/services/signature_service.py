"""Re-export shim for signature service.

The actual implementation has moved to
vibe3.services.shared.signatures.
"""

from vibe3.services.shared.signatures import (
    AI_ASSISTANT_ACTORS,
    WORKFLOW_ACTOR,
    SignatureService,
)

__all__ = ["WORKFLOW_ACTOR", "AI_ASSISTANT_ACTORS", "SignatureService"]
