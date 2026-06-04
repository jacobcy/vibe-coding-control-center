---
document_type: reference
title: Flow 依赖管理参考
status: current
scope: flow-dependency
author: Vibe Team
related_docs:
  - ../standards/v3/command-standard.md
  - ../standards/v3/handoff-store-standard.md
---

# Flow 依赖管理参考

> **说明**：本文档为参考材料，权威规范见 `docs/standards/v3/*.md`。

本文档说明 V3 架构下 Flow 依赖管理的实现方式和命令使用场景。

## 架构变化

**V2 架构**：
- 本地 `roadmap.json` 作为过时或备份镜像
- `roadmap item` 包含依赖关系

**V3 架构**：
- GitHub Issues API 作为工作项真源
- SQLite `flow_issue_links` 表记录 Flow 与 Issue 的关系
- 无本地 `roadmap.json`（主规划真源为 GitHub Issues），依赖关系通过 issue role 表达

## 依赖关系建模

### 数据结构

**flow_issue_links 表**：
```sql
CREATE TABLE flow_issue_links (
    branch TEXT NOT NULL,
    issue_number INTEGER NOT NULL,
    issue_role TEXT NOT NULL,  -- 'task' | 'related' | 'dependency'
    created_at TEXT NOT NULL,
    PRIMARY KEY (branch, issue_number, issue_role)
)
```

**Issue Role 语义**：
- `task` - Flow 的主要执行目标（唯一）
- `related` - 相关 issue（需求来源、参考）
- `dependency` - 依赖的其他 task

### 依赖关系示例

```sql
-- Flow: task/reports-unified-storage
-- 主任务: #220
-- 依赖: #218 (API 先完成)
-- 相关: #219 (需求来源)

INSERT INTO flow_issue_links VALUES
  ('task/reports-unified-storage', 220, 'task', '2026-03-23T10:00:00'),
  ('task/reports-unified-storage', 218, 'dependency', '2026-03-23T10:05:00'),
  ('task/reports-unified-storage', 219, 'related', '2026-03-23T10:05:00');
```

**查询依赖关系**：
```bash
# 查看某个 flow 的依赖
vibe3 flow show task/reports-unified-storage

# 输出包含：
# Task Issue: #220
# Dependencies: #218
# Related Issues: #219
```

---

## 阻塞管理

### flow_state 表字段

```sql
CREATE TABLE flow_state (
    branch TEXT PRIMARY KEY,
    flow_status TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'blocked' | 'done' | 'aborted'
    blocked_by_issue INTEGER,  -- dependency issue number (INT)
    blocked_reason TEXT,       -- blocking reason description
    ...
)
```

### 命令对比

| 命令 | 使用场景 | 数据影响 | 建立依赖关系 |
|------|---------|---------|------------|
| `flow blocked --task <issue>` | Flow 执行中遇到依赖阻塞 | `flow_issue_links` + `flow_state` | ✅ 是 |
| `handoff next <text>` | Agent 交接时记录阻塞状态 | 仅 `flow_state` | ❌ 否 |

> **注意**：`--task` 是主要选项。

### 详细操作影响

#### 1. `vibe3 flow blocked --task <issue>`

**使用场景**：Flow 执行过程中被具体的依赖 issue 阻塞。

**命令示例**：
```bash
# 使用 --task 建立依赖
vibe3 flow blocked --task 218

# 使用 --reason 描述阻塞原因
vibe3 flow blocked --reason "等待外部反馈"

# --task 和 --reason 可同时使用，分别记录依赖 issue 和原因描述
vibe3 flow blocked --task 218 --reason "等待 API 完成"
```

**数据库变更**：
```sql
-- 1. 更新 flow 状态
UPDATE flow_state SET
  flow_status = 'blocked',
  blocked_by_issue = 218,
  blocked_reason = '等待依赖 issue #218'
WHERE branch = 'task/my-feature';

-- 2. 建立依赖关系
INSERT INTO flow_issue_links
  (branch, issue_number, issue_role, created_at)
VALUES
  ('task/my-feature', 218, 'dependency', '2026-03-23T...');

-- 3. 记录事件
INSERT INTO flow_events
  (branch, event_type, actor, detail, created_at)
VALUES
  ('task/my-feature', 'flow_blocked', 'system', 'Blocked by dependency #218', '2026-03-23T...');
```

**目的**：
- 在 `flow_issue_links` 表中建立明确的依赖关系
- 自动更新 `flow_status` 和 `blocked_by`
- 避免遗漏依赖关系

#### 2. `vibe3 handoff next <message>`

**使用场景**：Agent 交接时记录下一步或阻塞状态。

**设计原则**：
- **软约束**：不强制执行，agent 可以绕过
- **灵活性**：不限制阶段顺序，可以自由决定
- **结构化记录**：替代单一的 task.md 文件
- **覆盖语义**：最新的状态最重要，允许覆盖之前的值

**命令示例**：
```bash
vibe3 handoff next "等待外部反馈" --branch task/issue-218

vibe3 handoff next "开始实现 API 接口" --branch task/issue-218
```

