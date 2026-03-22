# 文档整理总结

**日期**: 2026-03-22

---

## 一、最终文档结构

### 1. 标准文档 (`docs/standards/`)

| 文档 | 标题 | 内容 |
|------|------|------|
| `glossary.md` | 术语表 | 项目术语定义 |
| `issue-standard.md` | Issue 标准 | Issue 概念、Issue Role 定义 |
| `github-labels-standard.md` | GitHub 标签标准 | Issue 和 PR 标签体系 |
| `task-flow-guide.md` | Task & Flow 操作标准 | 命令使用指南 |

### 2. 改动计划 (`docs/plans/`)

| 文档 | 标题 | 内容 |
|------|------|------|
| `2026-03-22-vibe3-task-management-changes.md` | Task 管理修改计划 | 参数命名修改方案 |

---

## 二、已删除的中间文档

| 文档 | 删除原因 |
|------|----------|
| `docs/updates/issue-concept-unification.md` | 概念已统一到标准文档 |
| `docs/plans/2026-03-22-flow-show-vs-task-show.md` | 分析已合并到 task-flow-guide.md |
| `docs/plans/2026-03-22-second-truth-source-analysis.md` | 分析已合并到 issue-standard.md |
| `docs/plans/2026-03-22-task-show-command-issue.md` | 分析已合并到 task-flow-guide.md |
| `docs/plans/2026-03-22-vibe3-task-management-analysis.md` | 分析已合并到修改计划 |
| `docs/plans/2026-03-22-vibe3-task-management-target.md` | 设计目标已合并到标准文档 |

---

## 三、文档职责

### 标准文档

- **性质**: 最终确定的标准和规范
- **维护**: 长期维护，随概念演进更新
- **用户**: 所有项目成员

### 改动计划

- **性质**: 具体的修改方案和实施步骤
- **维护**: 完成实施后可归档或删除
- **用户**: 开发人员

---

## 四、文档链接更新

需要更新以下文档中的引用：

- ✅ [CLAUDE.md](../../CLAUDE.md) - 更新术语真源引用
- ✅ [docs/standards/glossary.md](../standards/glossary.md) - 更新内部引用

---

## 五、总结

**原则**: 只保留最终标准和改动计划，删除中间分析文档

**结果**:
- 4 个标准文档（glossary, issue-standard, github-labels-standard, task-flow-guide）
- 1 个改动计划（task-management-changes）
- 6 个中间文档已删除