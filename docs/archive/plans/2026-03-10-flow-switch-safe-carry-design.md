---
title: "Flow Switch Safe Carry Design"
date: "2026-03-10"
status: "draft"
author: "GPT-5.4"
related_docs:
  - docs/standards/v2/git-workflow-standard.md
  - docs/standards/v2/worktree-lifecycle-standard.md
  - docs/standards/v2/command-standard.md
  - docs/standards/doc-quality-standards.md
  - lib/flow.sh
  - lib/flow_runtime.sh
  - lib/flow_help.sh
  - tests/test_flow.bats
  - tests/flow/test_flow_lifecycle.bats
---

# Flow Switch Safe Carry Design

## Goal

将 `vibe flow switch (shell)` 收敛为“安全复用当前目录进入另一个逻辑 flow”的正式能力。

本轮设计固定两条语义：

1. `flow switch` 默认携带当前未提交改动，不再要求显式 `--save-stash`。
2. 改动恢复必须基于本次操作对应的精确 stash 引用，而不是依赖裸 `git stash pop` 的栈顶语义。

## Non-Goals

- 不改变 `vibe flow new (shell)` 的默认保守语义；`new` 仍默认要求干净工作区，只有显式传参时才允许带入改动。
- 不在本轮设计中改变 `wtnew` / `vnew` 的并行物理 worktree 能力。
- 不直接重做 `flow` / `branch` / `worktree` 全局模型；本轮只收敛 `switch` 的安全切换语义。
- 不引入新的共享真源文件或持久化运行时状态。

## Context

当前实现里，`flow new` 和 `flow switch` 都已经包含“stash -> 切分支 -> runtime 更新 -> pop”的近似流程，但存在三个问题：

1. 两套逻辑分散在 [lib/flow.sh](lib/flow.sh) 和 [lib/flow_runtime.sh](lib/flow_runtime.sh)，后续容易漂移。
2. `flow switch` 仍把“是否携带未提交改动”做成显式参数，和它作为“安全切换”入口的定位不一致。
3. 两个路径都通过无参 `git stash pop` 恢复改动，默认依赖 stash 栈顶，面对多条历史 stash 或异常中断时不够稳。

同时，现有标准已经给出了足够清晰的边界：

- `flow` 是逻辑交付切片，不等于 `worktree`。
- 当前目录串行进入下一个 flow 是允许能力。
- `switch` 只用于进入未关闭且未发过 PR 的既有 flow。
- “不丢现场”比“裸 checkout 成功”更符合当前目录复用的真实目标。

## Problem Statement

`flow switch` 当前暴露的是“是否先 stash”的实现细节，而不是“安全切换 flow”的稳定语义。

这会带来三个具体问题：

1. 用户心智不稳定：必须记住 `--save-stash`，否则 dirty worktree 直接失败。
2. 恢复不够确定：无参 `stash pop` 默认拿栈顶，若中间插入其他 stash，恢复对象可能错误。
3. 实现重复：`new` 和 `switch` 的 stash 携带逻辑几乎相同，却没有共享 helper，后续修补容易只修一边。

## Design Principles

### 1. `switch` 的主语义是安全切换，不是裸切分支

如果命令名是 `flow switch`，它的默认行为就应当尽可能保留当前现场，并把现场迁移到目标 flow 语义下，而不是把“保留现场”做成额外开关。

### 2. `new` 与 `switch` 语义不同，不能强行完全对称

`new` 是开启新的交付切片，保守默认值合理。

`switch` 是复用当前目录切回另一个既有 flow，默认安全携带当前现场更合理。

因此本轮只统一内部恢复能力，不统一两者的默认触发策略。

### 3. 恢复必须基于精确 ref，而不是基于“当下栈顶”猜测

任何依赖“当前栈顶 stash 就是我要的那个”的恢复路径，本质上都不是确定性恢复。

## Options

### Option A: 保留现状

保留 `flow switch --save-stash`，继续把“是否带改动”暴露给用户。

优点：

- 外部 CLI 不变。
- 改动面最小。

缺点：

- 语义仍不对。
- 用户仍需记忆内部实现开关。
- 不解决“switch 应默认安全”的核心问题。

结论：不推荐。

### Option B: `switch` 默认携带改动，移除 `--save-stash`

`flow switch` 在检测到 dirty worktree 时自动进入 carry 流程；工作区干净时直接切换，不创建 stash。

优点：

- 与 `switch` 的命令语义一致。
- 用户心智稳定，不需要额外参数。
- 可以把安全恢复做成唯一受支持路径。

缺点：

- 需要更新 help、测试和相关文档。
- 与现有参数语义不兼容，需要明确迁移策略。

结论：推荐。

### Option C: 默认携带改动，但保留一个显式关闭开关

例如新增 `--no-carry` 或 `--discard-dirty`。

优点：

- 给高级用户一个绕开默认行为的出口。

缺点：

- 重新把主语义做成分叉模式。
- 容易把“破坏现场”的高风险路径伪装成普通选项。

结论：现阶段不推荐。

## Recommendation

采用 Option B。

也就是：

- `vibe flow switch (shell)` 默认携带当前未提交改动。
- 废弃 `--save-stash` 参数。
- dirty worktree 不再是“默认报错”，而是“默认进入安全 carry 流程”。
- 干净 worktree 不做 stash。

