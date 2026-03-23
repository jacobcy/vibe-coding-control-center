# GitHub 标签标准

**维护者**: Vibe Team
**最后更新**: 2026-03-22
**状态**: Active

---

## 1. 目标

这份标准定义 GitHub labels 在 V3 中承担的职责。

目标不是“给 issue 多打几个标签”，而是建立三层清晰语义：

1. 分类标签：说明这是什么工作
2. 关系镜像标签：说明这个 issue 是否是执行项
3. 编排状态标签：说明当前处于 flow 循环的哪一阶段

---

## 2. 真源边界

### 2.1 真源分层

- GitHub issue：任务身份真源
- SQLite `flow_issue_links.issue_role`：issue 与 flow 的关系真源
- GitHub `state/*` labels：编排状态真源
- GitHub `vibe-task`：关系镜像标签，不是真源
- GitHub Project：UI，不是真源

### 2.2 基本原则

1. 标签可以镜像真源，但不能反向改义。
2. `task/related/dependency` 是关系，不是状态。
3. `state/*` 是状态，不是类型。
4. 不允许再引入 `repo` 旧语义。

---

## 3. 标签分层

### 3.1 分类标签

分类标签用于描述工作属性，不参与状态机裁定。

### 类型标签

| 标签名称 | 描述 |
|---------|------|
| `type/feature` | 新功能 |
| `type/fix` | Bug 修复 |
| `type/refactor` | 重构 |
| `type/docs` | 文档 |
| `type/test` | 测试 |
| `type/chore` | 杂项 |
| `type/task` | 综合型任务 |

### 优先级标签

| 标签名称 | 描述 |
|---------|------|
| `priority/high` | 高优先级 |
| `priority/medium` | 中优先级 |
| `priority/low` | 低优先级 |

### 范围标签

| 标签名称 | 描述 |
|---------|------|
| `scope/python` | Python 改动 |
| `scope/shell` | Shell 改动 |
| `scope/documentation` | 文档改动 |
| `scope/infrastructure` | 基础设施 |
| `scope/skill` | Skill 改动 |
| `scope/supervisor` | agent/workflow/rules 改动 |

### 组件标签

| 标签名称 | 描述 |
|---------|------|
| `component/cli` | CLI 入口 |
| `component/flow` | Flow 相关 |
| `component/task` | Task 相关 |
| `component/pr` | PR 相关 |
| `component/client` | Client 层 |
| `component/config` | 配置层 |

### 3.2 关系镜像标签

### `vibe-task`

`vibe-task` 是执行项镜像标签。

它的职责只有一个：让 GitHub / Project 视角能快速筛出“被纳入 flow 管理的执行 issue”。

映射规则：

| `issue_role` | `vibe-task` |
|--------------|-------------|
| `task` | 应添加 |
| `dependency` | 应添加 |
| `related` | 不添加 |

重要约束：

- `vibe-task` 不能作为 task 真源
- `vibe-task` 不能反推出 `issue_role`
- 标签自动化失败时，不能改写本地 role

### 3.3 编排状态标签

编排状态标签是多 agent 协作的远端状态机真源。

### 状态集合

| 标签名称 | 含义 |
|---------|------|
| `state/ready` | 可认领 |
| `state/claimed` | 已认领，待进入执行 |
| `state/in-progress` | 执行中 |
| `state/blocked` | 阻塞中 |
| `state/handoff` | 待交接 |
| `state/review` | 待 review |
| `state/merge-ready` | 已满足合并条件 |
| `state/done` | 已完成 |

### 状态机约束

1. 一个 issue 任一时刻只能有一个 `state/*` 标签。
2. 状态变更优先发生在 issue 上，而不是 Project 字段上。
3. Project 只能镜像 `state/*`，不能定义第二套状态。
4. handoff 负责解释状态，label 负责表示状态。

---

## 4. 状态迁移规则

### 4.1 推荐主链

```text
state/ready
  -> state/claimed
  -> state/in-progress
  -> state/handoff
  -> state/review
  -> state/merge-ready
  -> state/done
```

### 4.2 允许的旁路

- `state/in-progress -> state/blocked`
- `state/blocked -> state/in-progress`
- `state/review -> state/in-progress`
- `state/handoff -> state/in-progress`

### 4.3 不允许的跳转

以下跳转默认视为异常，需要人工确认：

- `state/ready -> state/done`
- `state/claimed -> state/done`
- `state/blocked -> state/done`
- 同时存在多个 `state/*`

---

## 5. Agent 协作规则

### 5.1 认领

agent 认领 issue 时：

1. 确认当前是 `state/ready`
2. 更新为 `state/claimed`
3. 写入或更新 assignee / handoff 最小上下文

### 5.2 执行

进入实际修改后：

1. 从 `state/claimed` 进入 `state/in-progress`
2. 持续更新 handoff
3. 保持 `state/*` 单值

### 5.3 阻塞

当 agent 无法继续推进时：

1. 切换到 `state/blocked`
2. handoff 中必须写明阻塞原因和下一步

### 5.4 交接

当任务需要换手时：

1. 切换到 `state/handoff`
2. handoff 必须完整
3. 接手方读取 handoff 后再进入 `state/in-progress`

### 5.5 Review 与完成

1. 待 review 时使用 `state/review`
2. 达到可合并条件时使用 `state/merge-ready`
3. 真正完成后进入 `state/done`

---

## 6. 与 issue-role 的关系

### 6.1 关系与状态是两层语义

| 层 | 真源 | 例子 |
|----|------|------|
| 关系层 | SQLite `issue_role` | `task / related / dependency` |
| 状态层 | GitHub `state/*` labels | `ready / blocked / review` |

### 6.2 不能混写

错误示例：

- 把 `dependency` 当成一种状态
- 把 `review` 当成一种 issue 类型
- 用 `vibe-task` 表达 “现在正在执行”

正确示例：

- `issue_role = dependency` + `state/blocked`
- `issue_role = task` + `state/in-progress`

---

## 7. 历史标签处理

### 7.1 旧 `status/*` 标签

旧文档中的以下标签不再作为编排真源：

- `status/blocked`
- `status/in-progress`
- `status/ready-for-review`
- `status/wip`

处理原则：

1. 不再把 `status/*` 作为流程状态标准
2. 后续自动化应迁移到 `state/*`
3. 如仓库已有旧标签，可保留一段过渡期，但不能继续写入新逻辑

### 7.2 `repo` 旧语义

- 历史 `repo -> related` 迁移必须先完成
- 不允许新增任何依赖 `repo` 的标签或规则

---

## 8. 自动化要求

1. 自动化只消费统一后的 `task/related/dependency` 和 `state/*`。
2. `issue_role -> vibe-task` 是单向镜像。
3. `state/* -> Project Flow Lane` 是单向镜像。
4. 自动化失败不得修改本地 role。
5. 自动化补偿必须幂等。

---

## 9. 最小落地版本

第一阶段必须落地的标签只有两组：

1. `vibe-task`
2. `state/*`

其余 `type/*`、`priority/*`、`scope/*`、`component/*` 保持现有分类能力即可。

---

## 10. 术语规范

### 正确说法

- “给 issue 加 `state/in-progress`，表示正在执行”
- “给 issue 镜像 `vibe-task`，表示它是执行项”
- “`issue_role` 决定关系，`state/*` 决定阶段”

### 错误说法

- “`vibe-task` 就是 task 真源”
- “Project 列位就等于状态真源”
- “`dependency` 就是 blocked”
- “`status/wip` 继续作为标准流程标签”
