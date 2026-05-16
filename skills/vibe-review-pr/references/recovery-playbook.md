# recovery-playbook

## Agent 失联

1. `skills/vibe-review-pr/scripts/agent-exist.sh <agent>` 查看状态
2. 若 pane=missing: 重新 spawn
3. 若 alive=inactive/stale: `SendMessage(to=<agent>, message="【lead_ready】")` 测试握手
4. 3 次超时无应答: 标记 dead, 重新 spawn

## Team 状态不一致

1. `TeamDelete(team_name="pr-review-team")`
2. `TeamCreate(team_name="pr-review-team")` 重新创建全部 members
3. 所有 agent 重新握手

## 报告缺失

1. `skills/vibe-review-pr/scripts/agent-event.sh <agent>` 查看事件列表
2. 无 `agent_report` 事件 -> 检查 pane 诊断
3. 有 `agent_report` 但 agent-report.sh 无输出 -> 检查 jq filter

## Fix-executor 握手失败

1. 确认已执行 3 轮 escalating handshake（SKILL.md @handshake_fix_executor）
2. 检查 tmux pane: `tmux capture-pane -t <pane_id> -p -S -200 | grep -E "ToolSearch|SendMessage|InputValidationError|deferred"`
3. 常见原因:
   - Agent 未执行 ToolSearch（deferred tools 未加载）→ 已通过 escalating 消息指导
   - Agent 模型幻觉（认为自己已握手成功但实际未发送）→ 3 轮重试用事实打破幻觉
   - pane 已退出 → 标记 dead
4. 3 次重试失败后: @mark_fix_executor_blocked → 创建 follow-up issue → 继续流程
