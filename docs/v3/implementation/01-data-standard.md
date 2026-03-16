---
document_type: standard
title: Data Standard - Handoff Store Architecture
status: draft
author: Claude Sonnet 4.6
created: 2026-03-16
last_updated: 2026-03-16
related_docs:
  - docs/standards/glossary.md
  - docs/v3/plans/02-flow-task-foundation.md
  - docs/v3/implementation/02-architecture.md
---

# 数据标准 - Handoff Store 架构澄清

> **目的**: 澄清 SQLite Handoff Store 的职责边界，解决文档中的语义冲突。

---

## 核心原则（强制）

### 真源层级

```
GitHub 层（唯一真源 - gh CLI 直接访问）
├── GitHub Project Items (task, feature, bug) - 规划层真源
├── GitHub Issues (repo issue) - 来源层真源
├── GitHub PRs (pr) - 交付层真源
└── Git Branches (flow 身份锚点)

本地层（执行记录 - 责任链索引）
├── SQLite Handoff Store (.git/vibe3/handoff.db) - 执行过程记录
│   ├── handoff 记录（plan/execute/review 三阶段）
│   ├── 规范文件引用（spec ref）
│   ├── agent 署名（谁做了什么）
│   └── 追责记录（问题、决策、解决方案）
├── .agent/context/task.md - v2 兼容 handoff
└── PR metadata (注入到 PR description) - 过程记录
```

### 职责边界

**SQLite Handoff Store 存储**:
- ✅ **Handoff 记录**：plan ref, execute report, review report
- ✅ **执行记录**：做了什么操作、什么时候做的
- ✅ **规范引用**：遵循了哪些规范文件
- ✅ **署名记录**：哪个 agent、哪个 model 执行的
- ✅ **追责记录**：遇到什么问题、如何解决、谁负责
- ❌ **不存储** GitHub Project 数据镜像
- ❌ **不存储** PR 缓存数据
- ❌ **不存储** Task 状态（状态在 GitHub Project）

**包装原则**:
- ✅ git 命令能做的 → 只包装，不缓存
- ✅ gh CLI 能做的 → 只包装，不缓存
- ✅ PR 数据 → 从 gh api 实时读取
- ✅ Task 状态 → 从 gh project item 实时读取
- ❌ 任何业务数据 → 不做本地缓存

**追责与审计**:
- 本地 handoff store 的核心价值是**追责**和**审计**
- 每条记录必须包含：agent、model、timestamp、操作内容
- 发生问题时，可以追溯到具体 agent、具体决策、具体规范引用

---

## 文档冲突修正清单

### 🔴 严重冲突（必须立即修正）

#### 1. `docs/v3/plans/02-flow-task-foundation.md` 第34行

**错误**:
```markdown
| 本地存储 | SQLite Handoff Store | ✅ **唯一真源** |
```

**修正**:
```markdown
| 本地存储 | SQLite Handoff Store | 责任链索引（非真源） |
```

**原因**: 真源在 GitHub Project，SQLite 只是 handoff 索引。

---

#### 2. `docs/v3/execution_plan/implementation-spec-phase3-draft.md` 第154行

**错误**:
```markdown
**状态收口**:
- 更新 SQLite task 状态为 `completed`
```

**修正**:
```markdown
**状态收口**:
- 更新 GitHub Project task 状态为 `completed`（通过 GitHub API）
- 记录 handoff 信息到 SQLite（merge 证据、agent 署名）
```

**原因**: Task 状态真源在 GitHub Project，SQLite 只记录 handoff。

---

#### 3. `docs/v3/plans/v3-rewrite-plan.md` 第41行

**错误**:
```markdown
**Objective**: Implement CRUD logic for Flows and Tasks using SQLite.
```

**修正**:
```markdown
**Objective**: Implement handoff store for Flow's three-phase process (plan/execute/review).
```

**原因**: "CRUD logic" 暗示缓存业务对象，实际是记录 handoff。

---

### ⚠️ 模糊表达（需要澄清）

#### 4. `docs/v3/plans/README.md` 第139行

**当前**:
```markdown
- `vibe check` 负责核对本地 handoff store 与远端真源是否一致
```

**建议补充**:
```markdown
- `vibe check` 负责核对本地 handoff store 与远端真源是否一致
  - 远端真源：GitHub Project Items, GitHub Issues, GitHub PRs
  - 本地索引：SQLite handoff store 只记录责任链，不缓存业务状态
```

---

#### 5. `docs/v3/plans/03-pr-domain.md` 第23行

**当前**:
```markdown
- [ ] `Vibe3Store` can successfully write/read from SQLite.
```

**建议补充**:
```markdown
- [ ] `Vibe3Store` can successfully write/read handoff records from SQLite.
  - SQLite stores handoff info only (plan ref, execute report, review report)
  - PR data fetched from GitHub API in real-time
  - No PR caching in SQLite
```

---

## 实现指导

### PR Domain 实现原则

```python
# ✅ 正确：PR 只作为指针，实时读取
def pr_show(pr_number: int) -> None:
    pr_data = github_client.get_pr(pr_number)  # 实时读取
    handoff = store.get_flow_handoff(branch)    # 读取 handoff 索引
    render_pr_with_handoff(pr_data, handoff)

# ❌ 错误：缓存 PR 数据到 SQLite
def pr_show_wrong(pr_number: int) -> None:
    pr_data = store.get_cached_pr(pr_number)  # 不要缓存 PR！
    render_pr(pr_data)
```

### Handoff 记录结构

```sql
-- ✅ 正确：记录 handoff 信息
CREATE TABLE flow_handoff (
    flow_branch TEXT PRIMARY KEY,
    plan_ref TEXT,           -- plan 文档引用
    execute_report TEXT,     -- execute 报告
    review_report TEXT,      -- review 报告
    agents TEXT,             -- agent 署名历史
    issues TEXT,             -- 遇到的问题
    created_at TEXT,
    updated_at TEXT
);

-- ❌ 错误：缓存 GitHub 数据
CREATE TABLE pr_cache (      -- 不要创建这种表！
    pr_number INTEGER,
    title TEXT,
    state TEXT,
    ...
);
```

---

## 审计检查清单

在实现 Phase 3 之前，请逐项确认：

- [ ] 所有文档中的"唯一真源"已修正为"责任链索引"
- [ ] 所有提到"缓存 PR/Task 数据"的地方已删除或标注为错误示例
- [ ] 实现代码中没有创建 `pr_cache` 或 `task_cache` 表
- [ ] Client 层只包装 git/github 命令，不做本地缓存
- [ ] Service 层调用 Client 实时读取，不依赖本地缓存

---

## 参考文档

- **[docs/standards/glossary.md](../../standards/glossary.md)** - 术语真源
- **[docs/v3/plans/02-flow-task-foundation.md](../plans/02-flow-task-foundation.md)** - Phase 2 计划
- **[docs/v3/implementation/02-architecture.md](../implementation/02-architecture.md)** - 架构设计

---

**维护者**: Vibe Team
**最后更新**: 2026-03-16