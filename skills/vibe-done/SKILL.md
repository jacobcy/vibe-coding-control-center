---
name: vibe-done
description: Use when a PR is already merged, or is review-ready for vibe flow done to merge, and the user wants to close the related task, close linked issues, run flow closure, and archive the final handoff without changing source code.
---

# /vibe-done - 合并后收口

## 核心职责

`/vibe-done` 负责最终收口编排，不做业务代码修复，不替代 PR 整合。

**核心职责**：

- 检查 PR 状态
- PR 已合并 → 关闭 issue
- 使用 `vibe3 check --all --fix` 自动同步并标记 flow 为 done

## 停止点

完成后输出：

- ✅ issue 已关闭
- ✅ flow 已归档
- ✅ 工作区已清理

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
  │   └─ 确认 flow、branch、task、issue、pr
  │
  ├─ Step 2: 确认 task 收口事实
  │   └─ 不再调用独立 task status；以 flow / issue closeout 为准
  │
  ├─ Step 3: 关闭 issue
  │   └─ gh issue close <issue-number-or-ref>
  │
  ├─ Step 4: 关闭 flow (自动)
  │   └─ vibe3 check --all --fix
  │       ├─ PR 已 merged → 自动标记 flow 为 done
  │       └─ 保持本地数据库与 GitHub 状态一致
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

- 允许：读取 `uv run python src/vibe3/cli.py flow show`、关闭 issue、执行 `uv run python src/vibe3/cli.py flow done`、写入 handoff
- 不允许：修业务代码、补 review follow-up、手工改 `.git/vibe/*.json`
- `uv run python src/vibe3/cli.py flow done` 只负责关闭 flow 并删本地/远端 branch；task / issue 的关闭由 skill 编排
- 若 PR 尚未 merged，但已满足 review gate，`flow done` 会先执行 merge，再继续 closeout
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
- PR 虽未 merged，但 shell 真源已经表明它属于 review-ready，可交给 `flow done` 执行 merge gate

若 handoff 与当前真源或现场不一致，必须在退出前修正，不能把过时 handoff 留给下一个环节。

若没有 task 或 issue，后续步骤按"可跳过"处理，不要伪造关联。

若当前事实显示：

- 没有 review evidence
- 或还有 unresolved review / CI 阻塞

则立即停止，返回 `/vibe-integrate`，不要继续 Step 2 以后动作。

### Step 2: 确认 task 收口事实

若 `flow show` 返回 `current_task`，只在 handoff / 总结中记录该 task 将随当前 flow 收口，不再调用独立的 `task status` 命令。

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
vibe3 check --all --fix
```

该命令会负责：

- 检测所有 active flows 关联的远端 PR
- 若 PR 已 merged 或 closed，自动标记本地 flow 为 `done`
- 写入 flow 自动完成事件

该命令不会负责：

- 强行 merge 未就绪的 PR
- 关闭关联的 GitHub Issue (由 Step 3 负责)
- 手工删除分支（不再作为 vibe3 核心动作，由用户自行决定或 git 原生清理）

### Step 5: 汇总并反馈问题

在完成 flow 收口前，必须从当前 flow 的所有 handoff 记录中提取 `Issues Found` 条目。

执行问题反馈：

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

3. **清理 Handoff**
   反馈完成后，清理 handoff 中当前 flow 的信息：
   - **保留**：
     - 当前 flow 的最终状态
     - 关键交付物链接（PR、issue）

   - **删除**：
     - 已反馈的问题记录
     - 过程性判断和临时状态

   最终格式：

   ```markdown
   ## Flow Closure

   - flow: <flow-name>
   - status: completed | blocked
   - pr: <pr-link>
   - issues_closed: <issue-links>
   - feedback_posted: <issue-links>
   - completed_at: <ISO-8601>
   ```

### Step 6: 写入 handoff

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

注意：问题记录已在 Step 5 反馈后清理，不再重复记录。

若当前 PR 已 merged，对应旧 plan 已进入 terminal state。此阶段只允许补记交付证据、审计说明、handoff 更正与 follow-up 链接；若出现新需求，必须创建或挂接新的 `repo issue`，不得继续塞回旧 plan。

## Restrictions

- 不得修改业务源代码文件
- 不得跳过 `uv run python src/vibe3/cli.py flow show` 直接猜测 task / issue / pr 关联
- 不得手工编辑 `.git/vibe/*.json`
- 建议运行 `vibe3 check --all --fix` 来确保状态正确同步
- 不得在 PR 合并前伪装收口
- 不得把 merge 后的新需求伪装成"补充说明"继续留在旧 plan
