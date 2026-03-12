---
document_type: plan
title: draft pr state flow plan
status: proposed
scope: flow-pr-state-machine
author: Codex GPT-5
created: 2026-03-12
last_updated: 2026-03-12
related_docs:
  - docs/standards/command-standard.md
  - docs/standards/git-workflow-standard.md
  - docs/standards/glossary.md
  - docs/plans/2026-03-11-roadmap-projects-sync-plan.md
  - docs/plans/2026-03-10-shared-state-github-project-alignment-plan.md
  - lib/flow.sh
  - lib/task.sh
  - lib/roadmap.sh
---

# Goal

为 `vibe flow bind`、GitHub Project 状态同步、Draft PR 创建时机建立统一决策，避免 execution 层与 roadmap mirror 层再次混线。

# Non-Goals

- 本文不直接实现 shell 命令或 GitHub API 调用。
- 本文不重写现有 `roadmap sync` 规划层 contract。
- 本文不定义完整 PR body 模板或 walkthrough 生成细节。

# Tech Stack

- Zsh shell CLI (`bin/vibe`, `lib/*.sh`)
- GitHub Issue / Pull Request / Project
- task / flow runtime shared state

---

## Current Assessment

当前讨论里其实有两个问题，不应混成一个动作：

1. `bind` 之后，execution record 是否立刻进入 `in_progress`
2. 什么时候出现可供 review 的 `pr`

现有标准已经足够明确两点：

1. `bind` 是 execution 层绑定动作，默认不应被继续口头扩展成“隐式做一切”。
2. `roadmap sync` 是规划层 mirror，同步 GitHub Project item，不负责 task 拆分、flow 编排或 PR 发布。

因此，如果要把线上看板联动做实，应该把它定义为：

- `task/flow` 生命周期事件触发的 GitHub bridge
- 不是把 execution 状态硬塞进 `roadmap sync`

## Options

### 方案 A: Draft on Bind

`vibe flow bind` 立即：

- task `status -> in_progress`
- GitHub Project item `status -> In Progress`
- 自动创建 Draft PR

优点：

- 透明度最高
- 团队能立刻看到谁接手了哪个 task

缺点：

- PR 列表噪音最大
- 会产生大量“尚无代码事实”的空 Draft PR
- 把 `bind` 从“绑定”推高为“绑定 + 发布”，语义过重

### 方案 B: Draft on First Commit or First Push

`vibe flow bind` 只做：

- task `status -> in_progress`
- GitHub Project item `status -> In Progress`

首次 `vibe commit` 且 push 成功后：

- 自动创建 Draft PR
- 自动把 PR 加入 GitHub Project
- 可附带 walkthrough 摘要

优点：

- PR 出现时已经存在代码事实
- 保持 Vibe 的早反馈，不必等到“完全做完”
- 噪音显著低于空 PR 直播模式

缺点：

- `bind` 到首交之间，PR 维度不可见
- 若用户长期本地提交但不 push，线上仍只看到 Issue / Project 状态

### 方案 C: Manual Draft PR

`bind` 只更新 task / Project 状态；只有显式执行 `vibe flow pr --draft` 时才创建 PR。

优点：

- 干扰最低
- 兼容传统开发习惯

缺点：

- Vibe 的连续反馈被延后
- 很容易把 review 入口拖到太晚
- 无法把“AI 已经开始形成代码方向”及时暴露给团队

## Recommendation

推荐 **方案 B 作为默认行为**，并保留 **方案 A 作为显式可选开关**。

原因：

1. Vibe 强调 review 前置，但 review 前置不等于“空 PR 前置”。
2. `bind = in_progress` 应立即成立，因为这表达的是 execution ownership，而不是 review readiness。
3. Draft PR 的最佳默认触发点应是“第一次有可审查代码事实”。
4. 对极度强调直播透明度的团队，可再提供显式模式，例如：
   - `vibe flow bind <task-id> --draft-pr`
   - 或 repo 级配置 `flow.draft_pr_on_bind=true`

## State Mapping

建议把“任务执行态”和“PR 审查态”拆开，不要只靠一个 Project Status 字段硬扛全部语义。

### 主状态机

1. `bind`
   - 本地 task: `in_progress`
   - GitHub Project status: `In Progress`
   - PR: 无

2. `first commit + push`
   - 自动创建 Draft PR
   - GitHub Project status: 仍为 `In Progress`
   - PR state: `Draft`

3. `ready for review`
   - 触发条件：`gh pr ready`、`vibe flow pr --ready`、或显式请求 reviewer
   - GitHub Project status: `In Review`
   - PR state: `Open`

4. `review follow-up`
   - 若 reviewer 要求修改：Project status 可保持 `In Review` 或回到 `In Progress`
   - 推荐：
     - 有未解决 review threads / requested changes 时：`In Progress`
     - 已重新提交并再次请求 review：`In Review`

5. `merge`
   - task: `completed`
   - GitHub Project status: `Done`
   - flow: `closed`

### 关键判断

最重要的一条是：

- **Draft PR 不等于 In Review**

否则看板会丢失“正在做”与“等待审查”的区分。

## Sync Responsibility

不建议新增一个泛化的 `vibe roadmap push` 来承接 execution 状态。

原因：

1. `roadmap` 在标准里是规划层。
2. 你这里要同步的是 task / flow / pr 生命周期，不是 roadmap window。
3. 若继续往 `roadmap` 塞 execution 语义，后续命令边界会再次漂移。

推荐做法：

1. 在 `vibe flow bind` 成功后触发 GitHub bridge：
   - 更新关联 issue / project item 到 `In Progress`
2. 在第一次成功 `vibe commit` 且 push 后触发 Draft PR bridge：
   - 若当前 flow 尚无 `pr_ref`，创建 Draft PR
3. 在 `vibe flow pr --ready` 或等价动作时：
   - 切换 Draft -> Ready for review
   - Project item `In Progress -> In Review`
4. 在 merge 后由 `vibe-integrate` / `vibe flow done` 收口：
   - task `completed`
   - Project item `Done`

实现形态上更像：

- `task update` / `flow bind` / `flow pr` 的 provider hook
- 或内部 helper：`_github_project_sync_task_state`
- 而不是新的 roadmap 顶层职责

## Expected Result

- `bind` 立即表达 ownership
- Draft PR 尽早出现，但基于真实代码事实
- `In Progress` 与 `In Review` 的看板语义清晰
- `roadmap sync` 仍保持规划层纯度

## Change Summary

- Modified: 0 files
- Added: 1 file
- Approximate lines: 140
