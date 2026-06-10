"""Re-export shim for timeline parser.

The actual implementation has moved to
vibe3.services.shared.timeline.
"""

from vibe3.services.shared.timeline import parse_timeline_from_comments

__all__ = ["parse_timeline_from_comments"]
