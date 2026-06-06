---
document_type: standard
title: Flow Lifecycle & Recycling Standard
status: active
scope: flow-lifecycle-processes
authority:
  - flow-lifecycle-mechanisms
  - recycling-operations
  - cleanup-orchestration
author: Claude Sonnet 4.6
created: 2026-04-28
last_updated: 2026-06-05
related_docs:
  - docs/standards/label-semantics.md
  - docs/standards/glossary.md
  - docs/standards/v3/error-severity-and-blocking-standard.md
  - docs/standards/v3/human-mirror-architecture-philosophy.md
  - docs/standards/v3/data-model-standard.md
  - docs/standards/v3/event-driven-standard.md
---

# Flow 生命周期与回收机制标准

本文档定义 Vibe3 Flow 的生命周期流程和资源回收机制。

**术语定义** 见 [glossary.md](glossary.md)，本文档不重复定义。

**角色权力边界** 见 [v3/human-mirror-architecture-philosophy.md](v3/human-mirror-architecture-philosophy.md)。

**数据模型** 见 [v3/data-model-standard.md](v3/data-model-standard.md)。

## 1. 单一真源原则

Flow 生命周期涉及三个真源：

- **GitHub Issue Label**: Orchestra 的唯一观察对象
- **SQLite Flow State**: Manager 的执行现场记录
- **Git Branch/Worktree**: Manager 的物理现场载体

跨层直接操作禁止：
- ❌ Orchestra 不直接写 flow_state
- ❌ Manager 不直接改 issue label（通过 LabelService）
- ❌ Check 不参与业务判断

## 2. Flow 状态流转

### 2.1 状态机

见 [glossary.md](glossary.md) §3.4.1 Flow Status 语义。

```
new → active ↔ blocked
        ↓        ↓
      done     stale
        ↓
     aborted
```

**区分 Flow Status 和 Issue State**：

- **Flow Status**：`active/blocked/done/stale/aborted`（SQLite flow_state）
  - 描述 flow 的执行状态
  - `failed` 已废弃，通过 `active` 状态配合 `blocked_reason` 表达

- **Issue State**：`ready/claimed/in-progress/blocked/handoff/review/merge-ready/done`（GitHub label）
  - 描述 issue 的编排状态。详细语义见 [label-semantics.md](./label-semantics.md)。
  - IssueState.FAILED 已废弃，统一到 BLOCKED

**关系**：
- Flow Status `blocked` → Issue State `blocked`
- Flow Status `aborted` → Issue State `ready`（被动清理）
- Flow Status `stale` → Issue State `ready`（被动清理）

### 2.2 Issue State 统一模型

**ERROR 与 BLOCK 的正交化 (Decoupling)**：

见 [error-severity-and-blocking-standard.md](./v3/error-severity-and-blocking-standard.md) §11。

- **ERROR 系统**：关注运行时基础设施健康（Runtime Infrastructure Health）。
  - 触发：`mark_issue(action="fail")` 或 `vibe3.services.error_helpers.record_error(...)` 或 `ErrorTrackingService.get_instance(...).record_error(...)`。
  - 存储：`error_log` 表。
  - 影响：控制 FailedGate 派发，**不直接改变** Flow 业务状态。
- **BLOCK 系统**：关注业务流状态（Business Flow State）。
  - 触发：`mark_issue(action="block")` 或 `BlockedStateService.block()`。
  - 存储：`flow_state.flow_status = "blocked"` 和 `blocked_reason`。
  - 影响：流程暂停，需要手动或自动 unblock。

**语义统一**：

- **设计原则**：`failed` 是执行过程的属性（发生了错误），`blocked` 是工作流的结果（流程停下了）。
- **语义边界**：`blocked` 是 workflow state，不是错误等级。
- **实现统一**：执行失败、contract deviation、依赖未满足等场景都进入 `state/blocked`。
- **数据模型**：
  - `failed_reason` 字段已废弃，其内容应反映到 `error_log` 或 `blocked_reason`。
  - 统一使用 `blocked_reason` 字段记录阻塞原因。
  - `IssueState.FAILED` 标签已废弃，系统自动将其映射为 `state/blocked`。

**遗留数据处理**：

- 残留代码识别 `state/failed` 标签（向后兼容）
- FailedGate 自动清理无 reason 的 `state/failed` 标签
- `task resume` 支持从 FAILED 状态恢复（遗留数据）

