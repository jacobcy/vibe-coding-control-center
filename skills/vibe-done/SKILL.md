---
name: vibe-done
description: Use when the current human-collaboration flow has reached terminal PR state and the user wants to do final closeout. confirm PR outcome, close owned issues, record terminal handoff, and stop using this branch. Do not use for code changes or abandoned work.
---

# /vibe-done - 终态收口

## 核心职责

`/vibe-done` 负责当前人机协作 flow 的最终收口编排，不做业务代码修复，不替代 PR 整合。

**核心职责**：

- 检查 PR 是否已进入终态（通常是 merged）
- 关闭当前 flow 负责收口的 issue
- 写入最终 handoff 与 closeout 证据
- 必要时运行 `vibe3 check` 做一致性审计

## 停止点

完成后输出：

- ✅ issue 已关闭
- ✅ terminal handoff 已写入
- ✅ 如需清理 branch，已明确交给 git / gh 原生命令

## 必读文档

- `docs/standards/v3/git-workflow-standard.md`
- `docs/standards/v3/worktree-lifecycle-standard.md`
- `docs/standards/v3/command-standard.md`
- `docs/standards/v3/handoff-governance-standard.md`

## 完整流程

```
/vibe-done
  ├─ Step 1: 读取当前 flow 事实
  │   ├─ uv run python src/vibe3/cli.py flow show
  │   ├─ uv run python src/vibe3/cli.py handoff show
  │   └─ gh pr view / gh issue view 确认终态事实
  │
  ├─ Step 2: 判断是否可收口
  │   └─ PR 未终态或仍有 review / CI 阻塞 → 返回 /vibe-integrate
  │
  ├─ Step 3: 关闭 issue
  │   └─ gh issue close <primary-issue-or-owned-related-issue>
  │
  ├─ Step 4: 记录 closeout 证据
  │   ├─ vibe3 handoff append
  │   └─ 必要时 vibe3 check
  │
  ├─ Step 5: 汇总并反馈问题
  │   ├─ 从 handoff 提取 Issues Found
  │   ├─ 创建或更新 issue（severity ≥ medium）
  │   └─ 清理 handoff，保持整洁
  │
  └─ Step 6: 写入 handoff
      └─ 输出停止点信息（流程结束）
```

## 核心边界

- 允许：读取 `flow show` / `handoff show` / `gh pr view`、关闭 issue、写入 handoff、必要时执行 `vibe3 check`
- 不允许：修业务代码、补 review follow-up、手工改 `.git/vibe/*.json`
- branch / PR / issue 生命周期优先直接使用 git / gh；`flow` / `handoff` 只负责创联和本地协作证据
- 若 review evidence 尚不存在，或 PR 还没达到 merge 条件，必须停回 `/vibe-integrate`，不得强行继续

## Workflow

### Step 1: 读取当前 flow 事实

先运行：

```bash
uv run python src/vibe3/cli.py flow show
```

必要时对指定目标运行：

