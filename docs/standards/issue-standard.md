# Issue 标准

**维护者**: Vibe Team
**最后更新**: 2026-03-22
**状态**: Active

---

## 核心概念

### GitHub Issue（统一概念）

```
所有 issue 都是 GitHub repository issue

- 在 GitHub Issues API 中管理
- 可以是需求、任务、缺陷、讨论等
- 通过 label 分类（如 vibe-task, enhancement, bug 等）
```

### Task Issue（vibe3 视角）

```
task issue 是 vibe3 的视角概念，不是独立的实体

判定基线：
1. SQLite flow_issue_links 中存在记录，且 issue_role = task 或 dependency
2. 如启用标签自动化，GitHub issue 应镜像 vibe-task 标签

本质：
- 一个 GitHub issue 被 vibe3 纳入 flow 管理时，就成了 task issue
- 这是关系视角，不是实体类型
```

**重要**：
- 不说 "创建 task issue"，而是 "将 issue 关联为 task"
- task issue 是 GitHub issue 在 vibe3 执行语义下的角色，不是 GitHub 的新实体分类

---

## Issue Role 定义

Issue Role 定义了 GitHub issue 在特定 flow 中的角色（相对于 flow 的关系）：

| Role | 含义 | 标签镜像建议 | 联动操作 |
|------|------|-------------|---------|
| `task` | Flow 的主要执行目标 | 应镜像 `vibe-task` | PR 合并时可关闭 issue |
| `related` | 相关 issue（需求来源、参考） | 不镜像 | 无联动 |
| `dependency` | 依赖的其他 task | 应镜像 `vibe-task` | 可用于阻塞判断 |

**语义说明**：
- Issue role 是**相对于 flow 的关系**，不是 issue 的类型属性
- 同一个 GitHub issue 可以在不同 flow 中有不同 role
- `flow_state.task_issue_number` 只存 role=`task` 的 issue

---

## 真源设计

```
✅ SQLite flow_issue_links.issue_role (唯一真源)
  - 定义 issue 在 flow 中的角色
  - 本地存储，离线可用
  - 由 vibe3 flow bind / task link 写入

❌ GitHub vibe-task label (同步副作用)
  - 用于 GitHub 视角过滤
  - 只能由自动化根据 issue_role 镜像
  - 不是判断 task 的真源
```

---

## 当前命令边界

### vibe3 flow bind

```bash
# 设置主要任务
vibe3 flow bind 220
# → 本地记录 role=task
# → 更新 flow_state.task_issue_number

# 关联需求来源
vibe3 flow bind 219 --role related
# → 本地记录 role=related

# 关联依赖
vibe3 flow bind 218 --role dependency
# → 本地记录 role=dependency
```

### vibe3 task link

```bash
# 为当前 flow 记录相关 issue
vibe3 task link 219 --role related
# → 本地记录 role=related

# 为当前 flow 记录依赖 issue
vibe3 task link 218 --role dependency
# → 本地记录 role=dependency
```

**约束**：
1. 一个 flow 只有一个 task 指针，重复 `flow bind <issue>` 会覆盖 `flow_state.task_issue_number`
2. 当前 CLI 以本地 SQLite 为准，不把 GitHub label 当真源
3. 后续标签自动化必须由 `issue_role` 单向镜像，不能反向生成 role

---

## 数据模型

### SQLite Schema

```sql
CREATE TABLE flow_issue_links (
    branch TEXT NOT NULL,
    issue_number INTEGER NOT NULL,
    issue_role TEXT NOT NULL CHECK(issue_role IN ('task', 'related', 'dependency')),
    created_at TEXT NOT NULL,
    PRIMARY KEY (branch, issue_number, issue_role)
);

CREATE TABLE flow_state (
    branch TEXT PRIMARY KEY,
    flow_slug TEXT,
    task_issue_number INTEGER,
    ...
);
```

### 兼容迁移

```sql
-- 历史数据迁移：repo -> related
UPDATE flow_issue_links
SET issue_role = 'related'
WHERE issue_role = 'repo';
```

---

## 查询语义

```bash
# 查看某个 issue 的所有关联 flow
vibe3 task list --issue 219

# 查看 flow 完整信息
vibe3 task show task/my-feature

# 输出示意：
Branch: task/my-feature
Task Issue: #220
Related Issue(s): #219
Dependencies: #218
```

---

## 架构原则

1. ✅ **不做第二真源**
   - SQLite `issue_role` 是唯一真源
   - GitHub label 只是镜像副作用

2. ✅ **自动化只能镜像，不得改义**
   - 标签自动化必须复用 `task/related/dependency`
   - 不得新增一套独立标签语义

3. ✅ **保持离线能力**
   - 本地数据库是当前 CLI 的执行基线
   - 自动化失败不能反向污染本地 role

4. ✅ **联动操作服从 issue_role**
   - PR merge / 标签镜像 / 后续规则判断都应从 issue_role 出发

---

## 术语规范

### ✅ 正确说法

- "将 issue #220 绑定为当前 flow 的 task"
- "issue #219 在这个 flow 中是 related"
- "issue #218 在这个 flow 中是 dependency"

### ❌ 错误说法

- "创建一个 task issue"
- "task issue 和 repo issue 是两种类型"
- "vibe-task 标签是真源"

---

**参考文档**：
- [vibe3-command-standard.md](vibe3-command-standard.md)
- [github-labels-standard.md](github-labels-standard.md)
- [glossary.md](glossary.md)
