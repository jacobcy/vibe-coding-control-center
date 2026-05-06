---
name: vibe-review-pr
description: |
  Use when the user wants a comprehensive PR review using multi-agent team workflow.
  Loads team configuration from .claude/team-templates/ and starts phased review.
---

# Vibe PR Review Skill

## 职责

**本 Skill 只负责**：
1. 环境检查
2. 选择执行模式
3. PR 队列排序与选择
4. 判断 PR 类型并分流（simple → vibe-review-code，standard/security → 多 agent 审核）
5. 创建/复用审查团队（仅 standard/security 类型）
6. 循环审查直到人类确认结束
7. 人类确认后删除团队（如果有）

**所有配置和流程定义在**：`.claude/team-templates/pr-review-team.yaml`

---

## 执行流程概述

**关键指令**：读取 template 后，按 `workflow.execution` 配置执行 Agent 调用。

```
主流程（环境检查通过后）：
1. 选择执行模式
2. PR 队列排序与选择
3. 对每个 PR：
   a. 判断 PR 类型（simple/standard/security）
   b. 根据类型决定审核模式：
      - simple：使用 vibe-review-code（不创建 Team）
      - standard/security：创建/复用 Team，启动多 agent 审核
   c. 执行审核流程
   d. 写回结果
   e. 询问是否继续下一个 PR
4. 人类确认结束审查 → 如果有 Team 则删除
```

**PR 类型与审核模式映射**（关键）：

| PR 类型 | 判断条件 | 审核模式 | Team 创建 |
|---------|----------|----------|-----------|
| simple | <50行 且 非安全相关 | vibe-review-code | ❌ 不创建 |
| standard | 其他 | 多 agent 审核 | ✅ 创建/复用 |
| security | 安全标签或 fix 标签 | 多 agent + security-reviewer | ✅ 创建/复用 |

**重要**：
- **PR 类型判断必须在 Team 创建之前**，避免不必要的 Team 创建/删除
- **Simple 类型不创建 Team**，直接分流到 vibe-review-code
- **Standard/Security 类型才创建 Team**，启动多 agent 审核
- Team 可以复用：第一个 standard/security PR 创建 Team，后续同类 PR 复用
- Team 只在人类明确确认结束审查后才删除
- `subagent_type` 必须匹配项目 `.claude/agents/pr-*.md` 定义
- Phase 2 并行 spawn 需要在**单次响应**中发起多个 Agent tool 调用
- Phase 4/5 由 team-lead（当前 session）执行，不 spawn 新 agent

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

---

## Step 1: 环境检查（必须最先执行）

**必须先检查环境是否支持 Claude Code Team 功能，不满足则直接分流，不创建 Team。**

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
`vibe-review-code` 单 agent 审查，不需要 TeamDelete。

**Codex 规则**：
- Codex 中遇到 `pr review <number>`、`review PR #<number>` 等请求时，不使用本 skill。
- Codex 先读取 PR metadata/diff/comments，再根据文件范围使用 `vibe-review-docs` 或 `vibe-review-code`。
- Codex 不得用 `spawn_agent`、`multi_tool_use` 或其他工具模拟 `.claude/team-templates/` workflow。

---

## Step 2: 选择执行模式

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
| **执行模式** | 审查后如何处理（修复/评论/询问） | Step 2 询问用户 |
| **PR 类型** | 是否创建 Team 及启动多少 agent | Step 4 自动判定 |

---

## Step 3: PR 队列排序与选择

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

## Step 4: 判断 PR 类型并分流

**在创建 Team 之前，必须先判断 PR 类型**，避免不必要的 Team 创建/删除。

### PR 类型判断规则

根据 Template 中的 `pr_classification` 规则：

| 类型 | 条件 | 审核模式 | agents |
|------|------|----------|--------|
| simple | <50行, 非安全相关 | vibe-review-code | **0（不启动）** |
| standard | 其他 | 多 agent 审核 | 3-4 |
| security | 安全标签或 fix 标签 | 多 agent + security-reviewer | 4 |

```bash
gh pr view <number> --json title,labels,additions
```

### 分流逻辑

**关键**：根据 PR 类型决定是否创建 Team。

#### Simple 类型处理

```yaml
# 不创建 Team，直接分流到单 agent 审核
if pr_type == "simple":
  - 检查 PR 文件范围：
    - 仅文档变更 → 使用 vibe-review-docs
    - 其他（代码/配置/测试）→ 使用 vibe-review-code
  - 执行审核
  - 写回结果
  - 返回 Step 3 处理下一个 PR
```

#### Standard/Security 类型处理

```yaml
# 检查是否已有 Team
if team_exists("pr-review-team"):
  # 复用已有 Team
  - 发送 SendMessage 唤醒 teammates
  - 进入 Step 5（多 agent 审核）
else:
  # 创建新 Team
  - TeamCreate(team_name="pr-review-team", agent_type="general-purpose")
  - 进入 Step 5（多 agent 审核）
```

---

## Step 5: 多 agent 审核（仅 standard/security）

**前置条件**：PR 类型为 standard 或 security，Team 已创建或复用。