## Proposed Command Semantics

### `vibe flow switch <name>`

语义：

- 进入一个未关闭且未发过 PR 的既有 flow。
- 如果当前目录有未提交改动，则自动保存并在目标 flow branch 中恢复。
- 如果当前目录干净，则直接切换。

失败条件仍保留：

- 当前分支是 `main/master`
- 目标 branch 非法
- 目标 branch 不存在
- 目标 flow 已有 PR 历史
- 目标 branch checkout 失败
- runtime 更新失败
- stash 恢复冲突

### `vibe flow new <name> [--save-unstash]`

本轮不改默认语义：

- 默认要求干净工作区。
- 只有显式 `--save-unstash` 才允许把当前未提交改动带入新的 flow。

这样可以保持：

- `new` = 开启新切片时默认保守
- `switch` = 复用当前目录时默认安全

## Internal Mechanism

### Shared Carry Helper

建议把携带未提交改动的流程提取为共享 helper，供 `new` 与 `switch` 复用。

helper 需要覆盖三段能力：

1. 保存当前现场
2. 在目标分支/目标 flow 完成切换
3. 恢复本次保存的改动，或在失败时回滚到原现场

建议拆成类似职责：

- `_flow_capture_dirty_state`
- `_flow_restore_captured_state`
- `_flow_abort_and_restore_source_state`

不要求这些名字固定，但职责必须清晰分层。

### Precise Stash Ref

保存阶段必须拿到本次 stash 的精确引用，并在后续恢复时只操作这个引用。

推荐做法：

1. 生成唯一 message，例如：`vibe-flow:switch:task/foo:<nonce>`
2. 执行 `git stash push -u -m "..."`
3. 立刻通过 `git stash list` 与唯一 message 精确定位本次 stash ref，例如 `stash@{0}`
4. 后续恢复只对这个 ref 执行 `apply` 与 `drop`

关键点：

- 不依赖“当前栈顶还是不是刚才那条 stash”
- 不只依赖命名空间前缀，而是依赖唯一 token + 精确 ref

### Restore Strategy

恢复不再使用裸 `git stash pop`，而改成：

1. `git stash apply <ref>`
2. 成功后 `git stash drop <ref>`

理由：

- `apply` 和 `drop` 可分离，便于失败时保留诊断现场
- 不会因为 `pop` 的复合语义让错误恢复更难排查

### Failure Rollback

若切换流程在以下阶段失败：

- 目标 branch checkout 失败
- runtime 更新失败

则应优先保证：

1. 当前分支仍处于原分支或恢复回原分支
2. 本次保存的未提交改动尽量恢复到原现场

若冲突导致无法自动恢复，也必须明确输出：

- 哪一步失败
- 对应 stash ref 是什么
- 用户接下来该如何手动恢复

## Edge Cases

设计必须显式覆盖这些场景：

1. 当前目录干净
2. 当前目录 dirty，但目标 branch checkout 失败
3. 当前目录 dirty，但 runtime 更新失败
4. 当前目录 dirty，目标 branch 切换成功，但 stash apply 冲突
5. 存在多条历史 stash，当前操作不能误取旧 stash
6. 目标 flow 已有 PR 历史，应拒绝切换，并确保原现场还在
7. 当前分支是 `main/master`，仍应直接拒绝，不进入 carry 流程

## Documentation Changes

至少需要同步这些文档面：

- [lib/flow_help.sh](lib/flow_help.sh)
  - 移除 `switch` 的 `--save-stash`
  - 明确写出 dirty worktree 会自动安全带入
- [docs/standards/v2/git-workflow-standard.md](docs/standards/v2/git-workflow-standard.md)
  - 若提到 `switch` 行为，需更新为默认安全 carry
- [docs/standards/v2/worktree-lifecycle-standard.md](docs/standards/v2/worktree-lifecycle-standard.md)
  - 若提到目录复用时的残留改动处理，需同步新语义

## Testing Strategy

最小测试集应覆盖：

1. `switch` 在 dirty worktree 下默认自动 stash + restore
2. `switch` 在干净 worktree 下不触发 stash
3. `switch` checkout 失败时恢复原现场
4. `switch` runtime 更新失败时恢复原现场
5. `switch` 在多条 stash 并存时仍恢复本次 stash
6. `switch` 帮助文案不再显示 `--save-stash`
7. `new` 仍保持显式 `--save-unstash` 语义不变

## Expected Result

完成后，`vibe flow switch (shell)` 应具备明确且稳定的安全语义：

- 复用当前目录切 flow 时不丢未提交现场
- 恢复基于精确 stash ref，而不是栈顶猜测
- `switch` 与 `new` 的差异来自命令职责，而不是偶然实现差异

## Open Questions

本轮设计后的剩余实现问题主要有两个：

1. 是否保留 `--save-stash` 作为一版兼容别名并输出废弃提示，还是直接移除。
2. 共享 helper 放在 [lib/flow.sh](lib/flow.sh) 还是 [lib/flow_runtime.sh](lib/flow_runtime.sh) 更利于边界清晰。

这两个问题不会影响主设计结论，但会影响实现细节和迁移成本。