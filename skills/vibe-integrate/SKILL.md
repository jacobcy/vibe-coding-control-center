---
name: vibe-integrate
description: Use when the user wants to assess, unblock, and merge one or more PRs, especially stacked PRs, based on CI state, review state, merge order, and post-PR handoff readiness.
---

# /vibe-integrate - PR 整合与合并

## 核心职责

`/vibe-integrate` 负责把 PR 从"已发出"推进到"可合并并已合并"。

**核心职责**：处理 PR 直到可合并状态

### 简单场景（快速通道）

- 纯文本修改
- 文档更新
- 配置调整
- **不要求 review evidence**

### 复杂场景（完整流程）

- 代码逻辑修改
- 架构调整
- **必须有 review evidence**：
  - 优先：在线 Codex/Copilot review
  - 备选：`uv run python src/vibe3/cli.py review base` 本地 review

### 总量/单文件超限场景（额外质量门）

满足以下任一条件时，除了 review evidence，还必须再做一轮代码质量复查：

- 当前分支会让核心代码总量超过 `config/loc_limits.yaml` 中的总量阈值
- 某个单文件超过默认 LOC 限制或 max 限制

这轮复查的目标不是机械阻断，而是确认：

- 是否存在明显可回收的坏味道
- 是否有业务逻辑越界或职责漂移
- 是否只是因为合理聚合导致总量上升
- 是否存在无调用死代码

真源约束：

- 所有总量阈值、单文件阈值、exception 都以 `config/loc_limits.yaml` 为准。
- `/vibe-integrate` 不自行发明阈值，也不凭口头结论接受超限。

## 停止点

- PR 已合并 → 进入 `/vibe-done`
- PR 未合并但有阻塞 → 停留并说明阻塞项

## 必读文档

- `docs/standards/v3/git-workflow-standard.md`
- `docs/standards/v3/worktree-lifecycle-standard.md`
- `docs/standards/v3/command-standard.md`
- `docs/standards/v3/handoff-governance-standard.md`

## 完整流程

```
/vibe-integrate
  ├─ Step 1: 建立整合上下文
  │   ├─ uv run python src/vibe3/cli.py flow show
  │   ├─ uv run python src/vibe3/cli.py flow status
  │   └─ 确认要处理的 PR、stacked 关系
  │
  ├─ Step 2: PR Review 状态审核（分层处理）
  │   ├─ 简单场景（文档/配置）
  │   │   └─ 跳过 review evidence 要求
  │   │
  │   └─ 复杂场景（代码逻辑/架构）
  │       ├─ 检查在线 Codex/Copilot review
  │       ├─ 无在线 review → 等待或触发 @codex comment
  │       └─ 备选：uv run python src/vibe3/cli.py review base
  │
  ├─ Step 3: 审核合并条件
  │   ├─ CI 是否通过
  │   ├─ review evidence 是否存在（复杂场景）
  │   ├─ 是否触发总量 / 单文件 LOC 超限
  │   ├─ 阻塞性 review threads 是否已处理
  │   └─ merge base / stack 顺序是否正确
  │
  ├─ Step 4: 处理阻塞项
  │   ├─ 修复 CI 或 review 阻塞问题
  │   ├─ 处理 LOC 超限后的质量收口
  │   ├─ 推送并重新检查状态
  │   └─ 只修当前 PR 的 follow-up
  │
  ├─ Step 5: 按顺序合并
  │   ├─ CI 通过
  │   ├─ review evidence 存在（复杂场景）
  │   ├─ 阻塞性 review 已处理
  │   └─ 堆叠上游已先合并
  │
  └─ Step 6: 写入 handoff
      ├─ PR 已合并 → 自动进入 /vibe-done
      └─ 有阻塞 → 停留并说明阻塞项
```

## 核心边界

- 允许：检查 CI、检查 review threads、判断堆叠顺序、修复小型 follow-up、推动 merge
- 不允许：直接关闭 task、直接关闭 issue、手工修改共享真源 JSON
- 若 flow 还没有 PR 事实，这不是 `/vibe-integrate` 的阶段，应回到 `/vibe-commit`
- 本 skill 是 `vibe-commit -> vibe-done` 之间的强制中间阶段；只要 PR 已创建，就不能跳过它直接宣告收口

