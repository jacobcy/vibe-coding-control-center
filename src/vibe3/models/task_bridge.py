"""Task Bridge 数据模型。

本模块定义本地 execution bridge 对象与合并视图对象。

字段分类：
- Bridge 字段：本地允许持久化的最小字段集合（identity + execution refs）
- Truth 字段：只能从 GitHub Project 实时读取，禁止写入本地存储
"""

from typing import Any, ClassVar, Literal

from pydantic import BaseModel


class TruthFieldWriteError(Exception):
    """尝试向本地存储写入 truth 字段时抛出。"""

    pass


class TaskBridgeModel(BaseModel):
    """本地 execution bridge 对象。

    bridge 字段：本地允许持久化的最小字段集合。
    truth 字段：只能从 GitHub Project 实时读取，标注为 ClassVar 防止实例化写入。
    """

    # --- Bridge 字段（本地持久化）---
    branch: str
    project_item_id: str | None = None  # 远端 item identity
    project_node_id: str | None = None  # 远端 node identity（GraphQL ID）
    task_issue_number: int | None = None  # 关联 issue 引用
    spec_ref: str | None = None
    plan_ref: str | None = None
    next_step: str | None = None
    blocked_by: str | None = None
    latest_actor: str | None = None

    # --- Truth 字段标记（ClassVar，不参与序列化/持久化）---
    # 这些字段只能从 GitHub Project 实时读取，禁止写入本地 SQLite
    TRUTH_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"title", "body", "status", "priority", "milestone", "assignees"}
    )

    @classmethod
    def assert_no_truth_write(cls, fields: dict[str, Any]) -> None:
        """检查写入字段中是否包含 truth 字段，若有则抛出异常。

        Args:
            fields: 准备写入本地存储的字段字典

        Raises:
            TruthFieldWriteError: 若 fields 中包含任何 truth 字段
        """
        violations = cls.TRUTH_FIELDS & set(fields.keys())
        if violations:
            raise TruthFieldWriteError(f"禁止向本地存储写入 truth 字段: {violations}")


class FieldSource(BaseModel):
    """带来源标注的字段值。"""

    value: Any
    source: Literal["local", "remote"]


class HydratedTaskView(BaseModel):
    """合并本地 bridge 字段与远端 truth 字段的视图对象。

    每个字段通过 FieldSource 标注数据来源（local / remote）。
    此对象为只读视图，不写入本地存储。
    """

    branch: str

    # --- Bridge 字段（来源：local）---
    project_item_id: FieldSource | None = None
    task_issue_number: FieldSource | None = None
    spec_ref: FieldSource | None = None
    next_step: FieldSource | None = None
    blocked_by: FieldSource | None = None

    # --- Truth 字段（来源：remote）---
    title: FieldSource | None = None
    body: FieldSource | None = None
    status: FieldSource | None = None
    priority: FieldSource | None = None
    assignees: FieldSource | None = None

    # --- 元信息 ---
    identity_drift: bool = False  # 本地与远端 identity 不一致时为 True
    offline_mode: bool = False  # 远端读取失败时为 True


class HydrateError(BaseModel):
    """hydrate 操作失败时返回的错误对象。"""

    type: str  # "no_remote_identity" | "binding_invalid"
    message: str
