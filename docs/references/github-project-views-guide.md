# GitHub Project Views Guide

**最后更新**: 2026-03-22
**状态**: Reference
**定位**: GitHub Project 视图方案参考。用于把 label 状态机映射成可观察 UI，不定义新的真源。

---

## 1. 这份文档解决什么

这份文档回答的是：

- GitHub Project 应该如何展示多 agent 编排状态
- Project 里哪些字段可以用，哪些字段不能当真源
- 为什么 Project 只能是 UI，而不能成为第三套状态机

这份文档不解决：

- label 名称标准
- issue-role 标准
- handoff 文件格式
- snapshot / diff 数据模型

这些分别由：

- [github-labels-standard.md](../standards/github-labels-standard.md)
- [issue-standard.md](../standards/issue-standard.md)
- [github-label-agent-orchestration-target.md](../prds/github-label-agent-orchestration-target.md)

---

## 2. 核心原则

### 2.1 真源分层

- GitHub issue：任务身份真源
- SQLite `flow_issue_links.issue_role`：issue 与 flow 的关系真源
- GitHub `state/*` labels：编排状态真源
- handoff：交接上下文，不是真源
- GitHub Project：可视化 UI，不是真源

### 2.2 Project 不做什么

Project 不能负责：

- 定义任务当前状态
- 定义 issue 是 `task` 还是 `related`
- 存储 handoff 正文
- 维护一套独立于 labels 的状态字段

如果 Project 字段和 labels 冲突，以 labels 为准。

### 2.3 为什么不能直接用 label 分栏

根据 GitHub 官方 Project 文档，Board 视图可以按**自定义字段**分组，但**不能按 labels 分组**。  
因此，如果要在 Board 里稳定显示流程列，就需要一个**由 labels 单向镜像出的派生字段**。

这意味着：

- `labels` 仍然是真源
- `Flow Lane` 之类的 Project 字段只是 UI 镜像
- 不允许人工直接把 Project 列拖拽当成状态变更真源

---

## 3. 推荐字段设计

### 3.1 必需字段

#### A. Labels

- 直接消费 GitHub issue / PR labels
- 是筛选与自动加项的重要依据

#### B. Assignees

- 表达当前人类或 agent 的拥有者
- 不替代状态机

#### C. Flow Lane

```yaml
字段名称: Flow Lane
类型: Single Select
定位: 仅 UI 镜像字段
来源: 由自动化根据 state/* label 单向映射
```

建议选项：

```yaml
- Ready
- Claimed
- In Progress
- Blocked
- Handoff
- In Review
- Merge Ready
- Done
```

### 3.2 可选字段

#### Priority

- 可镜像 `priority/*`
- 便于排序，不参与状态裁定

#### Type

- 可镜像 `type/*`
- 用于区分 feature/fix/docs 等工作类型

#### Agent

- 可选 Text / Single Select 字段
- 仅用于 UI 展示当前执行 agent
- 真正交接说明仍在 handoff

### 3.3 不推荐字段

以下字段如果存在，必须标记为 legacy 或逐步移除：

- `Status` 作为人工维护的主状态字段
- `Task State` 作为另一套流程字段
- 任意人工可拖拽即改义的列字段

原因很简单：它们会和 `state/*` labels 构成双真源。

---

## 4. 推荐视图方案

### 4.1 Flow Board

**用途**：主编排看板，观察 issue 当前位于哪个 flow 阶段。

**布局建议**：

```yaml
视图类型: Board
分组字段: Flow Lane
筛选:
  - is:issue
  - -is:closed
显示字段:
  - Labels
  - Assignees
  - Priority
  - Agent
```

**说明**：

- 这是最重要的视图
- 只看 issue，不把 PR 混进主板
- 所有列都来自 label 到 `Flow Lane` 的单向镜像

### 4.2 Blocked / Handoff Queue

**用途**：单独观察需要人工介入或需要交接的项。

**布局建议**：

```yaml
视图类型: Table
筛选:
  - label:"state/blocked" OR label:"state/handoff"
显示字段:
  - Title
  - Labels
  - Assignees
  - Agent
  - Updated
```

**说明**：

- 这是运维视图，不是主流程视图
- 目标是回答“现在哪里堵住了”

### 4.3 Review / Merge Queue

**用途**：观察哪些 issue 已进入 review 或 ready-to-merge。

**布局建议**：

```yaml
视图类型: Table
筛选:
  - label:"state/review" OR label:"state/merge-ready"
显示字段:
  - Title
  - Labels
  - Assignees
  - Linked pull requests
```

### 4.4 PR View

**用途**：观察 PR 生命周期，但不替代 issue 的编排状态机。

**布局建议**：

```yaml
视图类型: Table
筛选:
  - is:pr
  - -is:closed
显示字段:
  - Title
  - Labels
  - Reviewers
  - Assignees
```

