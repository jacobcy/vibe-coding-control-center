# Execution Reference

承接 `SKILL.md`，提供消息样例与等待策略。SKILL.md 定义生命周期、phase 契约与质量标准；本文件只展示样例。

> 审查会话只有 4 个 phase：背景调研 → 专项审查 → 综合判断 → 写回。完成 Phase 4 控制权回 Step 9。**没有 Phase 5**，不要操作 teammates 的 idle / pane / inbox。

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
      收集 PR #{pr_number} 的背景：
      1. 阅读 CLAUDE.md, AGENTS.md, docs/standards/glossary.md
      2. 读取相关 issue 的 body 与 comments（task/issue-* 分支）
      3. 分析依赖关系与时效性

      完成后通过 SendMessage 发送结构化报告给 team-lead。
  wait: true
```

接收报告优先级：team inbox → teammate-message → 必要时 SendMessage 补发。

## Phase 2: 专项审查

仅适用 `refactor / security / standard`。**Phase 1 必须先完成**，禁止并行启动。

同一响应内并行 spawn：

```yaml
- tool: Agent
  params:
    team_name: pr-review-team
    name: code-analyst
    subagent_type: pr-code-analyst
    model: haiku
    prompt: "分析 PR #{pr_number} 的代码质量。等待背景信息后开始。"
    run_in_background: true

- tool: Agent
  params:
    team_name: pr-review-team
    name: architect-reviewer
    subagent_type: pr-architect-reviewer
    model: sonnet
    prompt: "评估 PR #{pr_number} 的架构影响。等待背景信息后开始。"
    run_in_background: true

- tool: Agent
  params:
    team_name: pr-review-team
    name: security-reviewer
    subagent_type: pr-security-reviewer
    model: sonnet
    prompt: "评估 PR #{pr_number} 的安全性。等待背景信息后开始。"
    run_in_background: true
```

立即广播背景：

```yaml
- tool: SendMessage
  params:
    to: "code-analyst"  # 对每个 Phase 2 agent 都执行
    message: |
      ## PR #{pr_number} 背景报告
      {phase_1_output}
      请基于以上背景开始审查。
```

等待策略：等所有 Phase 2 agents idle；默认 5 分钟超时；超时只能标"部分审查未完成"。

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
