---
name: vibe-commit
description: Use when the user wants to classify dirty changes, create serial commits, split work into one PR or multiple PRs, and prepare publication from the correct flow without handling merge or post-merge closure.
---

# /vibe-commit - 提交代码与创建 PR

编排提交与创建 PR，不负责 merge、关 issue、关 task、关 flow。

---

## 核心职责

**核心职责**：

- 分组提交代码
- 处理 commit message（利用已有的 git hooks 自动格式化）
- 根据策略创建 PR：
  - 单个 PR
  - 并行 PR（多个 worktree）
  - 串行 PR（stacked PR）

## 停止点

PR 创建后停止，输出：

- ✅ commit 已推送
- ✅ PR 已创建
- **下一步**：运行 `/vibe-integrate` 检查 CI / review 并推进合并

## 必读文档

- `docs/standards/v3/git-workflow-standard.md` — 提交流程核心规范
- `docs/standards/v3/command-standard.md` — 命令用法规范
- `docs/standards/github-labels-standard.md` — PR 标签规则

## 完整流程

```
/vibe-commit [--strategy <single|parallel|stacked>]
  ├─ Step 1: 读取当前任务与交接状态
  │   ├─ uv run python src/vibe3/cli.py task show
  │   ├─ uv run python src/vibe3/cli.py handoff status
  │   └─ 检查 issue、task、branch、pr
  │
  ├─ Step 2: 检查主分支是否已更新
  │   ├─ git fetch origin main
  │   ├─ git log HEAD..origin/main --oneline
  │   └─ 若有新提交：先 rebase 或 merge，处理冲突
  │
  ├─ Step 3: 判断是否仍需提交
  │   ├─ 检查改动是否已被其他 PR 覆盖
  │   ├─ 若已不需要：handoff append 说明理由 → 标记 state/handoff → 停止
  │   └─ 若仍需提交：继续
  │
  ├─ Step 4: 审计工作区
  │   ├─ git status --short
  │   ├─ git diff --stat
  │   └─ 分类：commit now / stash / discard
  │
  ├─ Step 5: Pre-commit 强制验证与格式化
  │   ├─ uv run black src tests/vibe3
  │   ├─ uv run ruff check --fix src tests/vibe3
  │   ├─ 若有修改：提交临时 commit → 软重置（检查 commit 是否为临时）
  │   ├─ pre-commit run --all-files
  │   └─ Hard block: 任何错误必须修复，禁止跳过
  │
  ├─ Step 6: 组织 commit
  │   ├─ 每组变更包含哪些文件（含格式化修改）
  │   ├─ 每条 commit 草案
  │   └─ git hooks 自动格式化 commit message
  │
  ├─ Step 7: 处理串行多 PR（如需要）
  │   ├─ 列出待发布分组
  │   ├─ 从正确基线进入新的逻辑 flow
  │   ├─ cherry-pick（需处理冲突）
  │   └─ 依次验证、发 PR
  │
  ├─ Step 8: 发 PR 前复核
  │   ├─ 工作区已干净
  │   ├─ commit 只服务一个交付目标
  │   └─ uv run python src/vibe3/cli.py pr create --base <ref>
  │
  └─ Step 9: 写入 handoff 并停止
      ├─ vibe3 handoff append
      └─ 停止，等待用户确认后运行 /vibe-integrate
```

只要 shell 参数、子命令或 flag 有任何不确定，先运行对应命令的 `--help`。

## 核心边界

- 允许：分类脏改动、整理 commit、决定单 PR / 多 PR、创建或切换 flow、调用 `uv run python src/vibe3/cli.py pr create`
- 不允许：直接 merge PR、直接关闭 issue、直接关闭 task、直接做收口动作；收口统一交给 `/vibe-done`
- 若当前 flow 已有 `pr_ref`，只能处理该 PR 的 follow-up；若用户要开始下一个 PR，必须切到新 flow

## Workflow

### Step 1: 读取当前任务与交接状态

