# Execution Reference

承接 `SKILL.md`，提供消息样例与等待策略。SKILL.md 定义生命周期、phase 契约与质量标准；本文件只展示样例。

> 审查会话只有 4 个 phase：背景调研 → 专项审查 → 综合判断 → 写回。完成 Phase 4 控制权回 Step 9。**没有 Phase 5**，不要操作 teammates 的 idle / pane / inbox。

## Step 6: TeamCreate + Backlog Setup

> **顺序铁律**：先 TeamCreate，后 TaskCreate。反序创建的 task 不关联 team，TaskList 永远返回空。

```python
# 1. 创建 Team
TeamCreate(team_name="pr-review-team", description="PR review for PR #{pr_number}")

# 2. TeamCreate 成功后立即创建 phase 追踪 tasks
t1 = TaskCreate(subject="Phase 1: Context research",    description="...")
t2 = TaskCreate(subject="Phase 2: Parallel review",     description="...")
t3 = TaskCreate(subject="Phase 2.5: Codex verification", description="(optional) >500 LOC trigger")
t4 = TaskCreate(subject="Phase 3: Synthesis",           description="...")
t5 = TaskCreate(subject="Phase 4: Write back",          description="...")

# 3. 立即将 Phase 1 标记为 in_progress 并归属 team-lead
TaskUpdate(taskId=t1.id, status="in_progress", owner="team-lead")

# TaskList 可随时验证 5 个 task 都可见
```

## Phase 1: 背景调研

产出 `phase_1_output` 并回传 team-lead。

```yaml
- tool: Agent
  params:
    team_name: pr-review-team
    name: context-researcher
    subagent_type: pr-context-researcher
    model: haiku
    prompt: |
      【第一步只能握手】
      你现在不得开始调研。
      先执行 ToolSearch(query="select:SendMessage", max_results=1)，
      然后立刻 SendMessage(to="team-lead", message="已就绪")。
      在收到 team-lead 后续正式任务前，不得开始任何调研。

- tool: SendMessage
  params:
    to: "context-researcher"
    message: |
      请先执行 ToolSearch(query="select:SendMessage", max_results=1)。
      完成后仅回复“已就绪”；未完成握手前不得开始任何调研工作。

- tool: SendMessage
  params:
    to: "context-researcher"
    message: |
      【正式调研任务】
      收集 PR #{pr_number} 的背景：
      1. 阅读 CLAUDE.md, AGENTS.md, docs/standards/glossary.md
      2. 读取相关 issue 的 body 与 comments（task/issue-* 分支）
      3. 分析依赖关系与时效性

      完成后通过 SendMessage 发送结构化报告给 team-lead。
```

接收报告优先级：team inbox → teammate-message → 必要时 SendMessage 补发。
fresh spawn 只有在收到"已就绪"后，team-lead 才能把该 teammate 视为有效执行者。
未收到 ready 的 context-researcher，即使后续发来报告，也不得作为有效 Phase 1 输出。
握手成功后，才通过第二条 SendMessage 下发正式调研任务。

## Phase 2: 专项审查

仅适用 `refactor / security / standard`。**Phase 1 必须先完成**，禁止并行启动。

fresh spawn 的 Phase 2 agent 不在初始 prompt 中接收正式审查任务。
它们必须先完成握手并发送"已就绪"，之后再由 team-lead 通过第二条 SendMessage 下发背景和正式任务。

同一响应内并行 spawn：

```yaml
- tool: Agent
  params:
    team_name: pr-review-team
    name: code-analyst
    subagent_type: pr-code-analyst
    model: sonnet
    prompt: |
      【第一步只能握手】
      你现在不得开始审查。
      先执行 ToolSearch(query="select:SendMessage", max_results=1)，
      然后立刻 SendMessage(to="team-lead", message="已就绪")。
      在收到 team-lead 后续正式任务前，不得开始任何审查。
    run_in_background: true

- tool: SendMessage
  params:
    to: "code-analyst"
    message: |
      请先执行 ToolSearch(query="select:SendMessage", max_results=1)。
      完成后仅回复“已就绪”；未收到握手确认前，不得开始审查。

- tool: SendMessage
  params:
    to: "code-analyst"
    message: |
      【正式审查任务】
      分析 PR #{pr_number} 的代码质量。

      ## PR #{pr_number} 背景报告
      {phase_1_output}

      请基于以上背景开始审查。

- tool: Agent
  params:
    team_name: pr-review-team
    name: architect-reviewer
    subagent_type: pr-architect-reviewer
    model: opus
    prompt: |
      【第一步只能握手】
      你现在不得开始审查。
      先执行 ToolSearch(query="select:SendMessage", max_results=1)，
      然后立刻 SendMessage(to="team-lead", message="已就绪")。
      在收到 team-lead 后续正式任务前，不得开始任何审查。
    run_in_background: true

- tool: SendMessage
  params:
    to: "architect-reviewer"
    message: |
      请先执行 ToolSearch(query="select:SendMessage", max_results=1)。
      完成后仅回复“已就绪”；未收到握手确认前，不得开始审查。

- tool: SendMessage
  params:
    to: "architect-reviewer"
    message: |
      【正式审查任务】
      评估 PR #{pr_number} 的架构影响。

      ## PR #{pr_number} 背景报告
      {phase_1_output}

      你可以使用 Bash 工具补充读取 diff / git show / git log 数据。

- tool: Agent
  params:
    team_name: pr-review-team
    name: security-reviewer
    subagent_type: pr-security-reviewer
    model: sonnet
    prompt: |
      【第一步只能握手】
      你现在不得开始审查。
      先执行 ToolSearch(query="select:SendMessage", max_results=1)，
      然后立刻 SendMessage(to="team-lead", message="已就绪")。
      在收到 team-lead 后续正式任务前，不得开始任何审查。
    run_in_background: true

- tool: SendMessage
  params:
    to: "security-reviewer"
    message: |
      请先执行 ToolSearch(query="select:SendMessage", max_results=1)。
      完成后仅回复“已就绪”；未收到握手确认前，不得开始审查。

- tool: SendMessage
  params:
    to: "security-reviewer"
    message: |
      【正式审查任务】
      评估 PR #{pr_number} 的安全性。

      ## PR #{pr_number} 背景报告
      {phase_1_output}
```

