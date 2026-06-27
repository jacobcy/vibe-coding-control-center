# Services/Orchestra

编排状态聚合查询模块，提供全局视图、错误追踪、资源清理等功能。

## 职责

- 编排状态聚合查询（OrchestraStatusService、FlowOrchestratorService）
- 错误记录与追踪（ErrorTrackingService）
- 服务状态展示（ServeStatusService）
- 事件投影（error_projection）
- 过期资源清理
- 协调解析（CoordinationResolver）

## 文件列表

统计时间：2026-06-27

### 核心服务

| 文件 | 行数 | 职责 |
|------|------|------|
| orchestrator.py | 566 | FlowOrchestratorService - 主编排服务 |
| status.py | 577 | OrchestraStatusService, IssueStatusEntry, OrchestraSnapshot - 状态聚合 |
| serve_status.py | 524 | ServeStatusService - 服务状态展示 |
| cleanup.py | 625 | 过期资源清理（branches, worktrees, handoff files）|

### 错误处理

| 文件 | 行数 | 职责 |
|------|------|------|
| error_recording.py | 191 | record_error, record_dispatch_failure_if_unexpected - 错误记录包装器 |
| error_projection.py | 57 | build_error_projection_hook - ADR-0004 事件投影实现 |

### 协调与辅助

| 文件 | 行数 | 职责 |
|------|------|------|
| coordination.py | 194 | CoordinationResolver - 协调状态解析 |

### 错误追踪子模块

| 文件 | 行数 | 职责 |
|------|------|------|
| error_tracking/service.py | 304 | ErrorTrackingService - 错误追踪主服务 |
| error_tracking/queries.py | 338 | 错误查询与分析 |
| error_tracking/cleanup.py | 51 | 错误记录清理 |

**总计**：12 文件，3427 行

## 公共 API

从 `__init__.py` 导出的 14 个符号：

### 编排服务（4 个）

- `FlowOrchestratorService` - 主编排服务
- `OrchestraStatusService` - 状态聚合服务
- `OrchestraSnapshot` - 编排快照模型
- `IssueStatusEntry` - Issue 状态条目模型

### 错误处理（3 个）

- `ErrorTrackingService` - 错误追踪服务
- `record_error` - 错误记录包装器
- `record_dispatch_failure_if_unexpected` - 分发失败记录
- `build_error_projection_hook` - 错误投影 hook

### 服务状态（2 个）

- `ServeStatusService` - 服务状态展示
- `fetch_serve_status_data` - 获取服务状态数据

### 状态格式化（3 个）

- `format_issue_runtime_line` - 格式化 issue 运行时行
- `format_issue_summary_line` - 格式化 issue 摘要行
- `is_running_issue` - 检查是否运行中的 issue

### 协调（1 个）

- `CoordinationResolver` - 协调状态解析器

## 内部依赖

### 模块间依赖

```
orchestrator.py → status.py (状态聚合)
status.py → error_tracking/service.py (错误查询)
serve_status.py → status.py (状态展示)
cleanup.py → clients/git_client.py (资源清理)
error_recording.py → error_tracking/service.py (错误记录)
error_projection.py → domain/events.py (事件投影)
```

## 外部依赖

- `clients` - Git 客户端、GitHub 客户端、SQLite 客户端
- `config` - 配置加载（manager usernames, handoff state label）
- `models` - 领域模型定义
- `services/flow` - Flow 服务
- `services/pr` - PR 服务
- `services/shared` - 共享工具（labels, status query）
- `services/task` - Task 服务
- `environment` - 环境检测

## 被依赖

- `commands` - 命令层调用编排服务
- `domain` - 事件处理器使用 error projection
- `execution` - 执行器调用编排服务
- `roles` - Role handlers 使用状态查询
- `server` - Server 使用状态展示

## 设计原则

### Lazy Import

使用 `__getattr__` 实现延迟导入：

```python
def __getattr__(name: str) -> Any:
    if name in _SYMBOL_MODULES:
        import importlib
        module = importlib.import_module(_SYMBOL_MODULES[name])
        symbol = getattr(module, name)
        globals()[name] = symbol
        return symbol
    raise AttributeError(...)
```

### 事件投影（ADR-0004）

`build_error_projection_hook` 实现事件投影模式：

- 从 `flow_events` 表读取错误事件
- 投影为 `ErrorProjection` 模型
- 供 OrchestraStatusService 聚合

详见 `docs/adr/0004-event-projection.md`。

### 过期资源保护

`cleanup.py` 实现多层保护机制：

- **时间阈值**：只清理超过 N 天的资源
- **分支保护**：不清理 main/master 分支
- **状态检查**：不清理 active flow 的资源
- **用户确认**：可选 dry-run 模式

### Singleton Pattern

`ErrorTrackingService` 使用 singleton 模式：

```python
_instance: ErrorTrackingService | None = None

@classmethod
def get_instance(cls, store: SQLiteClient) -> ErrorTrackingService:
    if cls._instance is None:
        cls._instance = cls(store=store)
    return cls._instance
```

**原因**：全局错误追踪需要统一实例，避免多个 database connection。

## 架构说明

### 状态聚合流程

```
OrchestraStatusService.get_snapshot()
  ├── Query flow_state from SQLite
  ├── Query issue status via GitHub API
  ├── Query error tracking (ErrorTrackingService)
  └── Aggregate into OrchestraSnapshot
```

### 错误追踪架构

```
ErrorTrackingService (singleton)
  ├── record_error() → Write to error_records table
  ├── has_recent_specific_error() → Query recent errors
  └── get_error_summary() → Aggregate error stats
```

### 资源清理流程

```
cleanup.py
  ├── cleanup_old_branches() → Delete merged branches
  ├── cleanup_old_worktrees() → Delete stale worktrees
  └── cleanup_old_handoff_files() → Delete old handoff files
```

### 事件投影链路

```
domain/events.py (emit_issue_failed)
  → Write to flow_events table
  → error_projection.py (build_error_projection_hook)
  → Read and project events
  → OrchestraStatusService (aggregate)
```