**说明**：

- PR 是交付出口，不是主编排对象
- 编排状态仍以 issue labels 为主

### 4.5 Intake / Triage View

**用途**：查看还没有进入 flow 状态机的 issue。

**布局建议**：

```yaml
视图类型: Table
筛选:
  - is:issue
  - -is:closed
  - -label:"state/ready"
  - -label:"state/claimed"
  - -label:"state/in-progress"
  - -label:"state/blocked"
  - -label:"state/handoff"
  - -label:"state/review"
  - -label:"state/merge-ready"
  - -label:"state/done"
```

**说明**：

- 这不是执行视图
- 它只用来回答“哪些 issue 还没被纳入编排”

---

## 5. 标签到 Project 字段的映射

### 5.1 状态映射

| Label | Flow Lane | 含义 |
|------|-----------|------|
| `state/ready` | `Ready` | 可认领 |
| `state/claimed` | `Claimed` | 已认领，待进入执行 |
| `state/in-progress` | `In Progress` | 执行中 |
| `state/blocked` | `Blocked` | 阻塞 |
| `state/handoff` | `Handoff` | 待交接 |
| `state/review` | `In Review` | 待 review |
| `state/merge-ready` | `Merge Ready` | 可合并 |
| `state/done` | `Done` | 已完成 |

### 5.2 分类映射

| Labels | Project 字段建议 |
|--------|------------------|
| `type/*` | `Type` |
| `priority/*` | `Priority` |
| `scope/*` | 可直接显示在 Labels 中 |
| `component/*` | 可直接显示在 Labels 中 |

### 5.3 关系标签映射

| 真源 | GitHub 标签 | Project 用法 |
|------|-------------|--------------|
| `issue_role = task` | `vibe-task` | 便于筛选执行项 |
| `issue_role = dependency` | `vibe-task` | 便于筛选执行项 |
| `issue_role = related` | 无镜像 | 只作为关系，不作为主执行项 |

---

## 6. 自动化建议

### 6.1 内建 Workflows 的适用范围

GitHub Project 内建 workflows 适合：

- 自动把符合条件的 issue / PR 加入 Project
- 在 close / merge 时更新派生字段
- 在特定 label 组合下归档项目项

不适合：

- 直接裁定复杂状态迁移
- 替代 handoff 检查
- 从 Project 字段反推回 labels 真源

### 6.2 推荐自动化方向

#### A. Auto-add

根据 GitHub 官方文档，Project 的 Auto-add 支持 `is`、`label`、`assignee`、`reason` 等过滤条件。  
推荐只自动加入以下对象：

- 带 `vibe-task` 的 issue
- 带 `state/*` 状态标签的 issue
- 活跃 PR

#### B. Label -> Flow Lane 镜像

自动化职责：

1. 读取 issue 的 `state/*` label
2. 找出唯一状态标签
3. 把 `Flow Lane` 更新为对应值

限制：

- 只能单向镜像
- 不允许把 `Flow Lane` 反向回写为 labels

#### C. Done / Archive

可使用 GitHub 内建规则：

- issue / PR closed -> `Flow Lane = Done`
- merged PR -> `Flow Lane = Done`
- 已完成项可自动归档

但注意：

- 真正的编排完成仍应以 issue labels 与 merge/close 规则共同裁定
- 归档是 UI 操作，不是业务真相

---

## 7. 运维约束

1. 一个 issue 在任一时刻只应有一个 `state/*` 标签。
2. 任何人工调整 Project 列位，都应视为 UI 修复，不应代替标签变更。
3. 如果 `Flow Lane` 与 labels 冲突，先修 labels，再让自动化重放。
4. Project 中不要写 handoff 正文，只展示链接或摘要。
5. Project 不负责表达 `task/related/dependency` 关系细节。

---

## 8. 推荐最小落地版本

第一版只做：

1. Auto-add 把执行中的 issue / PR 加入 Project
2. 建立 `Flow Lane` 派生字段
3. 让 `state/*` labels 单向镜像到 `Flow Lane`
4. 建立 3 个核心视图：
   - Flow Board
   - Blocked / Handoff Queue
   - Review / Merge Queue

暂时不要做：

- 用 Project 字段反向改 labels
- 在 Project 中定义第二套状态
- 在 Project 中沉淀执行正文

---

## 9. 参考来源

以下 GitHub 官方文档支撑了本方案的关键判断：

- [Filtering projects](https://docs.github.com/enterprise-cloud%40latest/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/filtering-projects)
- [Customizing the board layout](https://docs.github.com/enterprise-cloud%40latest/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/customizing-the-board-layout)
- [Adding items automatically](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/adding-items-automatically)
- [Automating your project](https://docs.github.com/issues/planning-and-tracking-with-projects/automating-your-project)
