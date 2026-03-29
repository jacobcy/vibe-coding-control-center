"""Orchestra - GitHub assignee-driven agent orchestration.

Primary entry point: HeartbeatServer (vibe3 serve start)
  - AssigneeDispatchService: dispatches manager on issues/assigned webhook
  - CommentReplyService: acknowledges @vibe-manager-agent (or configured) mentions
  - Polling fallback every 15 min via on_tick()
"""

from vibe3.orchestra.config import MasterAgentConfig, OrchestraConfig
from vibe3.orchestra.dispatcher import Dispatcher
from vibe3.orchestra.master import TriageDecision, run_master_agent
from vibe3.orchestra.models import IssueInfo

__all__ = [
    "MasterAgentConfig",
    "OrchestraConfig",
    "Dispatcher",
    "IssueInfo",
    "TriageDecision",
    "run_master_agent",
]
