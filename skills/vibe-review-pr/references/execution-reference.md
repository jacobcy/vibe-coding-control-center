# execution-reference

只展示消息样例和常用诊断命令。完整流程以 SKILL.md 为准。

## 消息样例

### agent_ready

```
SendMessage(to="team-lead", message="【agent_ready】已就绪")
```

### agent_report

```
SendMessage(to="team-lead", message="【agent_report】

## PR #843 审查报告

# 审查范围
...")
```

## 诊断命令

### 检查 agent 存活

```bash
skills/vibe-review-pr/scripts/agent-exist.sh <agent>
```

### 查看 agent 事件

```bash
skills/vibe-review-pr/scripts/agent-event.sh <agent>
```

### 提取 agent 报告

```bash
skills/vibe-review-pr/scripts/agent-report.sh <agent>
```

### 检查 agent pane 错误

```bash
tmux capture-pane -t <pane-id> -p -S -1000 | grep -E "ToolSearch|SendMessage|InputValidationError"
```
