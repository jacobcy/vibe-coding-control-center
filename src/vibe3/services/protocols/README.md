# Services/Protocols

内部服务协议定义模块，使用 Protocol-based DI 打破循环依赖（ADR-0002）。

## 职责

- 定义 Flow 相关 Protocol 接口（解决 flow ↔ task 循环依赖）
- 定义 Task 相关 Protocol 接口（解决 task ↔ flow 循环依赖）
- 提供类型安全的依赖注入契约

## 文件列表

统计时间：2026-06-27

| 文件 | 行数 | 职责 |
|------|------|------|
| flow_protocols.py | 63 | FlowBootstrapProtocol - Flow 初始化协议 |
| flow_protocols_ext.py | 106 | FlowTimelineProtocol, FlowQueryProtocol - Flow 扩展协议 |
| task_protocols.py | 54 | TaskQueryProtocol - Task 查询协议 |

**总计**：3 文件，223 行

## 公共 API

从 `__init__.py` 导出的 4 个 Protocol 类：

- `FlowBootstrapProtocol` - Flow 初始化协议（解决 flow ↔ orchestra 循环依赖）
- `FlowTimelineProtocol` - Flow 时间线协议（解决 flow ↔ timeline 循环依赖）
- `FlowQueryProtocol` - Flow 查询协议（解决 flow ↔ query 循环依赖）
- `TaskQueryProtocol` - Task 查询协议（解决 task ↔ flow 循环依赖）

## 已知反模式

### TYPE_CHECKING 导入限制

当前实现仅支持 `TYPE_CHECKING` 导入，无 lazy import mechanism：

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.services.protocols.flow_protocols import FlowBootstrapProtocol
    ...
```

**影响**：运行时无法通过 `from vibe3.services.protocols import FlowBootstrapProtocol` 导入，必须从子模块直接导入：

```python
# 运行时导入方式
from vibe3.services.protocols.flow_protocols import FlowBootstrapProtocol
```

**原因**：Protocol 类主要用于类型注解，不需要运行时导入。未来如需运行时导入，需扩展 lazy import mechanism。

## 依赖关系

### 依赖

- `models` - IssueInfo, FlowStatusResponse 等领域模型
- `clients` - SQLiteClient（用于 Protocol 定义）
- `config` - TimelineCommentPolicy（配置常量）

### 被依赖

- `services/flow` - 实现 FlowBootstrapProtocol, FlowQueryProtocol
- `services/task` - 实现 TaskQueryProtocol
- `domain` - 事件处理器使用 Protocol 类型注解
- `orchestra` - 编排服务使用 Protocol 类型注解

## 设计原则

### Protocol-based DI

通过 Protocol 定义接口，打破模块间循环依赖：

```
Before: services/flow ↔ services/task (循环依赖)
After:  services/flow → services/protocols (Protocol定义)
        services/task → services/protocols (Protocol定义)
        services/flow → services/task (实现Protocol)
```

### 单一职责

每个 Protocol 解决一个循环依赖方向：

- `FlowBootstrapProtocol` → 解决 flow ↔ orchestra
- `FlowTimelineProtocol` → 解决 flow ↔ timeline
- `FlowQueryProtocol` → 解决 flow ↔ query
- `TaskQueryProtocol` → 解决 task ↔ flow

### ADR-0002

详见 `docs/adr/0002-protocol-based-di.md`：

- Protocol 优于抽象类（无运行时开销）
- 类型安全的依赖注入
- 测试时可替换实现（mock/stub）

## 架构说明

### 循环依赖解决方案

Protocol 层作为中间层，提供接口定义：

```
services/protocols/
  ├── flow_protocols.py      ← 定义 FlowBootstrapProtocol
  ├── flow_protocols_ext.py  ← 定义 FlowTimelineProtocol, FlowQueryProtocol
  └── task_protocols.py      ← 定义 TaskQueryProtocol

services/flow/
  ├── bootstrap.py           ← 实现 FlowBootstrapProtocol
  └── query.py               ← 实现 FlowQueryProtocol

services/task/
  ├── service.py             ← 实现 TaskQueryProtocol
```

### 依赖注入模式

```python
# 在 services/flow/bootstrap.py 中实现 Protocol
class FlowBootstrapService:
    def __init__(self, task_query: TaskQueryProtocol) -> None:
        self._task_query = task_query  # 注入 Protocol
```

### 测试替换

```python
# 测试时提供 mock 实现
class MockTaskQueryProtocol:
    def get_task_issue(self, branch: str) -> IssueInfo | None:
        return None

service = FlowBootstrapService(task_query=MockTaskQueryProtocol())
```