---
document_type: standard
title: Git Workflow Standard
status: active
scope: git-delivery
authority:
  - flow-pr-process
  - delivery-splitting
  - recovery-rules
author: Codex GPT-5
created: 2026-03-08
last_updated: 2026-03-09
related_docs:
  - SOUL.md
  - CLAUDE.md
  - docs/standards/glossary.md
  - docs/standards/action-verbs.md
  - docs/standards/command-standard.md
  - docs/standards/worktree-lifecycle-standard.md
---

# Git Workflow Standard

本文档定义本项目的 Git 交付流程标准，重点回答：

- `roadmap -> task -> flow -> PR` 应如何推进
- `flow`、`branch`、`worktree` 在交付中的职责如何分离
- 何时继续当前 flow
- 何时必须新开 branch / 新开 flow
- 何时必须进入整合或收口，而不是继续开发
- 现场偏离标准后，如何回归标准 flow

术语以 [glossary.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/glossary.md) 为准。高频动作词以 [action-verbs.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/action-verbs.md) 为准。物理目录生命周期见 [worktree-lifecycle-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/worktree-lifecycle-standard.md)。

## 1. Scope

本文档只定义：

- 交付流程语义
- `flow` 与 `PR` 的默认对应关系
- `branch` 在交付切片中的使用规则
- 偏离标准场景下的恢复动作

本文档不重写：

- 共享状态命令语义
- `worktree` 的物理创建、复用与清理细节
- shell 自动化设计

## 2. Core Model

默认交付模型如下：

- `roadmap` 负责规划窗口与优先级
- `task` 负责可执行单元
- `flow` 负责当前交付切片
- `pr` 负责当前交付产物
- `branch` 负责承载当前交付切片的 Git 提交线
- `worktree` 只是物理容器，不是 flow 本体

默认关系：

- 一个 `flow` 对应一个当前交付目标
- 一个当前交付目标默认对应一个当前 `pr`
- 一个 `flow` 默认绑定一个当前 `branch`
- 一个 `worktree` 可以承载当前 `flow`，但 `flow` 不等于目录

因此：

- 开下一个 `flow` 的关键是切换到新的交付目标与新的 `branch`
- 不要求必须新建 `worktree`
- 但不得让同一个 `flow` 同时承载多个当前 `pr` 目标
- 复用当前目录串行进入下一个 `flow` 时，应显式执行 flow 切换，而不是把旧 `flow` 继续伪装成新目标

## 3. Flow Lifecycle States

标准 flow 生命周期只分三类：

- `open + no_pr`
  - flow 已打开
  - 当前 branch 尚未形成 PR 事实
  - 允许继续开发
  - 允许通过 `vibe flow switch` 重新进入
- `open + had_pr`
  - flow 尚未关闭
  - 当前 branch 已经形成 PR 事实
  - 不再允许当作普通开发 flow 重新进入
  - 应交由 `vibe-integrate` 或同类 skill 处理 review、CI、merge 与收口 handoff
- `closed`
  - flow 已完成并进入历史
  - 不允许再次 `new` 同名 flow
  - 不允许复用同名 branch 语义重新发 PR

命令语义对应：

- `show`：查看单个 flow 的当前或历史详情
- `status`：只看未关闭 flow 大盘
- `list`：看所有 flow，包括已关闭历史

## 4. Happy Path

标准路径如下：

1. 从 `roadmap` 选择当前要推进的 `roadmap item`
2. 将目标拆成一个或多个 `task`
3. 为当前这轮交付创建或进入一个 `flow`
4. 让该 `flow` 绑定本轮要交付的 `task`
5. 在该 `flow` 对应的 `branch` 上提交本地 commit
6. 执行 `review`
7. 提交 `pr`
8. 进入整合阶段，直到该 `pr` 可合并
9. 合并后收尾并结束当前 `flow`

执行要求：

- 同一 `flow` 内的 commit 应服务同一个当前交付目标
- 若一组 commit 已经不再服务当前目标，应停止继续堆在该 `flow`
- `done` 只应发生在当前交付目标已经完成或明确废弃之后

## 5. Flow Decision Rules

### 5.1 Continue Current Flow

继续当前 `flow` 的条件：

- 仍然服务同一个当前交付目标
- 仍然准备进入同一个当前 `pr`
- 当前 `branch` 语义仍与该交付目标一致
- 新改动只是 review follow-up、补测试、补文档或同一目标下的必要修正

补充约束：

- 若当前 flow 仍处于 `open + no_pr`，可以继续正常开发
- 若当前 flow 已进入 `open + had_pr`，只能继续处理该 PR 的 follow-up 或整合阻塞
- 不得把 `open + had_pr` 的 flow 当作“下一个新目标”的开发现场继续复用

### 5.2 Open a New Flow

以下情况必须新开下一个 `flow`：

- 新改动应进入另一个 `pr`
- 当前交付目标被另一个独立交付目标阻塞
- 当前 `flow` 中已经混入多个 feature，决定拆成多个 `pr`
- 当前 `pr` 已经提交，而剩余改动属于下一个目标而非当前 review follow-up

默认恢复动作：

- 保留上层 `roadmap item` / `issue`
- 将新的交付切片切到新的 `branch`
- 让新的 `flow` 对应新的当前 `pr` 目标
- 若复用当前目录，使用 `vibe flow switch` 一类显式 flow 切换能力进入新 `flow`

