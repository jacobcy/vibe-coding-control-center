---
name: vibe-review-pr
description: |
  Use when the user wants a comprehensive PR review using multi-agent team workflow.
  Loads team configuration from .claude/team-templates/ and starts phased review.
---

# Vibe PR Review Skill

## 职责

**本 Skill 只负责**：
1. 环境检查（必须最先执行）
2. 创建审查团队（环境通过后，一次性）
3. PR 队列排序与选择
4. 加载 Team Template
5. 循环审查直到人类确认结束
6. 人类确认后删除团队

**所有配置和流程定义在**：`.claude/team-templates/pr-review-team.yaml`

---

## 执行流程概述

**关键指令**：读取 template 后，按 `workflow.execution` 配置执行 Agent 调用。

```
1. 环境检查（必须先检查，不满足则直接回退）
2. TeamCreate(team_name="pr-review-team") → 环境通过后创建（一次性）
3. 选择执行模式
4. PR 队列排序与选择
5. 循环审查每个 PR（不检查 team，假设已存在）
   - Phase 1-4: 审查流程
   - Phase 5: 只清理 inboxes/tasks（不删除 team）
   - 询问是否继续下一个 PR
6. 人类确认结束审查 → 删除 team
```

**重要**：
- 环境检查必须在 TeamCreate 之前执行
- Team 只在环境检查通过后创建，避免无效创建
- Team 创建是**一次性操作**，整个审查周期只执行一次
- 循环中不检查/创建/删除 Team，假设 Team 已存在
- Team 只在人类明确确认结束审查后才删除
- `subagent_type` 必须匹配项目 `.claude/agents/pr-*.md` 定义
- Phase 2 并行 spawn 需要在**单次响应**中发起多个 Agent tool 调用
- Phase 4/5 由 team-lead（当前 session）执行，不 spawn 新 agent

---

## Step 1: 环境检查（必须最先执行）

**必须先检查环境是否支持 Team 功能，不满足则直接回退，不创建 Team。**

```bash
# 检查 tmux
echo "TMUX: ${TMUX:-未设置}"

# 检查团队模式
env | grep -i "CLAUDE.*TEAM" || echo "未设置"
```

### 环境要求

| 条件 | 要求 | 不满足时 |
|------|------|----------|
| TMUX | 必须设置 | 提示用户 + 直接回退到 vibe-review-code（不创建 Team） |
| CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS | = 1 | 提示用户 + 直接回退 |

**回退处理**：
```
"Team 功能需要在 tmux session 内运行。
 请运行: tmux new-session -s vibe-review
 然后重新启动 Claude Code。

 当前回退到单 agent 审查模式..."

→ 直接使用 vibe-review-code（不创建/删除 Team）
```

不要启动非 tmux team 模式。Team workflow 依赖 tmux panes、SendMessage 和
team cleanup 状态；环境不满足时，**直接回退**，不需要 TeamDelete。

---

## Step 2: 创建团队（环境通过后）

**环境检查通过后才创建 Team**。

```yaml
TeamCreate(team_name="pr-review-team", agent_type="general-purpose")
```

**关键原则**：
- Team 创建是**一次性操作**，整个审查周期只执行一次
- 创建后 Team 持续存在，直到人类确认结束审查
- 环境检查失败时不创建 Team，直接回退

---

## Step 3: 选择执行模式

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
| **执行模式** | 审查后如何处理（修复/评论/询问） | Step 3 询问用户 |
| **PR 类型** | 启动多少 agent（agents 数量） | Step 6 自动判定 |

---

## Step 4: PR 队列排序与选择

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

## Step 5: 加载 Team Template

**Team 已在 Step 2 创建**，这里只加载配置。

**读取配置文件**：`.claude/team-templates/pr-review-team.yaml`

```bash
# 加载团队配置
cat .claude/team-templates/pr-review-team.yaml
```

**Template 是可执行配置**：
- `agents` — 定义 subagent_type 和 spawn_config
- `workflow.execution` — 每个 phase 的具体执行步骤
- `pr_classification` — PR 类型判断规则

**Template 包含**：
- Agent 定义（subagent_type, model, spawn_config）
- PR 类型判断规则
- 工作流程（每个 phase 的 execution 步骤）
- 防幻觉机制
- 输出格式

