# GitHub 标签标准

**维护者**: Vibe Team
**最后更新**: 2026-06-03
**状态**: Active
**文档类型**: 标准规范

---

## 1. 目标

本文档定义 GitHub labels 的**语义标准**和**真源规则**。

**本文档回答的问题**:
- 标签的语义是什么？（为什么用）
- 标签的真源边界是什么？（何时用）
- 标签的状态机规则是什么？（怎么用才对）

**本文档不回答的问题**:
- 有哪些标签？→ 见 [github-labels-reference.md](github-labels-reference.md)
- 如何用标签管理 roadmap？→ 见 [roadmap-label-management.md](roadmap-label-management.md)
- 具体命令怎么用？→ 见 [v3/command-standard.md](v3/command-standard.md)

---

## 2. 真源边界

### 2.1 真源分层

| 层级 | 真源 | 说明 |
|------|------|------|
| GitHub issue | 任务身份真源 | 所有工作项都是 GitHub issue |
| SQLite `flow_issue_links.issue_role` | issue 与 flow 的关系真源 | 本地存储，离线可用 |
| GitHub `state/*` labels | 编排状态真源 | 多 agent 协作状态 |
| GitHub `roadmap/*` labels | 路线图规划真源 | 迭代规划状态 |
| GitHub `priority/*` labels | 优先级真源 | 优先级排序 |
| GitHub `vibe-task` | 可视化辅助标签 | 辅助 Project 视图识别 Flow 任务 |
| GitHub Project | UI 展示 | 不是真源 |

### 2.2 基本原则

1. **标签可以镜像真源，但不能反向改义**
2. **`task/related/dependency` 是关系，不是状态**
3. **`state/*` 是状态，不是类型**
4. **`roadmap/*` 是规划，不是执行状态**
5. **`priority/*` 是优先级，不是规划**
6. 不允许再引入 `repo` 旧语义

---

## 3. 标签语义标准

### 3.1 标签分类语义

#### 类型标签 (type/*)

**语义**: 说明"这是什么工作"

**使用原则**:
- 每个 issue 应该有且只有一个 `type/*` 标签
- 用于分类和统计
- 不参与状态机裁定

#### 优先级标签 (priority/*)

**语义**: 说明"多紧急"

**使用原则**:
- 每个 issue 应该有一个 `priority/*` 标签
- `priority/high` = 核心功能、关键 bug 修复
- `priority/medium` = 重要但非紧急的功能
- `priority/low` = 优化、改进等非关键任务
- 优先级与 roadmap 状态独立

#### 范围标签 (scope/*)

**语义**: 说明"影响范围"

**使用原则**:
- 可选标签
- 用于过滤和分类
- 可以有多个

#### 组件标签 (component/*)

**语义**: 说明"涉及哪个组件"

**使用原则**:
- 可选标签
- 用于责任划分
- 可以有多个

### 3.2 路线图标签语义 (roadmap/*)

**语义**: 说明"何时做"

**使用原则**:
- 路线图标签表示规划窗口
- 与优先级标签配合使用
- 一个 issue 只能有一个 `roadmap/*` 标签

| 标签 | 语义 | 决策标准 |
|------|------|----------|
| `roadmap/p0` | 当前迭代必须完成 | 阻断性问题、核心功能 |
| `roadmap/current` | 当前迭代规划中 | 已进入当前开发计划 |
| `roadmap/next` | 下个迭代规划中 | 待确认的功能 |
| `roadmap/deferred` | 已推迟 | 暂不处理，保留在积压池 |
| `roadmap/rejected` | 已拒绝 | 不再处理，通常伴随 issue 关闭 |

**重要约束**:
- 路线图标签表示"何时做"
- 优先级标签表示"多紧急"
- 一个 issue 可以同时有 `roadmap/p0` 和 `priority/high`
- `roadmap/deferred` 表示暂时延期，不占用当前迭代容量

### 3.3 可视化辅助标签语义

#### `vibe-task`

**语义**: Flow bind 自动化镜像标签

**职责**: 让 GitHub 视图能通过标签快速识别"曾被 vibe3 flow bind 管理的 issue"。

**真源与映射规则**:
- **生命周期绑定**：由 `vibe3 flow bind` 在 issue 进入 flow 时自动添加；在 `vibe3 flow unbind` 或 flow 销毁时自动移除。
- **单向镜像**：标签仅作为 SQLite `flow_issue_links` 真源记录的远端展示。
- **非控制位**：不作为 governance 或执行引擎的判定依据。
- **手动操作后果**：手动添加/移除此标签不会改变 issue 的执行角色。系统在下次同步时会尝试根据真源状态纠正此标签。

