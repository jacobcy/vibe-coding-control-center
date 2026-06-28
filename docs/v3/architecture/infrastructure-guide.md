# Infrastructure Guide

> **Updated**: 2026-04-09 - 基础设施统一使用指南

本文档说明如何使用 Vibe 3.0 的核心基础设施服务。

## Architecture Tiers

Vibe 3.0 遵循 3-tier 架构模型，详见 [CLAUDE.md](../../../CLAUDE.md) §架构分层与 [docs/ARCHITECTURE_GUIDE.md](../../../docs/ARCHITECTURE_GUIDE.md)。

### Tier 3: Cognitive / Governance Layer

- **职责**：决策与治理层。负责全局策略、规则、Supervisor 治理。
- **核心命令**：`serve`, `scan`, `check`, `mcp`
- **执行层级**：L0/L1 (无 worktree 观察层)，L2 (Supervisor Apply 临时 worktree)
- **组件**：
  - Orchestra Driver (L0) - 调度主循环
  - Governance Service (L1) - 定期扫描（cron-supervisor, roadmap-intake）
  - Supervisor Apply (L2) - 轻量治理执行

### Tier 2: Skill Layer

- **职责**：任务执行层。Agent 通过组合不同的 Skill（位于 `skills/`）和 V3 Core Services 实现具体业务逻辑。
- **核心命令**：`flow`, `task`, `run`, `plan`, `review`
- **执行层级**：L3 (持久 worktree)
- **组件**：Manager, Planner, Executor, Reviewer

### Tier 1: Shell Layer

- **职责**：原子能力层。提供环境隔离、命令封装与基础工具集。
- **核心命令**：`handoff`, `inspect`, `pr`, `ask`
- **执行层级**：L3/L4 (原子工具)

---

## Tier 1 (Shell Layer) 原子能力

Tier 1 提供了系统运行的物理基础，主要由以下组件构成：

### 1. V3 Hub (lib3/)
`lib3/` 是 V3 Python 核心能力的包装器。它负责：
- 仓库路径的自动重定向（寻找 git root）。
- 环境初始化（确保 `uv run` 正确执行）。
- 作为 V2 Shell 与 V3 Python 的桥接点。

### 2. 命令入口 (bin/)
- **`vibe3`**: V3 统一命令面入口。驱动 flow, task, handoff, serve 等核心子命令。
- **`vibe`**: V2 兼容性入口。提供 alias 和环境增强工具。

### 3. 环境隔离 (Worktree)
利用 Git Worktree 实现任务间的完全物理隔离，确保每个 Issue 都在独立的环境中运行，互不干扰。

---

## Tier 3 Core Services (V3 Core)

Vibe 3.0 在 `src/vibe3/` 中提供了以下核心基础设施服务：

## ExecutionRolePolicyService

### 用途

统一解析各执行角色（manager/planner/executor/reviewer/supervisor/governance）的配置，包括：

- Backend 选择（claude/openai）
- Prompt template 解析
- Session 策略（tmux/async/inline）
- Agent preset 配置

### API

```python
from vibe3.execution.execution_role_policy import ExecutionRolePolicyService
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

详细文档见 **[docs/v3/architecture/capacity-control.md](capacity-control.md)**。

### 用途

统一管理所有执行角色的容量控制，解决双层节流问题。

**双层节流问题**：

- StateLabelDispatchService 跟踪 `in_flight_dispatches`
- ManagerExecutor 也跟踪 `in_flight_dispatches`
- 导致容量计算冲突，可能出现超额分发

**解决方案**：

CapacityService 提供单一的容量检查点，结合 live session count 和 in-flight dispatch tracking。

**容量检查触发路径**（详见 [capacity-control.md](capacity-control.md)）：

- **Heartbeat 自动调度**: GlobalDispatchCoordinator 通过 heartbeat 定期扫描
- **CLI 手动触发**: `vibe3 [run|plan|review|internal manager] <issue>` 等命令

两条路径共享同一个 `_shared_in_flight_dispatches`，确保容量计数一致。

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

### GlobalDispatchCoordinator 共享约束

**关键要求**：GlobalDispatchCoordinator 和 ExecutionCoordinator 必须使用同一个 CapacityService 实例（或共享同一个 db_path）。

**实现方式**：

1. **registry.py 注入**：
   ```python
   shared_capacity = CapacityService(config, shared_store, shared_backend)
   facade = OrchestrationFacade(dispatch_services=dispatch_services, capacity=shared_capacity)
   ```

2. **类变量共享机制**：
   CapacityService 使用类变量 `_shared_in_flight_dispatches` 基于 db_path 共享状态：
   ```python
   _shared_in_flight_dispatches: dict[str, dict[str, set[int]]] = {}
   # key = str(Path(store.db_path).resolve())
   ```

只要两个 CapacityService 实例使用相同的 store（指向同一个 db_path），它们会自动共享 in_flight 状态。

**验证**：
- registry.py 中的 `shared_store` 与 coordinator.py 内的 `SQLiteClient()` 默认 db_path 一致
- facade 将 shared_capacity 传入 GlobalDispatchCoordinator
- ExecutionCoordinator 使用同一个 shared_capacity 实例（通过依赖注入）

**回滚策略**：
如果 GlobalDispatchCoordinator 出现问题，可以回滚到旧路径：
1. 移除 registry.py 中的 shared_capacity 注入
2. facade.on_tick() 自动回退到 legacy asyncio.gather 路径（capacity=None）
3. 删除 global_dispatch_coordinator.py 文件

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
from vibe3.execution.execution_lifecycle import persist_execution_lifecycle_event

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
