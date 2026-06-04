"""Agent backend implementations.

Public API:
- ``CodeagentBackend`` — concrete backend implementation via codeagent-wrapper
- ``AsyncExecutionHandle`` — async execution handle returned by ``start_async_command``
- ``start_async_command`` — spawn async agent execution in tmux
- ``resolve_effective_agent_options`` — resolve agent options from env/config/defaults
- ``sync_models_json`` — sync models.json before execution
"""

from vibe3.agents.backends.async_launcher import (
    AsyncExecutionHandle,
    start_async_command,
)
from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.agents.backends.codeagent_config import sync_models_json
from vibe3.config import resolve_effective_agent_options

__all__ = [
    "CodeagentBackend",
    "AsyncExecutionHandle",
    "start_async_command",
    "resolve_effective_agent_options",
    "sync_models_json",
]
