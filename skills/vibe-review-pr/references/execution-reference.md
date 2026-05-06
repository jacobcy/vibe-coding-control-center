# Execution Reference

本文件承接 `skills/vibe-review-pr/SKILL.md` 中被下沉的长执行样例。主文件只定义流程骨架；需要具体消息形状或 phase 样例时再读本文件。

## Phase 1: 背景调研

目标：收集 PR 背景，并把结果保存为 `phase_1_output`。

适用范围：

- 复杂 PR：作为双阶段检查的第一步
- `simple` PR：这是唯一需要执行的检查阶段，但由 team-lead 使用对应单 agent skill 完成，不继续进入 Phase 2

示例：

```yaml
- tool: Agent
  params:
    team_name: pr-review-team
    name: context-researcher
    subagent_type: pr-context-researcher
    model: haiku
    prompt: |
      收集 PR #{pr_number} 的背景信息：
      1. 阅读 CLAUDE.md, AGENTS.md, docs/standards/glossary.md
      2. 获取 issue comments（如果是 task/issue-* 分支）
      3. 分析依赖关系和时效性

      完成后通过 SendMessage 发送结构化报告给 team-lead。
  wait: true
```

team-lead 接收报告的首选方式：

1. 读取 team inbox
2. 读取 teammate-message
3. 必要时 SendMessage 请求补发

## Phase 2: 专项审查

目标：在同一响应中并行启动多个审查 agent，并把 `phase_1_output` 广播给它们。

仅适用于：

- `refactor`
- `security`
- `standard`

`simple` PR 不进入本节。

示例：

```yaml
- tool: Agent
  params:
    team_name: pr-review-team
    name: code-analyst
    subagent_type: pr-code-analyst
    model: haiku
    prompt: "分析 PR #{pr_number} 的代码质量。等待接收背景信息后开始分析。"
    run_in_background: true

- tool: Agent
  params:
    team_name: pr-review-team
    name: architect-reviewer
    subagent_type: pr-architect-reviewer
    model: sonnet
    prompt: "评估 PR #{pr_number} 的架构影响。等待接收背景信息后开始评估。"
    run_in_background: true

- tool: Agent
  params:
    team_name: pr-review-team
    name: security-reviewer
    subagent_type: pr-security-reviewer
    model: sonnet
    prompt: "评估 PR #{pr_number} 的安全性。等待接收背景信息后开始评估。"
    run_in_background: true
```

然后立即发送背景：

```yaml
- tool: SendMessage
  params:
    to: "code-analyst"
    message: |
      ## PR #{pr_number} 背景报告
      {phase_1_output}
      请基于以上背景分析代码质量。
```

对 `architect-reviewer`、`security-reviewer` 也执行同样的 SendMessage。

等待策略：

- 等待全部 Phase 2 agents 返回 idle notification
- 超时默认 5 分钟
- 超时后只能标注“部分审查未完成”，不能脑补结果

## Phase 3: 综合判断

目标：收集报告、识别缺失、处理冲突、形成最终决策。

最低要求：

1. 检查 `required_agents - received_agents`
2. 缺失报告时标注 `审查不完整`
3. 记录相互矛盾的结论
4. 由 team-lead 仲裁并说明理由

## Phase 4: 写回与改进

目标：根据 execution mode 决定 comment / fix / follow-up issue。

示例：

```yaml
- action: 评估 execution_mode（auto-fix / comment-only / auto-decide / ask-each）

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

范围外发现才允许创建 follow-up issue。

## Phase 5: 准备下一个 PR

目标：保留可复用状态，不做手工清理。

只做两件事：

1. 记录当前 PR 审查完成
2. 保留 teammates 的 idle / pane / inbox 状态

不要：

- 清空 inbox
- 删除 tasks
- 手工 kill panes

## AskUserQuestion 样例

执行模式选择：

```yaml
question: |
  请选择审核后的执行模式：

  1. auto-fix
  2. comment-only
  3. auto-decide
  4. ask-each
```

继续下一个 PR：

```yaml
question: |
  PR #{pr_number} 审查完成。是否继续审查队列中的下一个 PR？
```
