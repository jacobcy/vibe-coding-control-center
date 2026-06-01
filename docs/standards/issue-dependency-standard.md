# Issue 依赖关系与 Scope 拆分标准

**维护者**: Vibe Team
**最后更新**: 2026-05-26
**状态**: Active
**文档类型**: 标准

---

## 1. 目标

本文档定义**Issue 依赖关系管理、Scope 拆分决策模型、Epic/RFC 标签语义、Comment marker 约定**的权威标准。

**本文档回答的问题**:
- Issue 依赖关系的真源是什么？
- Scope 拆分的两个窗口是什么，如何判定？
- `roadmap/epic` 和 `roadmap/rfc` 标签的语义区别是什么？
- 各角色的 comment marker 有哪些约定？
- `task status` 命令如何展示 RFC/Epic issues？

**本文档不回答的问题**:
- 有哪些标签？→ 见 [github-labels-reference.md](github-labels-reference.md)
- 标签如何管理？→ 见 [roadmap-label-management.md](roadmap-label-management.md)
- 具体命令怎么用？→ 见 [v3/command-standard.md](v3/command-standard.md)

---

## 2. 依赖关系真源 (Truth Source)

### 2.1 依赖关系的权威来源

Issue 依赖关系由**两个互补源**共同定义：

1. **数据库层**：`flow_issue_links` 表
   - 存储本地 SQLite 中的 issue-flow 绑定关系
   - 包含 `blocked_by` 字段，记录阻塞依赖链
   - 由 `vibe3 flow bind` 自动维护

2. **GitHub 层**：Issue body 的 `## Dependencies` section
   - 人类可读的依赖关系声明
   - 用于跨仓库依赖、外部系统依赖等场景
   - 由 agent 或人工手动维护

**优先级规则**：
- 本地执行引擎（manager、plan/run agents）优先读取 `flow_issue_links`
- 跨系统可见性（GitHub Projects、外部工具）依赖 `## Dependencies` section
- 两者应保持一致，若冲突以 `flow_issue_links` 为准

### 2.2 依赖关系的表示约定

**数据库层格式**（`flow_issue_links.blocked_by`）：
```json
{
  "blocked_by": [123, 456],  // issue numbers
  "blocked_reason": "等待 #123 完成 API 设计"
}
```

**GitHub 层格式**（Issue body）：
```markdown
## Dependencies

- Blocked by #123 (API 设计完成)
- Blocked by #456 (数据库迁移)
```

---

## 3. Scope 拆分决策模型（两个窗口）

### 3.1 拆分窗口概述

Issue Scope 拆分有**两个明确的时间窗口**，超出窗口后禁止拆分：

| 窗口 | 角色 | 触发条件 | 决策权 |
|------|------|----------|--------|
| **窗口 1: Roadmap 阶段** | Roadmap decider | Issue 在 `roadmap/*` 状态，未进入 `state/ready` | 可拆分 / 继续单 issue / 标记 `roadmap/rfc` |
| **窗口 2: Manager 阶段** | Manager | Issue 从 `state/ready` → `state/claimed` 前 | 可拆分 / 继续单 issue |
| **关闭** | Plan/Run/Review | Issue 已进入 `state/claimed` | **禁止拆分** |

### 3.2 窗口 1：Roadmap 阶段

**触发条件**：Issue 有 `roadmap/*` 标签，尚未进入执行状态（`state/ready` 及之后）。

**决策者**：Roadmap decider（可能是 governance observer 或 manager）。

**决策选项**：
1. **继续单 issue**：Issue 范围合理，无需拆分
2. **拆分为 Epic + Sub-issues**：
   - 创建 sub-issues，主 issue 添加 `roadmap/epic` 标签
   - 主 issue 成为治理容器，不进入执行状态
   - Sub-issues 独立进入执行流程
3. **标记为 RFC**：若无法判断目标、架构方向、拆分形态，添加 `roadmap/rfc`，等待人类输入

**Comment marker**：
```
[roadmap decision] <决策内容>
```

**示例**：
```
[roadmap decision] Issue #456 范围过大，拆分为 #457, #458, #459。主 issue #456 标记为 epic。
```

### 3.3 窗口 2：Manager 阶段

**触发条件**：Issue 在 `state/ready`，manager 准备 claim 前。

**决策者**：Manager agent。

**决策选项**：
1. **继续单 issue**：直接 claim，进入 plan 阶段
2. **拆分**：
   - 调用 `check_scope_split_before_plan()` 判断是否需要拆分
   - 若需要，创建 sub-issues，主 issue 添加 `roadmap/epic`
   - 写 `[manager]` comment 说明拆分理由
   - 主 issue 不进入 `state/claimed`

**硬性规则**：
- **一旦 `state/claimed` 被设置，拆分窗口永久关闭**
- Plan、Run、Review agents **必须**按单 issue 执行，不得拆分
- 若发现 scope 过大，应记录 finding 并在 review 阶段提出

**Comment marker**：
```
[manager] <拆分说明>
```

**示例**：
```
[manager] Scope 拆分：#123 范围过大，拆分为 #124 (API 设计), #125 (实现), #126 (测试)。主 issue #123 保持治理容器。
```

### 3.4 Epic 主 Issue 的治理容器角色

当主 issue 被标记为 `roadmap/epic` 时：

- **主 issue**：作为治理容器，不进入执行状态（不 claim、不 plan、不 run）
- **Sub-issues**：独立进入执行流程，各自有独立的 flow、plan、run、review
- **主 issue 的职责**：
  - 追踪整体进度（通过 sub-issues 的状态）
  - 提供上下文和背景说明
  - 在 `task status` 的 `Roadmap Epic` section 中展示

---

