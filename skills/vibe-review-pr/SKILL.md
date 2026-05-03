---
name: vibe-review-pr
description: |
  Use only in Claude Code environments with Agent Teams enabled when the user wants
  a comprehensive PR review using the multi-agent team workflow.
---

# Vibe PR Review Skill

## Overview

`vibe-review-pr` 是 **Claude Code Agent Teams 专用入口**。它依赖
Claude Code 的 TeamCreate / Agent / SendMessage / teammate-message / tmux pane
能力，以及 `.claude/team-templates/` 和 `.claude/agents/pr-*.md`。

非 Claude team 环境（包括 Codex）不要模拟本 workflow，也不要用本 skill
启动替代性 subagent 编排。Codex 审核 PR 时直接走：
- `vibe-review-docs`：docs-only PR
- `vibe-review-code`：源码、脚本、配置、测试，或代码与文档混合 PR

## 职责

**本 Skill 只负责**：
1. 环境检查
2. PR 队列排序与选择
3. 加载 Team Template
4. 启动审查团队

**所有配置和流程定义在**：`.claude/team-templates/pr-review-team.yaml`

---

## When to Use

使用本 skill 之前必须同时满足：
- 当前 host 是 Claude Code
- `TMUX` 已设置
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- 当前工具面提供 TeamCreate / Agent / SendMessage / teammate-message 等 team 能力

不满足任一条件时，停止本 skill，并按 PR 文件范围分流：
- docs-only：使用 `vibe-review-docs`
- 其他：使用 `vibe-review-code`

## 执行流程概述

**关键指令**：读取 template 后，按 `workflow.execution` 配置执行 Agent 调用。

```
1. TeamCreate(team_name="pr-review-team") → 创建 team
2. 读取 template.agents → 确定 subagent_type 和 spawn_config
3. Phase 1: Agent(name="context-researcher", subagent_type="pr-context-researcher", ...)
4. Phase 2: 并行 spawn 3 个 agents（单次响应中多个 Agent 调用）
5. Phase 3: 收集结果，仲裁，决策
6. Phase 4: team-lead 执行写回（Bash tool）
7. Phase 5: 清理或复用
```

**重要**：
- `subagent_type` 必须匹配项目 `.claude/agents/pr-*.md` 定义
- Phase 2 并行 spawn 需要在**单次响应**中发起多个 Agent tool 调用
- Phase 4/5 由 team-lead（当前 session）执行，不 spawn 新 agent

---

## Step 0: 初始化任务跟踪

**启动时创建 task 跟踪进度**（使用 TaskCreate tool）：

```yaml
TaskCreate(
  title: "PR Review Queue",
  description: "审查 PR 队列：自动排序并依次审查"
)
```

创建后后续步骤标记为 in_progress/completed。

---

## Step 1: 环境检查

**必须先检查环境是否支持 Claude Code Team 功能。**

```bash
# 检查 tmux
echo "TMUX: ${TMUX:-未设置}"

# 检查团队模式
env | grep -i "CLAUDE.*TEAM" || echo "未设置"
```

### 环境要求

| 条件 | 要求 | 不满足时 |
|------|------|----------|
| Host | Claude Code | 分流到 `vibe-review-docs` / `vibe-review-code` |
| Team tools | TeamCreate / Agent / SendMessage 可用 | 分流到 `vibe-review-docs` / `vibe-review-code` |
| TMUX | 必须设置 | 分流到 `vibe-review-docs` / `vibe-review-code` |
| CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS | = 1 | 分流到 `vibe-review-docs` / `vibe-review-code` |

**回退处理**：
```
"Claude Code Team 功能需要在 tmux session 内运行。
 请运行: tmux new-session -s vibe-review
 然后重新启动 Claude Code。

 当前回退到单 agent 审查模式..."

-> docs-only PR 使用 vibe-review-docs
-> 其他 PR 使用 vibe-review-code
```

不要启动非 tmux team 模式。Team workflow 依赖 tmux panes、SendMessage 和
team cleanup 状态；环境不满足时，直接转入 `vibe-review-docs` 或
`vibe-review-code` 单 agent 审查。

**Codex 规则**：
- Codex 中遇到 `pr review <number>`、`review PR #<number>` 等请求时，不使用本 skill。
- Codex 先读取 PR metadata/diff/comments，再根据文件范围使用 `vibe-review-docs` 或 `vibe-review-code`。
- Codex 不得用 `spawn_agent`、`multi_tool_use` 或其他工具模拟 `.claude/team-templates/` workflow。

---

## Step 1.5: 选择执行模式

**在开始审查前，询问用户执行模式**（除非用户已指定）。

### 执行模式选项

