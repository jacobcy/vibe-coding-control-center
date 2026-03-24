---
name: vibe-task
description: Use when the user wants a cross-worktree flow/task overview, asks which existing flow or task context to resume next in the current repo, wants to inspect task registry health, needs audit and repair of roadmap-task mappings, or mentions "/vibe-task" or "vibe task audit". Do not use for project-level roadmap prioritization or task-flow runtime repair.
---

# /vibe-task - Cross-Worktree Task Overview & Roadmap-Task Audit

查看当前仓库下各个 worktree 当前承载的 `flow / task` 现场总览，并给出下一步优先回到哪个 flow / task 现场的建议。同时也支持核对 task 注册完整性，以及修复 `roadmap <-> task` 对应关系和相关数据质量问题。

**核心原则:** Shell 层负责物理真源和确定性操作，Skill 层负责语义分析、智能判断和用户交互。

`vibe-task` 是 task-centered audit，不处理 runtime / recovery audit。

标准真源：

- 术语与默认动作语义以 `docs/standards/glossary.md`、`docs/standards/action-verbs.md` 为准。
- Skill 与 Shell 边界以 `docs/standards/v3/skill-standard.md`、`docs/standards/v3/command-standard.md`、`docs/standards/v3/python-capability-design.md` 为准。
- 触发时机与相邻 skill 分流以 `docs/standards/v3/skill-trigger-standard.md` 为准。
- task / flow / worktree 生命周期语义以 `docs/standards/v3/git-workflow-standard.md`、`docs/standards/v3/worktree-lifecycle-standard.md` 为准。

**职责拆分:**

- `vibe-task`：负责 `roadmap <-> task` 对应关系、task registry 完整性、task 相关数据质量
- `vibe-check`：负责 `task <-> flow` / runtime 绑定修复
- `vibe-roadmap`：负责规划、分类、版本目标，不负责执行层修复
- `vibe-issue`：负责 GitHub Issue intake、模板补全、查重与创建

对象约束：

- 用户主链：`repo issue -> flow -> plan/spec -> commit -> PR -> done`
- 内部桥接链：`repo issue -> roadmap item -> task -> flow`
- `roadmap item = GitHub Project item mirror`
- `task = execution record / execution bridge`
- `spec_standard/spec_ref` 是 task 的 execution spec 扩展字段
- `task audit` = execution record 审计 / 修复，不是规划层 mirror 同步
- OpenSpec / plans 注册 = execution spec 来源桥接，不是 roadmap item 创建
- 任何判断都必须先读 shell 输出，再做语义分析

**Announce at start:**

- Task overview: "我正在使用 vibe-task 技能来查看跨 worktree 的 flow/task 总览。"
- Audit mode: "我正在使用 vibe-task 技能来核对任务注册完整性和数据质量。"

## Trigger Examples

### Task Overview

- `vibe task`
- `/vibe-task`
- `查看 flow 任务`
- `任务总览`
- `现在该回哪个 flow`
- `当前该回哪个现场`

### Audit Mode

- `vibe task audit`
- `/vibe-task audit`
- `核对任务注册`
- `修复 roadmap 和 task 对应关系`
- `检查 roadmap task 映射`
- `检查任务完整性`
- `修复任务数据`
- `任务健康检查`

## Hard Boundary

**通用原则:**

- 必须通过 `vibe task` 命令获取数据和执行操作
- 不得直接读取或修改 `registry.json`、`worktrees.json`
- 不得自己重写 task 匹配逻辑或数据修复逻辑

**Task Overview 模式:**

- 必须先运行 `vibe task list`
- 不得补充 CLI 未提供的字段
- 若 CLI 已返回 `spec_standard/spec_ref`，必须把它们当作 execution spec 展示或解释

**Audit 模式:**

- 必须通过 `bin/vibe task audit` 获取核对结果
- 允许补充使用 `bin/vibe roadmap audit --check-links ` 获取 roadmap 侧证据
- 必须通过真实存在的 `bin/vibe task add`、`bin/vibe task update`、`bin/vibe task remove` 执行修复操作
- 不得直接修改 JSON 文件
- 所有修复操作必须经过用户确认

如果 CLI 失败，直接报告失败原因并停止，不要绕过 CLI。

## Workflow Mode Selection

根据用户输入选择工作流：

