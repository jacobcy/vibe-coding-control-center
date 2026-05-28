# debug-guide

## Agent 不回复

1. `skills/vibe-team-review/scripts/agent-exist.sh` — 检查 pane 是否运行
2. `tmux capture-pane -t <pane-id> -p -S -500 | tail -30` — 看最后输出
3. 常见原因:
   - InputValidationError -> 重新 ToolSearch SendMessage
   - Thinking... (busy) -> 等待
   - idle notification (正常通知，agent 正在工作) -> 运行 `agent-event.sh <agent>` 检查事件

## 报告不完整

1. `skills/vibe-team-review/scripts/agent-event.sh <agent>` 查看是否发了 agent_report
2. `skills/vibe-team-review/scripts/agent-report.sh <agent>` 提取完整报告
3. 若报告缺失 -> 检查 pane: `tmux capture-pane` grep token/error