**数据库变更**：
```sql
-- 仅更新 flow_state
UPDATE flow_state SET
  plan_ref = 'docs/plans/feature-a.md',
  planner_actor = 'claude',      -- plan → planner_actor
  latest_actor = 'claude'
WHERE branch = 'task/my-feature';

-- 记录事件
INSERT INTO flow_events
  (branch, event_type, actor, detail, created_at)
VALUES
  ('task/my-feature', 'handoff_plan', 'claude', 'Plan recorded: docs/plans/feature-a.md', '2026-03-23T...');
```

**Actor 映射关系**：
- `handoff plan` → `planner_actor` (计划 agent)
- `handoff report` → `executor_actor` (执行 agent)
- `handoff audit` → `reviewer_actor` (Review agent)

**目的**：
- 记录 agent 交接时的下一步或阻塞状态
- `next_step` 是自由文本，可以是任何描述
- 不建立具体的依赖关系
- handoff 是软约束，不强制执行

---

## 多依赖语义

当使用 `flow bind --role dependency` 同时绑定多个依赖时，系统表现出**双重语义**：

### 行为描述

```bash
vibe3 flow bind --role dependency 100 101 102
```

执行流程：
1. **按顺序调用**: 对每个依赖 issue 依次调用 `block_flow()`（100 → 101 → 102）
2. **数据库字段**: `flow_state.blocked_by_issue` 被最后一次调用覆盖，最终值为 102
3. **Issue Body 累积**: 所有依赖都累积到 issue body 的 `blocked_by` 字段（100, 101, 102 均保留）
4. **链接记录**: 所有依赖都记录在 `flow_issue_links` 表中，角色为 `dependency`

### 双重存储机制

这种"双重语义"源于两层存储：

| 存储层 | 字段 | 更新行为 | 最终值 |
|--------|------|---------|--------|
| **flow_state 表** | `blocked_by_issue` | 每次调用覆盖 | 102（最后一个） |
| **issue body** | `blocked_by` | 通过 `_project_blocked_state()` 合并去重 | [100, 101, 102] |
| **flow_issue_links 表** | `issue_role='dependency'` | 每次调用插入 | 三条记录 |

代码位置：
- 多 ref 循环：`src/vibe3/commands/flow_manage.py:310-320`
- 字段覆盖：`src/vibe3/services/flow_block_mixin.py:121-127`
- 累积合并：`src/vibe3/services/flow_block_mixin.py:23-65`

### 最佳实践

**不推荐**同时绑定多个依赖：
```bash
# 可能造成语义混淆
vibe3 flow bind --role dependency 100 101 102
```

**推荐**逐个绑定：
```bash
vibe3 flow bind --role dependency 100
vibe3 flow bind --role dependency 101
vibe3 flow bind --role dependency 102
```

或使用 `flow blocked --task` 命令建立依赖关系，语义更明确。

### 详细说明

参见 [Flow Bind 使用指南](../v3/infrastructure/flow-bind-usage.md) 获取完整用法说明。

---

## 查询与验证

### 查看依赖关系

```bash
# 查看单个 flow 的依赖
vibe3 flow show task/my-feature

# 输出：
# Task Issue: #220
# Dependencies: #218
# Related Issues: #219
# Flow Status: blocked
# Blocked By Issue: 218
# Blocked Reason: 等待依赖 issue #218
```

### 解除阻塞

```bash
# 方法 1: 恢复 flow 状态
vibe3 task resume

# 注意：依赖关系仍保留在 flow_issue_links 表中
# 依赖满足后，Orchestra 会自动检测并恢复 flow
```

---

## 最佳实践

### 何时使用哪个命令

**使用 `flow blocked --task`**：
- Flow 执行中遇到具体的 issue 阻塞
- 需要在数据库中建立依赖关系
- 方便后续查询和分析

**使用 `handoff next`**：
- Agent 交接时记录下一步或阻塞状态
- 阻塞原因不一定是具体的 issue
- 阻塞原因可能是：外部反馈、资源等待、审批流程等

### 组合使用

```bash
# 场景：Agent 在 plan 阶段发现依赖阻塞

# Step 1: Agent 执行 handoff 记录 plan
vibe3 handoff plan docs/plans/feature-a.md --actor "claude/sonnet-4.6"

# Step 2: Agent 记录下一步（可选）
vibe3 handoff next "需要等待 API 完成" --branch task/my-feature

# Step 3: 开发者补充依赖关系
vibe3 flow blocked --task 218

# 结果：
# - flow_state.next_step 可能被更新（如果使用了 handoff next）
# - flow_issue_links 新增 dependency 记录
```

### 依赖解除验证

**V2 设计**：
- 依赖解除需要 PR merged 证据

**V3 简化**：
- 不强制验证 PR merged
- 依赖关系保留在 `flow_issue_links` 表中
- 开发者自行判断何时解除阻塞

---

## 与 V2 的差异

| 维度 | V2 | V3 |
|------|----|----|
| **规划层** | 本地 `roadmap.json` (过时/备份) | GitHub Issues API (主真源) |
| **依赖建模** | `roadmap item` 层 | `flow_issue_links` 表 |
| **阻塞验证** | 强制 PR merged 证据 | 不强制验证 |
| **查询方式** | `roadmap show` | `flow show` |
| **解除阻塞** | 自动检测 | 手动操作 |

---

## 相关文档

- [Task & Flow 操作指南](../standards/v3/command-standard.md)
- [项目概览](../../README.md)
- [数据模型标准](../standards/v3/handoff-store-standard.md)