## Workflow

### Step 1: 建立整合上下文

优先读取：

```bash
uv run python src/vibe3/cli.py flow show
uv run python src/vibe3/cli.py flow status
```

必要时再看：

```bash
uv run python src/vibe3/cli.py task status --all --check
```

结合 `vibe3 handoff show` 输出，先确认：

- 当前要处理哪些 PR
- 哪些 PR 是独立的，哪些是 stacked
- 哪些 flow 已经进入 `open + had_pr`

若 handoff 与当前真源或现场不一致，必须在退出前修正，不能把旧 handoff 继续传给下一个环节。

### Step 2: PR Review 状态审核（分层处理）

**重要：根据 PR 类型选择审核策略。**

#### 简单场景（快速通道）

满足以下任一条件，跳过 review evidence 要求：

- 纯文本修改（README、文档、注释）
- 配置调整（.gitignore、.editorconfig）
- 非逻辑性变更（格式化、重命名）

直接进入 Step 3。

#### 复杂场景（完整流程）

涉及以下任一条件，必须有 review evidence：

- 代码逻辑修改（函数、类、算法）
- 架构调整（新增模块、重构）
- 安全相关（认证、授权、加密）

**Review evidence 来源优先级**：

1. **优先：在线 Codex/Copilot review**

   ```bash
   uv run python src/vibe3/cli.py review pr [pr_number]
   ```

   - 检查 PR 上是否有 Codex/Copilot 的 review comment
   - 若无在线 review，在 PR 中添加 `@codex` comment 触发 review
   - 等待 10 分钟后重新检查

2. **备选：本地 review**

   ```bash
   uv run python src/vibe3/cli.py review base
   ```

   - 在线 review 不可用时使用
   - 将 review 结果回贴到 PR comment

**等待在线 Review 完成后再继续**：

- 不可在 Codex/Copilot 的 review 尚未出现在 PR 上时就断言"无阻塞"
- 若 review decision 是 `PENDING` 且没有 review threads，说明 reviewer 尚未完成，**必须等待或告知用户让其确认**
- 默认按异步场景处理：若用户当前不在线或没有急迫性，可先等待 10 分钟，再重新运行一次 `uv run python src/vibe3/cli.py review pr <pr>` 检查是否已有新的在线 review evidence
- 若等待一段时间后仍没有 Codex 在线 comment / review thread，默认由 agent 自动在 PR 中补一条 `@codex` comment 触发评论，再继续停留在 `/vibe-integrate`
- 若 review decision 是 `CHANGES_REQUESTED`，必须先处理 follow-up，不可直接提 merge
- 若再次等待后仍没有任何线上 review，不要把"作者自己看过"当成 review evidence；应优先使用 `uv run python src/vibe3/cli.py review base` 或 browser/subagent 生成外部审查结果，再把结果回贴到 PR comment

### Step 3: 审核合并条件

对每个候选 PR，至少检查：

- CI 是否通过
- review evidence 是否存在
- 是否触发代码总量或单文件 LOC 超限
- 是否还有阻塞性的 unresolved review threads
- merge base / stack 顺序是否正确
- 当前分支是否还需要 review follow-up patch

常用证据入口：

```bash
gh pr view <pr>
gh pr checks <pr>
uv run python src/vibe3/cli.py review pr <pr>
```

LOC / 代码质量证据入口：

```bash
cat config/settings.yaml
bash scripts/hooks/check-python-loc.sh
bash scripts/hooks/check-per-file-loc.sh
uv run python src/vibe3/cli.py review base
```

判断原则：