1. **Task Overview 模式**: 用户询问任务总览、flow 优先级或现场去向等
2. **Audit 模式**: 用户请求核对任务注册、修复数据问题等

---

# Task Overview Workflow

查看跨 worktree 的 flow/task 总览和优先级建议。

### Step 1: 运行 CLI

```bash
vibe task list
```

目标：

- 获取当前所有 worktree 的任务总览（JSON 格式）
- 包含 Registry 任务信息

### Step 2: 解析 CLI 输出

从输出中提炼：

- worktree 名称
- 路径
- branch
- state
- current task
- title
- status
- current subtask
- next step
- spec standard / spec ref（如果 CLI 提供）

不得补充 CLI 未提供的字段。

### Step 3: 生成对话摘要

用简洁报告向用户说明：

1. 当前有哪些 worktree
2. 每个 worktree 当前承载的 flow 对应什么 current task
3. 哪些 worktree 是 dirty，哪些是 clean
4. 哪个 flow / 现场最值得优先回到，以及它当前由哪个 worktree 承载
5. 为什么推荐它

优先级建议规则：

- 若某个 worktree 承载的 task `status` 为 `blocked`，优先提示阻塞
- 若存在 `in_progress` 且 `dirty` 的 worktree，优先建议回到该目录当前承载的 flow 收口
- 若多个 worktree 都是 `done` 或 `idle`，明确说明暂无明显优先级差异

### Step 4: 输出格式

输出至少包含：

- `Worktrees`
- `Current task`
- `Current subtask`
- `Next step`
- `State`
- `Recommendation`
- `Execution spec`

示例结构：

```text
Worktrees
- wt-claude-refactor: current task = 2026-03-02-cross-worktree-task-registry, state = active dirty

Recommendation
- 优先回到由 wt-claude-refactor 承载的当前 flow
- 原因：该现场仍处于 dirty 状态，且 next step 已明确
```

---

# Audit Workflow

核对任务注册完整性，发现并修复 `roadmap <-> task` 对应关系及 task 数据质量问题。

**本技能负责的修复类型:**

- task 未关联 roadmap item，但已有确定性映射证据
- roadmap item 缺少 task 反向链接
- task 缺少 roadmap item 反向链接
- task registry 数据质量问题
- task 缺少 `spec_standard/spec_ref` 或 execution spec 与当前资料不一致

**本技能不负责:**

- task runtime / flow 现场修复
- flow 现场状态修复
- worktree 缺失后的 runtime 决策
- `roadmap sync` 语义解释或 GitHub Project mirror 同步

其中前 3 项属于 `vibe-check` 范围；`roadmap sync` 规划层语义属于 `vibe-roadmap`。

**分层核对流程:**

1. **Layer 1: Flow / PR 审计** - 区分哪些 closed flow 只有 `pr_ref`，哪些已经有 task
2. **Layer 2: Task 审计** - 区分哪些 task 缺 `roadmap_item_ids` 或 execution spec
3. **Layer 3: Roadmap 审计** - 区分哪些 roadmap item 缺 `execution_record_id`
4. **Layer 4: 语义分析** - 只在证据足够时做历史补链，不为整齐伪造对象

**修复原则:**

- 能补则补：shell 真源、PR、plan、task README 能唯一推出就补
- 不能唯一推出就保留缺口，并明确说明不会阻塞当前开发流程
- 多任务汇总 PR 允许保持 `PR-only` 或 `tasks[]` 为主，不强造单一 `current_task`

## Step 1: 运行 Shell 层核对

根据用户需求选择核对范围：

### 1.1 注册和桥接核对

```bash
# 完整核对（所有维度）
vibe task audit --all

# 仅分支核对
vibe task audit --check-branches

# 仅 OpenSpec 核对
vibe task audit --check-openspec

# 仅 Plans/PRDs 核对
vibe task audit --check-plans
```

**目标:** 获取各维度的核对结果（纯数据，不含判断）

### 1.2 获取 PR 数据（用于语义分析）

如果有 PR 相关的分支或工作流，获取 PR 上下文：

```bash
# 获取当前分支的 PR 信息
vibe flow review

# 获取指定 PR 的信息
vibe flow review  <pr-number>

# 获取指定分支的 PR 信息
vibe flow review  <branch-name>
```

**返回的 PR 数据包括:**