补充语义：

- `vibe flow switch (shell)` 默认应安全携带当前目录的未提交改动进入目标 flow；这属于该命令的基础语义，而不是额外开关
- `vibe flow new (shell)` 仍可保持更保守的默认值，由显式参数决定是否带入未提交改动

`flow new` / `flow switch` 的准入规则：

- 若同名 flow 当前存在，`new` 必须拒绝，并提示 `switch`
- 若同名 flow 历史存在过且已关闭，`new` 必须直接报错
- `switch` 只允许进入 `open + no_pr`
- 已经 `had_pr` 但未关闭的 flow，不允许通过 `switch` 继续，应交给 skill 处理

## 6. Exception Paths

### 6.1 `A flow` 被 `B task` 阻塞

场景：

- 原本计划推进 `A`
- 发现 `A` 必须依赖 `B`
- `B` 需要单独合并，不能继续混在 `A` 的 `pr`

标准动作：

1. 将 `A` 标记为 `blocked`
2. 冻结当前 `A flow`，不再继续在其语义下提交 `B`
3. 为 `B` 新开一个 `flow` 与 `branch`
4. 在 `B flow` 中完成、review、提 `pr`
5. `B` 合并后，再重新开启或恢复 `A`

禁止：

- 在名义上属于 `A` 的 `flow` / `branch` 中直接提交 `B` 的独立 `pr`
- 用同一个当前 `flow` 同时承载 `A` 与 `B` 两个当前交付目标

### 6.2 `pr` 已提交，但现场仍有未提交改动

分两种情况：

- 若这些改动仍属于当前 `pr` 的 review follow-up：继续当前 `flow`
- 若这些改动已经属于下一个交付目标：必须新开下一个 `flow`

判断标准：

- 同一个 `pr` 的修订，继续当前 `flow`
- 不应进入当前 `pr` 的新 feature、新切片、新目标，不得继续留在当前 `flow`

默认恢复动作：

1. 识别未提交改动是否仍属于当前 `pr`
2. 若属于当前 `pr`，继续当前 `branch`
3. 若不属于当前 `pr`，切换到新的 `flow` / `branch`
4. 让剩余改动在新的交付语义下继续推进

补充规则：

- `pr` 已提交但 flow 未关闭时，该 flow 属于 `open + had_pr`
- 此时若需要检查 CI、处理 review、等待合并或补 follow-up，应进入整合阶段，而不是新开同名 flow
- 若该 PR 已完成且相关 follow-up 已收束，应进入 `vibe-done` 或等价收口流程

### 6.3 一个 `flow` 中做了不同 feature，想拆成多个 `pr`

场景：

- 当前 `flow` 已经混入多个 feature
- 一个 `pr` 不利于 review 或 merge

标准动作：

1. 先按交付目标重新分组 task
2. 当前 `flow` 只保留其中一个当前 `pr` 目标
3. 其他 feature 必须切到新的 `flow` 与新的 `branch`
4. 每个新的交付切片各自 review、提 `pr`

禁止：

- 继续把“多个 feature、多个 `pr` 目标”写在同一个当前 `flow` 中
- 用一个当前 `flow` 依次冒充多个当前 `pr` 目标而不重建语义

## 7. Recovery Rules

当现场偏离标准时，按下列优先级恢复：

1. 先判断当前改动真正服务哪个 `pr` 目标
2. 让当前 `flow` 只保留一个当前交付目标
3. 若当前语义与真实目标不符，立即切到新的 `flow` / `branch`
4. 旧 `flow` 要么进入 `blocked`，要么在其目标完成后 `done`

恢复原则：

- 谁要发当前 `pr`，当前 `flow` 就应该代表谁
- `flow` 名、`branch` 语义、`pr` 目标应尽量一致
- 目录是否变化不是首要判断条件
- 若复用同一 `worktree`，也必须显式切换到新的 `branch` 与新的 `flow` 语义
- 并行推进多个交付目标时，优先新建物理 `worktree`；串行推进下一个交付目标时，优先复用当前目录并显式切换 `flow`

## 8. Serial Handoff

针对“提交 -> 整合 -> 收口”的串行链路，职责固定如下：

- `vibe-commit`
  - 负责脏工作区分类、commit 分组、串行 PR 切片与 PR 草案
  - 不负责 merge、issue close、flow close
- `vibe-integrate`
  - 负责检查 CI、review、堆叠顺序、merge eligibility
  - 负责处理 `open + had_pr` 的 flow
  - 不直接承担 task / issue 真源写入
- `vibe-done`
  - 负责合并后的收口编排
  - 通过 `vibe task update`、`gh issue close`、`vibe flow done` 完成 task / issue / flow handoff

`.agent/context/task.md` 只作为 skill 之间的短期 handoff 记录，不是共享真源。

## 9. Branch Protection

`main` 是项目唯一主干，远端必须至少启用以下约束：

- 合并前必须经过 `pr`
- 合并前至少获得 1 个 review 批准
- 有新 commit 时需重新 review
- 必须解决 review discussion
- 禁止 force push
- 禁止删除主干

本文只定义这些保护规则的最低要求，不扩展平台实现细节。
