# Infrastructure Guide

> **Updated**: 2026-04-09 - 基础设施统一使用指南

本文档说明如何使用 Vibe 3.0 的核心基础设施服务。

## 概述

Vibe 3.0 提供了以下核心基础设施服务：

- **ExecutionRolePolicyService** - 统一的执行配置解析
- **CapacityService** - 统一的容量控制
- **ExecutionLifecycleService** - 统一的生命周期管理
- **BackendProtocol** - Protocol-based dependency injection

这些服务解决了以下问题：

1. **配置分散**：不同执行路径（manager/plan/run/review）的配置解析逻辑重复
2. **容量冲突**：StateLabelDispatchService 和 ManagerExecutor 之间的双层节流问题
3. **生命周期记录不一致**：不同角色的生命周期事件记录方式不统一
4. **依赖耦合**：Backend 实现硬编码，难以测试和扩展

## ExecutionRolePolicyService

### 用途

统一解析各执行角色（manager/planner/executor/reviewer/supervisor/governance）的配置，包括：

- Backend 选择（claude/openai）
- Prompt template 解析
- Session 策略（tmux/async/inline）
- Agent preset 配置

### API

```python
from vibe3.agents.execution_role_policy import ExecutionRolePolicyService
from vibe3.models.orchestra_config import OrchestraConfig

# 初始化
config = OrchestraConfig.from_settings()
policy_service = ExecutionRolePolicyService(config)

# 解析 backend
backend = policy_service.resolve_backend("planner")  # "claude" 或 "openai"

# 解析 prompt contract
prompt_contract = policy_service.resolve_prompt_contract("planner")
# 返回 PromptContract(template="orchestra.plan", supervisor_file="...")

# 解析 session 策略
session_strategy = policy_service.resolve_session_strategy("planner")
# 返回 SessionStrategy(mode="tmux", timeout=1800)

# 解析 agent options（完整配置）
agent_options = policy_service.resolve_agent_options("planner")
# 返回 AgentOptions(agent=..., backend=..., model=..., timeout_seconds=...)
```

### 配置映射

ExecutionRolePolicyService 使用以下配置映射：

| Role | Config Section |
|------|----------------|
| manager | `assignee_dispatch` |
| planner | `assignee_dispatch` |
| executor | `assignee_dispatch` |
| reviewer | `assignee_dispatch` |
| supervisor | `supervisor_handoff` |
| governance | `governance` |

### 配置示例

```yaml
# settings.yaml
orchestra:
  assignee_dispatch:
    agent: null  # 或 agent preset 名称
    backend: "claude"
    model: null  # 可选的 model override
    timeout_seconds: 1800
    prompt_template: "orchestra.assignee_dispatch.manager"
    supervisor_file: "supervisor/manager.md"
    include_supervisor_content: true
```

### 使用场景

**在 StateLabelDispatchService 中使用**：

```python
class StateLabelDispatchService:
    def __init__(self, config: OrchestraConfig):
        self._policy_service = ExecutionRolePolicyService(config)

    def _resolve_agent_options(self) -> AgentOptions:
        role = _TRIGGER_TO_REGISTRY_ROLE.get(self.trigger_name, self.trigger_name)
        return self._policy_service.resolve_agent_options(role)
```

**在 CLI 命令中使用**：

```python
# commands/run.py
def run_command():
    config = OrchestraConfig.from_settings()
    policy_service = ExecutionRolePolicyService(config)

    agent_options = policy_service.resolve_agent_options("executor")
    backend = policy_service.resolve_backend("executor")
    prompt_contract = policy_service.resolve_prompt_contract("executor")

    # 使用解析的配置执行 agent
    ...
```

## CapacityService

### 用途

统一管理所有执行角色的容量控制，解决双层节流问题。

**双层节流问题**：

- StateLabelDispatchService 跟踪 `in_flight_dispatches`
- ManagerExecutor 也跟踪 `in_flight_dispatches`
- 导致容量计算冲突，可能出现超额分发

**解决方案**：

CapacityService 提供单一的容量检查点，结合 live session count 和 in-flight dispatch tracking。

