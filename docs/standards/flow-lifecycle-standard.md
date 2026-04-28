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
last_updated: 2026-04-28
related_docs:
  - docs/standards/glossary.md
  - docs/standards/vibe3-role-checks-and-balances-standard.md
  - docs/standards/v3/data-model-standard.md
  - docs/standards/vibe3-event-driven-standard.md
---

# Flow 生命周期与回收机制标准

本文档定义 Vibe3 Flow 的生命周期流程和资源回收机制。

**术语定义** 见 [glossary.md](glossary.md)，本文档不重复定义。

**角色权力边界** 见 [vibe3-role-checks-and-balances-standard.md](vibe3-role-checks-and-balances-standard.md)。

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
new → active → blocked → active (恢复)
           ↓         ↓
         done      failed → blocked (业务错误)
           ↓
       merged
           ↓
       aborted
```

**区分 Flow Status 和 Issue State**：

- **Flow Status**：`active/blocked/done/merged/aborted`（SQLite flow_state）
  - 描述 flow 的执行状态
  - 图中的 `failed → blocked` 是 Flow Status 的转换

- **Issue State**：`ready/claimed/in-progress/blocked/handoff/review/merge-ready/done`（GitHub label）
  - 描述 issue 的编排状态
  - IssueState.FAILED 已废弃，统一到 BLOCKED

**关系**：
- Flow Status `failed` → Issue State `blocked`
- Flow Status `aborted` → Issue State `ready`（被动清理）

### 2.2 Issue State 统一模型

**FAILED → BLOCKED 统一**：

- **设计原则**：FAILED 是原因，BLOCKED 是结果
- **实现统一**：所有执行失败现在都进入 `state/blocked` 状态
- **数据模型**：
  - `failed_reason` 字段已废弃
  - 统一使用 `blocked_reason` 字段记录失败原因
  - `IssueState.FAILED` 枚举保留用于兼容遗留数据

**遗留数据处理**：

- 残留代码识别 `state/failed` 标签（向后兼容）
- FailedGate 自动清理无 reason 的 `state/failed` 标签
- `task resume` 支持从 FAILED 状态恢复（遗留数据）

**清理机制**：

- **被动清理**：`vibe check --clean-branch` 处理 aborted flows
- **主动清理**：`task resume` 人类重置权限
- **自动清理**：FailedGate 检测并清理无效 FAILED 标签

### 2.2 终端状态处理

Flow 进入终端状态（done/merged/aborted）后：

1. **等待 Check 清理**：`vibe check --clean-branch`
2. **物理资源回收**：删除 worktree/branch/handoff
3. **Flow 记录处理**：
   - done/merged: 保留记录（审计历史）
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

### 4.1 阻塞场景

**场景 1：手动阻塞**
- Manager 标记 `blocked_reason` 字段
- Issue label 自动转为 `state/blocked`
- **保留现场**：worktree/branch/flow 记录

**场景 2：依赖阻塞**
- Issue 链接表标记 `issue_role = 'dependency'`
- Orchestra 自动巡逻依赖状态
- 依赖满足后自动恢复

### 4.2 手动恢复

**情况 A：现场值得保留**（--label）
```bash
vibe3 task resume --label ready <issue_number>
```

流程：
```python
_clear_flow_reasons(branch)  # 清除 blocked_reason
resume_issue(..., to_state=READY)
# ✅ 不删除 worktree/branch/flow
```

**情况 B：现场不值得保留**
```bash
vibe3 task resume <issue_number>
```

流程：
```python
resume_blocked_issue_to_ready(...)
reset_task_scene(branch)  # 清理物理资源
```

### 4.3 自动恢复（依赖满足）

见 [glossary.md](glossary.md) §3.4.2 dependency 机制。

**恢复目标推断**：见 `flow_resume_resolver.py`。
1. 有 pr_ref → HANDOFF
2. 有 audit_ref → IN_PROGRESS 或 HANDOFF
3. 有 report_ref → REVIEW
4. 有 plan_ref → IN_PROGRESS
5. 默认 → CLAIMED

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
  ├─ 标记 flow_status = "merged"
  └─ 等待 vibe check --clean-branch
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
  └─ 等待 vibe check --clean-branch
```