- PR 编号、标题、描述
- 评论和审查意见
- Commits 列表
- 状态信息（open/merged）
- 分支信息

**处理失败情况:**

- 如果没有 PR，记录"无 PR 数据"，跳过 PR 语义分析
- 如果 `gh` 不可用，记录"GitHub CLI 不可用"，跳过 PR 分析

## Step 2: 解析核对结果

### 2.1 Flow / PR 分层结果

从 `flow-history`、`vibe flow review `、task/plan 证据中提取：

- `PR-linked flows without task`
- `Fully linked chains`

**判断逻辑:**

- 历史 closed flow 只有 `pr_ref` 但无 task：优先影响审计，不默认阻塞当前开发流程
- 若能从 PR + plan/task README 唯一推出 execution record，则允许补最小 task
- 若是多任务汇总 PR，则允许保留 `tasks[]` 或仅保留 `pr_ref`

### 2.2 Task 分层结果

从 `vibe task audit`、`vibe task list`、`vibe task show ` 中提取：

- `Tasks without roadmap item`
- 缺 `spec_standard/spec_ref` 的 task
- 已有 task 但缺 `pr_ref` / issue bridge 的样本

**判断逻辑:**

- 当前活跃 task 缺执行元数据：优先级高，可能影响流程质量
- 历史 completed task 缺 roadmap item：主要影响闭环展示，不一定阻塞开发

### 2.3 分支核对结果

从 `--check-branches` 输出中提取：

- 未注册的分支列表
- 每个分支的 worktree 路径
- 分支名模式（YYYY-MM-DD-slug）

**健康度评估:**

- `healthy`: 所有分支都已注册
- `warning`: 存在未注册分支（可能是遗漏注册）

### 2.4 Execution spec 核对

对 task 相关输出额外检查：

- `spec_standard` 是否存在
- `spec_ref` 是否存在
- 若 roadmap item 已记录 `execution_record_id`，task 是否与该 execution record 对齐

这些字段只作为扩展层桥接信息，不得解释为 GitHub 官方 item 身份。

- `error`: 分支名模式不符合规范

### 2.5 OpenSpec 核对结果

从 `--check-openspec` 输出中提取：

每个 OpenSpec change 的状态：

- change 名称
- 是否有 tasks.md 文件
- tasks.md 中的总任务数
- tasks.md 中的已完成任务数
- 是否已在 registry 中注册

**健康度评估:**

- `synced`: change 已在 registry 中
- `unsynced`: change 未在 registry 中（需要决定是否注册）
- `orphaned`: change 在 registry 中但目录不存在（不应发生）

**优先级判断:**

- 如果 change 有 tasks.md 且已完成任务数 > 0，优先建议注册
- 如果 change 没有 tasks.md，可能是新创建的，询问用户是否需要注册

### 2.6 Plans/PRDs 核对结果

## Step 2.7: 审计输出口径

最终审计结论至少分成四组：

- `PR-linked flows without task`
- `Tasks without roadmap item`
- `Roadmap items without execution record`
- `Fully linked chains`

并明确指出：

- 哪些缺口本轮已补
- 哪些缺口因为证据不足暂时保留
- 哪些缺口不会阻塞当前开发流程

从 `--check-plans` 输出中提取：

- docs/plans 中未注册的文件
- docs/prds 中未注册的文件

**健康度评估:**

- `clean`: 所有文档都已关联任务
- `warning`: 存在散落的计划/PRD 文档

## Step 2.5: PR 语义分析（AI 智能审计）

**这是 Skill 层的核心价值** - 利用 AI 能力理解 PR 内容，识别已完成的任务。

### 2.5.1 分析 PR 描述

从 PR 的 `body` 字段中提取：

**任务引用模式识别:**

- "完成 #task-id" 或 "完成了 #task-id"
- "实现 #task-id" 或 "实现 feature-name"
- "修复 #task-id" 或 "修复 bug-name"
- "Closes #task-id" / "Fixes #task-id" / "Resolves #task-id"

**自然语言任务描述:**

- "This PR implements user authentication" → 可能是一个新任务
- "添加了支付功能" → 可能是一个新任务
- "重构了数据库层" → 可能是一个新任务或子任务

**多任务识别:**