### API

```python
from vibe3.execution.capacity_service import CapacityService
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.agents.backends.codeagent import CodeagentBackend

# 初始化
store = SQLiteClient()
backend = CodeagentBackend()
capacity_service = CapacityService(config, store, backend)

# 检查容量
if capacity_service.can_dispatch("manager", issue_number):
    # 标记为 in-flight
    capacity_service.mark_in_flight("manager", issue_number)

    # 执行分发逻辑...

    # 完成后清理（可选，CapacityService 会自动清理）
    capacity_service.prune_in_flight("manager", {issue_number})

# 获取容量状态
status = capacity_service.get_capacity_status("manager")
# 返回: {
#     "active_count": 2,
#     "in_flight_count": 1,
#     "max_capacity": 3,
#     "remaining": 0
# }
```

### 容量公式

```
remaining = max_capacity(role) - active_count(role) - in_flight_count(role)
```

其中：
- `active_count`：当前正在运行的 live worker sessions 数量
- `in_flight_count`：正在分发中但尚未启动的目标数量
- `max_capacity`：该角色的最大并发数

### 配置

```yaml
# settings.yaml
orchestra:
  max_concurrent_flows: 3  # manager 的最大并发数
```

其他角色（planner/executor/reviewer）默认使用相同的 `max_concurrent_flows`。

### 使用场景

**在 StateLabelDispatchService 中使用**：

```python
async def on_tick(self):
    # ... 获取 ready issues ...

    # 应用容量控制
    capacity_service = CapacityService(self.config, self._store, self._backend)
    role = _TRIGGER_TO_REGISTRY_ROLE.get(self.trigger_name, self.trigger_name)

    to_dispatch = []
    for issue in ready:
        if capacity_service.can_dispatch(role, issue.number):
            capacity_service.mark_in_flight(role, issue.number)
            to_dispatch.append(issue)

    # 分发 issues
    for issue in to_dispatch:
        await self._dispatch_issue(issue)
```

## ExecutionLifecycleService

### 用途

统一记录所有执行角色的生命周期事件（started/completed/failed）。

### API

```python
from vibe3.agents.execution_lifecycle import persist_execution_lifecycle_event

# 记录 started 事件
persist_execution_lifecycle_event(
    store=store,
    branch="task/issue-42",
    role="planner",
    event="started",
    actor="claude-sonnet-4.6",
    detail="Started plan for issue #42",
    refs={"issue": "42", "tmux_session": "vibe3-plan-42"},
    extra_state_updates={"latest_actor": "claude-sonnet-4.6"}
)

# 记录 completed 事件
persist_execution_lifecycle_event(
    store=store,
    branch="task/issue-42",
    role="planner",
    event="completed",
    actor="claude-sonnet-4.6",
    detail="Plan completed for issue #42"
)

# 记录 failed 事件
persist_execution_lifecycle_event(
    store=store,
    branch="task/issue-42",
    role="planner",
    event="failed",
    actor="claude-sonnet-4.6",
    detail="Plan failed: timeout exceeded"
)
```

### 事件类型

- `started`：执行开始
- `completed`：执行成功完成
- `failed`：执行失败

### 状态更新

ExecutionLifecycleService 会自动更新以下 flow state 字段：

| Role | Event | State Updates |
|------|-------|---------------|
| planner | started | `planner_status=running`, `planner_session_id=...` |
| planner | completed | `planner_status=completed` |
| planner | failed | `planner_status=failed` |
| executor | started | `executor_status=running`, `executor_session_id=...` |
| executor | completed | `executor_status=completed` |
| executor | failed | `executor_status=failed` |
| reviewer | started | `reviewer_status=running`, `reviewer_session_id=...` |
| reviewer | completed | `reviewer_status=completed` |
| reviewer | failed | `reviewer_status=failed` |

## BackendProtocol

### 用途

定义 Backend 接口，支持 dependency injection，便于测试和扩展。

### Protocol 定义

