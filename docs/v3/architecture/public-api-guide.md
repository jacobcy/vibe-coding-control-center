# V3 公共接口使用指南

本文档旨在为 V3 系统的开发者提供公共接口的使用规范和最佳实践。V3 采用了分层架构，各层通过明确定义的接口进行交互。

## 1. 核心接口示例

### Execution 层 (执行层)

`ExecutionCoordinator` 是启动和跟踪角色执行的统一协调器。`CapacityService` 用于全局并发控制。

> 💡 更多底层基础设施服务（如 `ExecutionRolePolicyService`）的详细用法，请参考 [Infrastructure Guide](./infrastructure-guide.md)。

```python
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.execution.capacity_service import CapacityService
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.clients.sqlite_client import SQLiteClient

# 初始化建议
# 推荐从配置加载函数获取 config
from vibe3.config.orchestra_settings import load_orchestra_config
config = load_orchestra_config()
store = SQLiteClient()

# CapacityService 用于控制并发
capacity = CapacityService(config, store, backend)

# ExecutionCoordinator 统一管理执行生命周期
coordinator = ExecutionCoordinator(config, store, capacity=capacity)
```

### Agents 层 (智能体层)

`CodeagentBackend` 是基于 `codeagent-wrapper` 的执行后端，负责与底层 AI Agent 交互。

```python
from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.models.review_runner import AgentOptions

backend = CodeagentBackend()

# 示例：准备 prompt 并启动
# 通常在 Role 的实现中使用，不建议在业务逻辑中直接调用
from vibe3.utils.codeagent_helpers import prepare_prompt_file
prompt_path = prepare_prompt_file("Fix this bug", "task-123")
options = AgentOptions(agent="vibe-reviewer")
# backend.run(...) 或 backend.spawn_async(...)
```

### Roles 层 (角色层)

角色通过 `TriggerableRoleDefinition` 定义，并在 `registry.py` 中注册。

```python
from vibe3.roles import TriggerableRoleDefinition
from vibe3.models.orchestration import IssueState

# 角色定义示例
MY_ROLE = TriggerableRoleDefinition(
    name="my-role",
    registry_role="executor",     # 对应 backend 类型
    worktree="permanent",        # 工作区策略: none, temporary, permanent
    trigger_name="custom",       # 触发标识
    trigger_state=IssueState.CLAIMED, # 触发状态
)
```

### Services 层 (服务层)

`FlowService` 和 `TaskService` 是管理流程状态、Issue 链接和 PR 关联的核心服务。

```python
from vibe3.services.flow import FlowService
from vibe3.services.task import TaskService

# 初始化
flow_service = FlowService()
task_service = TaskService()
```

# 示例：绑定 Spec 到当前 Flow
# spec_ref 可以是 issue 编号或文件路径
flow_service.bind_spec(branch="dev/issue-1", spec_ref="1273")

# 示例：链接相关 issue
# role 可以是 'task', 'related', 'dependency'
task_service.link_issue(branch="dev/issue-1", issue_number=1277, role="related")
```

## 2. 最佳实践

### 如何正确导入模块

V3 倾向于显式导入以保持模块边界清晰，减少 `__init__.py` 带来的副作用。

- **优先从具体模块导入**（适用于 `execution`、`agents`、`services` 等层）：
  - ✅ `from vibe3.execution.coordinator import ExecutionCoordinator`
  - ❌ `from vibe3.execution import ExecutionCoordinator`
- **Roles 层支持统一入口导入**：
  - ✅ `from vibe3.roles import MANAGER_ROLE, TriggerableRoleDefinition`
  - ✅ `from vibe3.roles.manager import MANAGER_ROLE`（仍兼容）
- **避免相对导入**：在 `src/vibe3` 内部也应使用绝对路径导入。

### 何时使用依赖注入

为了提高可测试性和解耦，V3 服务应支持依赖注入。

- **构造函数注入**：
```python
def __init__(
    self, 
    store: SQLiteClient | None = None,
    github_client: GitHubClientProtocol | None = None
) -> None:
    self.store = store or SQLiteClient()
    self.github_client = github_client or GitHubClient()
```

### 如何避免循环依赖

1. **Type Checking 块**：仅用于类型提示的导入应放在 `if TYPE_CHECKING:` 中。
2. **延迟导入**：在方法内部进行 `import`，通常用于打破具体的实现依赖。
3. **接口隔离**：在 `vibe3.clients.protocols` 中定义 Protocol，让高层依赖协议而非具体实现。

## 3. 反模式示例

### 错误的导入方式

- **禁止导入内部实现**：不要从 `vibe3.X.internal` 或以 `_` 开头的模块导入。
- **避免循环依赖的硬编码**：不要在顶层作用域相互导入对方的类。

### 违反分层架构的调用

- **禁止底层向上层调用**：`execution` 或 `agents` 层不应了解 `services` 层的存在。
- **禁止跳过 Coordinator**：所有的 Role 执行都应通过 `ExecutionCoordinator` 或对应的 Runner Service，严禁业务代码直接调用 `subprocess` 或 `tmux` 命令。

---
*Created as part of Issue #1273 governance task.*