## 4. Epic/RFC 标签语义

### 4.1 `roadmap/epic` 标签

**定义**：主 issue 有 Sub-issues，作为治理容器。

**语义**：
- **结构维度**：表示 issue 有 parent-child 关系
- **主 issue 职责**：治理容器，不直接执行
- **Sub-issues 职责**：独立执行单元

**何时添加**：
- Roadmap decider 判定需要拆分
- Manager 在 claim 前判定需要拆分

**何时移除**：
- 若 sub-issues 被合并回主 issue（罕见情况）
- 若主 issue 本身进入执行状态（sub-issues 已完成或取消）

**参考**：[github-labels-reference.md](github-labels-reference.md#roadmap-labels)

### 4.2 `roadmap/rfc` 标签

**定义**：Issue 处于 RFC/设计阶段，agent 无法判断目标、架构方向或拆分形态。

**语义**：
- **讨论维度**：表示需要人类输入设计方案
- **阻塞原因**：缺少明确的目标、架构决策、或拆分策略

**何时添加**：
- Roadmap decider 发现 scope 不清晰、目标不明确
- Agent 尝试拆分但无法确定合理的子任务边界
- 需要人类决策架构方向（技术选型、接口设计等）

**何时移除**：
- 人类提供明确的设计方案（通过 comment）
- 人类明确指出不需要拆分（单 issue 即可）
- Issue 进入执行阶段（`state/claimed`）

**与 `roadmap/epic` 的关系**：
- 一个 issue 可以**同时**有 `roadmap/epic` 和 `roadmap/rfc`
- 示例：Epic 主 issue 需要人类判断如何拆分 sub-issues

**参考**：[roadmap-label-management.md](roadmap-label-management.md#epic-vs-rfc)

---

## 5. Comment Marker 约定

### 5.1 Marker 的作用

Comment marker 用于区分自动化评论和人类指令，确保系统能准确识别：

- **自动化评论**：由 agent 产生，带 marker（如 `[manager]`、`[governance]`）
- **人类指令**：由真实人类账号产生，不带 marker

### 5.2 常用 Marker 列表

| Marker | 角色 | 用途 |
|--------|------|------|
| `[manager]` | Manager | 状态转换、质量判断、拆分说明、阻塞汇报 |
| `[roadmap decision]` | Roadmap decider | Scope 拆分决策、Epic/RFC 标记决定 |
| `[governance suggest]` | Governance observer | 治理建议、恢复建议、routing 建议 |
| `[plan]` | Planner | Plan 完成、范围澄清 |
| `[run]` | Executor | Run 完成、执行结论 |
| `[review]` | Reviewer | Review 裁决、合并建议 |

### 5.3 格式要求

**强制格式**：
```
[<marker>] <主要内容>
```

**示例**：
```
[manager] Issue #123 拆分为 #124, #125。主 issue 保持治理容器。
```

```
[roadmap decision] Issue #456 需要人类判断架构方向，标记为 RFC。
```

```
[governance suggest] 建议恢复 Issue #789：authoritative plan_ref 已存在。
```

**禁止格式**：
- ❌ `Manager: ...` （无方括号）
- ❌ `请尽快合并 [manager]` （marker 不在行首）
- ❌ `评论里嵌入 [manager] 字样作引用` （装饰性使用）

**参考**：[supervisor/manager.md](../../supervisor/manager.md#comment-contract)

---

## 6. `task status` 展示规范

### 6.1 RFC/Epic 独立展示

`task status` 命令应将 RFC 和 Epic issues 独立展示，不混入常规 `Blocked Issues` section。

**展示位置**：
```
Roadmap RFC:
  # 975  BLOCKED     Converge main-path skills onto existing vibe3 infrastructure
         flow: task/issue-975
  #1086  BLOCKED     [Meta] 上层 prompt 材料对依赖关系与 scope 拆分的支持升级
         flow: task/issue-1086

Roadmap Epic:
  (none)

Blocked Issues:
  # 898  BLOCKED     Enhancement: add state boundary protection to pr-code-analys...
         flow: task/issue-898
         reason: required ref missing: report_ref
```

### 6.2 过滤逻辑

**RFC Items**：
- 包含 `roadmap/rfc` 标签的 issues
- 显示在 `Roadmap RFC` section
- **不显示**在 `Blocked Issues` section

**Epic Items**：
- 包含 `roadmap/epic` 标签的 issues
- 显示在 `Roadmap Epic` section
- **不显示**在 `Blocked Issues` section

**Blocked Items**：
- 状态为 `BLOCKED` 且**不包含** `roadmap/rfc` 或 `roadmap/epic` 标签
- 显示在 `Blocked Issues` section

### 6.3 显示信息

每个 RFC/Epic issue 显示：
- Issue number
- State（如 `BLOCKED`、`IN-PROGRESS`）
- Title（截断至 60 字符）
- Flow branch（如果有）

**未来增强**：
- Epic issues 可显示 sub-issues 列表和进度
- RFC issues 可显示阻塞原因（需要人类输入的具体内容）

---

## 7. 跨文档引用

本文档与以下标准协同工作：

- **标签定义**：[github-labels-reference.md](github-labels-reference.md)
- **标签管理**：[roadmap-label-management.md](roadmap-label-management.md)
- **术语表**：[glossary.md](glossary.md)
- **Manager 行为规范**：[supervisor/manager.md](../../supervisor/manager.md)
- **Governance 规范**：[vibe3-role-checks-and-balances-standard.md](vibe3-role-checks-and-balances-standard.md)

---

## 8. 变更历史

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2026-05-26 | 1.0 | 初始版本，定义依赖真源、两窗口拆分模型、Epic/RFC 语义、Comment marker、`task status` 展示规范 |
