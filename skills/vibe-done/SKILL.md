---
name: vibe-done
description: Use when a PR is already merged, or is review-ready for vibe flow done to merge, and the user wants to close the related task, close linked issues, run flow closure, and archive the final handoff without changing source code.
---

# /vibe-done - 合并后收口

`/vibe-done` 负责最终收口编排，不做业务代码修复，不替代 PR 整合。它在用户主链中承接 `issue -> flow -> PR -> done` 的最后一跳。

先读这些真源：

- `docs/standards/v2/git-workflow-standard.md`
- `docs/standards/v2/worktree-lifecycle-standard.md`
- `docs/standards/v2/command-standard.md`
- `docs/standards/v2/handoff-governance-standard.md`
- `.agent/context/task.md`

对 `vibe flow`、`vibe task` 或 `gh` 参数有任何不确定时，先运行 `--help`。

进入本 skill 前，默认前提是已经经过 `/vibe-integrate`。若没有来自上一环节的 merge / gate 结论，先补读 shell 真源，不得自行脑补“现在应该 done 了”。

## 核心边界

- 允许：读取 `vibe flow show`、关闭 task、关闭 issue、执行 `vibe flow done`、写入 handoff
- 不允许：修业务代码、补 review follow-up、手工改 `.git/vibe/*.json`
- `vibe flow done` 只负责关闭 flow 并删本地/远端 branch；task / issue 的关闭由 skill 编排
- 若 PR 尚未 merged，但已满足 review gate，`vibe flow done` 会先执行 merge，再继续 closeout
- 若 review evidence 尚不存在，或 PR 还没达到 merge 条件，必须停回 `/vibe-integrate`，不得强行继续

## Workflow

### Step 1: 读取当前 flow 事实

先运行：

```bash
vibe flow show --json
```

必要时对指定目标运行：

```bash
vibe flow show <feature-or-branch> --json
```

确认：

- `flow`
- `branch`
- `current_task`
- `issue_refs`
- `primary_issue_ref`
- `pr_ref`
- 当前 flow 是否已经满足收口前提

最低收口前提：

- PR 已 merged
  或
- PR 虽未 merged，但 shell 真源已经表明它属于 review-ready，可交给 `vibe flow done` 执行 merge gate

若 handoff 与当前真源或现场不一致，必须在退出前修正，不能把过时 handoff 留给下一个环节。

若没有 task 或 issue，后续步骤按“可跳过”处理，不要伪造关联。

若当前事实显示：

- 没有 review evidence
- 或还有 unresolved review / CI 阻塞

则立即停止，返回 `/vibe-integrate`，不要继续 Step 2 以后动作。

### Step 2: 关闭 task

若 `flow show` 返回 `current_task`，执行：

```bash
vibe task update <task-id> --status completed --unassign
```

禁止直接编辑 `registry.json`。

### Step 3: 关闭 issue

若 task 绑定了 `issue_refs`，逐个执行：

```bash
gh issue close <issue-number-or-ref>
```

如果 issue 无法关闭，明确报出阻塞事实，不要假装 flow 已完全收口。

补充口径：

- `primary_issue_ref` 若存在，它对应的 `repo issue` 是当前 task 的 `task issue`，应作为主闭环 issue 优先确认
- 其余 `issue_refs` 只表示关联来源，不等于都应由当前收口动作负责关闭

### Step 4: 关闭 flow

执行：

```bash
vibe flow done
```

或在处理非当前分支时执行：

```bash
vibe flow done --branch <ref>
```

该命令会负责：

- 若 PR 已 merged，直接兼容收尾
- 若 PR 未 merged，先检查 review evidence，再尝试 merge
- 写入 flow 历史
- 删除本地与远端 branch

该命令不会负责：

- 关闭 task
- 关闭 issue
- 自动修复异常中间态

### Step 5: 写入 handoff

完成后必须更新 `.agent/context/task.md`，至少写入一段最新 handoff：

```markdown
## Skill Handoff
- skill: vibe-done
- updated_at: <ISO-8601>
- flow: <feature-or-none>
- branch: <closed-branch-or-none>
- task: <task-id-or-none>
- pr: <pr-ref-or-none>
- issues: <closed-issue-refs-or-none>
- completed: <已关闭的 task / issue / flow>
- next: <若已完成则写 none；若未完成则明确写“返回 vibe-integrate 处理 review evidence / CI / unresolved threads 阻塞”>
```

若当前 PR 已 merged，对应旧 plan 已进入 terminal state。此阶段只允许补记交付证据、审计说明、handoff 更正与 follow-up 链接；若出现新需求，必须创建或挂接新的 `repo issue`，不得继续塞回旧 plan。

## Restrictions

- 不得修改业务源代码文件
- 不得跳过 `vibe flow show` 直接猜测 task / issue / pr 关联
- 不得手工编辑 `.git/vibe/*.json`
- 不得把未 merge 的 branch 强行 `flow done`
- 若 `vibe flow done` 阻断，必须如实汇报原因，并停止收口
- 不得把 merge 后的新需求伪装成“补充说明”继续留在旧 plan
