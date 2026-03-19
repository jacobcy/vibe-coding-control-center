"""Metrics models - 指标相关的数据模型."""

from pydantic import BaseModel


class FileMetrics(BaseModel):
    """单文件指标."""

    path: str
    loc: int


class DeadFunctionInfo(BaseModel):
    """死函数信息."""

    name: str
    file: str
    line: int
    is_cli_candidate: bool  # True if in a file that might be CLI entry