**清理机制**：

- **被动清理**：`vibe3 check --clean-branch` 处理 aborted flows
- **主动恢复**：`task resume` 清除 blocked 状态（不删除现场）
- **主动重建**：`flow rebuild` 显式删除并重建 flow scene
- **自动清理**：FailedGate 检测并清理无效 FAILED 标签

### 2.2 终端状态处理

Flow 进入终端状态（done/aborted）后：

1. **等待 Check 清理**：`vibe3 check --clean-branch`
2. **物理资源回收**：删除 worktree/branch/handoff
3. **Flow 记录处理**：
   - done: 保留记录（审计历史）
   - aborted: 删除记录（允许重建）

## 3. Issue → Flow 流转

### 3.1 Orchestra 派发流程

```
GitHub Issue (state/ready)
  ↓ Orchestra tick
检查 assignee issue pool
  ↓ 符合条件
触发 Manager 派发
  ↓
Manager 创建 flow
```

**条件判断**：
- issue 有 `state/ready` 标签
- issue 在 assignee issue pool（有 assignee）
- 无其他 active flow 阻塞（capacity 未满）

### 3.2 Flow 绑定

见 [v3/data-model-standard.md](v3/data-model-standard.md) §2.1 flow_state 表。

**约束**：
- 一个 issue 只能绑定一个 flow（当前版本）
- flow 记录存入 `flow_state` 表
- issue 链接存入 `flow_issue_links` 表

## 4. 阻塞与恢复

### 4.1 阻塞 API：`BlockedStateService.block()`

阻塞 flow 的标准入口：

```python
def block(
    self,
    branch: str,
    reason: str | None,
    blocked_by_issue: int | None = None,
    actor: str = "system",
    issue_number: int | None = None,
    event_type: str = "flow_blocked",
) -> None
```

**副作用**（原子执行）：

1. SQLite：写入 `flow_state.blocked_by_issue`，可选写入 `blocked_reason`
2. GitHub：写入 Issue Body Projection (Truth Source)
3. GitHub：task issue label 转为 `state/blocked` (Signal)
4. Event：通过 `FlowTimelineService` 写入 `flow_blocked` 事件

### 4.2 何时使用 block vs abort vs stale

| 场景 | 动作 | API | 恢复路径 |
|------|------|-----|----------|
| 派发失败 | `block(reason=...)` | `BlockedStateService.block()` | `task resume` 或自动解封 |
| Health check 失败 | `block(reason=...)` | `BlockedStateService.block()` | `task resume` |
| 依赖未满足 | `block(blocked_by_issue=N)` | `BlockedStateService.block()` | 依赖 issue 关闭后自动解封 |
| 手动阻塞 | `block(reason=..., actor=...)` | `BlockedStateService.block()` | 仅 `task resume` |
| Issue 关闭 / Branch 丢失 | `mark_flow_aborted()` | `mark_flow_aborted()` | 无恢复（终端状态） |
| 空 ready flow / 孤儿 flow | `mark_flow_stale()` | `mark_flow_stale()` | Governance 重建 ready flow |

### 4.3 Abort API：`mark_flow_aborted()`

```python
def mark_flow_aborted(self, branch: str, reason: str) -> None
```

- **终端状态**：flow 状态标记为 `aborted`
- **软删除**：由下游 `vibe3 check --clean-branch` → `cleanup_flow_scene` → `soft_delete_flow()` 处理
- **事件类型**：`flow_auto_aborted`
- **GitHub label 处理**：⚠️ 当前实现未显式处理 task issue label 变更（实现缺口）
- **恢复**：下一轮 collect 不会重新拾取（issue 已 closed）；若 issue 重新打开，由 health check 处理

### 4.4 Stale API：`mark_flow_stale()`

```python
def mark_flow_stale(self, branch: str, reason: str) -> None
```

- **等待状态**：flow 等待 issue 状态变更或 ready flow 重建
- **事件类型**：`flow_auto_staled`
- **GitHub label 处理**：⚠️ 当前实现未显式处理 task issue label 变更（实现缺口）
- **恢复**：由 governance 机制重建 ready flow 后恢复

### 4.5 阻塞原因区分：`blocked_reason` vs `blocked_by_issue` vs dependency links

三个概念各有明确语义，不可混用：

