# Execution

执行控制平面，协调角色执行与容量控制。

## 职责

- 执行协调：管理角色执行的完整生命周期
- 容量控制：限制并发执行数量，避免资源争抢
- 角色执行请求构建：构建各角色的执行请求和上下文
- No-op 门控：检测并跳过无需执行的任务
- Session 管理：为执行分配独立的 session 和 worktree

## 文件列表

统计时间：2026-05-02

### 核心协调文件

| 文件 | 行数 | 职责 |
|------|------|------|
| coordinator.py | 345 | 执行协调器，管理执行生命周期与资源分配 |
| capacity_service.py | 114 | 容量服务，控制并发执行数 |
| contracts.py | 46 | 执行契约定义（请求/响应类型） |
| session_service.py | 64 | Session 管理服务 |

### 角色执行文件

| 文件 | 行数 | 职责 |
|------|------|------|
| codeagent_runner.py | 403 | Codeagent 执行器，处理异步执行 |
| governance_sync_runner.py | 115 | Governance 同步执行器 |
| issue_role_sync_runner.py | 185 | Issue 角色同步执行器（plan/run/review） |
| issue_role_support.py | 260 | Issue 角色执行辅助函数 |
| execution_lifecycle.py | 261 | 执行生命周期管理（前缀、后缀处理） |

### 辅助文件

| 文件 | 行数 | 职责 |
|------|------|------|
| flow_dispatch.py | 294 | Flow 分发逻辑，决定执行路径 |
| noop_gate.py | 242 | No-op 门控，检测无需执行的任务 |
| role_contracts.py | 21 | 角色契约定义 |
| role_policy.py | 77 | 角色执行策略 |
| execution_role_policy.py | 180 | 执行角色策略（权限控制） |
| agent_resolver.py | 120 | Agent 解析器，匹配 agent 到执行请求 |
| role_request_factory.py | 91 | 角色请求工厂 |
| prompt_meta.py | 87 | Prompt 元数据构建 |
| codeagent_support.py | 86 | Codeagent 辅助函数 |
| actor_support.py | 82 | Actor 辅助函数 |

### 其他文件

| 文件 | 行数 | 职责 |
|------|------|------|
| __init__.py | 5 | 模块导出 |

**总计**：20 文件，3078 行

## 依赖关系

### 依赖

- `clients`：Git 客户端、SQLite 客户端
- `environment`：Worktree 和 session 管理
- `models`：编排配置、执行请求模型
- `config`：编排配置加载
- `domain`：事件发布、状态机
- `agents`：Agent 后端（Codeagent、异步启动器）

### 被依赖

- `roles`：各角色通过执行器运行
- `domain handlers`：事件处理器触发执行
- `commands`：命令层触发执行

## 架构说明

### Sync vs Async 执行模式

Execution 模块支持两种执行模式：

- **同步执行（Sync）**：
  - 阻塞当前线程，等待执行完成
  - 适用于：Governance 扫描、Supervisor 检查、Issue 角色执行
  - 实现：`governance_sync_runner.py`, `issue_role_sync_runner.py`

- **异步执行（Async）**：
  - 启动后台进程，立即返回
  - 适用于：长期运行的任务（如复杂的 plan/run 流程）
  - 实现：`codeagent_runner.py`, 异步启动器

### Capacity-based Dispatch

容量控制机制避免系统过载：

```
Coordinator
├─ CapacityService.check_capacity() → 是否有空闲槽位
├─ 如果有空位 → 立即执行
└─ 如果无空位 → 排队等待或降级处理
```

### 执行流程

```
1. 接收执行请求
2. No-op 门控检查（是否需要执行）
3. 容量检查（是否有资源执行）
4. Worktree + Session 分配
5. 构建执行上下文（prompt、环境变量）
6. 启动执行（sync/async）
7. 监控执行状态
8. 回收资源（worktree、session）
```

### 关键设计

1. **资源隔离**：每次执行都在独立的 worktree 和 session 中
2. **容量控制**：全局并发限制，避免资源争抢
3. **No-op 优化**：自动跳过无需执行的任务，节省资源
4. **生命周期钩子**：执行前后的初始化和清理逻辑
5. **错误恢复**：执行失败时保留现场，支持恢复