**清理策略**：
- keep_flow_record = False（删除记录）
- 恢复 issue 到 READY（被动清理）

## 6. 资源回收机制

### 6.1 统一清理入口

所有终端状态的 flow 通过 `vibe check --clean-branch` 统一回收：

```python
# CheckCleanupService.clean_residual_branches
for flow in terminal_flows:  # done/merged/aborted
    _process_terminal_flow(flow)
```

**清理步骤**（FlowCleanupService.cleanup_flow_scene）：
1. 终止 tmux sessions（如存在）
2. 删除 worktree
3. 删除本地 branch
4. 删除远程 branch
5. 清理 handoff 文件
6. 删除 flow 记录（仅在 aborted 场景）

### 6.2 Issue Label 清理

**主动恢复**（task resume）：
```python
# 先恢复 label，再清理 flow
resume_blocked_issue_to_ready(...)
reset_task_scene(...)
```

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

### 6.3 保留策略

**保留 flow 记录**（done/merged）：
- 目的：审计历史，统计完成情况
- Issue 已关闭，无需处理 labels

**删除 flow 记录**（aborted）：
- 目的：允许 issue 重新开始，无历史包袱
- Issue 可能仍在 open，需要恢复 labels

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
  ├─ flow.flow_status: merged
  └─ issue.state: closed
  ↓ vibe check --clean-branch
清理物理资源
  ├─ worktree: deleted
  ├─ branch: deleted
  └─ flow 记录: preserved ✅
```

### 7.2 中止后重建

```
Issue #456 (state/ready)
  ↓ Orchestra 派发
Manager 创建 flow task/issue-456
  ↓ Agent 执行失败
Manager 标记 blocked
  ├─ flow.blocked_reason: "Agent error..."
  └─ issue label: state/blocked
  ↓ 用户决定放弃现场
vibe3 task resume 456
  ├─ resume_issue(#456, to_state=READY)
  └─ reset_task_scene(task/issue-456)
      ├─ 删除 worktree
      ├─ 删除 branch
      └─ 删除 flow 记录 ✅
  ↓ Orchestra 重新派发
Manager 创建新 flow task/issue-456
  └─ 全新开始
```

### 7.3 被动清理孤儿 Flow

```
Issue #789 (state/blocked)
  ↓ Flow 已被 aborted（可能是手动）
  ├─ flow.flow_status: aborted
  └─ flow 记录存在但无物理资源
  ↓ vibe check --clean-branch
检测 aborted flow
  ├─ cleanup_flow_scene(keep_flow_record=False)
  └─ _resume_blocked_issue(task/issue-789)
      └─ issue label: state/blocked → state/ready ✅
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

3. **主动清理**（task resume）：
   - 人类最高权限，可纠正任何非 DONE 状态
   - `resume_kind` 动态识别：failed/blocked/all
   - `resume_kind="all"` 支持：`state != DONE` 的任意状态重置
   - 人类可选择手动更改 label 或使用 task resume

**设计理由**：
- 状态机规则约束 Agent 自动化流程，防止机器越权
- 人类拥有最终决策权，不受规则约束
- 被动清理自动化执行，无需人类介入决策

### 8.3 测试覆盖

必须覆盖以下场景：
- 正常完成（PR merged）→ 清理
- 中止重建（task resume）→ 清理
- 被动清理（check --clean-branch）→ 恢复 labels
- 依赖阻塞 → 自动恢复
- FailedGate 自动清理无效 FAILED 标签

### 8.4 日志审计

每次 flow 状态变化必须记录事件：
```python
store.add_event(
    branch,
    event_type="blocked",  # or "resumed", "done", "aborted"
    actor="manager:claude",
    detail="Agent execution failed",
    refs={"issue": str(issue_number)}
)
```

## 9. 参考文档

- [glossary.md](glossary.md) - 术语定义（权威）
- [vibe3-role-checks-and-balances-standard.md](vibe3-role-checks-and-balances-standard.md) - 角色权力边界（权威）
- [v3/data-model-standard.md](v3/data-model-standard.md) - 数据模型（权威）
- [vibe3-event-driven-standard.md](vibe3-event-driven-standard.md) - 事件驱动架构
