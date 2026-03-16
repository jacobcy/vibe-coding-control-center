# Open-PR Prep-Only And Follow-Up Routing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 当当前 flow 已经发出 PR 但尚未 `close` 时，明确建立“下一个 flow 的准备期”规则：允许讨论，不允许直接执行；若用户要继续推进，必须先显式记录为后续工作，其中大改动走 `vibe-issue`，小改动走 `vibe-task` 本地任务。

**Non-Goals:** 不在本次计划中实现 `had_pr flow` 的 block/resume 能力；不修改 PR #89 对应的当前 flow 业务代码；不重做 `vibe-issue` / `vibe-task` 的总体设计。

**Architecture:** 这次改动分三层。第一层是标准真源，明确 “PR 已提交但未 close” 的语义是准备期而非执行期。第二层是 workflow / skill 层，把 `/vibe-commit` 在该阶段的行为改成 fail-fast 报错并给出路由建议。第三层是 shell 层，在 `vibe flow new` 上增加当前分支 had_pr 检查，阻止用户直接从一个未关闭 PR 的 flow 开新 flow 执行。

**Tech Stack:** Zsh shell, Bats, markdown standards/workflows, GitHub PR state via `gh`, `.agent/context/task.md`.

---

## 当前核实结论

1. 标准已经写明 `open + had_pr` 的 flow 不能继续作为“下一个新目标”的开发现场复用，见 `docs/standards/git-workflow-standard.md`。
2. 当前 `vibe flow new (shell)` 只检查目标 branch 是否已有 PR 历史，不检查“当前所在 branch 是否已经 had_pr”，因此仍可能从一个未关闭 PR 的 flow 直接切出新 flow。
3. `.agent/workflows/vibe-commit.md` 当前只写了 review/commit/PR slicing 规则，没有把“当前 flow 已 had_pr 时只能准备、不得执行”的行为写成硬 gate。
4. 当前 `.agent/context/task.md` 已与事实不一致：GitHub 上实际已有 PR `#89` open，但 handoff 仍写“没有正式 PR”。

## 目标规则

当满足以下条件时：

- 当前 flow 已提交 PR
- 当前 flow 尚未 `done` / `close`
- 不论 PR 是否已通过 CI/review

则进入“下一个 flow 的准备期”：

- 允许：讨论、分析、拆分、记录方案
- 禁止：直接执行下一个 flow 的代码工作
- 若用户坚持推进后续工作，必须先落记录：
  - 大的计划 / 新能力：走 `vibe-issue`
  - 小的后续任务 / 本地跟进：走 `vibe-task` 新增本地 task

## Task 1: 补标准真源

**Files:**
- Modify: `docs/standards/git-workflow-standard.md`
- Modify: `docs/standards/v2/command-standard.md`

**Step 1: 写标准补充点**

在 `git-workflow-standard` 中增加明确表述：

- `pr` 已提交且未 close 时，当前 flow 进入“下一个 flow 的准备期”
- 此阶段允许讨论，不允许直接执行新的 flow
- 若要形成后续工作，大项走 `vibe-issue`，小项走 `vibe-task`

在 `command-standard` 中补 `vibe flow new` / `vibe-commit` 的 fail-fast 约束：

- shell 检测到当前分支 had_pr 且未 close 时，`flow new` 必须拒绝
- workflow 检测到同样条件时，必须报错并引导记录，而不是直接执行

**Step 2: 文档验证**

Run:
```bash
rg -n "准备期|不得执行|vibe-issue|vibe-task|had_pr" docs/standards/git-workflow-standard.md docs/standards/v2/command-standard.md
```
Expected:
```text
能直接看到 preparation-only 规则、issue/task 路由、以及 shell/workflow fail-fast 约束
```

**Step 3: Commit**

```bash
git add docs/standards/git-workflow-standard.md docs/standards/v2/command-standard.md
git commit -m "docs(flow): define prep-only rule for open PR flows"
```

## Task 2: 补 workflow / skill 层 gate

**Files:**
- Modify: `.agent/workflows/vibe-commit.md`
- Modify: `skills/vibe-commit/SKILL.md`

**Step 1: 写 failing text audit**

先加一个最小文本检查，确认 workflow / skill 还没写这条规则。

Run:
```bash
rg -n "准备期|不得执行|vibe-issue|vibe-task|had_pr" .agent/workflows/vibe-commit.md skills/vibe-commit/SKILL.md
```
Expected:
```text
当前匹配不足，说明缺规则
```

**Step 2: 最小文案修改**

补明确行为：

