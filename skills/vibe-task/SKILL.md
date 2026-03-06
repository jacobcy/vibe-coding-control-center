---
name: vibe-task
description: Use when the user wants a cross-worktree task overview, says "vibe task" or "/vibe-task", asks which worktree to enter next, wants to review current task status across worktrees, or wants to audit/repair task registry issues.
---

# /vibe-task - Cross-Worktree Task Overview & Audit

查看当前仓库下各个 worktree 绑定的任务总览，并给出下一步优先进入哪个 worktree 的建议。同时也支持核对任务注册完整性和修复数据质量问题。

**核心原则:** Shell 层负责物理真源和确定性操作，Skill 层负责语义分析、智能判断和用户交互。

**Announce at start:**
- Task overview: "我正在使用 vibe-task 技能来查看跨 worktree 的任务总览。"
- Audit mode: "我正在使用 vibe-task 技能来核对任务注册完整性和数据质量。"

## Trigger Examples

### Task Overview
- `vibe task`
- `/vibe-task`
- `查看 worktree 任务`
- `任务总览`
- `现在该进哪个 worktree`
- `哪个 worktree 该优先处理`

### Audit Mode
- `vibe task audit`
- `/vibe-task audit`
- `核对任务注册`
- `检查任务完整性`
- `修复任务数据`
- `任务健康检查`

## Hard Boundary

**通用原则:**
- 必须通过 `bin/vibe task` 命令获取数据和执行操作
- 不得直接读取或修改 `registry.json`、`worktrees.json`
- 不得自己重写 task 匹配逻辑或数据修复逻辑

**Task Overview 模式:**
- 必须先运行 `bin/vibe task list --json`
- 不得补充 CLI 未提供的字段

**Audit 模式:**
- 必须通过 `bin/vibe task audit` 获取核对结果
- 必须通过 `bin/vibe task add/update/remove` 执行修复操作
- 不得直接修改 JSON 文件
- 所有修复操作必须经过用户确认

如果 CLI 失败，直接报告失败原因并停止，不要绕过 CLI。

## Workflow Mode Selection

根据用户输入选择工作流：

1. **Task Overview 模式**: 用户询问任务总览、worktree 优先级等
2. **Audit 模式**: 用户请求核对任务注册、修复数据问题等

---

# Task Overview Workflow

查看跨 worktree 的任务总览和优先级建议。

### Step 1: 运行 CLI

```bash
bin/vibe task list --json
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

不得补充 CLI 未提供的字段。

### Step 3: 生成对话摘要

用简洁报告向用户说明：

1. 当前有哪些 worktree
2. 每个 worktree 正在处理什么 current task
3. 哪些 worktree 是 dirty，哪些是 clean
4. 哪个 worktree 最值得优先进入
5. 为什么推荐它

优先级建议规则：

- 若某个 worktree 的 task `status` 为 `blocked`，优先提示阻塞
- 若存在 `in_progress` 且 `dirty` 的 worktree，优先建议回到该 worktree 收口
- 若多个 worktree 都是 `done` 或 `idle`，明确说明暂无明显优先级差异

### Step 4: 输出格式

输出至少包含：

- `Worktrees`
- `Current task`
- `Current subtask`
- `Next step`
- `State`
- `Recommendation`

示例结构：

```text
Worktrees
- wt-claude-refactor: current task = 2026-03-02-cross-worktree-task-registry, state = active dirty

Recommendation
- 优先进入 wt-claude-refactor
- 原因：它仍处于 dirty 状态，且 next step 已明确
```

---

# Audit Workflow

核对任务注册完整性，发现并修复数据质量问题。

**三阶段核对流程:**
1. **Phase 1: 数据质量修复** - 修复 worktrees.json 的 null branch 字段
2. **Phase 2: 确定性核对** - 分支核对 + OpenSpec 核对 + Plans/PRDs 核对
3. **Phase 3: 语义分析** - PR 语义分析（后续实现）

## Step 1: 运行 Shell 层核对

根据用户需求选择核对范围：

```bash
# 完整核对（所有维度）
bin/vibe task audit --all

# 仅数据质量修复
bin/vibe task audit --fix-branches

# 仅分支核对
bin/vibe task audit --check-branches

# 仅 OpenSpec 核对
bin/vibe task audit --check-openspec

