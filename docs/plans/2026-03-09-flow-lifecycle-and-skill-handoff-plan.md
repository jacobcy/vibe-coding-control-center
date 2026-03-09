---
title: Flow Lifecycle and Skill Handoff Alignment Plan
date: 2026-03-09
status: in_progress
owner: Codex
---

# 目标

统一 `flow` shell 能力、Git 工作流标准、以及 `vibe-commit` / `vibe-integrate` / `vibe-done` 三个 skill 的职责边界，使以下链路可验证且不混层：

- 串行提交
- 串行 PR 整合
- PR 合并后的 flow 收口
- task / issue / branch / flow 历史的 handoff
- `.agent/context/task.md` 的跨 skill 上下文归档

## 非目标

- 不把 `gh issue close`、`git branch -d`、`git push --delete` 等外围动作塞进 `vibe flow` 里
- 不让 shell 命令自动修复异常中间态
- 不在本计划中重做 roadmap / task 数据模型
- 不在本计划中重构整个 `vibe` dispatcher

# 推荐分层

## 结论

不要把所有内容继续堆进 [git-workflow-standard.md](/Users/jacobcy/src/vibe-center/wt-fix-pr-base-selection/docs/standards/git-workflow-standard.md)。

推荐拆成三层：

1. `docs/standards/git-workflow-standard.md`
   - 只定义交付 workflow 语义
   - 回答何时 `new`、何时 `switch`、何时 `done`
   - 定义 `open + no_pr` / `open + had_pr` / `closed` 这类 lifecycle 状态
   - 定义 `show` / `status` / `list` 的用途差异

2. `docs/standards/worktree-lifecycle-standard.md`
   - 只定义物理目录与 flow 关闭后的关系
   - 说明 worktree 复用、branch 关闭、历史留存之间的边界
   - 明确 shell 只暴露原子能力，不关闭 issue，不补 task，不做自动修复

3. `docs/standards/command-standard.md` + `docs/standards/data-model-standard.md`
   - 定义 shell 命令契约与 `flow-history.json` 的高层职责
   - 说明 `vibe flow new/switch/show/status/list/done` 的输入、输出、阻断条件、历史留存规则

4. skill 文档
   - `skills/vibe-commit/SKILL.md`
   - `skills/vibe-integrate/SKILL.md`（新增）
   - `skills/vibe-done/SKILL.md`
   - 只负责编排：何时调用 `vibe task update`、`gh issue close`、`git branch -d`、`git push origin --delete`
   - 明确每个 skill 完成后如何把摘要写入 `.agent/context/task.md`

## 原因

- `git-workflow-standard.md` 当前已经偏“交付语义真源”，不适合继续塞太多 shell 参数与状态机细节
- shell 命令契约若写进 workflow 标准，会再次把 workflow、shell、skill 混层
- “最佳实践”不建议单独再开第四份标准；skill 的执行最佳实践应直接写在 skill 文档里，否则会形成第四套重复真源

# Tech Stack

- Zsh shell modules: `lib/flow*.sh`, `bin/vibe`
- Markdown standards and skills
- Shared state under `$(git rev-parse --git-common-dir)/vibe/*`
- Git / GitHub CLI
- Bats tests

# 待修改文件

## 文档

- Modify: `docs/standards/git-workflow-standard.md`
- Modify: `docs/standards/worktree-lifecycle-standard.md`
- Modify: `docs/standards/command-standard.md`
- Modify: `docs/standards/data-model-standard.md`
- Modify: `skills/vibe-commit/SKILL.md`
- Create: `skills/vibe-integrate/SKILL.md`
- Modify: `skills/vibe-done/SKILL.md`

## Shell

- Modify: `lib/flow.sh`
- Modify: `lib/flow_help.sh`
- Modify: `lib/flow_status.sh`
- Create or Modify: `lib/flow_show.sh` 或等价实现文件

## Tests

- Modify: `tests/test_flow.bats`
- Modify: `tests/test_vibe.bats`（如帮助输出受影响）

## Context

- Modify: `.agent/context/task.md`（记录本轮完成的标准/skill 变更摘要与后续 handoff 指针）

# 任务拆分

## Task 1: 固化标准分层

