---
document_type: plan
title: GH-103 Runtime Branch-First Plan
status: proposed
author: GPT-5 Codex
created: 2026-03-12
last_updated: 2026-03-12
related_docs:
  - docs/standards/v3/data-model-standard.md
  - docs/standards/v3/git-workflow-standard.md
  - docs/standards/v3/worktree-lifecycle-standard.md
  - docs/standards/v3/command-standard.md
related_issues:
  - gh-103
  - gh-144
---

# GH-103 Runtime Branch-First Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 `#103` 在 shell 生命周期层先落一个可验证、可收口的最小实现：`vibe flow done` 不再把当前目录留在 detached HEAD，并把 closeout 后的继续开发路径明确收敛到 branch-first 语义。

**Architecture:** 先解决 `#144` 这个具体症状，再把相关标准、help 和测试同步到同一语义。当前轮不重做完整 runtime storage 迁移，也不在本轮引入新的 `branches.json`。实现以“保留现有共享状态文件、降低 worktree 作为治理主语的存在感”为原则。

**Tech Stack:** Zsh, jq, Git, GitHub CLI, Bats, Markdown

---

## Goal / Non-goals

**Goal**
- 修复 `vibe flow done` 在正常 merged-flow closeout 后把当前目录留在 detached HEAD 的行为
- 明确 closeout 后当前目录应落到一个安全、可解释、可继续起新 flow 的 branch 状态
- 让 shell help、workflow 文案和标准继续对齐 `branch/flow` 是逻辑空间、`worktree` 是物理容器的模型
- 为 `#103` 提供第一段可验证实现，而不是只停留在抽象原则

**Non-goals**
- 本轮不设计或落地完整 `worktrees.json -> branches.json` 迁移
- 本轮不全面重构所有 runtime 读写路径
- 本轮不改变多 worktree 并行开发能力
- 本轮不处理所有历史兼容字段清理，例如 `assigned_worktree`

## Problem Statement

当前标准已经基本收敛到：

- `worktree` 只是物理目录
- `branch` / `flow` 才是逻辑执行空间
- 同一物理目录可顺序承载多条交付线

当时实现里 `vibe flow done` 仍在关闭当前 branch 前调用 `_flow_checkout_detached_main`，导致：

- 当前目录被留在 detached HEAD
- 用户感知上像是必须切别的 worktree 才能继续
- closeout 行为反向强化了“worktree 是主体”的旧直觉

因此，本轮应把 `flow done` 的落点语义改成“当前目录回到安全 branch 落点，而不是掉进 detached HEAD”。

## Scope Boundary

本轮只处理 closeout 之后的当前目录落点，以及围绕这一点的文档/帮助/测试对齐。

本轮不处理：

- 全量 runtime 主索引迁移
- 所有审计项改成 branch-first
- flow list / status / show 的进一步结构优化
- 历史 flow 记录 schema 重做

## Files To Modify

- `lib/flow.sh`
- `lib/flow_history.sh`
- `lib/flow_help.sh`
- `docs/standards/v3/worktree-lifecycle-standard.md`
- `docs/standards/v3/git-workflow-standard.md`
- `tests/flow/test_flow_bind_done.bats`
- `tests/flow/test_flow_lifecycle.bats`

如需补充 task/skill 文案，只允许在实现后发现断言缺口时最小增加，不主动扩面。

## Design Decision To Validate

首选方案：

- 当 `vibe flow done` 关闭的是当前 branch 时，先把当前目录切到一个安全的非 detached 落点，再删除 feature branch
- 安全落点优先使用 `main` 对应的本地 branch；若本地 `main` 不存在，则显式创建/更新本地 `main` 指向 `origin/main`
- closeout 成功后，用户应能直接在同一目录继续 `vibe flow new` 或其它下一步操作

不采用的方案：

- 继续使用 detached HEAD，只靠文案解释
- 关闭 flow 时强制用户切换到别的 worktree
- 本轮直接引入新的 runtime storage 文件

## Tasks

### Task 1: 先把 closeout 落点行为收敛成可测试需求

**Files**
- Modify: `tests/flow/test_flow_bind_done.bats`
- Modify: `tests/flow/test_flow_lifecycle.bats`

**Steps**
1. 新增失败测试，覆盖 `vibe flow done` 关闭当前 branch 后不再处于 detached HEAD。
2. 新增回归测试，覆盖 closeout 后可直接在同一目录继续创建下一条 flow。
3. 明确测试中的安全落点预期，优先围绕本地 `main` 断言，而不是 worktree 切换。

