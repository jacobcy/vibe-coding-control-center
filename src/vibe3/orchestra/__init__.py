"""Orchestra - GitHub label-driven agent orchestration."""

from vibe3.orchestra.config import MasterAgentConfig, OrchestraConfig
from vibe3.orchestra.dispatcher import Dispatcher
from vibe3.orchestra.master import TriageDecision, run_master_agent
from vibe3.orchestra.models import IssueInfo, Trigger
from vibe3.orchestra.poller import Poller
from vibe3.orchestra.router import Router

__all__ = [
    "MasterAgentConfig",
    "OrchestraConfig",
    "Dispatcher",
    "IssueInfo",
    "Poller",
    "Router",
    "TriageDecision",
    "Trigger",
    "run_master_agent",
]
