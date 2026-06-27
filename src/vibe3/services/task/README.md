# Task Service Module

> **Module**: `vibe3.services.task` | **Epic**: #3178 | **Phase**: 3/10 — 服务层 A
> **Last Updated**: 2026-06-27

## 核心职责

Task Service 模块负责管理 Task 的绑定、展示、恢复和状态管理，包括：

- **Task 绑定**：Task 与 Issue 的绑定/解除绑定、绑定验证
- **状态展示**：Task 状态仪表盘数据获取、Task 摘要查询
- **失败恢复**：非破坏性恢复操作（resume、retry）
- **状态分类**：Task 状态桶分类（in-progress、blocked、done 等）

## 文件列表

### 核心服务文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `service.py` | 496 | Task 主服务（issue 绑定、重分类、flow 状态查询） |

### 展示与状态

| 文件 | 行数 | 职责 |
|------|------|------|
| `show.py` | 417 | Read-side task 摘要查询（task show data） |
| `status.py` | 464 | Task 状态仪表盘数据获取（fetch task status data） |
| `classifier.py` | 68 | Task 状态桶分类（classify task status） |

### 恢复操作

| 文件 | 行数 | 职责 |
|------|------|------|
| `resume.py` | 609 | 非破坏性恢复操作（resume candidates、resume operations） |

**总计**: 2,178 行（含 `__init__.py`）

## 公开 API

### Core Service

- `TaskService` — 主服务入口（issue 绑定、重分类、flow 状态查询）

### Show Operations

- `TaskShowService` — Task 摘要查询服务
- `TaskShowResult` — Task 摘要结果
- `TaskRefSummary` — Task 引用摘要
- `TaskCommentSummary` — Task 评论摘要
- `TaskPRSummary` — Task PR 摘要

### Status Operations

- `TaskStatusData` — Task 状态数据
- `build_api_task_data` — 构建 API task 数据
- `fetch_task_status_data` — 获取 task 状态数据
- `classify_task_issues_for_rendering` — 分类 task issues for rendering

### Resume Operations

- `TaskResumeUsecase` — Task 恢复用例
- `TaskResumeCandidates` — Task 恢复候选列表
- `TaskResumeOperations` — Task 恢复操作集合

### Classifier

- `TaskStatusBucket` — Task 状态桶枚举
- `classify_task_status` — Task 状态分类函数

### Binding Guard (Passthrough from `services.shared`)

- `MissingTaskIssueError` — Task-Issue 绑定缺失异常
- `ensure_task_issue_bound` — 确保 Task-Issue 绑定
- `has_task_issue` — 判断 Task 是否绑定 Issue
- `build_bind_task_hint` — 构建绑定提示

## 依赖关系

### 该模块依赖

- **domain 层**: `vibe3.domain.task` (Task 聚合根)
- **models 层**: `vibe3.models` (数据模型)
- **clients 层**: `vibe3.clients.github` (GitHub API 客户端)
- **config 层**: `vibe3.config` (配置管理)
- **services 层内部**:
  - `services.flow` (Flow 状态查询)
  - `services.issue` (Issue 服务)
  - `services.shared.binding_guard` (绑定验证工具)

### 被依赖

- **commands 层**: `commands.task_show`、`commands.task_resume` 等命令入口
- **roles 层**: `roles.run` (Task 恢复)、`roles.manager` (Task 状态查询)
- **services 层内部**:
  - `services.flow` (Flow 状态查询时调用 TaskService)
  - `services.check` (Check 服务调用 Task 恢复)

## 与服务层其他模块的关系

### 协作模式

1. **与 flow 模块**:
   - Task 绑定到 Flow (TaskService 管理 Task-Flow 关系)
   - Task 恢复依赖 Flow 状态 (TaskResumeUsecase 调用 FlowService)
   - Task 状态查询聚合 Flow 状态 (fetch_task_status_data 包含 flow 信息)

2. **与 issue 模块**:
   - Task 绑定到 Issue (TaskService 管理 Task-Issue 绑定)
   - Issue 状态变更触发 Task 状态更新

3. **与 pr 模块**:
   - Task 关联 PR (TaskPRSummary 聚合 PR 信息)
   - Task 状态查询聚合 PR 状态

4. **与 shared 模块**:
   - 使用 `binding_guard` 进行 Task-Issue 绑定验证
   - Passthrough re-export 4 个 binding_guard 符号（有意设计）

## 架构约束

- **Lazy import**: 使用 `__getattr__` 避免循环依赖
- **Passthrough re-export**: 从 `services.shared.binding_guard` 穿透重导出 4 个符号（有意设计，方便上层使用）
- **非破坏性恢复**: Task resume 操作不破坏现有状态（retry、resume）

## 已知问题

### Passthrough Re-export (有意设计)

- 4 个 binding_guard 符号（MissingTaskIssueError、ensure_task_issue_bound、has_task_issue、build_bind_task_hint）从 `services.shared.binding_guard` 穿透重导出
- 这是有意设计，让 task 模块的使用者无需直接依赖 shared 子包
- 外部引用验证：有 6 个外部文件引用这些符号（合理）

### 无 Dead Code 或反模式

所有导出符号均有外部引用，无反模式发现。

---

**参考**: 基础层 README (#3179)、外部对接层 README (#3180)