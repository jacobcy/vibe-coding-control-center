"""GitHub Project item 数据模型。

本模块定义与 GitHub Projects v2 API 交互的数据模型。
这些模型表示 task 的 truth 字段，只能从远端读取，禁止写入本地存储。
"""

from pydantic import BaseModel


class ProjectItemData(BaseModel):
    """GitHub Project item 数据（truth 字段）。

    此对象表示从 GitHub Projects v2 读取的 task 真值。
    partial=True 表示响应缺少必要字段，数据不完整。
    """

    item_id: str
    node_id: str
    title: str | None = None
    body: str | None = None
    status: str | None = None
    priority: str | None = None
    assignees: list[str] = []
    partial: bool = False  # 响应缺少必要字段时为 True


class ProjectItemError(BaseModel):
    """GitHub Project API 错误。

    type 取值：
    - "network_error"：网络失败或 API 超时
    - "auth_error"：认证失败（GITHUB_TOKEN 未设置或无效）
    - "not_found"：item 不存在
    - "parse_error"：JSON 解析失败
    """

    type: str
    message: str
    raw_response: str | None = None  # parse_error 时附带原始响应摘要


class LinkError(BaseModel):
    """link_project_item 操作失败时返回的错误对象。

    type 取值：
    - "flow_not_found"：当前 branch 尚未创建 flow，不能独立绑定 bridge
    - "item_not_found"：提供的 project_item_id 在 GitHub Project 中不存在
    - "already_bound"：本地 bridge 已绑定不同的 project_item_id，需要 --force
    """

    type: str
    message: str
