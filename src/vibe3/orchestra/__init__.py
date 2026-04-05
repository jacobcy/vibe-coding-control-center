"""Orchestra - GitHub assignee-driven agent orchestration.

Primary entry point: HeartbeatServer (vibe3 serve start)
  - AssigneeDispatchService: dispatches manager on issues/assigned webhook
  - CommentReplyService: acknowledges @vibe-manager-agent (or configured) mentions
  - Polling fallback every 15 min via on_tick()
"""

from vibe3.models.orchestration import IssueInfo
from vibe3.orchestra.config import OrchestraConfig

__all__ = [
    "OrchestraConfig",
    "IssueInfo",
]
