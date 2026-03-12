# History Backfill Reconciliation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 先产出一份可审计的历史恢复对账表，明确哪些历史 execution record 可以直接回填，哪些只能高置信推断，哪些必须保留为空待人工确认。

**Architecture:** 本轮不直接修改共享状态，只做事实对账。恢复链路以 `merged PR -> branch -> task -> issue` 为主，`flow-history.json` / `registry.json` / `roadmap.json` 为本地真源，`docs/tasks` / `docs/plans` / `docs/archive/*` 只作佐证，不作为第一锚点。

**Tech Stack:** Git, GitHub CLI (`gh`), Zsh, Python 3, JSON shared state (`registry.json` / `roadmap.json` / `flow-history.json`), Markdown

---

## Goal / Non-goals

**Goal**
- 产出一份历史恢复对账表，列清：
  - branch
  - merged PR
  - 当前 flow/task 桥接状态
  - 文档佐证
  - issue 对应状态
  - 恢复建议
- 明确“可直接回填 / 高置信待确认 / 暂不恢复”三类口径
- 为下一步真实补数提供稳定输入

**Non-goals**
- 本轮不直接写回 `registry.json` / `roadmap.json` / `flow-history.json`
- 本轮不创建新的 repo issue
- 本轮不补 shell 命令能力
- 本轮不把所有历史文档都强行转成 task

## Facts Used

- `origin/main` 最新已合并 `#125`：`remove-worktree-logic-anchor`
- `bin/vibe task audit --all` 当前输出 `Task registry is healthy`
- 本地统计：
  - `registry.json.tasks`: 36
  - `roadmap.json.items`: 30
  - `flow-history.json.flows`: 15
- 历史缺口仍主要集中在：
  - 旧 closed flow 缺 `current_task` / `pr_ref`
  - roadmap item 缺 `linked_task_ids` / `execution_record_id` / `spec_ref`
  - 旧 task 缺 `pr_ref` / `issue_refs` / `spec_ref`

## Reconciliation Rules

### Rule 1: PR First

- 若某 closed flow 的 `branch` 能唯一命中 merged PR 的 `headRefName`，则 PR 是第一锚点。
- 若 flow 已自带 `pr_ref`，且与 `gh pr list --state merged` 一致，则直接视为已确认。

### Rule 2: Branch to Task

- 若 `flow-history.current_task` 已存在，直接作为 task 锚点。
- 若缺失，则依次看：
  - `registry.json` 中同 branch 的历史/当前 task
  - `docs/tasks` / `docs/archive/tasks` 中同名 task README
  - `docs/plans` / `docs/archive/plans` 中同主题 plan

### Rule 3: Task to Issue

- issue 优先来源：
  - task 现有 `issue_refs`
  - roadmap item 现有 `issue_refs`
  - PR body/title 中明确 `Closes #...` / `Related to #...`
  - task/plan 文档中明确写出的 `gh-xxx`
- 若无稳定证据，不强行补 issue。

### Rule 4: Recovery Classes

- `Direct`：PR、task、issue 三层能唯一对应，可直接回填。
- `Candidate`：PR 唯一，但 task 或 issue 仍需人工确认。
- `Hold`：只能看出 PR，无法稳定落到 task/issue，先保留空值。

## Initial Reconciliation Table