| 模式 | 描述 | 风险 | 适用场景 |
|------|------|------|----------|
| **auto-fix** | 自动修复审核发现的问题并提交 | 高 | 用户明确要求自动修复 |
| **comment-only** | 只发布审核意见，不修改代码 | 无 | 用户要求只审核不修复 |
| **auto-decide** | team-lead 根据PR复杂度自动决定 | 中 | 用户授权自动决策 |
| **ask-each** | 每次审核完毕后询问用户（默认） | 无 | 最安全，推荐 |

### 询问方式

```yaml
# 使用 AskUserQuestion tool
question: |
  请选择审核后的执行模式：

  1. auto-fix - 自动修复问题并提交
  2. comment-only - 只发布审核意见
  3. auto-decide - 由 team-lead 根据复杂度决定
  4. ask-each - 每次审核完询问（默认）

  输入数字 (1/2/3/4) 或模式名称：

options:
  - key: "1"
    value: "auto-fix"
    description: "自动修复并提交（高风险）"
  - key: "2"
    value: "comment-only"
    description: "只写 comment（安全）"
  - key: "3"
    value: "auto-decide"
    description: "team-lead 自动决策"
  - key: "4"
    value: "ask-each"
    description: "每次询问（推荐）"
```

### 保存选择

将用户选择保存到 team context，供 Phase 4 使用：

```yaml
execution_context:
  mode: user_selected_mode
  pr_number: target_pr
```

### 概念区分

| 概念 | 决定什么 | 在哪个 Step |
|------|----------|-------------|
| **执行模式** | 审查后如何处理（修复/评论/询问） | Step 1.5 询问用户 |
| **PR 类型** | 启动多少 agent（agents 数量） | Step 4 自动判定 |

---

## Step 2: PR 队列排序与选择

当用户没有指定 PR 编号时，先检查当前 repo 的所有未合并 PR，排序后建议审查顺序。

```bash
gh pr list --state open --json number,title,labels,additions,deletions,baseRefName,headRefName,updatedAt
```

### PR 排序规则

优先级从高到低：

1. **merge-ready 状态**：标签含 `state/merge-ready`
2. **最小改动优先**：`additions + deletions` 行数最小
3. **无依赖优先**：`baseRefName == main` 优先于依赖其他 PR 分支
4. **范围重叠处理**：
   - 复杂 PR（改动更多文件）先审查
   - 简单 PR（改动较少文件）后审查
   - 同一文件的多个改动：先审查改动量大的

### PR 依赖关系检测

```bash
gh pr view <number> --json baseRefName,headRefName
```

依赖判断：
- `baseRefName == main`：无依赖，优先审查
- `baseRefName == task/issue-xxx` 或其他 PR 分支：可能依赖另一个 PR，需先审查依赖来源

如果用户已经明确指定 PR 编号，直接审查该 PR，不重新路由到其他 PR。

---

## Step 3: 加载 Team Template 并创建 Team

**读取配置文件**：`.claude/team-templates/pr-review-team.yaml`

```bash
# 加载团队配置
cat .claude/team-templates/pr-review-team.yaml
```

**Template 是可执行配置**：
- `team_create_config` — TeamCreate 参数
- `agents` — 定义 subagent_type 和 spawn_config
- `workflow.execution` — 每个 phase 的具体执行步骤

**创建 Team**（使用 template.team_create_config）：

```yaml
# 从 template 读取配置
team_create_config:
  team_name: pr-review-team
  agent_type: general-purpose

# 执行 TeamCreate
TeamCreate(team_name="pr-review-team", agent_type="general-purpose")
```

**Template 包含**：
- Agent 定义（subagent_type, model, spawn_config）
- PR 类型判断规则
- 工作流程（每个 phase 的 execution 步骤）
- 防幻觉机制
- 输出格式

---

## Step 4: 判断 PR 类型

**自动判定**：根据 PR 行数和标签自动分类，无需用户选择。
**注意**：PR 类型决定启动多少 agent；执行模式在 Step 1.5 已选择。

根据 Template 中的 `pr_classification` 规则：

| 类型 | 条件 | 流程 | agents |
|------|------|------|--------|
| simple | <50行, 非安全相关 | 回退 vibe-review-code | **0（不启动）** |
| refactor | 标题含 refactor | standard 多人流程 | 3 |
| security | 安全标签或 fix 标签 | 全流程 + security-reviewer | 4 |
| standard | 其他 | standard 多人流程 | 4 |

```bash
gh pr view <number> --json title,labels,additions
```

**simple 类型处理**：
- 不启动 team，根据 PR 文件范围选择单 agent 审查：
  - 仅文档变更 → 使用 `vibe-review-docs`
  - 其他（`scope/python`、`scope/shell`、`scope/infrastructure`、配置/测试/混合变更等）→ 使用 `vibe-review-code`
- 审查完成后返回 Step 2 处理队列中的下一个 PR

---

## Step 5: 按流程启动 Agent

**重要**：读取 template 中的 `workflow.execution` 配置，按步骤执行。

### Phase 1: 背景调研