- **`blocked_reason`**：手动阻塞信号 — 在 QualifyGate 中**阻止自动解封**
- **`blocked_by_issue`**：主要阻塞 issue 的快捷显示字段（不是完整依赖集合）
- **`flow_issue_links(role='dependency')`**：完整依赖集合的**真源**

**关键规则**：`--reason` 和 `--task`（`blocked_by_issue`）在当前行为中实质互斥。

原因：`blocked_reason` 的存在会导致 QualifyGate 将 flow 视为手动阻塞，优先级高于依赖自动解封。即使同时指定 `--reason` 和 `--task`，`blocked_reason` 也会阻止依赖自动解封生效。

### 4.6 Qualify Gate 在 blocked 恢复中的角色

QualifyGate 通过 `CoordinationTruth.is_blocked` 判断阻塞状态，其真源为 issue body projection 而非仅本地 DB。

**决策流程**：

1. **`resolve_coordination`** — 合并 remote issue body + local DB 出 `CoordinationTruth`
2. **`is_blocked` 综合判断** — 任一为真即 blocked：`projection_state == 'blocked'` OR `blocked_reason` OR `blocked_by_issue`
3. **若 blocked** → `_align_blocked_state` 并跳过（不继续后续检查）
4. **若 NOT blocked 但 local/label stale** → `_auto_resume_blocked`（清除 local blocked 缓存，移除 label）
5. **通过后运行 `_check_dependencies`** — 结构检查（非恢复判定）

**自动解封副作用**（由 `_auto_resume_blocked` 执行）：

- 清除 `blocked_by_issue`、`blocked_reason`
- 写入 `flow_unblocked` 事件
- 推断恢复目标 label（`infer_resume_label`），恢复 task issue label

### 4.7 各状态转换的 GitHub Label 管理

| 转换 | Flow Status 变更 | GitHub Label 变更 | 备注 |
|------|------------------|-------------------|------|
| → blocked | active → blocked | 当前 label → `state/blocked` | `block_flow()` 自动处理 |
| blocked → active（自动） | blocked → active | `state/blocked` → 推断目标 label | QualifyGate 处理 |
| blocked → active（手动） | blocked → active | `state/blocked` → 用户指定 label | `task resume` 处理 |
| → done | active → done | 无需处理（issue 自动关闭） | PR merged 触发 |
| → aborted | * → aborted | `state/*` → `state/ready` (被动) | `vibe3 check` 清理时恢复 |
| → stale | active → stale | `state/*` → `state/ready` (被动) | Governance 机制处理 |

**实现缺口说明**：`mark_flow_aborted()` 和 `mark_flow_stale()` 当前未在方法内显式管理 task issue label。对于 aborted，后续 `vibe3 check --clean-branch` 的被动清理会恢复 label；对于 stale，依赖 governance 机制在重建 ready flow 时处理。

## 5. PR 生命周期

### 5.1 PR Created

```python
pr_service.create_pr(branch, title, body)
store.update_flow_state(branch, pr_ref=pr_url)
```

Issue label 自动转换：
- `state/in-progress` → `state/review`（如触发）

### 5.2 PR Merged

```
PR merged (GitHub webhook)
  ↓ Check 检测
发现 flow.pr_ref == merged PR
  ├─ 标记 flow_status = "done"
  └─ 等待 vibe3 check --clean-branch
```

**清理策略**：
- keep_flow_record = True（保留历史）
- Issue 应已关闭，无需处理 labels

### 5.3 PR Closed（未合并）

```
PR closed (GitHub webhook)
  ↓ Check 检测
发现 flow.pr_ref == closed PR
  ├─ 标记 flow_status = "aborted"
  └─ 等待 vibe3 check --clean-branch
```

**清理策略**：
- keep_flow_record = False（删除记录）
- 恢复 issue 到 READY（被动清理）

### 5.4 Issue 自动关闭机制

**与 GitHub 原生关闭关键字的区别**：

GitHub 原生关闭关键字（`closes #N`、`fixes #N` 在 PR body 中）与 vibe3 flow done 是**两个独立机制**：

| 机制 | 触发时机 | 控制方式 |
|------|----------|----------|
| GitHub 原生关键字 | PR merge 时自动触发 | PR body 中的关键字 |
| vibe3 flow done（PR merge 后由 `vibe3 check` 触发） | `vibe3 check` 检测到 merged PR | `close_issue_if_open` API 调用 |