| Branch | Flow History | Merged PR | Task Evidence | Issue Evidence | Class | Note |
| --- | --- | --- | --- | --- | --- | --- |
| `claude/task-readme-audit` | task=`2026-03-02-task-readme-audit`, pr=`#24` | `#24` | [docs/archive/tasks/2026-03-02-task-readme-audit/README.md](/Users/jacobcy/src/vibe-center/wt-auto-task-runner/docs/archive/tasks/2026-03-02-task-readme-audit/README.md) | 未见稳定 repo issue 证据 | `Direct(task/pr)` | task/pr 已闭环，issue 暂空可接受 |
| `claude/bug-fix` | task=`2026-03-05-bug-fix`, pr=`#38` | `#38` | registry 中有 completed task | 未见稳定 repo issue 证据 | `Direct(task/pr)` | 先不补 issue |
| `task/gh-96-backlog-cleanup` | task/pr 缺失 | `#111` | registry 有 `2026-03-11-task-pr-bridge-audit` | task 自带 `gh-96,gh-99,gh-106,gh-107,gh-108,gh-109` | `Direct` | 这是高优先恢复样本 |
| `task/gh-101-105-roadmap-intake-gate` | task=`2026-03-11-roadmap-intake-gate`, pr=`116` | `#116` | registry + plan 都存在 | task 自带 `gh-101,gh-105` | `Direct` | 可作为标准恢复模板 |
| `task/issue-project-auto-sync` | task=`2026-03-11-roadmap-projects-sync`, pr 缺失 | `#118` | registry + plan 都存在 | roadmap item 仅有 `rm-2026-03-11-repo-issue-github-project`，无 repo issue | `Candidate` | 先补 pr_ref，再判断是否需要 repo issue |
| `task/pr77-followup` | task/pr 缺失 | `#84` | 未命中 task README/plan | PR 主题像 follow-up，不一定需要 issue | `Hold` | 暂不机械补 task |
| `task/flow-lifecycle-skill-handoff` | task/pr 缺失 | `#85` | 未命中 task README/plan | 未见稳定 issue 证据 | `Hold` | 先保留空值 |
| `task/loc-limit-5400-cleanup` | task/pr 缺失 | `#86` | 未命中 task README/plan | 未见稳定 issue 证据 | `Hold` | 偏工程清理型 |
| `task/flow-switch-safe-carry` | task/pr 缺失 | `#88` | 命中 archive plan | 未见稳定 issue 证据 | `Candidate` | 可从 plan 反推 task 是否应补建 |
| `task/github-project-compatibility` | task/pr 缺失 | `#94` | 命中多份 GitHub Project 迁移 plan | PR 主题为治理迁移 | `Candidate` | 需要先拆出实际 task 边界 |
| `task/auto-task-runner` | task/pr 缺失 | `#97` | registry 中有多条 `2026-03-11-*` 子任务指向同主题 | PR 97 无单一 task 锚点 | `Candidate` | 更像多 task 汇总 PR |
| `task/agent-worktree-boundary` | task/pr 缺失 | `#98` | 当前未命中稳定 task README/plan | PR body 可继续提取 issue 线索 | `Candidate` | 需二次检索文档正文 |
| `task/runtime-boundary-cleanup` | task/pr 缺失 | `#114` | 命中 [docs/plans/2026-03-11-runtime-boundary-cleanup-plan.md](/Users/jacobcy/src/vibe-center/wt-auto-task-runner/docs/plans/2026-03-11-runtime-boundary-cleanup-plan.md) | 未见 task/issue 桥接落盘 | `Candidate` | 很可能应恢复一个 execution task |

## Priority Order

1. 先恢复 `Direct` 类
   - `gh-96-backlog-cleanup`
   - `gh-101-105-roadmap-intake-gate`
   - `claude/task-readme-audit`
   - `claude/bug-fix`
2. 再处理 `Candidate` 类
   - `issue-project-auto-sync`
   - `runtime-boundary-cleanup`
   - `agent-worktree-boundary`
   - `github-project-compatibility`
   - `auto-task-runner`
   - `flow-switch-safe-carry`
3. `Hold` 类保持空值，避免伪造历史

## Files To Read In Execution

- Shared state:
  - `/Users/jacobcy/src/vibe-center/main/.git/vibe/flow-history.json`
  - `/Users/jacobcy/src/vibe-center/main/.git/vibe/registry.json`
  - `/Users/jacobcy/src/vibe-center/main/.git/vibe/roadmap.json`
- Docs:
  - `/Users/jacobcy/src/vibe-center/wt-auto-task-runner/docs/tasks`
  - `/Users/jacobcy/src/vibe-center/wt-auto-task-runner/docs/archive/tasks`
  - `/Users/jacobcy/src/vibe-center/wt-auto-task-runner/docs/plans`
  - `/Users/jacobcy/src/vibe-center/wt-auto-task-runner/docs/archive/plans`

## Validation Commands

```bash
git fetch origin main
git rev-list --left-right --count origin/main...HEAD
bin/vibe task audit --all
gh pr list --state merged --limit 80 --json number,title,headRefName,mergedAt,body,url
python3 <reconciliation-script>
```

**Expected Result**
- 能输出 branch / PR / task / issue 四层对照
- 能把样本分成 `Direct` / `Candidate` / `Hold`
- 不直接修改共享状态

## Next Execution Plan

### Task 1: 固化对账脚本输出

- 把当前 ad-hoc 查询整理成可重复执行的只读脚本或命令模板
- 输出 CSV/Markdown 都可以，但字段必须固定

### Task 2: 先补 `Direct`

- 只回填有唯一证据链的 `task/pr/issue`
- 每补一条都要保留证据来源

### Task 3: 再审 `Candidate`

- 逐条阅读对应 PR body、plan、task README
- 能唯一证明再补，不能证明就停

### Task 4: 最后评估 repo issue 补建

- 只针对“应当存在治理锚点但缺失”的 case
- 不对纯执行碎片批量补 issue

## Change Summary

- Added: 1 file
- Modified: 0 files
- Deleted: 0 files
- Estimated lines: +140 / -0
