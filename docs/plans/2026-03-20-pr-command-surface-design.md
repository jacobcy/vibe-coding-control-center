# PR Command Surface Design

**Date:** 2026-03-20
**Status:** Approved for planning
**Branch:** `codex/pr-command-surface`

---

## Goal

收敛 `vibe3 pr` 命令面，使其只保留有项目包装价值的交付动作，并修正 `task / flow / pr / review` 之间的职责边界。

## Design Anchor

术语与主链以以下真源为准：

- [glossary.md](/Users/jacobcy/src/vibe-center/wt-claude-v3/docs/standards/glossary.md)
- [git-workflow-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-v3/docs/standards/v3/git-workflow-standard.md)

本轮采用的主链表达：

`repo issue -> task issue -> flow new/bind -> pr create -> pr ready -> review pr -> integrate -> flow done -> close repo issue`

其中：

- `task` 负责目标治理
- `flow` 负责现场治理
- `pr` 负责交付承载与发布状态
- `review` 负责审查动作
- `integrate` / `done` 承担合并与收口，不由 `pr` 直接承载

## Responsibility Split

### `task`

`task` 吸收 `repo issue`，完成分合、依赖、主闭环 issue 指定与 execution record 建立。

`task` 不负责：

- branch 现场
- PR 状态切换
- merge / closeout

### `flow`

`flow` 是对 branch 的逻辑现场包装，表达当前交付切片。

`flow` 必须保留的动作：

- `flow new`
- `flow bind`
- `flow status`
- `flow show`
- `flow list`
- `flow done`

`flow` 不负责：

- PR 创建
- PR ready / merge
- review gate
- issue intake

### `pr`

`pr` 是 task 实现产物的交付承载，不是 workflow engine，也不是 GitHub CLI 的镜像包装。

`pr` 只保留以下公开命令：

- `pr create`
- `pr ready`
- `pr show`

设计理由：

- `create` 有项目包装价值：从当前 flow / task / branch 语境构造 draft PR。
- `ready` 有项目包装价值：从 draft 切换到 ready，并承载本项目质量门禁。
- `show` 有项目包装价值：快速显示 PR 状态、CI、comments、risk summary。

## Commands To Remove

### Remove `pr draft`

原因：

- `draft` 是 `create` 的模式，不是独立对象动作。
- 单独保留 `pr draft` 会强化“我们在包装 GitHub CLI”的误导。

收敛后应改为：

- `vibe3 pr create`

### Remove `pr merge`

原因：

- merge 属于整合与收口动作，不属于 `pr` 命令域。
- merge 的判断往往依赖 CI、review、stacked PR、closeout 语义，应该交给 integrate / done / skill。

### Remove `review-gate` From This PR Scope

原因：

- `review-gate` 是 hook / CI 的内部胶水，不是用户主命令。
- 顶层暴露会打乱原有命令体系。
- 放进 `hooks` 也不合适，因为 `hooks` 的职责是 enable / disable，不是执行 gate。

收敛原则：

- 不暴露 `review-gate`
- `pre-push.sh` 直接使用 `inspect` + `review` 现有链路

## `pr show` Scope

`pr show` 保留，但只承担“交付承载视图”。

推荐输出：

- PR 基本状态
- draft / ready 状态
- CI / checks 摘要
- review comments / reviews 摘要
- inspect 风险摘要

`pr show` 不负责：

- 执行 review
- 切换 ready 状态
- merge

## Internal Entry Strategy

对 hook / CI 内部能力，采用以下原则：

- 公开 CLI 只暴露用户稳定入口
- hook 内部调用改走模块函数或内部 Python 入口
- 不为内部脚本单独扩张顶层命令面

## Next PR Scope

下一轮 PR 聚焦 `pr` 命令面治理，只做：

1. 收敛 `pr` 公开命令到 `create / ready / show`
2. 删除 `pr merge`
3. 把 `pr draft` 重命名/迁移为 `pr create`
4. 移除 `review-gate`，不在本轮保留内部入口
5. 更新 handoff 与帮助文案

不做：

- merge 策略重构
- integrate 命令全面设计
- flow/task 大规模重写

## Handoff Note

下一位 agent 接手时，应以本设计和实现计划为准，不再重新讨论：

- 是否保留 `pr draft`
- 是否保留 `pr merge`
- 是否保留 `review-gate`

这些结论在本设计中已固定。