```bash
uv run python src/vibe3/cli.py task show
uv run python src/vibe3/cli.py handoff status
```

检查点：

- 当前 `issue` / `task` / `branch` / `pr`
- 当前 task 是否已经有 `pr_ref`
- `handoff status` 里上一环节留下了什么交接记录

若 handoff 与当前真源或现场不一致，必须在退出前修正，不能继续沿用旧判断。

### Step 2: 检查主分支是否已更新

在提交前必须检查 `origin/main` 是否有新提交，避免提交过时代码：

```bash
# 获取远程最新状态
git fetch origin main

# 检查是否有新提交
git log HEAD..origin/main --oneline
```

**处理策略**：

- 若有新提交：
  1. 先 `git rebase origin/main` 或 `git merge origin/main`
  2. 处理冲突（如有）
  3. 运行测试验证
  4. 再继续提交流程
- 若无新提交：直接继续

**Hard Block**：冲突未解决前禁止提交。

### Step 3: 判断是否仍需提交

在执行提交前，必须检查改动是否仍然必要：

**检查项**：

1. 改动是否已被其他 PR 覆盖（查看 `origin/main` 或相关分支）
2. Issue 是否已被关闭或标记为 `wontfix`
3. 功能是否已被其他实现替代

**若已不需要提交**：

```bash
# 记录原因
uv run python src/vibe3/cli.py handoff append "vibe-commit: 不再需要提交，理由：<具体原因>" --kind note

# 更新 issue 标签为 state/handoff
gh issue edit <issue-number> --add-label "state/handoff"

# 停止，等待 manager 决定
```

**若仍需提交**：继续下一步。

### Step 4: 审计工作区

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

### Step 5: Pre-commit 强制验证与格式化（强制两步流程）

**这是硬规定，不可跳过。未经用户明确允许，禁止使用 `--no-verify`。**

**强制两步流程**：

1. **第一步（temp commit）**：提交临时 commit → pre-commit 自动修复格式问题
2. **第二步（正式提交）**：软重置 → 按功能模块分组提交（包含格式化修改）

**理由**：防止 E501 等格式问题进入代码库，保证所有提交都经过质量门禁。

在组织任何 commit 之前，必须确保所有待提交文件通过 pre-commit 检查。项目使用 Python pre-commit 框架，配置见 `.pre-commit-config.yaml`。

**核心理念**：先对所有改动统一格式化，再按功能分组提交，避免单独的格式化 commit 打乱提交历史。

**执行步骤**：

1. **运行格式化工具（对所有改动）**：

   ```bash
   # 格式化所有 Python 代码
   uv run black src tests/vibe3

   # 运行 ruff linter 并自动修复
   uv run ruff check --fix src tests/vibe3
   ```

2. **检查是否有格式化修改**：

   ```bash
   # 查看哪些文件被修改
   git status --short
   git diff --stat
   ```

3. **提交临时格式化 commit（如果有修改）**：
   - 若有文件被 black 或 ruff 修改：

     ```bash
     # 只暂存格式化修改的文件（避免包含敏感文件）
     git add <formatted-files>

     # 提交临时格式化 commit
     git commit -m "temp: pre-commit format (will be squashed)"
     ```

4. **撤销临时 commit（保留修改在工作区）**：

   ```bash
   # 检查最近一次提交是否为临时格式化 commit
   if git log -1 --format="%s" | grep -q "temp: pre-commit format"; then
       # Soft reset：撤销 commit，但保留所有修改在工作区
       git reset HEAD~1
   fi

   # 确认修改已回到工作区
   git status --short
   ```

5. **运行 pre-commit 验证**：

   ```bash
   # 对所有文件运行 pre-commit 检查
   pre-commit run --all-files
   ```

6. **处理错误**：
   - **Hard Block 规则**：
     - 若 pre-commit 报告错误（如 mypy 类型错误、shellcheck 错误、LOC 超限）：
       - 必须修复所有错误
       - 不允许使用 `git commit --no-verify` 跳过
       - 不允许继续后续步骤
     - 修复后重新执行步骤 1-5，直到所有检查通过