- 一个 PR 可能提到多个完成的任务
- 列表项（"- 完成登录功能\n- 完成注册功能"）
- 章节标题（"## Features\n- Feature A\n- Feature B"）

### 2.5.2 分析 PR Comments 和 Reviews

**从评论中提取:**

- 审查者提到的任务："This completes the auth feature"
- 用户确认："Yes, this implements #task-123"
- 讨论中的任务引用

**置信度判断:**

- 明确引用 task-id → 高置信度
- 自然语言描述 → 中置信度（需要用户确认）
- 模糊提及 → 低置信度（仅作为提示）

### 2.5.3 分析 PR Commits

**从 commit messages 中提取:**

- "feat: implement user login (#123)" → 任务 #123
- "fix(auth): resolve token expiry issue" → 可能是修复任务
- "refactor(db): optimize queries" → 可能是重构任务

**统计信息:**

- Commits 数量
- 修改的文件数
- 代码变更量（additions/deletions）

### 2.5.4 生成任务候选列表

基于 PR 分析，生成：

```json
{
  "pr_number": 123,
  "pr_title": "Implement user authentication",
  "identified_tasks": [
    {
      "type": "referenced",
      "task_id": "2026-03-01-user-auth",
      "confidence": "high",
      "source": "pr_description",
      "evidence": "PR description says 'Completes #2026-03-01-user-auth'"
    },
    {
      "type": "inferred",
      "title": "Add password reset functionality",
      "confidence": "medium",
      "source": "commit_message",
      "evidence": "Commit: 'feat: add password reset'",
      "suggested_action": "create_new_task"
    }
  ]
}
```

**置信度分级:**

- **High**: 明确引用 task-id，可直接关联
- **Medium**: 自然语言描述，需要用户确认
- **Low**: 模糊提及，仅供参考

## Step 3: 扫描文档中的散落任务（增强版）

除了 Shell 层的 `--check-plans`，Skill 层做深度语义扫描：

### 3.1 扫描 docs/plans/\*.md

**识别任务模式:**

- 标题中的任务描述："# User Authentication System"
- TODO 列表："- [ ] Implement login"
- 日期模式："2026-03-01: Start auth implementation"
- 状态标记："[WIP]", "[DONE]", "[BLOCKED]"

### 3.2 扫描 docs/prds/\*.md

**识别 PRD 中的任务:**

- 功能需求章节
- 里程碑定义
- 验收标准

### 3.3 扫描 docs/archives/\*.md

**识别已归档但可能未注册的任务:**

- 旧的计划文档
- 历史功能说明

### 3.4 生成任务候选列表

```json
{
  "scanned_files": [
    {
      "path": "docs/plans/api-redesign.md",
      "identified_tasks": [
        {
          "title": "API Redesign",
          "type": "plan",
          "confidence": "medium",
          "evidence": "Document title and TODO list found",
          "suggested_task_id": "2026-03-07-api-redesign"
        }
      ]
    }
  ]
}
```

## Step 3: 生成修复建议

基于核对结果（Shell 层数据 + AI 语义分析），生成智能修复建议。

### 3.1 数据质量问题

```
📋 数据质量修复结果
- 修复了 N 个 worktree 的 null branch 字段
- 备份文件: worktrees.json.backup
- 状态: ✅ 已自动修复
```

### 3.2 未注册分支

对于每个未注册的分支，生成建议：

```
🌲 未注册分支检测

分支: 2026-03-07-task-registry-audit
Worktree: .agent/worktrees/wt-codex-roadmap-skill
建议操作:
  1. 创建新任务后再绑定分支:
     - vibe task add "Task Registry Audit"
     - vibe task update <task-id> --branch 2026-03-07-task-registry-audit
  2. 关联现有任务: vibe task update <task-id> --branch 2026-03-07-task-registry-audit
  3. 忽略（这不是一个任务分支）

您的选择?
```

### 3.3 PR 识别的任务（AI 智能分析）

对于 PR 语义分析识别出的任务：

```
🎯 PR #123 识别出的任务

PR 标题: Implement user authentication
置信度: 高

识别依据:
- PR 描述明确提到 "完成 #2026-03-01-user-auth"
- Commit message: "feat(auth): implement login flow"
- 审查者确认: "LGTM for auth feature"

建议操作:
  1. 关联到现有任务 #2026-03-01-user-auth
  2. 创建新任务并显式记录 PR:
     - vibe task add "User Authentication" --pr 123
  3. 忽略（任务已存在或不需要跟踪）

您的选择?
```