```python
from vibe3.clients.protocols import BackendProtocol

class BackendProtocol(Protocol):
    def start_async_command(
        self,
        command: list[str],
        *,
        execution_name: str,
        cwd: Path,
        env: dict[str, str] | None = None,
    ) -> AsyncCommandHandle:
        """Start an async command in a tmux session."""
        ...
```

### 使用场景

**在测试中注入 Mock Backend**：

```python
from unittest.mock import Mock
from vibe3.clients.protocols import BackendProtocol

def test_dispatch_with_mock_backend():
    mock_backend = Mock(spec=BackendProtocol)
    mock_backend.start_async_command.return_value = AsyncCommandHandle(
        tmux_session="test-session",
        log_path=Path("/tmp/test.log")
    )

    service = StateLabelDispatchService(
        config=config,
        backend=mock_backend
    )
    # 测试逻辑...
```

**在生产中使用真实 Backend**：

```python
from vibe3.agents.backends.codeagent import CodeagentBackend

backend = CodeagentBackend()
service = StateLabelDispatchService(config=config, backend=backend)
```

## 集成示例

### StateLabelDispatchService 集成

```python
class StateLabelDispatchService(ServiceBase):
    def __init__(self, config: OrchestraConfig):
        # 1. 初始化 ExecutionRolePolicyService
        self._policy_service = ExecutionRolePolicyService(config)

        # 2. 初始化 Backend
        self._backend = CodeagentBackend()

        # 3. 其他初始化
        self._store = SQLiteClient()
        self._registry = SessionRegistryService(self._store, self._backend)

    async def on_tick(self):
        # 获取 ready issues
        ready = self._select_ready_issues(raw_issues)

        # 使用 CapacityService 控制容量
        capacity_service = CapacityService(
            self.config, self._store, self._backend
        )
        role = _TRIGGER_TO_REGISTRY_ROLE.get(self.trigger_name, self.trigger_name)

        to_dispatch = []
        for issue in ready:
            if capacity_service.can_dispatch(role, issue.number):
                capacity_service.mark_in_flight(role, issue.number)
                to_dispatch.append(issue)

        # 分发 issues
        for issue in to_dispatch:
            await self._dispatch_issue(issue)

    def _dispatch_issue(self, issue: IssueInfo):
        # 使用 ExecutionRolePolicyService 解析配置
        agent_options = self._policy_service.resolve_agent_options(
            _TRIGGER_TO_REGISTRY_ROLE[self.trigger_name]
        )

        # 记录生命周期事件
        persist_execution_lifecycle_event(
            self._store,
            branch,
            role,
            "started",
            actor,
            detail=f"Started {self.trigger_name} for issue #{issue.number}",
            refs=refs,
        )

        # 使用 Backend 执行命令
        handle = self._backend.start_async_command(
            command,
            execution_name=f"vibe3-{self.trigger_name}-issue-{issue.number}",
            cwd=cwd,
        )
```

## 最佳实践

### 1. 统一配置源

- ✅ 使用 `ExecutionRolePolicyService` 解析配置
- ❌ 避免在不同地方重复实现配置解析逻辑

### 2. 单一容量检查点

- ✅ 使用 `CapacityService` 统一管理容量
- ❌ 避免在多个地方维护 `in_flight_dispatches`

### 3. 一致的生命周期记录

- ✅ 使用 `ExecutionLifecycleService` 记录事件
- ❌ 避免手动更新 `planner_status` 等字段

### 4. 依赖注入

- ✅ 通过构造函数注入 Backend
- ❌ 避免在服务内部硬编码 Backend 实例

## 参考

- **[docs/standards/glossary.md](../../standards/glossary.md)** - 术语表
- **[docs/standards/agent-workflow-standard.md](../../standards/agent-workflow-standard.md)** - Agent 工作流规范
- **[src/vibe3/agents/execution_role_policy.py](../../../src/vibe3/agents/execution_role_policy.py)** - 源代码
- **[src/vibe3/services/capacity_service.py](../../../src/vibe3/services/capacity_service.py)** - 源代码
- **[src/vibe3/agents/execution_lifecycle.py](../../../src/vibe3/agents/execution_lifecycle.py)** - 源代码

---

**维护者**: Vibe Team
**最后更新**: 2026-04-09