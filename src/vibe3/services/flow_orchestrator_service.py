"""Flow orchestrator service - 编排逻辑下沉到Service层."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vibe3.services.orchestra_status_service import OrchestraStatusService

if TYPE_CHECKING:
    from vibe3.config.orchestra_config import OrchestraConfig
    from vibe3.services.orchestra_status_service import OrchestraSnapshot


class FlowOrchestratorService:
    """Flow编排服务，提供快照和编排能力.

    职责：
    - 获取运行时快照
    - 编排Flow状态（但不直接执行）
    - 提供查询接口

    这个类替代Execution层对Service层的反向依赖.
    """

    def __init__(self, config: OrchestraConfig) -> None:
        """Initialize with config."""
        self.config = config

    def snapshot(self) -> OrchestraSnapshot | None:
        """Get current orchestra snapshot."""
        return OrchestraStatusService.fetch_live_snapshot(self.config)