---

## Step 6: 判断 PR 类型

**自动判定**：根据 PR 行数和标签自动分类，无需用户选择。
**注意**：PR 类型决定启动多少 agent；执行模式在 Step 3 已选择。

根据 Template 中的 `pr_classification` 规则：

| 类型 | 条件 | 流程 | agents |
|------|------|------|--------|
| simple | <50行, 非安全相关 | 回退 vibe-review-code | **0（不启动）** |
| refactor | 标题含 refactor | standard 多人流程 | 3 |
| security | 安全标签或 fix 标签 | 全流程 + Codex | 4 |
| standard | 其他 | standard 多人流程 | 4 |

```bash
gh pr view <number> --json title,labels,additions
```

**simple 类型处理**：
- 不启动 team，根据 PR 标签选择单 agent 审查：
  - `scope/documentation` → 使用 `vibe-review-docs`
  - 其他（`scope/python`、`scope/shell` 等）→ 使用 `vibe-review-code`
- 审查完成后返回 Step 4 处理队列中的下一个 PR

### 复杂情况使用 Codex

**当 PR 满足以下任一条件时，启用 Codex 辅助审查**：

| 复杂度指标 | 条件 | 说明 |
|------------|------|------|
| **代码量** | >500 行 | 大规模改动需更深入分析 |
| **安全相关** | 标签含 `security` 或 `fix` | 安全漏洞需专业审查 |
| **架构影响** | 标题含 `refactor` + >10 文件 | 架构变更需多方评估 |
| **核心模块** | 修改 `src/vibe3/core/` | 核心逻辑需额外验证 |
| **多领域交叉** | 跨 Python/Shell/Config | 多语言需交叉检查 |
| **复杂逻辑** | Agent 报告 flagged as complex | 团队判断需 Codex 深入 |

**Codex 调用方式**：

```yaml
# 在 Phase 2 并行审查中添加 Codex agent
- tool: Agent
  params:
    team_name: pr-review-team
    name: codex-reviewer
    subagent_type: codex:codex-rescue  # 使用 Codex 救援 agent
    model: opus  # Codex 使用 Opus 模型
    prompt: |
      深入分析 PR #{pr_number} 的复杂问题：
      背景信息：{phase_1_output}
      
      重点检查：
      1. 潜在的设计缺陷
      2. 边界条件和异常处理
      3. 性能瓶颈
      4. 安全隐患
      
      提供：
      - 问题诊断
      - 改进建议
      - 风险评估
    run_in_background: true
```

**Codex 结果处理**：
- Codex 报告与其他 agent 报告一起提交给 Phase 3 仲裁
- 如果 Codex 发现严重问题，优先级高于其他 agent
- Codex 建议需要 team-lead 人工确认后才执行

---

## Step 7: 按流程启动 Agent

**重要**：读取 template 中的 `workflow.execution` 配置，按步骤执行。

### 检查是否需要 Spawn 或复用

**在每个 PR 审查开始前检查**：

```bash
# 检查现有 teammates
cat ~/.claude/teams/pr-review-team/config.json | jq '.members[] | select(.name != "team-lead") | {name, isActive}'
```

**复用策略**（来自 template.reuse_policy）：
- 如果存在 idle 状态的 teammates → **SendMessage 唤醒**
- 如果不存在需要的 agent 类型 → spawn 新的

**SendMessage 唤醒方式**：
```yaml
SendMessage(
  to: "context-researcher",  # 使用现有 teammate 名称
  message: |
    新任务：审查 PR #{pr_number}
    
    请收集背景信息并输出报告。
)
```

**关键原则**：
- **第一个 PR**：spawn agents
- **后续 PR**：复用已有 teammates（SendMessage 唤醒）
- 不要为每个 PR spawn 新 agents

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

# Step 5: 等待所有结果（必须等待全部返回）
- action: |
    等待所有 Phase 2 agents 返回 idle notification。
    
    **重要**：必须等待以下全部 agents 返回：
    - code-analyst
    - architect-reviewer  
    - security-reviewer
    
    等待机制：
    1. 检查 ~/.claude/teams/pr-review-team/ 目录下的状态
    2. 或等待系统通知（idle notification）
    3. 超时设置：5 分钟
    
    如果超时仍有 agent 未返回：
    - 记录 WARNING
    - 在报告中标注"部分审查未完成"
    - 不要假设未返回的 agent 同意其他 agent 的结论