```bash
uv run python src/vibe3/cli.py flow show <branch>
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
- PR 已明确进入 closed / aborted 等终态，且用户要做终态记录与 issue closeout

若 handoff 与当前真源或现场不一致，必须在退出前修正，不能把过时 handoff 留给下一个环节。

若没有 task 或 issue，后续步骤按"可跳过"处理，不要伪造关联。

若当前事实显示：

- 没有 review evidence
- 或还有 unresolved review / CI 阻塞

则立即停止，返回 `/vibe-integrate`，不要继续 Step 2 以后动作。

### Step 2: 执行 PR 合并（如满足条件）

若 PR 状态为 MERGEABLE 且无阻塞：

```bash
gh pr merge <pr-number> --merge --delete-branch=false
```

**注意**：
- 不自动删除 branch（保留用于 handoff 记录和后续清理）
- Merge 后等待 CI 确认 merged 状态
- 若 merge 失败或 PR 状态不支持，回到 `/vibe-integrate` 处理阻塞

若 PR 已 merged 或明确 closed/aborted，跳过此步骤继续 Step 3。

### Step 3: 确认 task 收口事实

若 `flow show` 返回了 task / issue 线索，只在 handoff / 总结中记录该 flow 已进入终态；不要直接编辑任何本地 JSON / SQLite 真源。

### Step 4: 关闭 issue

优先关闭 `primary_issue_ref` 指向的主闭环 issue；其余 issue 只有在当前 flow 明确负责时才关闭：

```bash
gh issue close <issue-number-or-ref>
```

如果 issue 无法关闭，明确报出阻塞事实，不要假装 flow 已完全收口。

补充口径：

- `primary_issue_ref` 若存在，它对应的 `repo issue` 是当前 task 的 `task issue`，应作为主闭环 issue 优先确认
- 其余 `issue_refs` 只表示关联来源，不等于都应由当前收口动作负责关闭

### Step 5: 记录 closeout 与一致性审计

执行：

```bash
uv run python src/vibe3/cli.py handoff append "vibe-done: flow reached terminal state" --actor vibe-done --kind milestone
uv run python src/vibe3/cli.py check
```

这些动作负责：

- 记录当前 flow 的 terminal 证据
- 对 shared-state 做最小一致性审计

它们不会负责：

- 强行 merge 未就绪的 PR
- 替代 git / gh 去删除 branch 或处理远端生命周期

### Step 6: 汇总并反馈问题（仅在发现系统性问题时）

**重要**：仅在发现 vibe skill/system 性问题时创建 feedback issue，不针对单个 PR 的问题。

单个 PR 的问题已在：
- PR comment（review evidence）
- PR 自身的 issue 关联
- Handoff 记录中

系统性问题示例：
- Skill 流程设计缺陷（如 vibe-integrate 等待在线 review 超时）
- 命令参数错误（如文档与实际命令不符）
- 跨 PR 的重复问题模式

若发现系统性问题，执行问题反馈：

1. **汇总问题清单**
   - 从 `vibe3 handoff show` 读取当前 flow 的所有问题记录
   - 按严重等级分类：high / medium / low

2. **创建或更新 Issue**
   - 严重等级 ≥ medium 的问题：使用 `gh issue create` 创建新 issue
   - 已存在相关 issue：使用 `gh issue comment` 补充发现场景
   - 重复出现的问题：在 issue 中添加 `severity:high` 标签

   示例命令：

   ```bash
   gh issue create --title "vibe flow pr: Improve blocking logic" \
     --body "检测到 open PR 时直接阻止，不给用户选择机会。建议添加 --force 参数。" \
     --label "vibe-feedback,enhancement"
   ```

3. **补 terminal handoff**
   反馈完成后，不额外发明 handoff cleanup 动作；只补一条明确的 terminal milestone，记录当前 flow 的最终状态与关键交付物链接。

   推荐格式：

   ```markdown
   ## Flow Closure

   - flow: <flow-name>
   - status: completed | blocked
   - pr: <pr-link>
   - issues_closed: <issue-links>
   - feedback_posted: <issue-links>
   - completed_at: <ISO-8601>
   ```

### Step 7: 写入 handoff

完成后运行：

```bash
uv run python src/vibe3/cli.py handoff append "vibe-done: flow closed" --actor vibe-done --kind milestone
```

```markdown
## Flow Closure

- flow: <feature-or-none>
- status: completed | blocked
- pr: <pr-ref-or-none>
- issues_closed: <closed-issue-refs-or-none>
- feedback_posted: <issue-links-or-none>
- completed_at: <ISO-8601>
```

注意：handoff 没有单独的清理 / 删除命令；若需要纠正旧记录，应通过追加更正或终态说明来覆盖语义，而不是假设存在 cleanup 入口。

若当前 PR 已 merged，对应旧 plan 已进入 terminal state。此阶段只允许补记交付证据、审计说明、handoff 更正与 follow-up 链接；若出现新需求，必须创建或挂接新的 `repo issue`，不得继续塞回旧 plan。

## Restrictions

- 不得修改业务源代码文件
- 不得跳过 `uv run python src/vibe3/cli.py flow show` 直接猜测 task / issue / pr 关联
- 不得手工编辑 `.git/vibe*.json` 或本地 SQLite 真源
- 建议运行 `vibe3 check` 做收口后的最小一致性审计
- 不得在 PR 合并前伪装收口
- 不得把 merge 后的新需求伪装成"补充说明"继续留在旧 plan
