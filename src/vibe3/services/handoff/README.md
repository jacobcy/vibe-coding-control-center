# Services/Handoff

Handoff 记录、存储、恢复服务，跨 agent 上下文传递。

## 职责

- Handoff 记录管理：记录 agent 间的上下文传递事件
- 存储操作：管理 `.git/vibe3/handoff.db` 和文件系统 handoff 文件
- 状态追踪：追踪 handoff 状态和结果
- 引用解析：解析 handoff target 引用（`@current`, `@plan`, `@vibe/` 等）
- 外部事件：处理来自 CI、PR comment 的外部 handoff 事件

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| service.py | 643 | Handoff 主服务（记录、查询、事件处理） |
| resolution.py | 529 | Handoff target 解析（`@` namespace、路径验证） |
| storage.py | 272 | 文件系统操作（handoff 目录、current.md） |
| external_events.py | 197 | 外部事件处理（CI status、PR comment） |
| status.py | 165 | Handoff 状态追踪服务 |
| validation.py | 57 | 权威引用验证（validate_authoritative_ref） |
| __init__.py | 79 | 公共 API 导出（lazy import） |

截至 2026-06，总计 7 文件，约 1942 行代码。

## 架构说明

### Handoff 生命周期

Handoff 系统采用事件驱动架构，支持 agent 间的上下文传递：

```
Agent A 完成 → HandoffService.record() → SQLite DB
                                          ↓
                         HandoffStorage → current.md (共享文件)
                                          ↓
Agent B 恢复 → HandoffService.read() → SQLite DB
```

### 存储路径

- **SQLite 数据库**：`.git/vibe3/handoff.db`（权威数据源）
  - `handoff_events` 表：记录所有 handoff 事件
  - `flow_state` 表：存储 plan_ref、report_ref、audit_ref
- **文件系统**：`.git/vibe3/handoff/<branch-safe>/current.md`（轻量共享文件）

### Event Type 分类

HandoffService 维护以下事件类型集合：

**Handoff 事件类型**（`_HANDOFF_EVENT_TYPES`）：
- `handoff_plan`、`handoff_report`、`handoff_run`（legacy）
- `handoff_audit`、`handoff_indicate`
- `next_step_set`、`plan_recorded`、`report_recorded`、`run_recorded`（legacy）、`audit_recorded`
- `handoff_ci_status`、`handoff_pr_comment`

**成功 handoff 事件类型**（`_SUCCESS_HANDOFF_EVENT_TYPES`）：
- 上述所有 + `handoff_verdict`

### Kind 映射

HandoffService 维护 kind → DB 字段映射：

**Kind → Ref 字段**：
- `plan` → `plan_ref`
- `run` → `report_ref`
- `review` → `audit_ref`

**Kind → Actor 字段**：
- `plan` → `planner_actor`
- `run` → `executor_actor`
- `review` → `reviewer_actor`
- `indicate` → `manager_actor`

**Legacy Kind 别名**：
- `report` → `run`
- `audit` → `review`

### 四 Namespace 引用解析

`resolution.py` 支持四种 handoff target namespace：

1. **`@vibe/<path>`** → vibe3 installation materials
   - 解析为 vibe3 安装根目录下的 governance materials

2. **`@prefix/key`** → shared handoff artifact
   - 解析为 `.git/vibe3/handoff/` 下的共享文件
   - 特例：`@current` + `--branch` → per-branch current.md
   - 特例：`@plan/@report/@audit` → 从 flow_state refs 解析

3. **`relative/path`** → canonical worktree ref
   - 解析为目标分支的 worktree root（或当前 worktree）

4. **`/abs/path`** → absolute path passthrough（debug fallback）

### 设计原则

- **权威数据源**：SQLite DB 为唯一权威源，current.md 为轻量共享
- **Lazy import**：`__init__.py` 使用 lazy import 避免循环依赖
- **路径安全**：`resolution.py` 验证 branch name 和 vibe path，防止路径遍历攻击
- **事件溯源**：所有 handoff 操作记录为事件，支持状态重建
- **Namespace 分离**：四种 namespace 清晰分离，避免冲突

## 公共 API

`__init__.py` 导出以下 8 个符号：

### 服务类

- **HandoffService**: 主 handoff 服务（记录、查询、事件处理）
- **HandoffStatusService**: Handoff 状态追踪服务
- **HandoffStatusResult**: Handoff 状态结果类型
- **HandoffStorage**: Handoff 存储操作（文件系统）

### 解析函数

- **resolve_handoff_target**: 解析 handoff target 引用为绝对路径
- **is_shared_handoff_ref**: 检查引用是否为共享 handoff artifact（`@` namespace）
- **to_display_target**: 转换绝对路径为 display target（逆向解析）

### 验证函数

- **validate_authoritative_ref**: 验证权威引用（plan/report/audit ref）

## 内部依赖

```
handoff/
├── service.py → storage.py (HandoffStorage)
├── service.py → resolution.py (_SHARED_HANDOFF_PREFIX)
├── service.py → validation.py (validate_authoritative_ref)
├── service.py → external_events.py (ExternalEventRecorder)
├── status.py → service.py (HandoffService, KIND_TO_REF_FIELD)
└── resolution.py → shared/paths.py (_SHARED_HANDOFF_PREFIX, GitPathProtocol)
```

**循环依赖检查**：✅ 无循环依赖

**跨模块依赖**：
- `resolution.py` → `services/shared/paths.py`（共享路径工具）
- `resolution.py` → `services/shared/branch_resolver.py`（分支解析）

## 外部依赖

- **clients/**: GitClient（branch/worktree 操作）、SQLiteClient（数据库）
- **models/**: FlowEvent（事件模型）、VerdictRecord（裁决记录）
- **exceptions/**: UserError（用户错误）
- **services/shared/**: paths（路径工具）、actors（角色提取）、artifacts（artifact 解析）、signatures（签名服务）

## 被依赖

- **services/flow/**: cleanup.py（清理 handoff）、status.py、rebuild.py
- **commands/**: handoff_read.py、handoff_write.py、flow_manage.py、plan.py、run.py、pr_query.py
- **execution/**: codeagent_runner.py
- **config/**: timeline_comment_policy.py
- **roles/**: run_helpers.py

约 15 个文件引用。

## 架构演变说明

### Handoff 系统演进

**早期设计**：仅文件系统 handoff（`.git/vibe3/handoff/current.md`）

**当前设计**：
1. SQLite DB 作为权威数据源（handoff_events、flow_state）
2. 文件系统 current.md 作为轻量共享（非权威）
3. 事件溯源架构（所有操作记录为事件）
4. 四 namespace 引用解析系统

### External Events 系统设计

**设计目标**：支持外部事件（CI、PR comment）触发 handoff

**实现方式**：
1. `ExternalEventRecorder` 处理 CI status、PR comment 事件
2. 事件记录为 `handoff_ci_status`、`handoff_pr_comment`
3. 支持从事件重建状态

### Status 追踪系统设计

**设计目标**：追踪 handoff 状态，支持状态查询

**实现方式**：
1. `HandoffStatusService` 查询 SQLite DB
2. `HandoffStatusResult` 返回状态结果
3. 支持 branch-level 状态查询

## 设计原则

- **权威数据源**：SQLite DB 为唯一权威源，避免数据分散
- **事件溯源**：所有操作记录为事件，支持状态重建
- **Lazy import**：避免循环依赖，保持模块独立性
- **Namespace 分离**：四种 namespace 清晰分离，避免引用冲突
- **路径安全**：验证 branch name 和 vibe path，防止路径遍历攻击
- **向后兼容**：支持 legacy kind aliases（report → run, audit → review）