- **总量超限**：先开展一轮代码质量复查。若复查没有明显问题，包括没有业务逻辑越界、没有明显可拆分的脏聚合、没有无调用死代码，则允许提升代码总量。
- **单文件超限**：先判断是否值得拆分。若值得拆分，应优先拆分后再 merge；若不值得拆分，且职责仍单一、边界清楚、拆分只会放大耦合，则把该文件加入 `config/loc_limits.yaml` 的 exception 处理，并写明 reason。
- **不要**为了压 LOC 机械拆分单一职责但强耦合的聚合文件。
- **例外处理必须落配置**：无论是提升总量阈值还是单文件例外，只要结论是"允许超限"，都必须把对应配置与 reason 一起落到 `config/loc_limits.yaml`，不能只在 PR comment 或 handoff 里口头说明。

### Step 3.5: 总量上限触发时的死代码审计

当 `bash scripts/hooks/check-python-loc.sh` 报告 Python 总量触及或超过 `config/loc_limits.yaml` 中的 `total_file_loc.v3_python` 阈值时，**必须**先开展一轮死代码审计，而不是直接要求提升阈值。

审计目标：

1. **无调用符号扫描**：检查 `src/vibe3/` 中是否存在从未被任何文件 import 或调用的模块、类、函数。
   - 使用 `uv run python src/vibe3/cli.py inspect symbols <file>` 检查可疑模块的引用关系
   - 使用 `uv run python src/vibe3/cli.py inspect files <file>` 查看 imported-by 列表

2. **兼容层残留**：检查是否存在已废弃但仍保留的旧路径、旧接口、旧 fallback。
   - grep deprecated / obsolete / legacy / TODO-remove 等标记
   - 检查 exception 清单中的文件是否因历史原因保留了过时代码

3. **不可达代码**：检查是否存在永远为 True/False 的条件分支、空的 except/catch 块、return 后的死代码。

4. **重复逻辑**：检查是否存在多处复制粘贴的相同逻辑，本应提取为共享函数。

审计结论处理：

- **发现可立即删除的死代码**：在当前分支上清理，重新跑 LOC 检查，若降至阈值内则正常推进。
- **发现死代码但不宜立即删除**（影响面广、需要更多验证）：
  1. 记录死代码线索（文件、函数、行数、为什么判断为死代码）
  2. 创建 issue 说明情况（见 Step 3.6）
  3. 将 issue 编号写入 handoff 留痕
  4. 若清理后总量可降至合理范围，优先要求清理后再 merge

### Step 3.6: 发现死代码时创建 issue

当死代码审计发现需要后续处理但不宜在当前 PR 中立即删除时：

```bash
# 通过 vibe-issue 创建 issue
# 或直接通过 gh issue create
gh issue create \
  --title "cleanup: 死代码清理 - <模块/文件描述>" \
  --label "type/chore,scope/python" \
  --body "<死代码位置、原因、影响评估>"
```

Issue 内容模板：

```markdown
## 死代码线索

- **文件**: `src/vibe3/path/to/file.py`
- **符号**: `function_name` / `ClassName`
- **行数**: ~N 行
- **判断依据**: 无 import 引用 / 兼容层已废弃 / 不可达分支

## 删除风险

- 影响面：哪些模块可能间接依赖
- 是否需要 migration 或 deprecation 周期

## 建议

- 直接删除 / 标记 deprecated 后下个版本删除 / 需要进一步调查
```

创建后将 issue 编号通过 `vibe3 handoff append` 记录。

### Step 4: 处理阻塞项

若发现 CI 或 review 阻塞：

- 在对应分支上修复阻塞问题
- 运行受影响的本地验证命令
- 推送并重新检查远端 CI / review 状态

若发现 LOC 超限：

- 先做一轮质量复查，而不是立刻机械压行数
- 记录是否存在明显问题：
  - 业务逻辑越界
  - 单文件承担多个不相关职责
  - 大量可提取但未提取的重复逻辑
  - 兼容层/过时路径未清理
- 若没有明显问题，再决定：
  - 总量超限：允许提升总量阈值
  - 单文件超限：评估是否拆分；不值得拆分则进入 `config/loc_limits.yaml` 例外

执行细则：

- 总量提升前，必须明确说明为什么当前增长是合理聚合而不是失控膨胀。
- 单文件例外前，必须明确说明为什么拆分收益低，且不会降低边界清晰度。
- 如果复查发现明显业务逻辑越界、职责漂移或坏味道，则优先要求修正，而不是直接提升阈值或加 exception。