两者**互不干扰**：
- PR body 不会被 vibe3 修改以注入关闭关键字
- vibe3 通过 GitHub API 独立执行关闭操作
- 如果 PR body 已有关闭关键字，issue 会被 GitHub 先关闭，vibe3 检测到 `already_closed` 状态

**vibe3 自动关闭条件**：

`_mark_flow_done` 在以下全部满足时才自动关闭 task issue：

1. **Flow 有 `role=task` 的 issue 链接**
   - `role=related` 或 `role=dependency` 的 issue 不会被关闭
2. **无其他 active flow 绑定同一 issue**（多 flow 保护）
   - 如果 issue #123 同时绑定 `task/issue-123` 和 `dev/issue-123`，只有当两者都完成时才关闭
   - 防止因一个分支合并而过早关闭还在其他分支上工作的 issue
3. **Issue 在 GitHub 上仍处于 open 状态**
   - 如果已被关闭（通过 GitHub 关键字或其他方式），返回 `already_closed`

**多 Flow 绑定保护**：

```
Issue #123 绑定两个 flow:
  ├─ task/issue-123 (flow_status: active)
  └─ dev/issue-123   (flow_status: active)

当 task/issue-123 的 PR merged:
  ├─ flow_status → done
  └─ Issue #123 NOT closed (因为 dev/issue-123 仍 active)

当 dev/issue-123 的 PR 也 merged:
  ├─ flow_status → done
  └─ Issue #123 closed ✅ (无其他 active flow)
```

**幂等性保证**：

`close_issue_if_open` 返回值：
- `"closed"`: 本次成功关闭
- `"already_closed"`: issue 已处于关闭状态
- `"failed"`: 关闭失败（API 错误等）

实现不关心返回值类型，只保证无副作用重复调用。

## 6. 资源回收机制

### 6.1 统一清理入口

所有终端状态的 flow 通过 `vibe3 check --clean-branch` 统一回收：

```python
# CheckCleanupService.clean_residual_branches
for flow in terminal_flows:  # done/aborted
    _process_terminal_flow(flow)
```

**清理步骤**（FlowCleanupService.cleanup_flow_scene）：
1. 终止 tmux sessions（如存在）
2. 删除 worktree
3. 删除本地 branch
4. 删除远程 branch
5. 清理 handoff 文件
6. 处理 flow 记录（软删除或保留）

### 6.2 软删除机制（Soft Delete）

**设计原理**：

Flow 记录采用**软删除**策略，防止意外数据丢失并提供恢复能力：

- **软删除**：设置 `deleted_at` 时间戳，记录仍存在于数据库
- **硬删除**：物理删除记录及级联数据（需显式指定）
- **默认软删除**：所有 cleanup 操作默认使用软删除

**数据模型**：

```python
# FlowState 模型
deleted_at: str | None = None  # ISO 8601 时间戳

# SQLiteFlowStateRepo 方法
soft_delete_flow(branch)         # 设置 deleted_at
hard_delete_flow(branch)          # 物理删除 + 级联
delete_flow(branch, force=False) # 统一接口（默认软删除）
restore_flow(branch)              # 恢复软删除记录
get_deleted_flows()               # 查询所有已删除 flows
```

**查询行为**：

所有查询方法自动过滤已删除记录：

```python
# 示例：get_flow_state, get_all_flows, get_flows_by_issue 等
WHERE deleted_at IS NULL
```

特殊查询方法：

```python
get_flow_state_include_deleted(branch)  # 包含已删除记录（用于恢复检查）
get_deleted_flows()                      # 专门查询已删除记录
```

**删除策略**：

| Flow Status | 默认行为 | deleted_at | 说明 |
|-------------|---------|-----------|------|
| done | 保留记录 | NULL | 审计历史，Issue 已关闭 |
| aborted | 软删除 | 设置时间戳 | Issue 可能重新打开，允许重建 |

**恢复流程**：

```bash
# 查看已删除 flows（已废弃，不再作为公共 CLI 命令）
# vibe3 flow list-deleted

# 恢复软删除 flow（已废弃，不再作为公共 CLI 命令）
# vibe3 flow restore <branch>

# 创建新 flow 自动覆盖已删除记录
vibe3 flow update <branch>  # 自动清除 deleted_at
```

**硬删除场景**：