1. 在 `git-workflow-standard.md` 中补 lifecycle 语义：
   - `flow new` 不得创建“当前存在或历史存在过”的 feature
   - `flow switch` 只允许进入 `open + no_pr`
   - `open + had_pr` 是需交给 skill 收口的中间态
   - `show` / `status` / `list` 的职责差异
2. 在 `worktree-lifecycle-standard.md` 中定义：
   - flow 关闭后目录与 branch 的关系
   - 历史留存与物理目录清理的边界
3. 在 `command-standard.md` / `data-model-standard.md` 中定义：
   - flow 历史留存
   - `had_pr` 与 `had_commits` 的区别
   - `done` 只关闭 flow 并删除 branch，不关闭 task / issue

## Task 2: 补齐 shell 原子能力

1. 为 `flow` 增加单 flow 详情入口：
   - `vibe flow show [<feature>]`
   - 默认当前 flow
   - 输出 task / issue / pr / branch / close state / history state
2. 收敛 `status`：
   - 只显示未关闭 flow 的大盘
3. 收敛 `list`：
   - 显示所有 flow，包括历史
4. 收敛 `new` / `switch` / `done`：
   - `new`：存在则提示 `switch`；存在过则报错
   - `switch`：若 `had_pr=true` 则阻断
   - `done`：只接受已完成 PR 的 flow，关闭 flow、保留历史、关闭本地/远端 branch

## Task 3: 三个 skill 对齐

1. `vibe-commit`
   - 只负责串行 commit 与 PR 草案 / 发起
   - 不负责批量 merge，不负责收口 issue / task
2. `vibe-integrate`
   - 负责串行 PR 编排
   - 检查 CI、review threads、堆叠顺序
   - 必要时驱动用户或 shell 做 follow-up
   - 不直接修改共享真源 JSON
3. `vibe-done`
   - 读取 `flow show`
   - 若 flow 绑定 task，则调用 `vibe task update ...`
   - 若 task 绑定 issue，则调用 `gh issue close`
   - 调用 `vibe flow done`
   - 补充 branch 清理后的总结与 `.agent/context/task.md` 归档说明

## Task 4: `.agent/context/task.md` handoff 规则

1. 为三个 skill 定义统一的存档格式：
   - 本轮完成了什么
   - 当前 flow / task / PR / issue 的状态
   - 下一 skill 读取时需要的入口
2. 明确 `.agent/context/task.md` 是短期上下文归档，不是共享真源
3. skill 文档中统一写明：
   - 开始前读取 `.agent/context/task.md`
   - 结束后追加或更新对应小节

# 验证命令

```bash
bats tests/test_flow.bats
bats tests/test_vibe.bats
bin/vibe flow --help
bin/vibe flow show --help
bin/vibe flow status --help
bin/vibe flow list --help
```

如新增了 `show` 子命令的 JSON 输出，再补：

```bash
bin/vibe flow show --json
```

# 预期结果

- shell 层和 skill 层边界不再冲突
- `flow new/switch/show/status/list/done` 的语义互不重叠
- 已发过 PR 但未关闭的 flow 会被 shell 明确识别，并交由 skill 收口
- 已关闭 flow 会留存在历史中，阻断同名 feature 被再次 `new`
- 三个 skill 的 handoff 都能在 `.agent/context/task.md` 中找到上一环节摘要

# 风险与停止条件

## 风险 1: shell 越权变成 workflow engine

- 表现：`flow done` 自动关闭 issue / task，或偷偷修复异常中间态
- 对策：把外围动作严格保留在 skill 中
- 停止条件：如果实现需要 shell 代替 skill 决策，停止执行并回到讨论阶段

## 风险 2: “存在过” 无稳定真源

- 表现：删除分支后无法判断 feature 是否存在过
- 对策：先设计 flow 历史留存模型，再落命令
- 停止条件：若没有稳定历史记录字段，先补数据模型再动命令

## 风险 3: `show` / `status` / `list` 再次语义重叠

- 表现：三个命令都能展示相近集合，导致 skill 无法稳定调用
- 对策：在标准中先写清集合范围和默认过滤

# 变更规模预估

- 文件数：约 10 到 12 个
- 文档：约 `+220/-40`
- shell：约 `+140/-50`
- tests：约 `+120/-20`
- skill：约 `+160/-80`

# 建议执行顺序

1. 先改标准文档，锁定语义
2. 再补 shell 能力和测试
3. 最后修改三个 skill
4. 收尾时更新 `.agent/context/task.md`