### 5.1 检查 PR 是否已有审查记录

**在开始审查前，检查 PR 是否已有 review comments**。

```bash
# 检查 PR comments 数量
gh pr view <number> --json comments --jq '.comments | length'

# 检查是否有 bot 或 agent 的审查评论
gh pr view <number> --json comments --jq '.comments[].author.login'
```

#### 处理逻辑

| 情况 | 操作 |
|------|------|
| 无 review comments | 直接进入 Phase 1 |
| 有 review comments（用户） | 询问是否重新审查 |
| 有 review comments（agent/bot） | 询问是否补充审查 |

### 5.2 加载 Team Template

**读取配置文件**：`.claude/team-templates/pr-review-team.yaml`

```bash
# 加载团队配置
cat .claude/team-templates/pr-review-team.yaml
```

**Template 包含**：
- Agent 定义（subagent_type, model, spawn_config）
- PR 类型判断规则
- 工作流程（每个 phase 的 execution 步骤）
- 防幻觉机制
- 输出格式

### 5.3 按流程启动 Agent

**重要**：读取 template 中的 `workflow.execution` 配置，按步骤执行。

#### Phase 1: 背景调研

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

# Step 3: 保存背景报告为 phase_1_output
- action: |
    将背景报告内容保存为变量 phase_1_output
    这是 Phase 2 消息传递的关键输入
```

#### Phase 2: 专项审查

**关键：必须通过 SendMessage 传递 Phase 1 背景**

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
      分析 PR #{pr_number} 的代码质量。
      等待接收背景信息后开始分析。
    run_in_background: true

- tool: Agent
  params:
    team_name: pr-review-team
    name: architect-reviewer
    subagent_type: pr-architect-reviewer
    model: sonnet
    prompt: |
      评估 PR #{pr_number} 的架构影响。
      等待接收背景信息后开始评估。
    run_in_background: true

- tool: Agent
  params:
    team_name: pr-review-team
    name: security-reviewer
    subagent_type: pr-security-reviewer
    model: sonnet
    prompt: |
      评估 PR #{pr_number} 的安全性。
      等待接收背景信息后开始评估。
    run_in_background: true

# Step 2: 【关键】使用 SendMessage 发送 Phase 1 背景给各 agent
- tool: SendMessage
  params:
    to: "code-analyst"
    message: |
      ## PR #{pr_number} 背景报告
      
      {phase_1_output}
      
      请基于以上背景分析代码质量。

- tool: SendMessage
  params:
    to: "architect-reviewer"
    message: |
      ## PR #{pr_number} 背景报告
      
      {phase_1_output}
      
      请基于以上背景评估架构影响。

- tool: SendMessage
  params:
    to: "security-reviewer"
    message: |
      ## PR #{pr_number} 背景报告
      
      {phase_1_output}
      
      请基于以上背景评估安全性。

# Step 3: 等待所有结果（必须等待全部返回）
- action: 等待所有 Phase 2 agents 返回 idle notification
```

#### Phase 3: 综合判断

**执行步骤**（从 template.workflow.phase_3.execution）：

```yaml
# Step 1: 收集所有报告
- action: 从 idle notifications 获取各 agent 报告

# Step 2: 检测冲突
- action: 对比各报告，找出差异点

# Step 3: 仲裁
- condition: 存在冲突
  action: 进行仲裁并记录理由

# Step 4: 最终决策
- action: 生成 APPROVE / REJECT / NEEDS_INFO 决策
```

#### Phase 4: 写回与改进

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

#### Phase 5: 准备下一个 PR（不清理、不删除 Team）

**执行步骤**（由 team-lead 执行）：

```yaml
# 不需要清理 inbox 或 tasks
# - idle_notification 保留用于追踪 agents 状态和 paneId
# - tasks 最终由 TeamDelete 处理

# 只需要记录当前 PR 完成，准备下一个 PR
- action: 记录当前 PR #{pr_number} 审查完成
- action: 保留所有 teammates 的状态信息（paneId、idle_notification）
```

**重要**：Phase 5 **不删除 Team**，Team 和所有状态信息保持存在供下一个 PR 审查使用。

---

## Step 6: 询问是否继续

**每个 PR 审查完成后询问用户**：

```yaml
AskUserQuestion:
  question: |
    PR #{pr_number} 审查完成。是否继续审查队列中的下一个 PR？

    当前队列：{remaining_prs}

  options:
    - key: "y"
      value: "continue"
      description: "继续审查下一个 PR"
    - key: "n"
      value: "end"
      description: "结束审查，删除团队"
```

- **选择 continue**：返回 Step 3 处理下一个 PR
- **选择 end**：进入 Step 7（删除 Team，如果有）

---

## Step 7: 人类确认后删除 Team（最终步骤）

**只在人类明确确认结束审查后执行**：

```yaml
# 人类确认结束审查
if team_exists("pr-review-team"):
  TeamDelete(team_name="pr-review-team")
```

