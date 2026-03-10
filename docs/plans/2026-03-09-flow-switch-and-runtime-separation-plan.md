# Flow Switch And Runtime Separation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 `vibe flow` 收敛为逻辑 flow 工作环境管理：新增 `vibe flow switch` 承载当前目录串行切换能力，并为后续把 `flow new` 退回标准语义建立测试与帮助边界。

**Architecture:** 先用测试固定“逻辑 flow 切换”和“物理 worktree 创建”是两类能力，再把 `scripts/rotate.sh` 的当前目录切换逻辑上收进 `lib/flow.sh` 的新子命令，最后同步帮助、标准引用和相关 skill/workflow 文案。并行 worktree 继续保留在 `wtnew` / `vnew`，不塞回 `vibe flow` 的核心语义。

**Tech Stack:** Zsh CLI (`lib/flow.sh`, `lib/flow_help.sh`), Bats (`tests/test_flow.bats`, `tests/test_rotate.bats`), Markdown standards/skills/workflows, Git/GitHub CLI.

---

## Goal

- 引入 `vibe flow switch`，让当前目录可以安全进入另一个逻辑 flow
- 支持显式 `--save-stash`，收敛 `scripts/rotate.sh` 的核心能力
- 保持 `flow` 与 `worktree` 概念分离
- 为后续 `flow new` 语义收敛提供迁移落点

## Non-goals

- 本轮不移除 `wtnew` / `vnew`
- 本轮不一次性废弃现有 `flow new` 的 worktree 行为
- 本轮不直接批量拆分并提交当前所有待合并 PR

## Task 1: 先用测试固定 flow runtime 语义

**Files:**
- Modify: `tests/test_flow.bats`
- Inspect: `lib/flow.sh`
- Inspect: `scripts/rotate.sh`

**Step 1: 写 `flow switch` 的失败测试**

覆盖至少以下场景：
- dirty worktree 且未传 `--save-stash` 时拒绝切换
- 传 `--save-stash` 时允许 stash -> checkout/create branch -> unstash
- 目标分支名非法、等于当前分支、当前分支是 `main/master` 时拒绝

**Step 2: 写 flow 语义测试**

覆盖至少以下事实：
- `switch` 代表“进入已有或将承载新目标的逻辑 flow”，不只是裸 `git checkout`
- 帮助文案中必须区分 `flow` 与 `worktree`
- `new` 与 `switch` 的帮助描述不能再写成纯 Git 动词

**Step 3: 运行测试确认当前实现失败**

Run: `bats tests/test_flow.bats`

Expected:
- 新增 `switch` 用例失败
- 失败点直接暴露当前 shell 缺少该能力

**Step 4: Commit**

```bash
git add tests/test_flow.bats
git commit -m "test(flow): cover runtime switch semantics"
```

## Task 2: 在 shell 层实现 `vibe flow switch`

**Files:**
- Modify: `lib/flow.sh`
- Modify: `lib/flow_help.sh`
- Inspect: `lib/task.sh`

**Step 1: 提取 rotate 级原子逻辑**

在 `lib/flow.sh` 中补最小 helper，覆盖：
- worktree dirty 检查
- 可选 stash 保存
- 目标 branch 校验
- checkout/create branch
- stash pop 冲突暴露

**Step 2: 新增 `_flow_switch`**

要求：
- 命令形态：`vibe flow switch <name> [--branch <base-ref>] [--save-stash]`
- 若目标 flow 不存在，允许以“当前目录承载新 flow”方式初始化 branch 语义
- 只处理 flow runtime 切换，不创建新 worktree

**Step 3: 保留现有 `flow new`，但帮助文案明确其过渡身份**

本阶段不直接移除当前 `flow new` 行为，但帮助中必须明确：
- `flow new` 当前仍创建新物理现场
- `flow switch` 负责当前目录复用
- 并行开发继续使用 worktree 命令

**Step 4: 跑测试确认通过**

Run: `bats tests/test_flow.bats`

Expected:
- `switch` 新增用例通过
- 旧有 `flow` 帮助/绑定/收尾测试不回归

**Step 5: Commit**

```bash
git add lib/flow.sh lib/flow_help.sh tests/test_flow.bats
git commit -m "feat(flow): add runtime switch command"
```

## Task 3: 收敛 `rotate.sh` 到正式 shell 语义

**Files:**
- Modify: `scripts/rotate.sh`
- Modify: `tests/test_rotate.bats`
- Inspect: `lib/flow.sh`

