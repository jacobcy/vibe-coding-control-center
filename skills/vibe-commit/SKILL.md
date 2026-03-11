---
name: vibe-commit
description: Use when the user wants to classify dirty changes, create serial commits, split work into one PR or multiple PRs, and prepare publication from the correct flow without handling merge or post-merge closure.
---

# /vibe-commit - 串行提交与 PR 切片

`/vibe-commit` 只负责编排提交与发 PR 之前的判断，不负责 merge、关 issue、关 task、关 flow。

先读这些真源：

- `docs/standards/git-workflow-standard.md`
- `docs/standards/worktree-lifecycle-standard.md`
- `docs/standards/command-standard.md`
- `docs/standards/handoff-governance-standard.md`
- `.agent/context/task.md`

只要 shell 参数、子命令或 flag 有任何不确定，先运行对应命令的 `--help`。

## 核心边界

- 允许：分类脏改动、整理 commit、决定单 PR / 多 PR、创建或切换 flow、调用 `vibe flow pr`
- 不允许：直接 merge PR、直接关闭 issue、直接关闭 task、直接调用 `vibe flow done` 做收口
- 若当前 flow 已有 `pr_ref`，只能处理该 PR 的 follow-up；若用户要开始下一个 PR，必须切到新 flow

## Workflow

### Step 1: 读取当前 flow 与上下文

优先读取：

```bash
vibe flow show --json
```

如果当前 flow 不可解析，再退回：

```bash
vibe flow status --json
vibe flow list
```

检查点：

- 当前 `flow` / `branch` / `task` / `issue` / `pr`
- 当前 flow 是否已经进入 `open + had_pr`
- `.agent/context/task.md` 里上一环节留下了什么 handoff

若 handoff 与当前真源或现场不一致，必须在退出前修正，不能继续沿用旧判断。

### Step 2: 运行提交前 metadata preflight

在做任何 commit 分类前，必须先检查当前 execution record 的最小完整性。

若 `vibe flow show --json` 返回了 `current_task`，继续读取：

```bash
vibe task show <task-id> --json
```

第一版规则：

- `hard block`
  - 当前 flow 没有 `current_task`
  - `current_task` 无法从 shell 真源解析
  - 当前 task 的 `runtime_branch` 为空，或与当前 flow branch 不一致

- `warning`
  - 当前 task 缺 `issue_refs`
  - 当前 task 缺 `roadmap_item_ids`
  - 当前 task 缺 `spec_standard` 或 `spec_ref`

动作边界：

- `hard block`：停止提交，先补最小登记
- `warning`：允许继续，但必须把缺失元数据当作显式风险报告给用户

说明：

- `task` 是 execution record
- `issue_refs` / `roadmap_item_ids` / `spec_*` 是提交归类与后续补链的关键元数据
- 第一版不把缺 `spec_ref` 直接提升为硬阻断，避免历史遗留任务一次性全部卡死

### Step 3: 审计工作区

先运行：

```bash
git status --short
git diff --stat
git diff --cached --stat
```

必要时再读精确 diff。把未提交内容明确分成三类：

- `commit now`
- `stash`
- `discard`

执行前必须向用户说明：

- 哪些文件进入当前 commit
- 哪些内容会被 stash
- 哪些内容会被 discard

### Step 4: 组织 commit

每个 commit 只对应一个独立交付目标。生成 commit 草案前，先说明：

- 每组变更包含哪些文件
- 每条 commit 草案
- 这些 commit 将进入哪个 flow / 哪个 PR

若当前分支历史已经混入多个交付目标，不得继续硬挤进一个 PR。

### Step 5: 处理串行多 PR

对“当前已有一串待发布 commit，需要串行拆成多个 PR”的场景，固定按以下步骤执行：

1. 列出待发布分组，明确每组包含哪些 commit、目标 base 是什么。
2. 明确当前采用串行模式，而不是并行 worktree 模式。
3. 对每一组依次执行：
   - 确认当前工作区干净；若不干净，先分类为 `commit now` / `stash` / `discard`
   - 从正确基线进入新的逻辑 flow，默认优先使用最新主干，例如 `vibe flow switch <flow-name> --branch origin/main`
   - 若需要带入未提交改动，才显式追加 `--save-stash`
   - 只把当前这一组 commit 迁移到新 flow；默认使用 `git cherry-pick <commit...>`
   - 运行该组应有的验证命令
   - 使用 `vibe flow pr --base <ref>` 发当前这一组 PR
   - 当前这一组 PR 创建完成前，不要提前切到下一组

### Step 6: 发 PR 前复核

先读取：

```bash
vibe flow pr --help
git log --oneline <base>..HEAD
```

只有同时满足以下条件，才能继续发 PR：

- 工作区已干净
- 当前 commit 只服务一个交付目标
- 当前分支语义仍匹配这个目标
- 当前 flow 没有被错误复用

发布入口只用：

```bash
vibe flow pr --base <ref>
```

不要绕过 shell 规则直接把 `gh pr create` 当成真源入口。

### Step 7: 写入 handoff

完成当前 skill 后，必须更新 `.agent/context/task.md`，至少写入一段最新 handoff：

```markdown
## Skill Handoff
- skill: vibe-commit
- updated_at: <ISO-8601>
- flow: <feature-or-none>
- branch: <branch-or-none>
- task: <task-id-or-none>
- pr: <pr-ref-or-none>
- issues: <issue-refs-or-none>
- completed: <本轮已完成的提交/PR 草案>
- next: <交给 vibe-integrate 或继续 commit 的动作>
```

`.agent/context/task.md` 的读取、写入与修正义务以 `docs/standards/handoff-governance-standard.md` 为准。

## Restrictions

- 不得在用户确认前静默执行 `git commit`
- 不得把“是否拆多个 PR”的判断偷换成“先发一个再说”
- 不得把 `stash` 当垃圾桶
- 不得把 `discard` 当默认处理方式
- 不得在 skill 层发明 `rebase --onto`、`reset --hard` 等替代串行拆 PR 的主流程
- 若发现当前 flow 已有 PR 事实且用户要开始新目标，应停止并切换 flow，而不是继续堆在原 flow