限制：

- 只修当前 PR 的 follow-up
- 不得借机把下一个目标混进同一个 PR
- 不得直接改 `.git/vibe/*.json`
- 若当前 PR 已 merged，则旧 plan 视为 terminal state；此阶段只允许补交付证据或 follow-up 链接，不得把新需求写回旧 plan
- merge 后出现的新目标必须重新进入 `repo issue` intake，而不是继续挂在已完成 plan 下

### Step 4.5: 单文件 exception 容量约束

将文件加入 `config/loc_limits.yaml` 的 exception 清单时，必须遵守容量约束：

- **exception 文件的 limit 不得超过 max 阈值**（当前 `code_limits.single_file_loc.max = 400`，orchestra 类文件允许到 650 属已批准的例外）
- **新增 exception 必须写明 reason**，说明为什么职责单一、边界清楚、拆分只会放大耦合
- **已有 exception 文件如果继续增长**，需重新评估 limit 是否仍合理；如果接近新 limit 的 90%，应在 handoff 中标注预警
- **不要**因为"反正已经在 exception 里"就无限制增长；exception 是治理触发器后的安全阀，不是免死金牌

### Step 5: 按顺序合并

只有同时满足以下条件，才允许 merge：

- CI 通过
- 已存在 review evidence
- 若命中 LOC 超限，已完成额外代码质量复查且结论允许 merge
- 阻塞性 review 已处理完成（`APPROVED` 或所有 unresolved thread 已 resolve）
- 堆叠上游已先合并
- 当前 PR 已达到可合并状态

遇到 stacked PR 时，必须按依赖顺序推进，不得跳序合并。

### Step 5.5: 交接到 `/vibe-done`

只有当前 PR 已进入终态，才允许把下一步交给 `/vibe-done`：

1. 当前 PR 已经 merged
2. 或当前 PR 已被明确 close / abort，且用户要做终态记录与 issue closeout

若还不满足，`next` 必须继续留在 `/vibe-integrate`，并明确写出阻塞项。

### Step 6: 写入 handoff

完成后运行：

```bash
uv run python src/vibe3/cli.py handoff append "vibe-integrate: PR review completed" --actor vibe-integrate --kind milestone
```

```markdown
## Skill Handoff

- skill: vibe-integrate
- updated_at: <ISO-8601>
- flow: <feature-or-none>
- branch: <branch-or-none>
- task: <task-id-or-none>
- pr: <merged-or-pending-pr-ref>
- issues: <issue-refs-or-none>
- completed: <本轮已合并或已解除阻塞的 PR>
- next: <若已满足条件，交给 vibe-done；否则明确继续 vibe-integrate，并写清 review evidence / CI / unresolved threads 中哪一项仍阻塞>

## Issues Found (可选)

- type: <flow|doc|command|other>
- severity: <low|medium|high>
- description: <问题描述>
- context: <发现场景>
- suggestion: <改进建议（可选）>
```

## Restrictions

- 不得把 Codex / Copilot 的 review 线程一律当噪声忽略
- 不得在未验证 CI 的情况下声称"可合并"
- 不得在 review 尚未完成（无 review threads、decision 为 PENDING）的情况下声称"无阻塞"
- 不得跳过 stack 顺序
- 不得直接关闭 task 或 issue
- 不得因为总量超限就机械要求压行；必须先做质量复查
- 不得因为单文件超限就机械拆分；必须先判断是否值得拆分
- 不得在需要进 `config/loc_limits.yaml` 例外时只口头说明，必须把 exception 和 reason 一起落到配置
- 不得在发现明显业务逻辑越界时，仍以"允许提升总量/允许例外"为结论继续 merge
- 不得跳过总量上限触发时的死代码审计；触及阈值必须先审计再决定
- 不得在 exception 文件中无限制增长 LOC；exception 是安全阀不是免死金牌
- 若 PR 尚未达到合并条件，必须停在整合阶段并说明阻塞项