# 仅 Plans/PRDs 核对
bin/vibe task audit --check-plans
```

**目标:** 获取各维度的核对结果（纯数据，不含判断）

## Step 2: 解析核对结果

### 2.1 数据质量修复结果

从 `--fix-branches` 输出中提取：

- 修复的 worktree 数量
- 修复前后对比（null → 实际分支名）
- 是否有备份文件创建

**判断逻辑:**
- 如果修复数量 > 0，提示用户数据质量问题已修复
- 如果修复失败，停止流程并报告错误

### 2.2 分支核对结果

从 `--check-branches` 输出中提取：

- 未注册的分支列表
- 每个分支的 worktree 路径
- 分支名模式（YYYY-MM-DD-slug）

**健康度评估:**
- `healthy`: 所有分支都已注册
- `warning`: 存在未注册分支（可能是遗漏注册）
- `error`: 分支名模式不符合规范

### 2.3 OpenSpec 核对结果

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

### 2.4 Plans/PRDs 核对结果

从 `--check-plans` 输出中提取：

- docs/plans 中未注册的文件
- docs/prds 中未注册的文件

**健康度评估:**
- `clean`: 所有文档都已关联任务
- `warning`: 存在散落的计划/PRD 文档

## Step 3: 生成修复建议

基于核对结果，生成智能修复建议。

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
  1. 创建新任务: vibe task add "Task Registry Audit" --branch 2026-03-07-task-registry-audit
  2. 关联现有任务: vibe task update <task-id> --branch 2026-03-07-task-registry-audit
  3. 忽略（这不是一个任务分支）

您的选择?
```

### 3.3 未同步 OpenSpec Changes

对于每个未同步的 change，生成建议：

```
📦 OpenSpec Change 未同步

Change: task-registry-audit-repair
Tasks.md: ✅ 存在 (12/28 任务已完成)
状态: 未在 registry 中注册

建议操作:
  1. 注册为新任务: vibe task add "Task Registry Audit & Repair" --openspec-change task-registry-audit-repair
  2. 关联现有任务: vibe task update <task-id> --openspec-change task-registry-audit-repair
  3. 稍后处理（保留在 OpenSpec 中）

您的选择?
```

### 3.4 散落的 Plans/PRDs

```
📄 散落的计划文档

docs/plans/api-redesign.md - 未关联任何任务
docs/prds/performance-optimization.md - 未关联任何任务

建议操作:
  1. 为每个文档创建新任务
  2. 忽略（这些是参考文档，不需要任务跟踪）
  3. 移动到其他目录

您的选择?
```

## Step 4: 用户交互流程

提供两种修复模式：

### 模式选择

```
检测到以下问题:
- N 个未注册分支
- M 个未同步 OpenSpec changes
- K 个散落文档

请选择修复模式:
1. 批量修复（自动处理所有问题）
2. 逐个确认（每个问题单独询问）
3. 仅查看（不执行修复）
```

### 批量修复模式

1. 显示所有将要执行的操作
2. 请求一次性确认
3. 按顺序执行所有操作
4. 输出执行结果摘要

### 逐个确认模式

1. 对每个问题单独询问用户
2. 提供多个选项（创建新任务/关联现有任务/忽略）
3. 如果选择关联现有任务，提供任务列表供选择
4. 立即执行用户选择的操作
5. 继续下一个问题

### 仅查看模式

1. 显示所有问题和建议
2. 不执行任何操作
3. 提示用户可以手动执行修复命令

## Step 5: 执行修复操作

根据用户选择，调用 Shell 命令执行修复。

### 5.1 创建新任务

```bash
bin/vibe task add "<task-title>" \
  --branch "<branch-name>" \
  --openspec-change "<change-name>" \
  --source-path "<doc-path>"
```

### 5.2 关联现有任务

```bash
# 显示任务列表供用户选择
bin/vibe task list --json

# 更新任务关联
bin/vibe task update "<task-id>" \
  --branch "<branch-name>" \
  --openspec-change "<change-name>"
```

### 5.3 验证修复结果

```bash
# 再次运行核对，确认问题已解决
bin/vibe task audit --all
```

## Step 6: 输出修复报告

生成修复结果摘要：

```
🎯 任务注册核对完成

数据质量:
- ✅ 修复了 3 个 null branch 字段

分支核对:
- ✅ 注册了 2 个新任务
  - 2026-03-07-task-registry-audit
  - 2026-03-05-doc-update

OpenSpec 核对:
- ✅ 同步了 1 个 change
  - task-registry-audit-repair (12/28 完成)

Plans/PRDs 核对:
- ⚠️ 2 个文档未处理（用户选择忽略）

总体健康度: 良好（8/10）
建议: 定期运行 vibe task audit 保持数据质量
```

## Failure Handling

### Task Overview 模式

如果 `bin/vibe task list` 失败：

- 直接展示 CLI 返回的阻塞原因
- 明确告诉用户当前无法生成可靠总览
- 不要自行 fallback 到共享 registry 文件

### Audit 模式

如果 `bin/vibe task audit` 失败：

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
