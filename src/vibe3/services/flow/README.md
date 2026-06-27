# Flow Service Module

> **Module**: `vibe3.services.flow` | **Epic**: #3178 | **Phase**: 3/10 — 服务层 A
> **Last Updated**: 2026-06-27

## 核心职责

Flow Service 模块负责管理 Flow 的完整生命周期，包括：

- **CRUD 操作**：Flow 的创建、读取、更新、删除
- **状态转变**：Flow 状态机管理（state transitions）
- **生命周期管理**：Flow 的启动、暂停、恢复、完成、放弃
- **查询与投影**：Flow 数据查询和投影（projection）
- **一致性检查**：Flow 数据一致性验证和修复

## 文件列表

### 核心服务文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `service.py` | 67 | Flow 主服务入口（CRUD、状态查询） |
| `classifier.py` | 87 | Flow 分类器（category、state） |
| `status.py` | 296 | Flow 状态服务（dashboard、状态解析） |
| `status_resolver.py` | 175 | 状态解析器（复合状态判断） |

### Mixin 层（继承链）

| 文件 | 行数 | 职责 |
|------|------|------|
| `read_mixin.py` | 249 | 读操作 mixin（查询、过滤） |
| `write_mixin.py` | 261 | 写操作 mixin（创建、更新） |
| `block_mixin.py` | 167 | 阻塞状态 mixin（blocked flow 管理） |
| `transition.py` | 291 | 状态转变 mixin（状态机） |

### Blocked 状态管理

| 文件 | 行数 | 职责 |
|------|------|------|
| `blocked_state_service.py` | 404 | 阻塞状态统一管理服务 |
| `blocked_state_io.py` | 263 | 阻塞状态 I/O（读写操作） |
| `blocked_state_types.py` | 65 | 阻塞状态类型定义（BlockedState、ConsistencyReport、UnblockResult） |

### 投影与事件

| 文件 | 行数 | 职责 |
|------|------|------|
| `projection.py` | 160 | Flow 投影服务（projection building） |
| `event_projection.py` | 120 | 事件投影 hook（构建事件投影） |

### 恢复与重建

| 文件 | 行数 | 职责 |
|------|------|------|
| `recovery.py` | 295 | Flow 恢复服务（recovery from failure） |
| `rebuild.py` | 183 | Flow 重建用例（rebuild from scratch） |
| `rebuild_postconditions.py` | 63 | 重建后置条件验证 |
| `resume_resolver.py` | 67 | Resume 标签推断（infer resume label） |

### 清理与维护

| 文件 | 行数 | 职责 |
|------|------|------|
| `cleanup.py` | 480 | Flow 清理服务（cleanup、LiveSessionsDetectedError） |
| `abandon.py` | 156 | Flow 放弃服务（abandon flow） |
| `timeline.py` | 201 | Flow 时间线服务（timeline events） |

### 辅助工具

| 文件 | 行数 | 职责 |
|------|------|------|
| `factory.py` | 36 | Flow manager 工厂（create_flow_manager） |
| `branch_resolution.py` | 54 | 分支解析工具（resolve branch args） |
| `consistency.py` | 116 | 一致性检查工具 |

**总计**: 4,385 行（含 `__init__.py`）

## 公开 API

### Core Service

- `FlowService` — 主服务入口（继承 FlowTransitionMixin → FlowWriteMixin → FlowReadMixin）
- `resolve_flow_ref` — Flow 引用解析

### Classification

- `FlowCategory` — Flow 分类枚举
- `FlowState` — Flow 状态枚举
- `classify_flow` — Flow 分类函数
- `get_flow_state` — 获取 Flow 状态

### Blocked State Management

- `BlockedStateService` — 阻塞状态统一管理服务
- `BlockedState` — 阻塞状态类型
- `BlockedStateIO` — 阻塞状态 I/O 操作
- `ConsistencyReport` — 一致性报告
- `UnblockResult` — 解阻塞结果

### Projection

- `FlowProjection` — Flow 投影类型
- `FlowProjectionService` — Flow 投影服务
- `build_event_projection_hook` — 事件投影 hook 构建器

### Recovery & Cleanup

- `FlowRecoveryService` — Flow 恢复服务
- `FlowCleanupService` — Flow 清理服务
- `FlowRebuildUsecase` — Flow 重建用例
- `AbandonFlowService` — Flow 放弃服务 ⚠️ **Finding**: 0 external references (dead code candidate)
- `LiveSessionsDetectedError` — 活跃会话检测异常
- `FlowTimelineService` — Flow 时间线服务

### Utilities

- `create_flow_manager` — Flow manager 工厂函数
- `infer_resume_label` — Resume 标签推断
- `resolve_branch_and_issue` — 分支与 issue 解析
- `resolve_branch_arg` — 分支参数解析
- `FlowStatusService` — Flow 状态服务
- `FlowStatusResolver` — Flow 状态解析器

## 依赖关系

### 该模块依赖

- **domain 层**: `vibe3.domain.flow` (Flow 聚合根)
- **models 层**: `vibe3.models` (数据模型)
- **clients 层**: `vibe3.clients` (外部客户端：GitHub、Git)
- **config 层**: `vibe3.config` (配置管理)
- **services 层内部**:
  - `services.shared` (共享工具：binding_guard、timeline)
  - `services.issue` (Issue 服务)
  - `services.task` (Task 服务)
  - `services.pr` (PR 服务)

### 被依赖

- **commands 层**: 多个命令入口直接调用 FlowService
- **roles 层**: manager、plan、run、review 等角色使用 flow 管理
- **services 层内部**:
  - `services.task` (TaskService 调用 FlowService)
  - `services.pr` (PR 服务调用 flow 状态检查)
- **server 层**: HTTP API 端点使用 flow 投影

## 与服务层其他模块的关系

### 协作模式

1. **与 task 模块**:
   - Task 绑定到 Flow (FlowService 管理绑定关系)
   - Task 恢复依赖 Flow 状态 (TaskResumeUsecase 调用 FlowService)

2. **与 pr 模块**:
   - PR 创建依赖 Flow 状态 (PRCreateUsecase 检查 flow 状态)
   - PR merge 触发 Flow 状态转变

3. **与 shared 模块**:
   - 使用 `binding_guard` 进行 Task-Issue 绑定验证
   - 使用 `timeline` 服务记录 Flow 事件

4. **与 issue 模块**:
   - Flow 与 Issue 双向关联
   - Flow 状态变更触发 Issue 状态更新

## 架构约束

- **继承链设计**: FlowService 采用 mixin 组合模式（Read → Write → Transition → Lifecycle）
- **Lazy import**: 使用 `__getattr__` 避免循环依赖
- **状态机**: Flow 状态转变遵循严格的状态机规则（transition.py）
- **一致性保证**: Blocked 状态管理提供事务性操作

## 已知问题

### Dead Code Candidate

- `AbandonFlowService` — 公开导出但无外部引用（需 follow-up 验证是否可移除）

### 反模式

无（所有导出均有明确外部引用）

---

**参考**: 基础层 README (#3179)、外部对接层 README (#3180)
