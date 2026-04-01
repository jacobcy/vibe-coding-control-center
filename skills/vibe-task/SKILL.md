---
name: vibe-task
description: Use when the user wants a cross-worktree flow/task overview, asks which existing flow or task context to resume next in the current repo, wants to inspect task registry health, needs flow/task status check and repair, or mentions "/vibe-task". Do not use for project-level roadmap prioritization or task-flow runtime repair.
---

# /vibe-task - Cross-Worktree Flow Overview & Metadata Audit

查看当前仓库下各个 worktree 当前承载的 `flow / task` 现场总览，并给出下一步优先回到哪个 flow / task 现场的建议。同时也支持核对任务元数据完整性，以及修复相关数据质量问题。

**核心原则:** Shell 层负责物理真源和确定性操作，Skill 层负责语义分析、智能判断和用户交互。

`vibe-task` 处理以 task 为桥接语义的 flow 总览与任务元数据审计，不处理 runtime / recovery audit。

> 项目命令参考见 `skills/vibe-instruction/SKILL.md`

**职责拆分:**

- `vibe-task`：负责 task 对应关系、task registry 完整性、task 相关数据质量
- `vibe-check`：负责 `task <-> flow` / runtime 绑定修复
- `vibe-roadmap`：负责规划、分类、版本目标，不负责执行层修复
- `vibe-issue`：负责 GitHub Issue intake、模板补全、查重与创建

对象约束：

- 用户主链：`repo issue -> flow -> plan/spec -> commit -> PR -> done`
- 内部桥接链：`repo issue -> task -> flow`
- 任何判断都必须先读 shell 输出，再做语义分析

**Announce at start:**

- Task overview: "我正在使用 vibe-task 技能来查看跨 worktree 的 flow/task 总览。"
- Audit mode: "我正在使用 vibe-task 技能来核对任务注册完整性和数据质量。"

## References

- [docs/standards/glossary.md](../../docs/standards/glossary.md)
- [docs/standards/action-verbs.md](../../docs/standards/action-verbs.md)
- [docs/standards/v2/git-workflow-standard.md](../../docs/standards/v2/git-workflow-standard.md)
- [docs/standards/v2/worktree-lifecycle-standard.md](../../docs/standards/v2/worktree-lifecycle-standard.md)


### Task Overview

- `vibe task`
- `/vibe-task`
- `查看 flow 任务`
- `任务总览`
- `现在该回哪个 flow`
- `当前该回哪个现场`

### Audit Mode

- `/vibe-task audit`
- `核对任务注册`
- `修复任务数据对应关系`
- `检查任务映射`
- `检查任务完整性`
- `修复任务数据`
- `任务健康检查`

## Hard Boundary

**通用原则:**

- Task Overview 模式必须通过 `uv run python src/vibe3/cli.py status` / `flow show` 命令获取数据
- Audit 模式必须通过 `uv run python src/vibe3/cli.py check` 命令进行核对和修复
- 不得直接读取或修改 `registry.json`
- 不得自己重写 task 匹配逻辑或数据修复逻辑

**Task Overview 模式:**

- 必须先运行 `uv run python src/vibe3/cli.py status`
- 不得补充 CLI 未提供的字段
- 不得补充 CLI 未提供的字段

**Audit 模式:**

- 必须通过 `uv run python src/vibe3/cli.py check --all` 获取核对结果
- 必须通过 `uv run python src/vibe3/cli.py check --fix` 执行修复操作
- 不得直接修改 JSON 文件
- **所有修复操作必须在用户明确确认后执行**

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
uv run python src/vibe3/cli.py status
uv run python src/vibe3/cli.py flow show
```

目标：

- 获取当前所有活跃 flow 的总览
- 必要时补当前 flow 的 task 绑定详情

### Step 2: 解析 CLI 输出

从输出中提炼：

- worktree 名称
- 路径
- branch
- flow state
- current task issue
- issue title
- PR / worktree 状态
- next step

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

核对任务注册完整性，发现并修复 task 对应关系及 task 数据质量问题。

**本技能负责的修复类型:**

- task 数据质量问题
- task 绑定的 task issue 缺失或与当前资料不一致

**本技能不负责:**

- task runtime / flow 现场修复
- flow 现场状态修复
- worktree 缺失后的 runtime 决策

其中前 3 项属于 `vibe-check` 范围。

## Step 1: 运行 Shell 层核对

根据用户需求选择核对范围：

```bash
# 完整核对
uv run python src/vibe3/cli.py check --all
```

**注意**: 修复操作 (`--fix`) 必须在用户确认后才可执行。

## Step 2: 解析核对结果

### 2.1 Task 分层结果

从命令输出中提取：

- Tasks without issue
- 缺绑定 task issue 的 task
- 已有 task 但缺 `pr_ref` 的样本

**判断逻辑:**

- 当前活跃 task 缺执行元数据：优先级高，可能影响流程质量
- 历史 completed task 缺数据：主要影响闭环展示，不一定阻塞开发

## Step 3: 生成修复建议

基于核对结果，生成智能修复建议。

### 3.1 数据质量问题

```
📋 数据质量修复结果
- 修复了 N 个问题
- 状态: ✅ 已自动修复
```

## Step 4: 用户交互流程

提供三种修复模式，根据问题数量和用户偏好选择。

### 模式选择

```
检测到以下问题:
- N 个数据质量问题（已自动修复）
- M 个需要确认的问题

请选择修复模式:
1. 批量修复（自动处理所有高置信度问题）
2. 逐个确认（每个问题单独询问）
3. 仅查看（不执行修复）
```

## Step 5: 执行修复操作

**修复前必须获得用户明确确认。**

根据用户确认，调用 Shell 命令执行修复：

```bash
uv run python src/vibe3/cli.py check --fix
```

### 5.1 验证修复结果

```bash
# 再次运行核对，确认问题已解决
uv run python src/vibe3/cli.py check --all
```

## Step 6: 输出修复报告

生成详细的修复结果摘要，包括数据来源统计。

```
🎯 任务注册核对完成

━━━━━━ 执行摘要 ━━━━━━
处理时间: 2026-03-07 14:32:15
总问题数: 15
已修复: 12
需人工确认: 2
已忽略: 1

━━━━━━ 总体健康度 ━━━━━━
健康度评分: 8.5/10
评级: 良好 ✨

✅ 优点:
   - 所有活跃分支已注册
   - PR 关联度高 (92%)
   - 数据质量良好

⚠️  改进建议:
   - 定期运行 uv run python src/vibe3/cli.py check 保持数据质量
```

## Failure Handling

### Task Overview 模式

如果命令失败：

- 直接展示 CLI 返回的阻塞原因
- 明确告诉用户当前无法生成可靠总览
- 不要自行 fallback 到共享 registry 文件

### Audit 模式

如果命令失败：

- 直接展示 CLI 返回的错误信息
- 明确告诉用户当前无法完成核对
- 不要尝试自行修复或绕过 CLI

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
