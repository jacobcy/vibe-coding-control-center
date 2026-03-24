---
name: vibe-commit
description: Use when the user wants to classify dirty changes, create serial commits, split work into one PR or multiple PRs, and prepare publication from the correct flow without handling merge or post-merge closure.
---

# /vibe-commit - 提交代码与创建 PR

## 核心职责

`/vibe-commit` 只负责编排提交与创建 PR，不负责 merge、关 issue、关 task、关 flow。

**核心职责**：

- 分组提交代码
- 处理 commit message（利用已有的 git hooks 自动格式化）
- 根据策略创建 PR：
  - 单个 PR
  - 并行 PR（多个 worktree）
  - 串行 PR（stacked PR）

## 停止点

PR 创建后 → 自动进入 `/vibe-integrate`

## 必读文档

- `docs/standards/v3/git-workflow-standard.md`
- `docs/standards/v3/worktree-lifecycle-standard.md`
- `docs/standards/v3/command-standard.md`
- `docs/standards/v3/handoff-governance-standard.md`
- `docs/standards/github-labels-standard.md`
- `.agent/context/task.md`

## 完整流程

```
/vibe-commit [--strategy <single|parallel|stacked>]
  ├─ Step 1: 读取当前 flow 与上下文
  │   ├─ vibe flow show
  │   └─ 检查 issue、flow、branch、task、pr
  │
  ├─ Step 2: 运行提交前 metadata preflight
  │   ├─ vibe task show <task-id>
  │   └─ 检查 task 的 issue_refs、roadmap_item_ids、spec_* 等元数据
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
  │   └─ vibe flow pr --base <ref>
  │
  └─ Step 7: 写入 handoff 与自动进入 /vibe-integrate
      ├─ 更新 .agent/context/task.md
      └─ 自动进入 /vibe-integrate
```

只要 shell 参数、子命令或 flag 有任何不确定，先运行对应命令的 `--help`。

## 核心边界

- 允许：分类脏改动、整理 commit、决定单 PR / 多 PR、创建或切换 flow、调用 `vibe flow pr`
- 不允许：直接 merge PR、直接关闭 issue、直接关闭 task、直接调用 `vibe flow done` 做收口
- 若当前 flow 已有 `pr_ref`，只能处理该 PR 的 follow-up；若用户要开始下一个 PR，必须切到新 flow

## Workflow

### Step 1: 读取当前 flow 与上下文

优先读取：

```bash
vibe flow show
```

如果当前 flow 不可解析，再退回：

```bash
vibe flow status
vibe flow list
```

检查点：

- 当前 `issue` / `flow` / `branch` / `task` / `pr`
- 当前 flow 是否已经进入 `open + had_pr`
- `.agent/context/task.md` 里上一环节留下了什么 handoff

若 handoff 与当前真源或现场不一致，必须在退出前修正，不能继续沿用旧判断。

### Step 2: 运行提交前 metadata preflight

在做任何 commit 分类前，必须先检查当前 execution record 的最小完整性。

若 `vibe flow show ` 返回了 `current_task`，继续读取：

```bash
vibe task show <task-id>
```

第一版规则：

- `hard block`
  - `current_task` 无法从 shell 真源解析
  - 当前 task 的 `runtime_branch` 为空，或与当前 flow branch 不一致

- `warning`
  - 当前 task 缺 `issue_refs`
  - 当前 task 缺 `roadmap_item_ids`
  - 当前 task 缺 `spec_standard` 或 `spec_ref`

动作边界：

- 若当前 flow 没有 `current_task`：
  - 先检查当前 flow / issue / plan 事实能否**唯一推出**一个 execution spec
  - 若能唯一推出，则由 skill 直接补 `vibe task add/update ... --spec-standard --spec-ref`，并绑定到当前 flow；这一步默认不再额外征求用户确认
  - 若无法唯一推出 plan 是哪个，或 issue / plan 归属存在歧义，再 `hard block` 并向用户确认