硬删除仅在以下情况使用：

1. **显式指定**：`force=True` 参数
2. **数据清理**：测试环境数据清理
3. **隐私合规**：需要永久删除敏感数据

```python
# 硬删除示例
flow_service.delete_flow(branch, force=True)  # 物理删除
```

**容错保障**：

- ✅ **误删恢复**：软删除记录可通过 `restore_flow()` 恢复
- ✅ **审计追踪**：保留删除时间戳，支持审计查询
- ✅ **自动覆盖**：创建新 flow 自动清除 deleted_at
- ✅ **查询隔离**：普通查询不包含已删除记录，避免污染

### 6.3 Issue Label 清理

**主动恢复**（task resume）：

- `vibe3 task resume <issue>` 等价于 `vibe3 task resume <issue> --label auto`。
- `task resume` 只负责清除 blocked cache/body/label，并按 flow refs 推断恢复 label。
- `task resume` 不删除 worktree、branch 或 flow record。
- 若 label-auto 恢复发现 recorded worktree/ref 场景已经丢失，应委托 explicit rebuild path，而不是在 resume 内静默继续。

**主动重建**（flow rebuild）：

- `vibe3 flow rebuild <issue>` 是唯一公共 destructive rebuild 入口。
- rebuild 使用 hard delete 清理旧 flow/worktree/branch scene。
- rebuild 完成后重新 bootstrap flow/worktree，append rebuild handoff event，然后调用 label-auto resume 清除 blocked。

**被动清理**（check --clean-branch）：
```python
# 先清理 flow，再恢复 label（针对 aborted）
cleanup_service.cleanup_flow_scene(...)
if flow_status == "aborted":
    _resume_blocked_issue(branch)
```

**禁止重复调用**：
- FlowCleanupService 不处理 issue labels
- 调用者负责协调 resume_issue() 的时机

### 6.5 保留策略

**保留 flow 记录**（done）：
- 目的：审计历史，统计完成情况
- Issue 已关闭，无需处理 labels
- deleted_at 保持 NULL

**软删除 flow 记录**（aborted）：
- 目的：允许 issue 重新开始，同时保留审计追踪
- Issue 可能仍在 open，需要恢复 labels
- deleted_at 设置为删除时间戳
- 可通过内部 `restore_flow()` API 恢复（CLI 命令已废弃）

## 7. 典型场景流程

### 7.1 正常完成流程

```
Issue #123 (state/ready)
  ↓ Orchestra 派发
Manager 创建 flow task/issue-123
  ├─ worktree: .worktrees/task/issue-123
  ├─ branch: task/issue-123
  └─ flow_status: active
  ↓ Agent 执行
Manager 提交 PR
  ├─ flow.pr_ref: https://github.com/...
  └─ issue label: state/review
  ↓ 人工审查
PR merged
  ├─ flow.flow_status: done
  └─ issue.state: closed
  ↓ vibe3 check --clean-branch
清理物理资源
  ├─ worktree: deleted
  ├─ branch: deleted
  └─ flow 记录: preserved ✅
```

### 7.2 阻塞后恢复

```
Issue #456 (state/blocked)
  ↓ Agent 执行失败
Manager 标记 blocked
  ├─ flow.blocked_reason: "Agent error..."
  └─ issue label: state/blocked
  ↓ 用户决定恢复
vibe3 task resume 456
  ├─ 清除 blocked_reason
  ├─ 推断恢复目标 label (auto)
  └─ issue label: state/blocked → state/in-progress ✅
  ↓ 继续执行
Agent 恢复运行
  └─ flow 现场保持完整
```

### 7.3 阻塞后重建

```
Issue #789 (state/blocked)
  ↓ 用户决定放弃现场并重建
vibe3 flow rebuild 789
  ├─ hard cleanup: 删除 worktree/branch/flow
  ├─ bootstrap: 创建新 flow/worktree
  ├─ append rebuild handoff event
  └─ label-auto resume: 清除 blocked
  ↓ 全新开始
Manager 重新派发
  └─ Issue #789 → state/ready
```

### 7.4 被动清理孤儿 Flow

```
Issue #789 (state/blocked)
  ↓ Flow 已被 aborted（可能是手动）
  ├─ flow.flow_status: aborted
  └─ flow 记录存在但无物理资源
  ↓ vibe3 check --clean-branch
检测 aborted flow
  ├─ cleanup_flow_scene(keep_flow_record=False)
  └─ _resume_blocked_issue(task/issue-789)
      └─ issue label: state/blocked → state/ready ✅
```

