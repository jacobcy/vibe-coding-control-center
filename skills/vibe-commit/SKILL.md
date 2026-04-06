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

- `docs/standards/v3/git-workflow-standard.md`
- `docs/standards/v3/worktree-lifecycle-standard.md`
- `docs/standards/v3/command-standard.md`
- `docs/standards/v3/handoff-governance-standard.md`
- `docs/standards/github-labels-standard.md`

## 完整流程

```
/vibe-commit [--strategy <single|parallel|stacked>]
  ├─ Step 1: 读取当前 flow 与上下文
  │   ├─ uv run python src/vibe3/cli.py flow show
  │   └─ 检查 issue、flow、branch、task、pr
  │
  ├─ Step 2: 运行提交前 metadata preflight
  │   ├─ uv run python src/vibe3/cli.py flow show --branch <branch>
  │   └─ 检查 task 绑定、issue_refs、spec_* 等元数据
  │
  ├─ Step 3: 审计工作区
  │   ├─ git status --short
  │   ├─ git diff --stat
  │   └─ 分类：commit now / stash / discard
  │
  ├─ Step 3.5: Pre-commit 强制验证与格式化
  │   ├─ uv run black src tests/vibe3
  │   ├─ uv run ruff check --fix src tests/vibe3
  │   ├─ 若有修改：提交临时 commit → soft reset
  │   ├─ pre-commit run --all-files
  │   └─ Hard block: 任何错误必须修复，禁止跳过
  │
  ├─ Step 4: 组织 commit
  │   ├─ 每组变更包含哪些文件（含格式化修改）
  │   ├─ 每条 commit 草案
  │   └─ git hooks 自动格式化 commit message
  │
  ├─ Step 5: 处理串行多 PR（如需要）
  │   ├─ 列出待发布分组
  │   ├─ 从正确基线进入新的逻辑 flow
  │   └─ 依次 cherry-pick、验证、发 PR
  │
  ├─ Step 6: 发 PR 前复核
  │   ├─ 工作区已干净
  │   ├─ commit 只服务一个交付目标
  │   └─ uv run python src/vibe3/cli.py pr create --base <ref>
  │
  └─ Step 7: 写入 handoff 并停止
      ├─ vibe3 handoff append
      └─ 停止，等待用户确认后运行 /vibe-integrate
```

只要 shell 参数、子命令或 flag 有任何不确定，先运行对应命令的 `--help`。

## 核心边界

- 允许：分类脏改动、整理 commit、决定单 PR / 多 PR、创建或切换 flow、调用 `uv run python src/vibe3/cli.py pr create`
- 不允许：直接 merge PR、直接关闭 issue、直接关闭 task、直接做收口动作；收口统一交给 `/vibe-done`
- 若当前 flow 已有 `pr_ref`，只能处理该 PR 的 follow-up；若用户要开始下一个 PR，必须切到新 flow

## Workflow

### Step 1: 读取当前 flow 与上下文

优先读取：

```bash
uv run python src/vibe3/cli.py flow show
```

如果当前 flow 不可解析，再退回：

```bash
uv run python src/vibe3/cli.py flow status
uv run python src/vibe3/cli.py task status --all --check
```

检查点：

- 当前 `issue` / `flow` / `branch` / `task` / `pr`
- 当前 flow 是否已经进入 `open + had_pr`
- `vibe3 handoff show` 里上一环节留下了什么 handoff

若 handoff 与当前真源或现场不一致，必须在退出前修正，不能继续沿用旧判断。

### Step 2: 运行提交前 metadata preflight

在做任何 commit 分类前，必须先检查当前 execution record 的最小完整性。

若 `flow show` 返回了 `current_task`，针对目标 branch 重新读取：

```bash
uv run python src/vibe3/cli.py flow show --branch <branch>
```

> **参数说明**：`<branch>` 为当前分支名，用于读取该分支绑定的 flow / task 详情。

第一版规则：

- `hard block`
  - `current_task` 无法从 shell 真源解析
  - 当前 task 的 `runtime_branch` 为空，或与当前 flow branch 不一致

- `warning`
  - 当前 task 缺 `issue_refs`
  - 当前 task 缺 `spec_standard` 或 `spec_ref`

动作边界：

- 若当前 flow 没有 `current_task`：
  - 先检查当前 flow / issue / plan 事实能否**唯一推出**一个 execution spec
  - 若能唯一推出，则由 skill 直接补相关数据，并绑定到当前 flow；这一步默认不再额外征求用户确认
  - 若无法唯一推出 plan 是哪个，或 issue / plan 归属存在歧义，再 `hard block` 并向用户确认
- 其余 `hard block`：停止提交，先补最小登记
- `warning`：允许继续，但必须把缺失元数据当作显式风险报告给用户

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

### Step 3.5: Pre-commit 强制验证与格式化

**这是硬规定，不可跳过。**

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
     # 暂存所有格式化修改
     git add -A

     # 提交临时格式化 commit
     git commit -m "temp: pre-commit format (will be squashed)"
     ```

4. **撤销临时 commit（保留修改在工作区）**：

   ```bash
   # Soft reset：撤销 commit，但保留所有修改在工作区
   git reset HEAD~1

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
- 接下来的 Step 4 将按功能分组提交
- 每个功能 commit 都会包含相应的格式化修改
- 不会有单独的 "style: ..." commit 打乱历史

**边界约束**：

- 不允许使用 `--no-verify` 跳过 pre-commit
- 不允许在有 pre-commit 错误的情况下继续分组提交
- 不允许保留临时格式化 commit，必须 soft reset
- 格式化修改必须分散到各个功能 commit 中