**Step 1: 明确 `rotate.sh` 的定位**

将脚本收敛为：
- 兼容包装器，委托到 `vibe flow switch --save-stash`
- 或保留为底层脚本，但帮助文案明确其已被正式命令吸收

**Step 2: 为包装/兼容行为补测试**

Run: `bats tests/test_rotate.bats`

Expected:
- `rotate.sh` 仍可工作
- 但其核心逻辑不再与 `lib/flow.sh` 重复分叉

**Step 3: Commit**

```bash
git add scripts/rotate.sh tests/test_rotate.bats
git commit -m "refactor(flow): route rotate through flow switch"
```

## Task 4: 更新标准、skills、workflow 的语义边界

**Files:**
- Modify: `docs/standards/git-workflow-standard.md`
- Modify: `docs/standards/worktree-lifecycle-standard.md`
- Modify: `docs/standards/command-standard.md`
- Modify: `skills/vibe-commit/SKILL.md`
- Modify: `.agent/workflows/vibe-commit.md`

**Step 1: 收紧标准表述**

标准必须明确：
- `flow` 是逻辑工作空间
- `worktree` 是物理工作空间
- `switch` 用于重新进入/复用逻辑 flow
- 并行开发继续依赖独立 worktree

**Step 2: 同步 commit/PR slicing 指南**

`vibe-commit` 相关文案必须改成：
- 发现下一个交付目标时，优先进入新的 `flow`
- 当前目录串行推进时，优先用 `vibe flow switch`
- 需要并行时才建议 worktree

**Step 3: 运行引用审计**

Run: `bash skills/vibe-skill-audit/scripts/audit-skill-references.sh skills/vibe-commit/SKILL.md`

Expected:
- 无缺失引用
- 文案不再把 `flow` 和 `worktree` 混用

**Step 4: Commit**

```bash
git add docs/standards/git-workflow-standard.md docs/standards/worktree-lifecycle-standard.md docs/standards/command-standard.md skills/vibe-commit/SKILL.md .agent/workflows/vibe-commit.md
git commit -m "docs(flow): separate runtime flow from worktree"
```

## Task 5: 汇总验证并更新待发 PR 清单

**Files to inspect during execution:**
- `lib/flow.sh`
- `lib/flow_help.sh`
- `scripts/rotate.sh`
- `tests/test_flow.bats`
- `tests/test_rotate.bats`
- `skills/vibe-commit/SKILL.md`
- `.agent/workflows/vibe-commit.md`

**Step 1: 跑核心测试**

Run:

```bash
bats tests/test_flow.bats
bats tests/test_rotate.bats
```

Expected:
- flow/rotate 相关测试全部通过

**Step 2: 跑命令帮助验证**

Run:

```bash
bin/vibe flow help
bin/vibe flow new --help
bin/vibe flow switch --help
```

Expected:
- 帮助中出现 `switch`
- `flow` / `worktree` 的职责区分清晰

**Step 3: 更新 task 记录**

记录：
- 本轮功能完成后待串行提交的 commit 分组
- PR77 patch 分支需要单独补
- 哪些本地旧 commit 已被 squash merge 吸收，不再重复发 PR

**Step 4: Commit**

```bash
git add docs/plans/*.md
git commit -m "docs(plan): track flow runtime separation rollout"
```

## Files To Modify

- `lib/flow.sh`
- `lib/flow_help.sh`
- `scripts/rotate.sh`
- `tests/test_flow.bats`
- `tests/test_rotate.bats`
- `docs/standards/git-workflow-standard.md`
- `docs/standards/worktree-lifecycle-standard.md`
- `docs/standards/command-standard.md`
- `skills/vibe-commit/SKILL.md`
- `.agent/workflows/vibe-commit.md`

## Test Command

```bash
bats tests/test_flow.bats
bats tests/test_rotate.bats
bin/vibe flow help
bin/vibe flow new --help
bin/vibe flow switch --help
bash skills/vibe-skill-audit/scripts/audit-skill-references.sh skills/vibe-commit/SKILL.md
```

## Expected Result

- 当前目录可以通过正式命令串行切换到下一个 flow
- `rotate.sh` 不再是游离脚本心智
- `flow` 与 `worktree` 的职责边界在 shell、标准、skill 文案中一致
- 为后续把所有待合并提交按主题串行发 PR 提供稳定入口

## Change Summary

- Files affected in implementation: 10
- Expected added lines: 180-320
- Expected removed lines: 40-120
- Expected modified lines: 120-220