#### `orchestra-governed`

**语义**: 治理决策镜像标签 (Governance Review Mark)

**职责**: 辅助 governance (assignee-pool) 识别已完成池内评估（priority/roadmap/epic 判定）的 issue。

**规则**:
- **决策触发**：由 `assignee-pool` 扫描并做出实质性决策（如设置 `state/ready`、`roadmap/rfc` 等）后添加。
- **过滤依据**：governance 扫描时会过滤掉已持有此标签的 issue，避免重复评估。
- **与 vibe-task 区别**：
  - `vibe-task` 是 **自动化副作用**，表示 issue "正在/曾被" flow 绑定。
  - `orchestra-governed` 是 **治理状态**，表示 issue "已通过" 治理审查。
  - 严禁混用。

#### `orchestra-scanned`

**语义**: Intake 审查镜像标签 (Intake Review Mark)

**职责**: 辅助 governance (roadmap-intake) 识别已完成 Level 1 审查但未进入执行池（通常是跳过或拒绝）的 issue。

**规则**:
- **触发**：由 `roadmap-intake` 审查后决定跳过或拒绝时添加。
- **过滤依据**：intake 扫描时会过滤掉已持有此标签的 issue。

#### `roadmap-reviewed`

**语义**: Roadmap 终审镜像标签 (Roadmap Review Mark)

**职责**: 辅助 governance (vibe-roadmap) 识别已完成 Level 3 终审决策的 issue。

**规则**:
- **触发**：由 `vibe-roadmap` 在发布 `[roadmap decision]` 评论后同步添加。
- **角色**：治理体系的终态标记，表示决策已固化并写入 memory，Step 0 自动跳过。

#### 三层治理联动

- `orchestra-scanned`: Level 1 intake 审查标记。
- `orchestra-governed`: Level 2 assignee-pool 决策标记。
- `roadmap-reviewed`: Level 3 roadmap 终审标记。


### 3.4 编排状态标签语义 (state/*)

**语义**: 说明"当前处于 flow 循环的哪一阶段"

**使用原则**:
- **状态镜像**：编排状态标签是多 agent 协作的远端状态机镜像。
- **真源位置**：本地 SQLite `flow_state` 表是执行状态的绝对真源。
- **自动同步**：由 `vibe3` 在状态迁移事件发生时自动更新 GitHub 标签。
- **单值约束**：一个 issue 任一时刻只能有一个 `state/*` 标签。
- **同步方向**：状态变更应通过 flow 命令触发（如 `vibe3 flow move`），然后由系统同步到标签，而非通过修改标签来改变执行态。

| 标签名称 | 语义 | 使用场景 |
|---------|------|----------|
| `state/ready` | 可认领 | 任务可认领 |
| `state/claimed` | 已认领，待进入执行 | 已认领，准备执行 |
| `state/in-progress` | 执行中 | 正在执行 |
| `state/blocked` | 阻塞中 | 被阻塞，无法继续 |
| `state/failed` | (已弃用) 执行失败 | **不再建议使用**。请迁移至 `active` + `blocked_reason` 或 `state/blocked` |
| `state/handoff` | 待交接 | 需要交接 |
| `state/review` | 待 review | 等待 review |
| `state/merge-ready` | 已满足合并条件 | 可合并 |
| `state/done` | 已完成 | 已完成 |

> **注意**：`failed` 状态字面值已从核心模型中移除。目前的失败语义由 `active` 状态配合 `blocked_reason` 表达，或在基础设施错误时触发 `FailedGate`（由 Orchestra 监控）。

#### 状态机约束

1. 一个 issue 任一时刻只能有一个 `state/*` 标签
2. 状态变更优先发生在 issue 上，而不是 Project 字段上
3. Project 只能镜像 `state/*`，不能定义第二套状态
4. handoff 负责解释状态，label 负责表示状态

#### 状态迁移规则

**推荐主链**:

```text
state/ready
  -> state/claimed
  -> state/in-progress
  -> state/handoff
  -> state/review
  -> state/merge-ready
  -> state/done
```

**允许的旁路**:

- `state/in-progress -> state/blocked`
- `state/blocked -> state/in-progress`
- `state/review -> state/in-progress`
- `state/handoff -> state/in-progress`

**不允许的跳转**:

以下跳转默认视为异常，需要人工确认：