- 若当前 flow 已进入 `open + had_pr`，`/vibe-commit` 只能报告“当前处于下一个 flow 的准备期”
- 大项记录到 `vibe-issue`
- 小项记录到 `vibe-task`
- 不得继续创建下一个 flow 并执行代码动作

**Step 3: 回归验证**

Run:
```bash
rg -n "准备期|不得执行|vibe-issue|vibe-task|had_pr" .agent/workflows/vibe-commit.md skills/vibe-commit/SKILL.md
```
Expected:
```text
workflow 和 skill 都包含 prep-only 规则与 issue/task 路由
```

**Step 4: Commit**

```bash
git add .agent/workflows/vibe-commit.md skills/vibe-commit/SKILL.md
git commit -m "docs(vibe-commit): gate open PR flows to prep-only mode"
```

## Task 3: 给 `vibe flow new` 增加 shell 拦截

**Files:**
- Modify: `lib/flow.sh`
- Test: `tests/flow/test_flow_lifecycle.bats`

**Step 1: 写 failing test**

新增用例：

- 当前 branch 已有 PR 历史时执行 `vibe flow new next-flow`
- 预期直接失败，并提示当前 flow 处于未关闭 PR 阶段，不允许启动下一个 flow 执行

**Step 2: 跑失败用例**

Run:
```bash
bats tests/flow/test_flow_lifecycle.bats
```
Expected:
```text
新增用例失败，说明 shell 还没拦截当前 branch had_pr
```

**Step 3: 最小实现**

在 `lib/flow.sh::_flow_new` 中，在解析出 `current_branch` 后增加：

- 若 `current_branch` 已有 PR 历史且当前 flow 未 close，则 fail-fast
- 报错信息要显式提示：
  - 当前是 open PR flow
  - 现在只能准备后续工作，不能直接执行新 flow
  - 大项走 `vibe-issue`，小项走 `vibe-task`

**Step 4: 回归验证**

Run:
```bash
bats tests/flow/test_flow_lifecycle.bats
```
Expected:
```text
全部通过，新增用例验证当前 branch had_pr 时 `flow new` 被阻止
```

**Step 5: Commit**

```bash
git add lib/flow.sh tests/flow/test_flow_lifecycle.bats
git commit -m "fix(flow): block flow new from open PR branches"
```

## Task 4: 修正本地 handoff

**Files:**
- Modify: `.agent/context/task.md`

**Step 1: 修正事实**

把当前 handoff 中与事实冲突的内容修正为：

- 当前 GitHub PR 为 `#89`
- 当前 PR 状态为 open，CI failure
- 本轮新增 issue `#90`
- 后续能力不在当前 flow 实施

并补一条新的 handoff：

- 当前 open PR 未 close 前，只允许准备后续 flow，不允许执行
- 大项：`vibe-issue`
- 小项：`vibe-task`

**Step 2: 手工验证**

Run:
```bash
sed -n '1,240p' .agent/context/task.md
```
Expected:
```text
handoff 与 PR #89 / issue #90 的事实一致，且包含 prep-only 规则
```

**Step 3: Commit**

```bash
git add .agent/context/task.md
git commit -m "docs(task): record prep-only rule for open PR flow"
```

## Verification Commands

Run:
```bash
gh pr list --head "$(git branch --show-current)" --state all --json number,state,statusCheckRollup,mergeStateStatus
```
Expected:
```text
返回当前 open PR 事实，用于确认 handoff 和规则描述的外部依据
```

Run:
```bash
bats tests/flow/test_flow_lifecycle.bats
```
Expected:
```text
包含新增 `flow new` gate 用例在内的 flow 生命周期测试全部通过
```

Run:
```bash
rg -n "准备期|不得执行|vibe-issue|vibe-task|had_pr" docs/standards/git-workflow-standard.md docs/standards/v2/command-standard.md .agent/workflows/vibe-commit.md skills/vibe-commit/SKILL.md .agent/context/task.md
```
Expected:
```text
规则、workflow、skill、handoff 四处表述一致
```

## Expected Result

- 标准明确：open PR 未 close 前属于“下一个 flow 的准备期”
- `vibe flow new` 在当前 branch 已 had_pr 时 fail-fast
- `vibe-commit` 在该阶段只允许引导记录，不允许继续执行
- `.agent/context/task.md` 与 PR #89 / issue #90 的事实对齐

## Change Summary

- Planned files to modify: `6`
- Planned tests: `1` existing Bats suite + `rg`/`sed` verification
- Estimated change size: `+40/-5` lines across docs/workflow/shell/test/handoff
