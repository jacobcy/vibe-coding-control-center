# Flow 依赖管理参考

本文档说明 V3 架构下 Flow 依赖管理的实现方式和命令使用场景。

## 架构变化

**V2 架构**：
- 本地 `roadmap.json` 作为规划层
- `roadmap item` 包含依赖关系

**V3 架构**：
- GitHub Issues API 作为工作项真源
- SQLite `flow_issue_links` 表记录 Flow 与 Issue 的关系
- 无本地 `roadmap.json`，依赖关系通过 issue role 表达

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
    blocked_by TEXT,  -- 阻塞原因描述
    ...
)
```

### 命令对比

| 命令 | 使用场景 | 数据影响 | 建立依赖关系 |
|------|---------|---------|------------|
| `flow blocked --by <issue>` | Flow 执行中遇到依赖阻塞 | `flow_issue_links` + `flow_state` | ✅ 是 |
| `handoff --blocked-by <text>` | Agent 交接时记录阻塞状态 | 仅 `flow_state` | ❌ 否 |

### 详细操作影响

#### 1. `vibe3 flow blocked --by <issue>`

**使用场景**：Flow 执行过程中被具体的依赖 issue 阻塞。

**命令示例**：
```bash
# 自动生成描述
vibe3 flow blocked --by 218

# 自定义描述
vibe3 flow blocked --by 218 --reason "需要 #218 的 API 先完成"

# 仅记录原因（不建立依赖）
vibe3 flow blocked --reason "等待外部反馈"
```

**数据库变更**：
```sql
-- 1. 更新 flow 状态
UPDATE flow_state SET
  flow_status = 'blocked',
  blocked_by = '等待依赖 issue #218'  -- 或自定义 reason
WHERE branch = 'task/my-feature';

-- 2. 建立依赖关系（如果指定 --by）
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

#### 2. `vibe3 handoff plan/report/audit --blocked-by <text>`

**使用场景**：Agent 完成 plan/report/audit 阶段时记录阻塞状态。

**设计原则**：
- **软约束**：不强制执行，agent 可以绕过
- **灵活性**：不限制阶段顺序，可以自由决定
- **结构化记录**：替代单一的 task.md 文件
- **覆盖语义**：最新的状态最重要，允许覆盖之前的值

**命令示例**：
```bash
vibe3 handoff plan docs/plans/feature-a.md --blocked-by "等待外部反馈"

vibe3 handoff report docs/reports/feature-a.md --blocked-by "需要等待 API 完成"
```

**数据库变更**：
```sql
-- 仅更新 flow_state
UPDATE flow_state SET
  plan_ref = 'docs/plans/feature-a.md',
  planner_actor = 'claude',      -- plan → planner_actor
  latest_actor = 'claude',
  blocked_by = '等待外部反馈',  -- 自由文本
  next_step = NULL
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
- 记录 agent 交接时的阻塞状态
- `blocked_by` 是自由文本，可以是任何原因
- 不建立具体的依赖关系
- handoff 是软约束，不强制执行

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
# Blocked By: 等待依赖 issue #218
```

### 解除阻塞

```bash
# 方法 1: 更新 flow 状态
vibe3 task status active

# 方法 2: 切换到其他 flow
vibe3 flow switch other-feature

# 注意：依赖关系仍保留在 flow_issue_links 表中
# 如果依赖完成，可以手动清除：
vibe3 task unlink 218 --role dependency
```

---

## 最佳实践

### 何时使用哪个命令

**使用 `flow blocked --by`**：
- Flow 执行中遇到具体的 issue 阻塞
- 需要在数据库中建立依赖关系
- 方便后续查询和分析

**使用 `handoff --blocked-by`**：
- Agent 交接时记录阻塞状态
- 阻塞原因不一定是具体的 issue
- 阻塞原因可能是：外部反馈、资源等待、审批流程等

### 组合使用

```bash
# 场景：Agent 在 plan 阶段发现依赖阻塞

# Step 1: Agent 执行 handoff
vibe3 handoff plan docs/plans/feature-a.md --blocked-by "需要等待 API 完成"

# Step 2: 开发者补充依赖关系
vibe3 flow blocked --by 218

# 结果：
# - flow_state.blocked_by 可能被更新（如果指定了 --reason）
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
| **规划层** | 本地 `roadmap.json` | GitHub Issues API |
| **依赖建模** | `roadmap item` 层 | `flow_issue_links` 表 |
| **阻塞验证** | 强制 PR merged 证据 | 不强制验证 |
| **查询方式** | `roadmap show` | `flow show` |
| **解除阻塞** | 自动检测 | 手动操作 |

---

## 相关文档

- [Task & Flow 操作指南](../standards/v3/command-standard.md)
- [项目概览](../../README.md)
- [Flow 状态转换计划](../plans/2026-03-23-flow-status-transitions.md)
- [数据模型标准](../standards/v3/handoff-store-standard.md)