### 3.4 未同步 OpenSpec Changes

对于每个未同步的 change，生成建议：

```
📦 OpenSpec Change 未同步

Change: task-registry-audit-repair
Tasks.md: ✅ 存在 (12/28 任务已完成)
状态: 未在 registry 中注册

建议操作:
  1. 当前 shell 没有 `--openspec-change` 原子能力；仅报告该 change，等待人类决定是否创建普通 task
  2. 若要先落普通 task，可执行: vibe task add "Task Registry Audit & Repair"
  3. 稍后处理（保留在 OpenSpec 中）

您的选择?
```

### 3.5 文档中识别的任务（AI 扫描）

对于从 docs/ 扫描出的任务：

```
📄 文档中识别的任务

来源: docs/plans/api-redesign.md
置信度: 中

识别依据:
- 文档标题: "API Redesign Plan"
- 包含 TODO 列表: 5 项待办事项
- 创建时间: 2026-03-05

建议操作:
  1. 当前 shell 没有 `--source-path` 原子能力；若要先落普通 task，可执行: vibe task add "API Redesign"
  2. 忽略（这是参考文档，不需要任务跟踪）
  3. 移动到其他目录

您的选择?
```

### 3.6 散落的 Plans/PRDs

```
📄 散落的计划文档

docs/plans/2026-03-02-vibe-new-task-flow-convergence.md - 未关联任何任务
docs/prds/performance-optimization.md - 未关联任何任务

建议操作:
  1. 为每个文档创建新任务
  2. 忽略（这些是参考文档，不需要任务跟踪）
  3. 移动到其他目录

您的选择?
```

## Step 4: 用户交互流程

提供三种修复模式，根据问题数量和用户偏好选择。

### 模式选择

```
检测到以下问题:
- N 个数据质量问题（已自动修复）
- M 个未注册分支
- P 个 PR 识别的任务
- O 个未同步 OpenSpec changes
- D 个散落文档

请选择修复模式:
1. 批量修复（自动处理所有高置信度问题）
2. 逐个确认（每个问题单独询问）
3. 仅查看（不执行修复）
```

### 批量修复模式

**适用场景:** 问题数量多，大部分是高置信度的

**流程:**

1. 显示所有将要执行的操作（按置信度排序）
2. 请求一次性确认："将执行 X 个操作，是否继续？"
3. 按优先级顺序执行：
   - 数据质量修复（自动）
   - 高置信度任务注册（PR 明确引用、分支名匹配）
   - 中置信度任务注册（PR 模糊匹配、文档扫描）
   - 低置信度任务注册（仅供参考）
4. 输出执行结果摘要

**示例:**

```
即将执行以下操作:
✅ 高置信度 (12 项):
  - 关联 PR #123 到任务 #2026-03-01-user-auth
  - 注册分支 2026-03-05-doc-update 为新任务
  ...

⚠️  中置信度 (3 项):
  - 从 docs/plans/api-redesign.md 创建新任务
  - 从 PR #124 描述推断任务
  ...

❓ 低置信度 (1 项):
  - docs/prds/performance.md 可能包含任务（需人工确认）

是否继续？[Y/n]
```

### 逐个确认模式

**适用场景:** 问题数量少，或需要精细控制

**流程:**

1. 对每个问题单独询问用户
2. 提供多个选项：
   - **创建新任务**: 自动生成任务 ID 和标题
   - **关联现有任务**: 从任务列表中选择
   - **忽略**: 跳过此项，不记录
   - **稍后处理**: 保存到待处理列表
3. 如果选择关联现有任务，调用 `vibe task list` 显示任务列表供选择
4. 立即执行用户选择的操作
5. 继续下一个问题

**示例交互:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
问题 1/15: PR #123 识别的任务

PR 标题: Implement user authentication
置信度: 高

识别依据:
- PR 描述: "完成 #2026-03-01-user-auth"
- Commit: "feat(auth): implement login"

建议:
  1. 关联到任务 #2026-03-01-user-auth [推荐]
  2. 创建新任务
  3. 忽略
  4. 稍后处理

您的选择 [1-4]: 1

✅ 已关联 PR #123 到任务 #2026-03-01-user-auth
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 仅查看模式