- `state/ready -> state/done`
- `state/claimed -> state/done`
- `state/blocked -> state/done`
- 同时存在多个 `state/*`

---

## 4. Agent 协作规则

Agent 执行生命周期的状态变迁遵循**事件驱动架构**。Agent 本身负责发布领域事件，由统一的事件处理器负责执行实际的 GitHub 标签更新。

### 4.1 认领

agent 认领 issue 时：

1. 确认当前是 `state/ready`
2. 发布事件通知状态迁移意图
3. 处理器更新标签为 `state/claimed`
4. 写入或更新 assignee / handoff 最小上下文

### 4.2 执行

进入实际修改后：

1. 发布事件从 `state/claimed` 进入 `state/in-progress`
2. 处理器更新标签为 `state/in-progress`
3. 持续更新 handoff
4. 保持 `state/*` 单值

### 4.3 阻塞

当 agent 无法继续推进时：

1. 发布 `IssueBlocked` 事件
2. 处理器切换标签到 `state/blocked`
3. handoff 中必须写明阻塞原因和下一步

### 4.4 交接

当任务需要换手时：

1. 发布阶段完成事件（如 `PlanCompleted`）
2. 处理器切换标签到 `state/handoff`
3. handoff 必须完整
4. 接手方（如 Manager）在 `state/handoff` 自动恢复后读取 handoff，决定下一步迁移

### 4.5 Review 与完成

1. 待 review 时使用 `state/review`
2. review 成功后发布 `ReviewCompleted` 事件，处理器自动生成最小 audit_ref 并迁移状态
3. 达到可合并条件时进入 `state/merge-ready`
4. 真正完成后进入 `state/done`

---

## 5. 与 issue-role 的关系

### 5.1 关系与状态是两层语义

| 层 | 真源 | 例子 |
|----|------|------|
| 关系层 | SQLite `issue_role` | `task / related / dependency` |
| 规划层 | GitHub `roadmap/*` labels | `p0 / p1 / p2` |
| 优先级层 | GitHub `priority/*` labels | `high / medium / low` |
| 状态层 | GitHub `state/*` labels | `ready / blocked / review` |

### 5.2 不能混写

**错误示例**:

- 把 `dependency` 当成一种状态
- 把 `review` 当成一种 issue 类型
- 用 `vibe-task` 表达 "现在正在执行"
- 用 `vibe-task` 作为治理审查标记（应使用 `orchestra-governed`）
- 把 `roadmap/p0` 等同于 `priority/high`

**正确示例**:

- `issue_role = dependency` + `state/blocked`
- `issue_role = task` + `state/in-progress`
- `roadmap/p0` + `priority/high` + `state/in-progress`

---

## 6. 历史标签处理

### 6.1 旧 `status/*` 标签

旧文档中的以下标签不再作为编排真源：

- `status/blocked`
- `status/in-progress`
- `status/ready-for-review`
- `status/wip`

**处理原则**:

1. 不再把 `status/*` 作为流程状态标准
2. 后续自动化应迁移到 `state/*`
3. 如仓库已有旧标签，可保留一段过渡期，但不能继续写入新逻辑

### 6.2 `repo` 旧语义

- 历史 `repo -> related` 迁移必须先完成
- 不允许新增任何依赖 `repo` 的标签或规则

---

## 7. 自动化要求

1. 自动化只消费统一后的 `task/related/dependency` 和 `state/*`
2. `issue_role -> vibe-task` 是单向镜像
3. `state/* -> Project Flow Lane` 是单向镜像
4. `roadmap/*` 和 `priority/*` 由人工或 governance skill 管理
5. 自动化失败不得修改本地 role
6. 自动化补偿必须幂等

---

## 8. 最小落地版本

第一阶段必须落地的标签只有两组：

1. `vibe-task`
2. `state/*`

其余 `type/*`、`priority/*`、`scope/*`、`component/*`、`roadmap/*` 保持现有分类能力即可。

---

## 9. 参考文档

- [github-labels-reference.md](github-labels-reference.md) - 标签速查手册（有哪些标签）
- [roadmap-label-management.md](roadmap-label-management.md) - 如何使用标签管理 roadmap
- [v3/command-standard.md](v3/command-standard.md) - 共享状态命令与状态同步标准
- [issue-standard.md](issue-standard.md) - Issue 标准
- [../../AGENTS.md](../../AGENTS.md) - 项目导览与操作手册
- [v3/handoff-store-standard.md](v3/handoff-store-standard.md) - Handoff 存储标准