**关键点**：

- 此时工作区包含：原始改动 + 格式化修改
- 接下来的 Step 7 将按功能分组提交
- 每个功能 commit 都会包含相应的格式化修改
- 不会有单独的 "style: ..." commit 打乱历史

**边界约束**：

- 不允许使用 `--no-verify` 跳过 pre-commit
- 不允许在有 pre-commit 错误的情况下继续分组提交
- 不允许保留临时格式化 commit，必须软重置
- 格式化修改必须分散到各个功能 commit 中
- 软重置前必须检查最近提交是否为临时格式化 commit

### Step 6: 组织 commit

每个 commit 只对应一个独立交付目标。生成 commit 草案前，先说明：

- 每组变更包含哪些文件
- 每条 commit 草案
- 这些 commit 将进入哪个 task / 哪个 PR

若当前分支历史已经混入多个交付目标，不得继续硬挤进一个 PR。

### Step 7: 处理串行多 PR

对"当前已有一串待发布 commit，需要串行拆成多个 PR"的场景，固定按以下步骤执行：

1. 列出待发布分组，明确每组包含哪些 commit、目标 base 是什么。
2. 明确当前采用串行模式，而不是并行 worktree 模式。
3. 对每一组依次执行：
   - 确认当前工作区干净；若不干净，先分类为 `commit now` / `stash` / `discard`
   - 从正确基线进入新的逻辑 flow，默认优先使用最新主干
   - 若需要带入未提交改动，才显式追加 `--save-stash`
   - 只把当前这一组 commit 迁移到新 flow；默认使用 `git cherry-pick <commit...>`
   - **处理 cherry-pick 冲突**：
     - 若发生冲突：停止并报告冲突详情
     - 手动解决冲突后运行 `git cherry-pick --continue`
     - 或使用 `git cherry-pick --abort` 放弃并重新规划
   - 运行该组应有的验证命令
   - 使用 `uv run python src/vibe3/cli.py pr create --base <ref>` 发当前这一组 PR
   - 当前这一组 PR 创建完成前，不要提前切到下一组

### Step 8: 发 PR 前复核

先读取：

```bash
uv run python src/vibe3/cli.py pr create --help
git log --oneline <base>..HEAD
```

只有同时满足以下条件，才能继续发 PR：

- 工作区已干净
- 当前 commit 只服务一个交付目标
- 当前分支语义仍匹配这个目标
- 当前 flow 没有被错误复用
- 当前分支 upstream 正常；如果 `git branch -vv` 显示任务分支 tracking 到 `origin/main`，先修 upstream，再继续发 PR

发布入口只用：

**人类用户使用 vibe3 pr create --yes**：

```bash
vibe3 pr create --yes
```

**Agent 使用 vibe3 pr create --agent**：

**重要**：Agent 模式必须提供 `-t` (title) 和 `-b` (body)，不允许交互式输入。

```bash
vibe3 pr create --agent -t "..." -b "..."
```

**说明**：

- `vibe3 pr create --agent` 是 Agent 专用入口，自动获取 base branch、flow metadata、Contributors 块，创建 draft PR
- `vibe3 pr create --yes` 是人类专用入口，需要明确确认，创建 draft PR
- Agent 禁止使用 `--ai` 参数（与 `--agent` 冲突）
- Agent 模式必须提供完整的 `-t` (title) 和 `-b` (body)，否则报错
- 所有 PR 创建默认都是 draft 状态，需要手动转换为正式 PR
- `vibe3 pr create --agent` 仍然依赖当前 git 现场正确；若任务分支被错误 tracking 到 `origin/main`，请先修正 branch/upstream，再重试

**发 PR 前的最小 upstream 检查**：

```bash
git branch -vv
```

如果当前任务分支显示类似：

```bash
task/issue-337 [origin/main: ahead 1, behind 1]
```