- 其余 `hard block`：停止提交，先补最小登记
- `warning`：允许继续，但必须把缺失元数据当作显式风险报告给用户

说明：

- `task` 是 execution record / execution bridge
- `issue_refs` / `roadmap_item_ids` / `spec_*` 是提交归类与后续补链的关键元数据
- 第一版不把缺 `spec_ref` 直接提升为硬阻断，避免历史遗留任务一次性全部卡死
- 这里的自动补 task 只适用于“plan 唯一明确”的场景；若存在多个候选 plan / spec，不得替用户猜

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

7. **确认准备就绪**：
   ```bash
   # 确认工作区包含所有改动（包括格式化修改）
   git status --short
   git diff --stat
   ```

**关键点**：
- 此时工作区包含：原始改动 + 格式化修改
- 接下来的 Step 4 将按功能分组提交
- 每个功能 commit 都会包含相应的格式化修改
- 不会有单独的 "style: ..." commit 打乱历史

**常见检查项**（见 `.pre-commit-config.yaml`）：
- **Shell**: shellcheck、自定义 lint
- **Python**: ruff (linter + auto-fix)、black (formatter)、mypy (type checker)
- **LOC 限制**:
  - Shell 总 LOC ≤ 7000
  - Python 总 LOC ≤ config:code_limits.v3_python.total_loc
  - 单文件 LOC ≤ 300 (测试文件 ≤ 300)

**边界约束**：
- 不允许使用 `--no-verify` 跳过 pre-commit
- 不允许在有 pre-commit 错误的情况下继续分组提交
- 不允许保留临时格式化 commit，必须 soft reset
- 格式化修改必须分散到各个功能 commit 中

**验证证据**：
完成此步骤后，必须向用户展示：
- `uv run black src tests/vibe3` 和 `uv run ruff check --fix src tests/vibe3` 的输出
- pre-commit 所有检查通过的输出
- `git status` 显示所有改动（包括格式化）都在工作区

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
- 若这是该 branch 第一次写 CHANGELOG，必须准备好非占位的 `--msg`

发布入口只用：

```bash
vibe flow pr --base <ref>
```

不要绕过 shell 规则直接把 `gh pr create` 当成真源入口。

补充约束：

- 首次发布若当前 branch 还没有已确认的 changelog message cache，agent 必须显式提供 `--msg`
- `--msg` 不允许使用空字符串、`...` 或默认占位文案糊弄过关
- 同一 branch 若已经提供过一次有效 `--msg`，后续重复执行 `vibe flow pr` 时默认复用缓存值，不必反复询问
- 若本轮是按显式输入的 plan 执行改动，发布对应实现/文档改动时必须同时提交该 plan 文件，不得把 plan 留在工作区外游离

### Step 6.5: 自动应用标签与智能审查

PR 创建成功后，根据以下规则自动应用标签（详见 `docs/standards/github-labels-standard.md`）：

**类型标签（根据 PR 标题）**：
- 标题以 `feat:` 或 `feature:` 开头 → 添加 `type/feature` → **触发 Codex AI 审查**
- 标题以 `fix:` 或 `bugfix:` 开头 → 添加 `type/fix` → **触发 Copilot AI 审查**
- 标题以 `refactor:` 开头 → 添加 `type/refactor` → **自动运行本地测试**
- 标题以 `docs:` 或 `documentation:` 开头 → 添加 `type/docs` → **需要手动决定是否测试**
- 标题以 `test:` 或 `testing:` 开头 → 添加 `type/test` → **需要手动决定是否测试**
- 标题以 `chore:` 开头 → 添加 `type/chore` → **需要手动决定是否测试**

**智能审查策略**：

| 标签类型 | 审查方式 | 自动化程度 |
|---------|---------|-----------|
| `type/feat` | Codex AI 审查 | ✅ 全自动 - 在 PR 中评论 `@codex review` |
| `type/fix` | Copilot AI 审查 | ✅ 全自动 - 请求 Copilot 作为审查者 |
| `type/refactor` | 本地测试 | ✅ 全自动 - 运行 lint + pytest + bats |
| `type/docs` | 人工审查 | ⏸️ 需要手动决定是否测试 |
| `type/test` | 人工审查 | ⏸️ 需要手动决定是否测试 |
| `type/chore` | 人工审查 | ⏸️ 需要手动决定是否测试 |