**适用场景:** 先了解问题全貌，不立即修复

**流程:**

1. 显示所有问题和建议（按类型分组）
2. 显示置信度分布
3. 显示潜在的操作命令
4. 不执行任何操作
5. 提示用户可以手动执行命令

**示例输出:**

```
🔍 任务注册核对报告

━━━━━━ 数据质量 ━━━━━━
✅ 3 个 null branch 字段可修复
   修复命令: vibe task audit --fix-branches

━━━━━━ 未注册分支 ━━━━━━
⚠️  2 个未注册分支:
   - 2026-03-07-audit-feature
     注册命令:
       1. vibe task add "Audit Feature"
       2. vibe task update <task-id> --branch 2026-03-07-audit-feature
   - temp-experiment
     建议: 忽略（非任务分支）

━━━━━━ PR 识别任务 ━━━━━━
🎯 3 个 PR 可能完成任务:
   - PR #123 (高置信度): 完成 #2026-03-01-user-auth
     关联命令: vibe task update 2026-03-01-user-auth --pr 123
   - PR #124 (中置信度): 实现了登录功能
     建议创建: vibe task add "Login Feature" --pr 124

━━━━━━ 置信度分布 ━━━━━━
✅ 高置信度: 8 项（建议自动处理）
⚠️  中置信度: 4 项（建议人工确认）
❓ 低置信度: 2 项（仅供参考）

━━━━━━ 建议操作 ━━━━━━
1. 先修复数据质量: vibe task audit --fix-branches
2. 批量注册高置信度任务（手动执行上述命令）
3. 逐个确认中置信度任务

总耗时估计: 5-10 分钟
```

## Step 5: 执行修复操作

根据用户选择，调用 Shell 命令执行修复。

### 5.1 创建新任务

```bash
vibe task add "<task-title>"
vibe task update "<task-id>" --branch "<branch-name>"
```

OpenSpec change 或文档路径目前没有对应 shell 原子 flag。若需要这类关联，应明确标记为 capability gap，不要自造 `--openspec-change` 或 `--source-path`。

### 5.2 关联现有任务

```bash
# 显示任务列表供用户选择
vibe task list

# 更新任务关联
vibe task update "<task-id>" --branch "<branch-name>"
```

### 5.3 验证修复结果

```bash
# 再次运行核对，确认问题已解决
vibe task audit --all
```

## Step 6: 输出修复报告

生成详细的修复结果摘要，包括数据来源统计。

### 修复报告模板

```
🎯 任务注册核对完成

━━━━━━ 执行摘要 ━━━━━━
处理时间: 2026-03-07 14:32:15
总问题数: 15
已修复: 12
需人工确认: 2
已忽略: 1

━━━━━━ 数据质量 ━━━━━━
✅ 修复了 3 个 null branch 字段
   - wt-feature-a: null → feature/2026-03-01-auth
   - wt-bugfix-b: null → codex/2026-03-05-fix-token
   - wt-docs-c: null → 2026-03-06-docs
   备份: worktrees.json.backup

━━━━━━ 分支核对 ━━━━━━
✅ 注册了 2 个新任务
   - 2026-03-07-audit-feature (来自分支名)
   - 2026-03-05-performance (来自分支名)

━━━━━━ PR 智能识别 ━━━━━━
✅ 关联了 3 个 PR 到任务
   - PR #123 → #2026-03-01-user-auth (置信度: 高)
   - PR #124 → #2026-03-02-login-ui (置信度: 高)
   - PR #125 → #2026-03-03-api (置信度: 中)

🎯 新发现 1 个任务（来自 PR #126）
   - 2026-03-07-bugfix-token (置信度: 中)
   来源: PR 描述 "修复 token 过期问题"

━━━━━━ OpenSpec 核对 ━━━━━━
✅ 同步了 1 个 change
   - task-registry-audit-repair (12/28 完成)

⚠️  1 个 change 待处理
   - api-redesign (0/5 完成)
   建议: 等待 OpenSpec 任务完成后再注册

━━━━━━ 文档扫描 ━━━━━━
✅ 从文档创建了 1 个任务
   - docs/plans/performance-optimization.md → #2026-03-07-perf

⚠️  2 个文档未处理（用户选择忽略）
   - docs/prds/api-v2.md (参考文档)
   - docs/plans/archived/old-feature.md (已归档)

━━━━━━ 置信度分布 ━━━━━━
✅ 高置信度: 9 项 (100% 准确)
   - PR 明确引用: 3
   - 分支名匹配: 2
   - 数据质量: 3
   - OpenSpec 同步: 1

⚠️  中置信度: 4 项 (需验证)
   - PR 模糊匹配: 2
   - 文档扫描: 2

❓ 低置信度: 2 项 (仅供参考)
   - 文档推测: 2

━━━━━━ 任务来源统计 ━━━━━━
Shell 层确定性核对: 5 个任务
AI 层 PR 语义分析: 4 个任务
AI 层文档扫描: 1 个任务
用户手动创建: 2 个任务

━━━━━━ 总体健康度 ━━━━━━
健康度评分: 8.5/10
评级: 良好 ✨

✅ 优点:
   - 所有活跃分支已注册
   - PR 关联度高 (92%)
   - 数据质量良好

⚠️  改进建议:
   - 2 个中置信度任务需人工验证
   - docs/prds/ 目录建议整理
   - 定期运行 vibe task audit 保持数据质量

━━━━━━ 下次建议 ━━━━━━
建议每周运行一次: vibe task audit --all
或集成到 CI/CD: vibe task audit --check-branches --check-openspec
```