说明 upstream 错绑到了 `origin/main`。此时不要继续运行 `vibe3 pr create --agent`；先修正 git 现场，必要时直接改用 `gh pr create` 完成人工收口。

**失败时的收口**：

- 把失败命令、关键 stderr、当前 `git branch -vv` 摘要写进 issue comment
- 把同样的错误摘要写进 handoff，便于 manager / human 接手
- 明确说明是 branch/upstream 现场问题、权限问题，还是普通 push 失败

**Contributors 块自动生成**：

PR 创建时，系统会自动从 flow state 中读取 actor 信息并生成 Contributors 块：

1. **数据来源**：flow state 中的 `planner_actor`、`executor_actor`、`reviewer_actor`、`latest_actor`
2. **自动生成位置**：PR body 末尾
3. **生成格式**：

```markdown
---

## Contributors

claude/sonnet-4.6, gemini, jacob
```

4. **前置条件**：
   - Flow 创建时使用了 `vibe3 flow update --actor <identity>`
   - 各个操作步骤正确更新了 actor 字段

**手动添加**：如果自动生成失败，可在 PR body 末尾手动添加 Contributors 块。

### Step 9: 应用标签与智能审查

**智能审查策略**：

| 标签类型        | 审查方式     | 自动化程度                     |
| --------------- | ------------ | ------------------------------ |
| `type/feat`     | Codex 审查   | 在 PR 中评论 `@codex review`   |
| `type/fix`      | Copilot 审查 | 在 PR 中评论 `@copilot review` |
| `type/refactor` | claude 审查  | 在 PR 中评论 `@claude review`  |
| `type/docs`     | 人工审查     | ⏸️ 需要手动决定是否测试        |
| `type/test`     | 人工审查     | ⏸️ 需要手动决定是否测试        |
| `type/chore`    | 人工审查     | ⏸️ 需要手动决定是否测试        |

**执行方式**：

```bash
# 查看当前 PR
gh pr view <pr-number>

# 添加标签
gh pr edit <pr-number> --add-label "type/feature"
```

### Step 10: 写入 handoff 并停止

PR 创建成功后，当前 task 进入 `open + had_pr` 状态，skill 在此停止。

**此阶段**：

- 允许：进入 `/vibe-integrate` 检查 review、CI、merge 阻塞
- 不允许：直接进入 `/vibe-done`
- 不允许：把当前 task 当作下一个新目标继续开发

若用户问"下一步是什么"，回答：

> 运行 `/vibe-integrate` 检查 CI 状态和 review，确认合并条件后推进。

**写入 handoff**：

```bash
# actor 使用 agent 自身的 backend/model，若不确定则留空
uv run python src/vibe3/cli.py handoff append "vibe-commit: PR created" --kind note
```

## Restrictions

- **Pre-commit 硬规定**：
  - 不得使用 `git commit --no-verify` 跳过 pre-commit 检查
  - 不得在有 pre-commit 错误（如 mypy、shellcheck、LOC 超限）的情况下继续提交
  - 必须在组织 commit 分组前完成 pre-commit 验证
  - 格式化流程：对所有改动统一格式化 → 提交临时 commit → 软重置（检查是否为临时 commit）→ 分组提交
  - 不得保留单独的格式化 commit，格式化修改必须分散到各功能 commit 中
- **主分支同步**：
  - 提交前必须检查 `origin/main` 是否有新提交
  - 冲突未解决前禁止提交
- **提交必要性检查**：
  - 若改动已不需要提交，必须用 `handoff append` 说明理由
  - 必须更新 issue 标签为 `state/handoff`，等待 manager 决定
- 不得在用户确认前静默执行 `git commit`
- 不得把"是否拆多个 PR"的判断偷换成"先发一个再说"
- 不得把 `stash` 当垃圾桶
- 不得把 `discard` 当默认处理方式
- 若发现当前 task 已有 PR 事实且用户要开始新目标，应停止并切换 task，而不是继续堆在原 task
