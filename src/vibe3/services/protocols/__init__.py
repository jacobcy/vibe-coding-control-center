"""Services protocols namespace."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.services.protocols.flow_protocols import FlowBootstrapProtocol
    from vibe3.services.protocols.flow_protocols_ext import (
        FlowQueryProtocol,
        FlowTimelineProtocol,
    )
    from vibe3.services.protocols.task_protocols import TaskQueryProtocol

__all__: list[str] = [
    "FlowBootstrapProtocol",
    "FlowQueryProtocol",
    "FlowTimelineProtocol",
    "TaskQueryProtocol",
]