除强制握手和正式任务激活外，fresh spawn 不需要额外 SendMessage 传背景。只有两类场景继续使用 SendMessage：

- 复用上一轮已经存在的 teammate
- Phase 2 过程中需要补发额外上下文

但“握手用的 SendMessage”不在上述例外之外，它是 fresh spawn 的强制 gate：
- 未回复“已就绪”的 teammate 不计入有效执行
- 未通过握手的 teammate 报告必须丢弃，并在最终结论中标注审查不完整

```yaml
- tool: SendMessage
  params:
    to: "code-analyst"
    message: |
      ## 切换到 PR #{next_pr_number}
      {phase_1_output_of_next_pr}
      请基于以上背景分析新的 PR。
```

等待策略：idle 只表示空闲/等待态，最终结果以 `task-notification(status=completed)` 为准；默认 5 分钟超时；超时只能标"部分审查未完成"。

### 多 PR 复用模式（第二个及之后的 PR）

**不 spawn 新 agent**，给已有 agent 发新任务：

```yaml
- tool: SendMessage
  params:
    to: "code-analyst"
    message: |
      ## 切换到 PR #{next_pr_number}
      {phase_1_output_of_next_pr}
      请基于以上背景分析新的 PR。
```

## Phase 3: 综合判断

### 消息验证（强制）

```
if message.pr_number != current_pr_number:
    检查 session 文件 → 确认是否存在正确报告 → 标注消息路由错误
```

定位 session 文件（消息错误时）：

```bash
cat ~/.claude/teams/pr-review-team/config.json | jq '.members[] | select(.name=="architect-reviewer")'
cat ~/.claude/projects/.../<sessionId>.jsonl | grep -A 5 "PR #"
```

### 缺失处理

1. 检查 `required_agents - received_agents`
2. 缺失 → 标"审查不完整"
3. 冲突 → team-lead 仲裁并说明理由

禁止：脑补缺失 agent 立场 / 假装收到完整报告 / 用错误内容作审查依据。

### 写回前质量自查（按 SKILL.md 的 Review Quality Standards 8 条）

逐条核对：无虚假评分、每条违规有规则引用、数字基于本 PR diff、不滑动靶点、无无关指标、扫了重复模式、测试评估区分性质、comment 格式合规。任一不满足先修正。

## Phase 4: 写回与改进

```yaml
- action: 评估 execution_mode

- condition: mode == "auto_fix"
  tool: Agent
  params:
    team_name: pr-review-team
    name: fix-executor
    subagent_type: pr-fix-executor

- tool: Bash
  params:
    command: gh pr comment {pr_number} --body "{final_report}"
```

**comment 应含**：决策一行 / 已解决（带 diff） / 遗留（带规则引用） / follow-up issue 链接 / 审查依据。

**comment 禁含**：百分制 / 字母评分 / 内部 phase 标题作叙事结构 / 与本 PR 无关的项目级指标。

范围外的真实技术债转 follow-up issue，不塞 comment。

## Step 10: 会话结束（TeamDelete 前必发 shutdown_request）

```python
# 1. 向所有活跃 teammates 广播 shutdown_request
for agent in ["code-analyst", "architect-reviewer", "security-reviewer", "context-researcher"]:
    SendMessage(to=agent, message={"type": "shutdown_request"})

# 2. 等待 idle 通知（通常 < 5s），然后执行 TeamDelete
TeamDelete()

# 3. 若 TeamDelete 返回 "no team found"（agents 已自行退出）
#    fallback 手动清理：
#    rm -rf ~/.claude/teams/pr-review-team ~/.claude/tasks/pr-review-team
```

## AskUserQuestion 样例

执行模式：

```yaml
question: 请选择审核后的执行模式：1. auto-fix  2. comment-only  3. auto-decide  4. ask-each
```

继续下一 PR：

```yaml
question: |
  PR #{pr_number} 审查完成。是否继续？
  - continue: 复用当前 Team / agents 审查下一个
  - end: TeamDelete，结束会话
```