### Step 4: 组织 commit

每个 commit 只对应一个独立交付目标。生成 commit 草案前，先说明：

- 每组变更包含哪些文件
- 每条 commit 草案
- 这些 commit 将进入哪个 flow / 哪个 PR

若当前分支历史已经混入多个交付目标，不得继续硬挤进一个 PR。

### Step 5: 处理串行多 PR

对"当前已有一串待发布 commit，需要串行拆成多个 PR"的场景，固定按以下步骤执行：

1. 列出待发布分组，明确每组包含哪些 commit、目标 base 是什么。
2. 明确当前采用串行模式，而不是并行 worktree 模式。
3. 对每一组依次执行：
   - 确认当前工作区干净；若不干净，先分类为 `commit now` / `stash` / `discard`
   - 从正确基线进入新的逻辑 flow，默认优先使用最新主干
   - 若需要带入未提交改动，才显式追加 `--save-stash`
   - 只把当前这一组 commit 迁移到新 flow；默认使用 `git cherry-pick <commit...>`
   - 运行该组应有的验证命令
   - 使用 `uv run python src/vibe3/cli.py pr create --base <ref>` 发当前这一组 PR
   - 当前这一组 PR 创建完成前，不要提前切到下一组

### Step 6: 发 PR 前复核

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

发布入口只用：

```bash
uv run python src/vibe3/cli.py pr create --base <ref>
```

不要绕过 shell 规则直接把 `gh pr create` 当成真源入口。

### Step 6.5: 自动应用标签与智能审查

PR 创建成功后，根据以下规则自动应用标签（详见 `docs/standards/github-labels-standard.md`）：

**类型标签（根据 PR 标题）**：

- 标题以 `feat:` 或 `feature:` 开头 → 添加 `type/feature` → **触发 Codex AI 审查**
- 标题以 `fix:` 或 `bugfix:` 开头 → 添加 `type/fix` → **触发 Copilot AI 审查**
- 标题以 `refactor:` 开头 → 添加 `type/refactor` → **自动运行本地测试**
- 标题以 `docs:` 或 `documentation:` 开头 → 添加 `type/docs`
- 标题以 `test:` 或 `testing:` 开头 → 添加 `type/test`
- 标题以 `chore:` 开头 → 添加 `type/chore`

**智能审查策略**：

| 标签类型        | 审查方式        | 自动化程度                               |
| --------------- | --------------- | ---------------------------------------- |
| `type/feat`     | Codex AI 审查   | ✅ 全自动 - 在 PR 中评论 `@codex review` |
| `type/fix`      | Copilot AI 审查 | ✅ 全自动 - 请求 Copilot 作为审查者      |
| `type/refactor` | 本地测试        | ✅ 全自动 - 运行 lint + pytest + bats    |
| `type/docs`     | 人工审查        | ⏸️ 需要手动决定是否测试                  |
| `type/test`     | 人工审查        | ⏸️ 需要手动决定是否测试                  |
| `type/chore`    | 人工审查        | ⏸️ 需要手动决定是否测试                  |

详见 `docs/standards/github-code-review-standard.md`。

**范围标签（根据文件路径）**：

- 包含 `src/vibe3/**/*.py` → 添加 `scope/python`
- 包含 `lib/**/*.sh` 或 `scripts/**/*.sh` → 添加 `scope/shell-script`
- 包含 `docs/**` 或 `*.md` → 添加 `scope/documentation`
- 包含 `.github/**` 或 `.pre-commit-config.yaml` → 添加 `scope/infrastructure`

**状态标签**：

- PR 创建后 → 自动添加 `status/ready-for-review`

**执行方式**：

```bash
# 查看当前 PR
gh pr view <pr-number>

# 添加标签
gh pr edit <pr-number> --add-label "type/feature,scope/python,status/ready-for-review"
```

### Step 7: 写入 handoff 并停止

PR 创建成功后，当前 flow 进入 `open + had_pr` 状态，skill 在此停止。

此阶段：

- 允许：进入 `/vibe-integrate` 检查 review、CI、merge 阻塞
- 不允许：直接进入 `/vibe-done`
- 不允许：把当前 flow 当作下一个新目标继续开发

若用户问"下一步是什么"，回答：

> 运行 `/vibe-integrate` 检查 CI 状态和 review，确认合并条件后推进。

### Step 8: 写入 handoff

完成当前 skill 后，运行：

```bash
uv run python src/vibe3/cli.py handoff append "vibe-commit: PR created" --actor vibe-commit --kind milestone
```

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
- next: <若 PR 已创建，明确写"进入 vibe-integrate 检查 review evidence / CI / merge readiness"；否则写继续 commit 的动作>
```

## Restrictions

- **Pre-commit 硬规定**：
  - 不得使用 `git commit --no-verify` 跳过 pre-commit 检查
  - 不得在有 pre-commit 错误（如 mypy、shellcheck、LOC 超限）的情况下继续提交
  - 必须在组织 commit 分组前完成 pre-commit 验证
  - 格式化流程：对所有改动统一格式化 → 提交临时 commit → soft reset → 分组提交
  - 不得保留单独的格式化 commit，格式化修改必须分散到各功能 commit 中
- 不得在用户确认前静默执行 `git commit`
- 不得把"是否拆多个 PR"的判断偷换成"先发一个再说"
- 不得把 `stash` 当垃圾桶
- 不得把 `discard` 当默认处理方式
- 若发现当前 flow 已有 PR 事实且用户要开始新目标，应停止并切换 flow，而不是继续堆在原 flow