### 7.5 软删除恢复流程

```
Issue #999 (state/blocked)
  ↓ Flow 被软删除
vibe3 check --clean-branch
  ├─ cleanup_flow_scene(keep_flow_record=False)
  ├─ deleted_at: "2026-04-28T15:00:00"
  └─ issue label: state/blocked → state/ready
  ↓ 用户发现需要恢复
# 通过 gh issue / flow status 确认已删除的 flow
vibe3 flow update task/issue-999
  ├─ deleted_at: NULL ✅（创建新 flow 自动清除 deleted_at）
  └─ flow 记录恢复可用
  ↓ 验证恢复结果
vibe3 flow show task/issue-999
  └─ Flow 显示正常，可继续操作
```

## 8. 实现约束

### 8.1 架构约束

- FlowCleanupService 只清理物理资源，不处理 issue labels
- CheckCleanupService 负责 issue labels 的恢复（被动场景）
- TaskResumeOperations 负责 issue labels 的恢复（主动场景）
- 每条路径只调用一次 resume_issue()

### 8.2 状态转换权限分层

**三层权限模型**：

1. **Agent 自动化**：
   - 遵循状态机规则（ALLOWED_TRANSITIONS）
   - 只能在允许的状态间转换
   - 示例：READY → CLAIMED → HANDOFF

2. **被动清理**（check --clean-branch）：
   - 自动清理 aborted/done flows
   - 使用 `force=True` 绕过状态机规则
   - `from_state` 为语义标签（不验证实际状态）

3. **主动恢复**（task resume）：
   - 清除 blocked 状态，不删除现场
   - 推断恢复目标 label（auto 模式）
   - 人类可选择手动更改 label 或使用 task resume

4. **主动重建**（flow rebuild）：
   - 显式 destructive 重建入口
   - hard delete + re-bootstrap
   - 需要明确意图，不作为常规恢复路径

**设计理由**：
- 状态机规则约束 Agent 自动化流程，防止机器越权
- 人类拥有最终决策权，不受规则约束
- 被动清理自动化执行，无需人类介入决策
- 恢复优先尝试保留现场，重建显式声明放弃现场

### 8.3 测试覆盖

必须覆盖以下场景：
- 正常完成（PR merged）→ 清理
- 阻塞后恢复（task resume）→ 清除 blocked 状态
- 阻塞后重建（flow rebuild）→ hard delete + re-bootstrap
- 被动清理（check --clean-branch）→ 恢复 labels
- 依赖阻塞 → 自动恢复
- FailedGate 自动清理无效 FAILED 标签
- 软删除设置 deleted_at 时间戳
- 软删除记录查询自动过滤
- 软删除恢复流程（restore_flow）
- 硬删除流程（force=True）
- 创建新 flow 覆盖已删除记录

### 8.4 日志审计

每次 flow 状态变化必须记录事件：
```python
store.add_event(
    branch,
    event_type="blocked",  # or "resumed", "done", "aborted", "deleted", "restored"
    actor="manager:claude",
    detail="Agent execution failed",
    refs={"issue": str(issue_number)}
)
```

**软删除相关事件**：
- `deleted`: 软删除记录，记录删除时间和操作者
- `restored`: 恢复软删除记录，记录恢复时间
- 日志示例：
  ```python
  logger.info("Soft deleted flow record", branch=branch, deleted_at=now)
  logger.info("Restored soft-deleted flow", branch=branch)
  ```

## 9. 参考文档

- [glossary.md](glossary.md) - 术语定义（权威）
- [v3/human-mirror-architecture-philosophy.md](v3/human-mirror-architecture-philosophy.md) - 角色权力边界（权威）
- [v3/data-model-standard.md](v3/data-model-standard.md) - 数据模型（权威）
- [event-driven-standard.md](v3/event-driven-standard.md) - 事件驱动架构
- [noop-gate-boundary-standard.md](v3/noop-gate-boundary-standard.md) - 阻塞原则与 noop gate 边界
- [../analysis/flow-blocked-vs-bind-dependency-analysis.md](../analysis/flow-blocked-vs-bind-dependency-analysis.md) - blocked_reason vs dependency 依赖分析
