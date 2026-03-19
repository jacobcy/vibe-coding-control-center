"""改动源抽象模型 - 统一 PR/Commit/Branch/Uncommitted 四种改动场景."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ChangeSourceType(str, Enum):
    """改动源类型."""

    PR = "pr"
    COMMIT = "commit"
    BRANCH = "branch"
    UNCOMMITTED = "uncommitted"


class PRSource(BaseModel):
    """PR 改动源."""

    type: Literal[ChangeSourceType.PR] = ChangeSourceType.PR
    pr_number: int = Field(..., description="PR 编号")


class CommitSource(BaseModel):
    """Commit 改动源."""

    type: Literal[ChangeSourceType.COMMIT] = ChangeSourceType.COMMIT
    sha: str = Field(..., description="Commit SHA")


class BranchSource(BaseModel):
    """Branch 改动源（与 base 分支对比）."""

    type: Literal[ChangeSourceType.BRANCH] = ChangeSourceType.BRANCH
    branch: str = Field(..., description="目标分支")
    base: str = Field(default="main", description="基准分支")


class UncommittedSource(BaseModel):
    """未提交改动源（工作区 + 暂存区）."""

    type: Literal[ChangeSourceType.UNCOMMITTED] = ChangeSourceType.UNCOMMITTED


# 联合类型，供所有接受改动源的函数使用
ChangeSource = PRSource | CommitSource | BranchSource | UncommittedSource
