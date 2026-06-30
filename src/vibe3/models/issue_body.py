"""Issue body managed section models."""

from typing import Literal

from pydantic import BaseModel, Field


class FlowStateProjection(BaseModel):
    """托管 flow-state section 数据结构.

    用于在 GitHub issue body 中投影当前协作状态。
    """

    state: Literal["active", "blocked", "done", "aborted"] = Field(
        default="active",
        description="Flow status inferred from labels",
    )
    blocked_by: list[int] = Field(
        default_factory=list,
        description="Dependency issue numbers",
    )
    blocked_reason: str | None = Field(
        default=None,
        description="Human-readable block reason",
    )

    def is_empty(self) -> bool:
        """Check if projection has any meaningful data."""
        return (
            self.state == "active" and not self.blocked_by and not self.blocked_reason
        )