### 报告字段说明

**健康度评分计算:**

- 基础分: 10.0
- 数据质量问题: -1.0/个
- 未注册分支: -0.5/个
- 未同步 change: -0.3/个
- 低置信度任务: -0.1/个

**评级标准:**

- 9.0-10.0: 优秀 ✨
- 7.0-8.9: 良好 ✅
- 5.0-6.9: 一般 ⚠️
- < 5.0: 需改进 ❌

**任务来源追踪:**
每个任务记录其来源:

- `shell_deterministic`: Shell 层确定性核对
- `ai_pr_analysis`: AI 分析 PR 语义
- `ai_doc_scan`: AI 扫描文档
- `manual`: 用户手动创建
- `openspec_sync`: OpenSpec 同步

## Failure Handling

### Task Overview 模式

如果 `vibe task list` 失败：

- 直接展示 CLI 返回的阻塞原因
- 明确告诉用户当前无法生成可靠总览
- 不要自行 fallback 到共享 registry 文件

### Audit 模式

如果 `vibe task audit` 失败：

- 直接展示 CLI 返回的错误信息
- 明确告诉用户当前无法完成核对
- 不要尝试自行修复或绕过 CLI

如果修复操作失败：

- 显示失败的操作和错误原因
- 提示用户可以检查备份文件（如 worktrees.json.backup）
- 建议用户手动验证数据完整性
- 不要继续执行后续修复操作

## Terminology Contract

本 skill 统一使用以下术语：

**Task Overview:**

- `worktree`
- `current task`
- `current subtask`
- `next step`
- `dirty`
- `clean`

**Audit:**

- `数据质量` (data quality)
- `未注册分支` (unregistered branch)
- `未同步 change` (unsynced change)
- `散落文档` (orphaned documents)
- `健康度` (health)
- `修复` (repair/fix)
- `核对` (audit/check)

不要改写成其他近义词。

## Architecture Notes

**Shell 层职责** (物理真源):

- 执行具体操作、数据读写
- 提供确定性核对结果（纯数据）
- 不做智能判断或语义分析

**Skill 层职责** (智能编排):

- 调用 Shell 获取数据和执行操作
- 分析数据、评估健康度
- 生成智能建议
- 与用户交互确认
- 不直接修改底层数据文件

**严格遵循三层架构:**

1. Shell 层提供数据和原子操作
2. Skill 层负责语义分析和决策
3. 用户负责最终确认

## Integration with vibe check

任务审计功能已集成到 `vibe check` 命令中，形成完整的闭环工作流。

### 使用方式

```bash
# 运行 task 域审计
vibe check task

# 或单独运行任务审计
vibe task audit
```

### 闭环工作流

```
vibe check task
    ↓
Phase 0: Task Audit (修复任务注册问题)
    ↓
Phase 1-6: 主审计流程
    ↓
完整的项目健康检查
```

**价值:** 确保在进行项目审计时，任务注册数据是完整和准确的，从而提供更可靠的审计结果。
