# PR Save And Had-PR State Audit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 核实当前 `vibe flow pr (shell)`、`vibe flow show/status (shell)` 与 `/vibe-save (skill)` 在“PR 已创建但未通过、未关闭”场景下的真实行为，并给出是否需要修改的最小实现方案。

**Non-Goals:** 本文档不直接修改 shell/skill 实现；不处理 PR base 选择问题本身；不扩展新的 flow 生命周期模型。

**Architecture:** 当前 PR 事实分成三层：GitHub 云端事实、task 共享真源中的 `pr_ref`、flow 运行时视图中的 `open + had_pr`。现状显示 shell 层只用 `gh pr view` 判断“是否有过 PR”，但 `show/status` 主要依赖 task/worktree 投影，因此“能阻止 switch”与“能显示 had_pr”已经发生分离。后续若修复，应优先让 shell 真源写回一致，而不是让 skill 文案兜底。

**Tech Stack:** Zsh shell, `gh`, `jq`, GitHub PR metadata, `.git/vibe/{registry,worktrees}.json`, skill markdown docs.

---

## 当前核实结论

1. 当前分支 `task/gh-36-task-flow-github` 在 2026-03-10 已存在 GitHub PR `#89`，状态为 `OPEN`，CI `Lint & Test` 失败，`mergeStateStatus=BLOCKED`。
2. 当前 worktree `wt-fix-pr-base-selection` 在共享真源 `worktrees.json` 中 `current_task=null`、`tasks=[]`，因此 `flow show` 无法从 task 投影拿到 `pr_ref`。
3. `vibe flow pr (shell)` 当前会 `git push` 并执行 `gh pr create --web` / `gh pr edit`，但不会把 PR 编号回写到 task 真源。
4. `/vibe-save (skill)` 只有在“当前 flow 已能从共享真源识别当前 task”时，才允许通过 `vibe task update` 同步最小事实；在当前这个未绑定 task 的现场，它不会自动回写 `pr_ref`。
5. `vibe flow switch (shell)` 已按标准阻止进入有 PR 历史的 flow，因为它直接调用 `_flow_branch_has_pr`，优先看 `gh pr view`，并不依赖 `flow show` 的 `pr_ref` 展示。

## 证据命令

Run:
```bash
bin/vibe flow show --json
```
Expected:
```text
当前 worktree 返回 pr_ref: null，且 current_task: null
```

Run:
```bash
branch=$(git rev-parse --abbrev-ref HEAD)
gh pr list --head "$branch" --state all --json number,state,title,url,mergeStateStatus,statusCheckRollup
```
Expected:
```text
返回 PR #89，state=OPEN，mergeStateStatus=BLOCKED，CI conclusion=FAILURE
```

Run:
```bash
jq '.worktrees[] | select(.worktree_name=="wt-fix-pr-base-selection")' "$(git rev-parse --git-common-dir)/vibe/worktrees.json"
```
Expected:
```text
current_task 为 null，tasks 为空数组
```

## 根因摘要

1. `flow show/status/list` 的 PR 展示依赖 `_flow_branch_dashboard_entry`，而它只会从当前绑定 task 取 `pr_ref`。
2. `flow switch` 的 had-pr 阻断依赖 `_flow_branch_has_pr`，它会直接查 `gh pr view`，因此即使 `show` 仍显示 `pr_ref: null`，switch 也会拒绝进入。
3. `/vibe-save` 不是 PR 发现器；它只在 task 已识别时同步最小事实，不负责把“云端已有 PR”自动认领回某个未绑定 task。

## 建议改动方向

### Task 1: 修正 shell 真源写回

**Files:**
- Modify: `lib/flow_pr.sh`
- Modify: `lib/task_actions.sh`（仅当需要补充更方便的 PR 写回接口时）
- Test: `tests/flow/test_flow_pr_review.bats`

**Step 1: 写 failing test**

新增一个场景：`vibe flow pr` 成功创建或识别到现有 PR 后，会把 PR 编号回写到当前绑定 task 的 `pr_ref`。

**Step 2: 运行测试确认失败**

Run:
```bash
bats tests/flow/test_flow_pr_review.bats
```
Expected:
```text
新增用例失败，提示 pr_ref 未被写回
```

**Step 3: 实现最小修复**

在 `flow_pr` 成功拿到 PR number 后，仅当当前 worktree 绑定 task 时，通过现有 `vibe task update <task-id> --pr <ref>` 回写真源。

**Step 4: 回归验证**

Run:
```bash
bats tests/flow/test_flow_pr_review.bats
```
Expected:
```text
全部通过；新用例验证 pr_ref 已持久化
```

**Step 5: Commit**

```bash
git add lib/flow_pr.sh lib/task_actions.sh tests/flow/test_flow_pr_review.bats
git commit -m "fix(flow): persist pr ref after flow pr"
```

### Task 2: 明确 `/vibe-save` 边界文案

**Files:**
- Modify: `skills/vibe-save/SKILL.md`
- Test: `rg -n "识别当前 task|必要时的 pr_ref|只更新本地 task.md" skills/vibe-save/SKILL.md`

**Step 1: 调整说明**

明确 `/vibe-save` 只会同步“已识别 task”的最小事实，不负责把未绑定 flow 的云端 PR 自动写回。

**Step 2: 验证文案**

Run:
```bash
rg -n "识别当前 task|必要时的 pr_ref|只更新本地 task.md" skills/vibe-save/SKILL.md
```
Expected:
```text
文案同时覆盖“可同步 pr_ref”的前提和“无法识别 task 时不回写”的边界
```

**Step 3: Commit**

```bash
git add skills/vibe-save/SKILL.md
git commit -m "docs(skill): clarify vibe-save pr sync boundary"
```

## 预期结果

- `vibe flow show/status` 在绑定 task 的正式 flow 上能稳定展示 `pr_ref`
- `open + had_pr` 的“显示事实”和“switch 阻断事实”不再分离
- `/vibe-save` 的边界对用户与 agent 都更清晰

## Change Summary

- Added: `1` plan file
- Modified: `0` source files in this discussion session
- Estimated implementation scope if approved: `3-4` files, `+30/-10` lines