**Run command**

```bash
bats tests/flow/test_flow_bind_done.bats
bats tests/flow/test_flow_lifecycle.bats
```

**Expected Result**

- 改实现前至少有一条 closeout 落点测试失败

### Task 2: 修改 shell closeout 行为，去掉 detached 落点

**Files**
- Modify: `lib/flow.sh`
- Modify: `lib/flow_history.sh`

**Steps**
1. 审核 `_flow_checkout_safe_main_branch` 的唯一职责与调用点。
2. 把当前 branch closeout 时的落点改为安全 branch checkout，而不是 detached checkout。
3. 保持 branch 删除、history 关闭、runtime 清理的现有顺序不被破坏。
4. 处理本地 `main` 缺失场景，避免因为默认 branch 不存在导致 closeout 卡死。

**Run command**

```bash
bats tests/flow/test_flow_bind_done.bats
bats tests/flow/test_flow_lifecycle.bats
```

**Expected Result**

- closeout 后当前目录位于可解释的 branch 状态
- 删除当前 flow branch 后，不影响同目录继续下一条逻辑线

### Task 3: 同步 help 与标准语义

**Files**
- Modify: `lib/flow_help.sh`
- Modify: `docs/standards/v3/worktree-lifecycle-standard.md`
- Modify: `docs/standards/v3/git-workflow-standard.md`

**Steps**
1. 删除或改写任何把 closeout 后目录理解成 detached 中转态的表述。
2. 明确写出：`vibe flow done` 关闭 flow 后，当前物理目录仍可复用，继续开发不要求切换 worktree。
3. 保持文案边界清晰，不把本轮包装成完整 runtime 存储重构。

**Run command**

```bash
rg -n "detach|detached|worktree" lib/flow_help.sh docs/standards/v3/worktree-lifecycle-standard.md docs/standards/v3/git-workflow-standard.md
```

**Expected Result**

- help 与标准不再暗示 closeout 后应依赖 detached 过渡

### Task 4: 做最小端到端复核

**Files**
- Modify: 如前述文件；不新增实现范围外文件

**Steps**
1. 跑 flow closeout 相关 bats 用例。
2. 在一个最小真实 shell 场景中验证：当前 flow closeout 后，可直接在同目录 `vibe flow new`。
3. 记录如果仍存在更大层级的 runtime 索引问题，回挂到 `#103` 后续，而不是在本轮继续扩张。

**Run command**

```bash
bats tests/flow/test_flow_bind_done.bats
bats tests/flow/test_flow_lifecycle.bats
bin/vibe flow status --json
```

**Expected Result**

- 用例通过
- 实际 shell 现场与标准一致

## Risks

### Risk 1: closeout 删除 branch 前后的切换顺序被打乱
- **Impact:** `vibe flow done` 可能在删分支前后报错，导致 flow 半关闭
- **Mitigation:** 保持 history/runtime 清理顺序不变，只替换当前目录的 checkout 目标
- **Stop Condition:** 若 closeout 测试出现半关闭状态，停止实现并回看步骤顺序

### Risk 2: 本地 `main` 缺失导致 checkout 失败
- **Impact:** 某些测试仓库或新 worktree 中没有本地 `main`
- **Mitigation:** 在 helper 中兼容 `origin/main -> local main` 的恢复路径
- **Stop Condition:** 若必须引入复杂 default-branch 发现逻辑，则收缩到只支持项目当前 `main` 约定，并在 plan 偏差中记录

### Risk 3: 文档说得过大，实际只修了 `flow done`
- **Impact:** 让 `#103` 看起来像已经整体完成
- **Mitigation:** 文档明确标注本轮只是 `#103` 的第一段落地，聚焦 `#144`
- **Stop Condition:** 若任何文档段落开始承诺 storage 迁移，则回退措辞

## Test Command

- `bats tests/flow/test_flow_bind_done.bats`
- `bats tests/flow/test_flow_lifecycle.bats`
- `bin/vibe flow status --json`

## Expected Result

- `vibe flow done` 不再把当前目录留在 detached HEAD
- 同一物理目录可直接继续下一条 flow，符合 branch-first 语义
- 标准、help、测试对 closeout 后落点的描述一致
- `#103` 获得一段真正可交付、可验证的实现，而不是继续停留在抽象讨论

## Change Summary Estimate

- Files to modify: 6 到 7 个
- Approx line changes: 90 到 170 行
- 类型分布：
  - 代码：20 到 50 行
  - 测试：30 到 70 行
  - 文档：20 到 50 行
