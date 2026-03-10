# Fix PR Base Selection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 `vibe flow pr` 与 `/vibe-commit` 的 PR 基线选择逻辑，避免从非 `main` 近切分支直接错误地对 `main` 发 PR。

**Architecture:** 先在 shell 层为 `vibe flow pr` 建立明确的 base branch 判定与参数接口，再让 `/vibe-commit` 在提议发 PR 前读取这套能力，而不是自行假定 `main`。测试优先覆盖“从 `claude/refactor` 派生时不得默认比较 `main`”这一事故路径。

**Tech Stack:** Zsh CLI (`lib/flow.sh`, `lib/flow_help.sh`)、Markdown workflow/skill files、Bats (`tests/test_flow.bats`)。

---

## Goal

- 让 `vibe flow pr` 不再硬编码 `main..HEAD`
- 让 `/vibe-commit` 在建议发 PR 前显式检查正确 base
- 为错误基线事故补回归测试

## Non-goals

- 不重做 `flow/worktree/branch` 全局语义模型
- 不修改已关闭/已替代的历史 PR
- 不重构无关的 release bump / CHANGELOG 流程

## Task 1: 为 PR base 选择补失败测试

**Files:**
- Modify: `tests/test_flow.bats`
- Inspect: `lib/flow.sh`

**Step 1: 添加针对 `_flow_pr` 的失败测试**

覆盖至少两种场景：
- 当前分支从 `main` 近切时，默认基线可仍为 `main`
- 当前分支不是从 `main` 近切、且存在更近祖先分支时，默认逻辑不能继续静默使用 `main`

**Step 2: 运行单测确认当前实现失败**

Run: `bats tests/test_flow.bats`

Expected:
- 新增用例失败
- 失败原因明确指向 `_flow_pr` 仍把 `main` 当默认基线

**Step 3: Commit**

```bash
git add tests/test_flow.bats
git commit -m "test(flow): cover PR base selection"
```

## Task 2: 在 shell 层实现明确的 base branch 选择

**Files:**
- Modify: `lib/flow.sh`
- Modify: `lib/flow_help.sh`

**Step 1: 为 `vibe flow pr` 增加显式 base 入口**

新增或收紧参数契约，例如：
- `--base <ref>` 或等价命名
- 若未传，先通过 Git ancestry 计算候选 base，而不是直接写死 `main`

**Step 2: 明确默认判定策略**

要求实现满足：
- 若当前分支确实从 `main` 近切，允许默认使用 `main`
- 若当前分支并非从 `main` 近切，必须报错或要求显式确认/显式 `--base`
- `commit_logs`、Open PR 检查、PR 创建所用 base 必须统一，不允许一处推断、一处仍写死 `main`

**Step 3: 更新帮助文案**

`lib/flow_help.sh` 必须说明：
- `--base <ref>` 的用途
- 默认行为何时会拒绝继续
- 为什么不能从任意历史分支直接假定对 `main` 发 PR

**Step 4: 运行测试确认通过**

Run: `bats tests/test_flow.bats`

Expected:
- 新增测试通过
- 旧有 `_flow_pr` 相关测试不回归

**Step 5: Commit**

```bash
git add lib/flow.sh lib/flow_help.sh tests/test_flow.bats
git commit -m "fix(flow): guard PR base selection"
```

## Task 3: 收紧 `/vibe-commit` 的 PR 提议文案与前置检查

**Files:**
- Modify: `skills/vibe-commit/SKILL.md`
- Modify: `.agent/workflows/vibe-commit.md`

**Step 1: 更新 workflow 文案**

明确：
- `/vibe-commit` 只是在提交完成后“提议”发 PR
- 真正的 base 判定以 `vibe flow pr (shell)` 为准
- 在 shell 未确认 base 之前，不得默认向用户暗示“准备好合并到主干”

**Step 2: 更新 skill 文案**

要求 skill 在生成 PR 草案前至少做两件事：
- 先读取 `vibe flow pr --help` 或等价 shell 能力说明
- 检查当前分支相对哪个 base 才是最小差异；若不是 `main`，不得默认建议发往 `main`

**Step 3: 文案对齐 slash / shell 边界**

把 `/vibe-commit`、`vibe flow pr`、`gh pr create` 三者职责写清楚：
- `/vibe-commit`：skill 层编排
- `vibe flow pr`：shell 层发布
- `gh pr create`：底层外部工具

**Step 4: Commit**

```bash
git add skills/vibe-commit/SKILL.md .agent/workflows/vibe-commit.md
git commit -m "docs(commit): require PR base validation"
```

## Task 4: 端到端验证

**Files to inspect during execution:**
- `lib/flow.sh`
- `lib/flow_help.sh`
- `skills/vibe-commit/SKILL.md`
- `.agent/workflows/vibe-commit.md`
- `tests/test_flow.bats`

**Step 1: 运行 flow 相关测试**

Run: `bats tests/test_flow.bats`

Expected:
- `_flow_pr` 基线选择相关用例全部通过

**Step 2: 运行 PR 发布相关全量回归**

Run: `bin/vibe check`

Expected:
- `flow` / `link` / `task` / `docs` 组不因本次改动新增失败

**Step 3: 运行命令帮助校验**

Run:

```bash
bin/vibe flow pr --help
```

Expected:
- 输出中出现新的 base 说明
- 不再暗示所有 PR 都默认对 `main`

**Step 4: Commit**

```bash
git add lib/flow.sh lib/flow_help.sh skills/vibe-commit/SKILL.md .agent/workflows/vibe-commit.md tests/test_flow.bats
git commit -m "test(flow): verify PR base selection workflow"
```

## Files To Modify

- `lib/flow.sh`
- `lib/flow_help.sh`
- `skills/vibe-commit/SKILL.md`
- `.agent/workflows/vibe-commit.md`
- `tests/test_flow.bats`

## Test Command

```bash
bats tests/test_flow.bats
bin/vibe check
bin/vibe flow pr --help
```

## Expected Result

- `vibe flow pr` 不再把 `main` 作为无条件默认基线
- `/vibe-commit` 不再在未校验 ancestry 时默认建议“发往 main”
- 从非 `main` 近切分支发布时，系统会要求显式 base 或直接拒绝继续

## Change Summary

- Files affected: 5
- Expected added lines: 80-160
- Expected removed lines: 20-60
- Expected modified lines: 40-100