```

### Phase 3: 综合判断

**执行步骤**（从 template.workflow.phase_3.execution）：

```yaml
# Step 0: 前置检查（新增）
- action: |
    在进入 Phase 3 前，验证所有 Phase 2 agents 已返回：
    
    required_agents = ["code-analyst", "architect-reviewer", "security-reviewer"]
    received_agents = [从 idle notifications 获取]
    
    missing = set(required_agents) - set(received_agents)
    if missing:
      log_warning(f"缺失审查报告: {missing}")
      在最终报告中标注"审查不完整"
      # 不要假设缺失的 agent 同意其他结论

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

### Phase 5: 循环清理（不删除 Team）

**执行步骤**（由 team-lead 执行）：

```yaml
# 只清理当前 PR 的 inboxes/tasks，Team 继续存在
- actions:
    - 清空 inboxes: rm ~/.claude/teams/pr-review-team/inboxes/*.json
    - 重置 tasks: rm ~/.claude/tasks/pr-review-team/*
```

**重要**：Phase 5 **不删除 Team**，Team 保持存在供下一个 PR 审查使用。

---

## Step 8: 询问是否继续

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

- **选择 continue**：返回 Step 4 处理下一个 PR
- **选择 end**：进入 Step 9（删除 Team）

---

## Step 9: 人类确认后删除 Team（最终步骤）

**只在人类明确确认结束审查后执行**：

```yaml
# 人类确认结束审查
TeamDelete(team_name="pr-review-team")
```

**TeamDelete 自动执行的清理**（无需手动操作）：
1. 杀死 tmux panes（从 config.json 读取 paneId）
2. 删除 team 目录：`~/.claude/teams/pr-review-team/`
3. 删除 tasks 目录：`~/.claude/tasks/pr-review-team/`
4. 清除会话中的 team context

**重要**：
- ❌ 不要手动执行上述步骤
- ✅ 只调用 TeamDelete 工具，它会自动完成全部清理

**关键原则**：
- Team 删除是**最终步骤**，只在人类确认后执行一次
- 整个审查周期中 Team 只创建一次、删除一次
- 循环中不检查/创建/删除 Team

---

## Team-lead 控制规则

1. **不同时启动所有 agent**
2. **Phase 1 完成后才启动 Phase 2**
3. **用 SendMessage 传递背景**
4. **差异必须仲裁**

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
- 直接手动删除目录和杀死 panes
- **会话文件中的 teamName 引用未清除**
- TeamDelete 工具会自动清除会话 context，手动删除不会

**正确的清理顺序**（重要）：
```
1. 等待所有 teammates 完成（idle 状态）
2. 调用 TeamDelete 工具（自动清理会话 context）
3. 不要手动删除目录或杀死 panes
```

**TeamDelete 工具说明**：
```
TeamDelete will fail if the team still has active members.
Gracefully terminate teammates first, then call TeamDelete after all teammates have shut down.
```

**错误做法**（会导致会话残留）：
```bash
# ❌ 错误：直接杀死 panes
tmux kill-pane -t %42

# ❌ 错误：直接删除目录
rm -rf ~/.claude/teams/pr-review-team
```

**正确做法**：
```yaml
# ✅ 正确：使用 TeamDelete 工具
TeamDelete(team_name="pr-review-team")
# 工具会自动：
# 1. 杀死 tmux panes
# 2. 删除 team 目录
# 3. 清除会话中的 team context
```

**补救措施**（如果已手动删除或发现残留）：

**推荐：重启 Claude Code 会话**
```
这是最干净、最可靠的解决方式：
1. 输入 /exit 或 Ctrl+D 退出当前会话
2. 重新启动 Claude Code
3. 新会话不会有残留的 team context
```

**备选：手动清理会话文件**（不推荐，可能影响其他功能）：
```bash
sed -i '' 's/"teamName":"pr-review-team"//g' \
  ~/.claude/projects/-*/{session-id}.jsonl
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
