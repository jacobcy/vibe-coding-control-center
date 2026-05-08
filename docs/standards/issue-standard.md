# Issue 标准

**维护者**: Vibe Team
**最后更新**: 2026-03-27
**状态**: Active

---

## Issue 池分层

本项目中的 issue 按职责和执行链分为三层：

1. **Assignee Issue Pool**（本地开发链）
   - **对象**：已分配、待执行的需求、缺陷或功能任务。
   - **处理链**：Manager -> Plan -> Run -> Review -> PR。
   - **治理关注**：Orchestra 的实时观察与排序对象。

2. **Supervisor Issue Pool**（本地治理链）
   - **对象**：带 `supervisor` 标签的治理任务（如文档修正、过期测试清理）。
   - **处理链**：Supervisor/Apply。
   - **边界**：不进入 Manager 开发主链，不影响业务代码交付。

3. **Broader Repo Issue Pool**（全量池 / 规划池）
   - **对象**：Repo 中所有 Open issues。
   - **处理链**：Future Governance / Cron 扫描。
   - **状态**：非当前执行真源，仅作为积压需求参考。

---

## 核心概念

### GitHub Issue（统一对象）

```
所有 issue 都是 GitHub repository issue，是外部实体对象。
```

### Task Issue（执行关系角色）

```
task issue 是 vibe3 视角下的角色映射，不是 GitHub 的新实体分类。

判定基线：
1. SQLite flow_issue_links 中存在记录，且 issue_role = task 或 dependency
2. 对应的 issue 属于 assignee issue pool
3. flow bind / flow_issue_links 是执行绑定的唯一事实真源

副作用（Mirror）：
- vibe-task 标签由 flow bind 自动镜像，用于 GitHub 视角过滤
- 它不是治理判定的依据，也不是 execution record 本体
```

**重要**：
- 不说 "创建 task issue"，而是 "将 issue 关联为 task"。
- task issue 是 GitHub issue 在 vibe3 执行语义下的角色，不是新的 GitHub 对象类型。

---

## Issue Role 定义

Issue Role 定义了 GitHub issue 在特定 flow 中的角色（相对于 flow 的关系）：

| Role | 含义 | 标签镜像建议 | 联动操作 |
|------|------|-------------|---------|
| `task` | Flow 的主要执行目标 | flow bind 时自动镜像 `vibe-task` | PR 合并时可关闭 issue |
| `related` | 相关 issue（需求来源、参考） | 不镜像 | 无联动 |
| `dependency` | 依赖的其他 task | 自动镜像 `vibe-task` | 可用于阻塞判断 |

**语义说明**：
- Issue role 是**相对于 flow 的关系**，不是 issue 的类型属性
- 同一个 GitHub issue 可以在不同 flow 中有不同 role
- `flow_state.task_issue_number` 只存 role=`task` 的 issue

---

## 真源设计

```
✅ SQLite flow_issue_links.issue_role (唯一真源)
   - 只定义本地 flow <-> issue 绑定中的角色
   - 只保存最小运行时绑定事实
  - 由 vibe3 flow bind 写入

❌ GitHub vibe-task label (同步副作用)
  - 用于 GitHub 视角过滤
  - 只能由自动化根据 issue_role 镜像
  - 不是判断 task 的真源

❌ 本地缓存 GitHub Project / Issue 远端字段
   - Status / Priority / Assignees / title / body 等远端字段应按需读取现场
   - 不应作为长期本地真源持久化
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

### 统一入口原则

```bash
# 相关关系
vibe3 flow bind 219 --role related

# 依赖关系
vibe3 flow bind 218 --role dependency
```

说明：
- Issue 与 Flow 的角色关系统一由 `flow bind` 表达

**约束**：
1. 一个 flow 只有一个 task 指针，重复 `flow bind <issue>` 会覆盖 `flow_state.task_issue_number`
2. 当前 CLI 以本地 SQLite 为准，不把 GitHub label 当真源
3. 后续标签自动化必须由 `issue_role` 单向镜像，不能反向生成 role
4. labels / milestones / assignees 等远端写操作优先使用 `gh`，不在本地 CLI 中重复包装

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
# 查看所有活跃 flow（总览入口）
vibe3 task status

# 查看 flow 完整信息
vibe3 flow show --branch task/my-feature

# 输出示意：
task_issue: #220
related_issues:
   - #219
dependencies:
   - #218
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
   - 本地数据库只保留本地绑定事实
   - 自动化失败不能反向污染本地 role

4. ✅ **远端字段按需读取**
   - GitHub Issue / Project 远端字段默认现场读取
   - 不为展示便利把远端字段长期落地到本地

5. ✅ **联动操作服从 issue_role**
   - PR merge / 标签镜像 / 后续规则判断都应从 issue_role 出发

---

## 术语规范

### ✅ 正确说法

- "将 issue #220 绑定为当前 flow 的 task"
- "issue #219 在这个 flow 中是 related"
- "issue #218 在这个 flow 中是 dependency"

### ❌ 错误说法

- "创建一个 task issue"
- "task issue 和 GitHub issue 是两种类型"
- "vibe-task 标签是真源"

---

**参考文档**：
- [v3/command-standard.md](v3/command-standard.md)
- [github-labels-standard.md](github-labels-standard.md)
- [glossary.md](glossary.md)