详见 `docs/standards/github-code-review-standard.md`。

**范围标签（根据文件路径）**：
- 包含 `src/vibe3/**/*.py` → 添加 `scope/python`
- 包含 `lib/**/*.sh` 或 `scripts/**/*.sh` → 添加 `scope/shell-script`
- 包含 `docs/**` 或 `*.md` → 添加 `scope/documentation`
- 包含 `.github/**` 或 `.pre-commit-config.yaml` → 添加 `scope/infrastructure`

**组件标签（根据文件路径）**：
- 包含 `src/vibe3/cli.py` 或 `src/vibe3/commands/*.py` → 添加 `component/cli`
- 包含 `flow.py` 或 `flow_service.py` → 添加 `component/flow`
- 包含 `pr.py` 或 `pr_service.py` → 添加 `component/pr`
- 包含 `task.py` 或 `task_service.py` → 添加 `component/task`
- 包含 `src/vibe3/observability/**` → 添加 `component/logger`
- 包含 `src/vibe3/clients/**` → 添加 `component/client`

**状态标签**：
- PR 创建后 → 自动添加 `status/ready-for-review`

**执行方式**：
```bash
# 查看当前 PR
gh pr view <pr-number>

# 添加标签
gh pr edit <pr-number> --add-label "type/feature,scope/python,status/ready-for-review"
```

**注意事项**：
- 如果 GitHub Actions 已配置自动打标签（`.github/workflows/label.yml`），则无需手动执行
- 每个 PR 至少应有一个类型标签
- 标签应与 PR 内容一致，不要误导性标签

### Step 7: PR 发出后的强制停点

`vibe flow pr` 成功后，必须立即把当前 flow 视为 `open + had_pr`。

此时：

- 允许：进入 `/vibe-integrate` 检查 review、CI、merge 阻塞
- 不允许：直接进入 `/vibe-done`
- 不允许：把当前 flow 当作下一个新目标继续开发现场

若用户问“下一步是什么”，默认回答应是：

- 先去 `/vibe-integrate`
- 先确认或补齐 review evidence
- 再决定是否已满足 `vibe flow done` 的收口条件

### Step 8: 写入 handoff

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
- next: <若 PR 已创建，明确写”进入 vibe-integrate 检查 review evidence / CI / merge readiness”；否则写继续 commit 的动作>

## Issues Found (可选)

- type: <flow|doc|command|other>
- severity: <low|medium|high>
- description: <问题描述>
- context: <发现场景>
- suggestion: <改进建议（可选）>
```

`.agent/context/task.md` 的读取、写入与修正义务以 `docs/standards/v3/handoff-governance-standard.md` 为准。

## Restrictions

- **Pre-commit 硬规定**：
  - 不得使用 `git commit --no-verify` 跳过 pre-commit 检查
  - 不得在有 pre-commit 错误（如 mypy、shellcheck、LOC 超限）的情况下继续提交
  - 必须在组织 commit 分组前完成 pre-commit 验证
  - 格式化流程：对所有改动统一格式化 → 提交临时 commit → soft reset → 分组提交
  - 不得保留单独的格式化 commit，格式化修改必须分散到各功能 commit 中
  - 若 pre-commit 自动修复了格式，必须按上述流程处理后再进行分组提交
- 不得在用户确认前静默执行 `git commit`
- 不得把”是否拆多个 PR”的判断偷换成”先发一个再说”
- 不得把 `stash` 当垃圾桶
- 不得把 `discard` 当默认处理方式
- 不得在 skill 层发明 `rebase --onto`、`reset --hard` 等替代串行拆 PR 的主流程
- 若发现当前 flow 已有 PR 事实且用户要开始新目标，应停止并切换 flow，而不是继续堆在原 flow