**执行步骤**（从 template.workflow.phase_1.execution）：

```yaml
# Step 1: spawn context-researcher
- tool: Agent
  params:
    team_name: pr-review-team
    name: context-researcher
    subagent_type: pr-context-researcher  # 引用项目 agent 定义
    model: haiku
    prompt: |
      收集 PR #{pr_number} 的背景信息：
      1. 阅读 CLAUDE.md, AGENTS.md, docs/standards/glossary.md
      2. 获取 issue comments（如果是 task/issue-* 分支）
      3. 分析依赖关系和时效性
      输出结构化背景报告。
  wait: true  # 必须等待结果

# Step 2: 接收背景报告
- action: 等待 teammate-message，获取 context-researcher 的背景报告

# Step 3: 准备 Phase 2 上下文
- action: 将背景报告保存为 phase_1_output，用于 SendMessage
```

### Phase 2: 专项审查

**执行步骤**（从 template.workflow.phase_2.execution）：

```yaml
# Step 1: 并行 spawn Phase 2 agents
# 注意：在单次响应中发起多个 Agent 调用实现并行
- tool: Agent
  params:
    team_name: pr-review-team
    name: code-analyst
    subagent_type: pr-code-analyst
    model: haiku
    prompt: |
      分析 PR #{pr_number} 的代码质量：
      背景信息：{phase_1_output}
      1. 检查代码风格和规范符合性
      2. 识别技术债
      3. 评估可维护性
    run_in_background: true

- tool: Agent
  params:
    team_name: pr-review-team
    name: architect-reviewer
    subagent_type: pr-architect-reviewer
    model: sonnet
    prompt: |
      评估 PR #{pr_number} 的架构影响：
      背景信息：{phase_1_output}
      1. 检查架构符合性
      2. 评估扩展性影响
      3. 判断是否有替代方案
    run_in_background: true

- tool: Agent
  params:
    team_name: pr-review-team
    name: security-reviewer
    subagent_type: pr-security-reviewer
    model: sonnet
    prompt: |
      评估 PR #{pr_number} 的安全性：
      背景信息：{phase_1_output}
      1. 检查安全漏洞
      2. 进行红队测试
      3. 评估敏感信息泄露风险
    run_in_background: true

# Step 2-4: 发送上下文（agents 启动后自动接收 team broadcast）
# 注意：run_in_background 的 agents 会自动收到 team context

# Step 5: 等待所有结果
- action: 等待所有 Phase 2 agents 返回 idle notification
```

### Phase 3: 综合判断

**执行步骤**（从 template.workflow.phase_3.execution）：

```yaml
# Step 1: 收集所有报告
- action: 从 idle notifications 获取各 agent 报告

# Step 2: 检测冲突
- action: 对比各报告，找出差异点
  example: |
    code-analyst: "建议使用 logger.bind()"
    architect-reviewer: "当前实现已足够，无需修改"
    → 记录差异，需要仲裁

# Step 3: 仲裁
- condition: 存在冲突
  action: 进行仲裁并记录理由

# Step 4: 最终决策
- action: 生成 APPROVE / REJECT / NEEDS_INFO 决策
```

### Phase 4: 写回与改进

**执行步骤**（由 team-lead 执行，非 spawn）：

```yaml
# Step 1: 写 PR 评论
- tool: Bash
  params:
    command: gh pr comment {pr_number} --body "{review_report}"

# Step 2: 创建 follow-up issues（条件执行）
- condition: has_out_of_scope_findings
  tool: Bash
  params:
    command: gh issue create --title "[follow-up] {title}" --body "{body}"
```

### Phase 5: 清理与复用准备

**执行步骤**（由 team-lead 执行）：

```yaml
- condition: continue_next_pr
  actions:
    - 清空 inboxes: rm ~/.claude/teams/pr-review-team/inboxes/*.json
    - 重置 tasks: rm ~/.claude/tasks/pr-review-team/*

- condition: full_cleanup
  actions:
    - 杀死 panes: 从 config.json 读取 paneId 并 kill-pane
    - 删除 team: rm -rf ~/.claude/teams/pr-review-team
    - 删除 tasks: rm -rf ~/.claude/tasks/pr-review-team
```

---

## Team-lead 控制规则

1. **不同时启动所有 agent**
2. **Phase 1 完成后才启动 Phase 2**
3. **用 SendMessage 传递背景**
4. **差异必须仲裁**

---

## 文件位置

| 文件 | 职责 |
|------|------|
| `skills/vibe-review-pr/SKILL.md` | 本文件：检查和启动 |
| `.claude/team-templates/pr-review-team.yaml` | 团队配置和流程定义 |
| `.claude/agents/pr-*.md` | Agent 详细定义 |
| `docs/references/team-guide.md` | 使用指南 |

---

## 使用方式

```
/vibe-review-pr 604
```

或

```
用 vibe-review-pr 审查 PR #604
```