**TeamDelete 自动执行的清理**（无需手动操作）：
1. 杀死 tmux panes（从 config.json 读取 paneId）
2. 删除 team 目录：`~/.claude/teams/pr-review-team/`
3. 删除 tasks 目录：`~/.claude/tasks/pr-review-team/`

**完整清理流程**（重要）：
```yaml
1. 等待所有 teammates 进入 idle 状态
2. 调用 TeamDelete(team_name="pr-review-team")
3. ✅ 建议：重启 Claude Code 会话（清除 UI 残留显示）
```

**关键原则**：
- Team 删除是**最终步骤**，只在人类确认后执行一次
- 整个审查周期中 Team 只创建一次、删除一次
- 循环中不检查/创建/删除 Team

---

## 常见问题与处理

### 问题 1：Context-researcher 报告 "Invalid tool parameters"

**原因**：Agent 尝试调用未授权工具或参数格式错误

**解决方案**：
```yaml
# 确保只调用授权工具
tools: [Read, Grep, Glob, WebFetch, Bash]

# prompt 中明确禁止
prompt: |
  只使用授权工具：Read, Grep, Glob, WebFetch, Bash
  禁止调用：Agent, Edit, Write, TeamCreate, TeamDelete
```

### 问题 2：Architect/Security Reviewer 延迟返回

**现象**：报告已发布后，延迟的 agent 返回重要发现

**解决方案**：
1. 在 Phase 3 前置检查中验证所有 agents 已返回
2. 如有缺失，在报告中明确标注"审查不完整"
3. 设置 5 分钟超时，超时后记录 WARNING

### 问题 3：Phase 2 并行 Spawn 不完整

**现象**：只启动了部分 agents

**解决方案**：
```yaml
# 在单次响应中发起所有 Agent 调用
# 错误：分多次响应
# 正确：在同一条消息中调用 3 个 Agent tools

Agent(..., run_in_background=true)  # code-analyst
Agent(..., run_in_background=true)  # architect-reviewer
Agent(..., run_in_background=true)  # security-reviewer
# 三个调用必须在同一响应中
```

### 问题 4：报告冲突处理

**现象**：不同 agents 给出矛盾结论

**解决方案**：
1. 记录冲突点
2. 进行仲裁（team-lead 负责或请求人类判断）
3. 在报告中说明仲裁理由
4. 不要假设缺失的 agent 同意其他结论

### 问题 5：TeamCreate 与 Agent spawn 状态不一致

**现象**：
- TeamCreate 报错：`Already leading team "pr-review-team"`
- Agent spawn 报错：`Team "pr-review-team" does not exist`

**根因**：
- 系统状态残留：会话记录显示 team 存在，但实际配置文件不存在
- 可能原因：之前 team cleanup 不完整，或会话中断

**解决方案**：
```bash
# 临时方案：手动创建 team 配置
mkdir -p ~/.claude/teams/pr-review-team
echo '{"team_name":"pr-review-team","members":[]}' > ~/.claude/teams/pr-review-team/config.json

# 然后正常 spawn agents
Agent(team_name="pr-review-team", ...)
```

**预防措施**：
1. 每次会话结束时确保 TeamDelete 正确执行
2. 启动前检查 `~/.claude/teams/pr-review-team/` 是否存在残留
3. **如发现残留，建议重启 Claude Code 会话**（最干净的解决方式）

### 问题 6：Team 清理不完整（会话残留）

**现象**：
- UI 显示团队成员仍在 running
- 但 `~/.claude/teams/` 目录已删除
- tmux panes 已杀死

**根因**：
- 直接手动删除目录和杀死 panes，或仅调用 TeamDelete 但未重启会话
- **会话 JSONL 文件中的 teamName 历史记录无法被修改**（append-only 日志）
- TeamDelete 能删除目录，但**不能清除 session JSONL 中已写入的 teamName 字段**

**正确的清理顺序**（重要）：
```
1. 等待所有 teammates 完成（idle 状态）
2. 调用 TeamDelete 工具（删除目录和 tmux panes）
3. ✅ 重启 Claude Code 会话（清除 UI 残留显示）
```

**TeamDelete 工具说明**：
```
TeamDelete will fail if the team still has active members.
Gracefully terminate teammates first, then call TeamDelete after all teammates have shut down.
```

**TeamDelete 的局限性**：
- ✓ 能删除目录和杀死 tmux panes
- ❌ **不能清除 session JSONL 中已写入的 teamName 字段**

**正确做法**：
```yaml
# ✅ 正确：TeamDelete + 重启会话
TeamDelete(team_name="pr-review-team")
# 工具会自动：
# 1. 杀死 tmux panes
# 2. 删除 team 目录
# 3. 删除 tasks 目录
# 但不会清除 session JSONL 中的 teamName

# ✅ 然后重启会话
/exit  # 或 Ctrl+D
# 新会话不会有残留的 team context
```

**补救措施**（如果已手动删除或发现残留）：

**推荐：重启 Claude Code 会话**
```
这是最干净、最可靠的解决方式：
1. 输入 /exit 或 Ctrl+D 退出当前会话
2. 重新启动 Claude Code
3. 新会话不会有残留的 team context
```

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
