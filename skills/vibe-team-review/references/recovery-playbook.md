# recovery-playbook

## Agent 失联

1. `skills/vibe-team-review/scripts/agent-exist.sh <agent>` 查看状态
2. 若 pane=missing: 重新 spawn
3. 若 alive=inactive/stale: `SendMessage(to=<agent>, message="【lead_ready】")` 测试握手
4. 3 次超时无应答: 标记 dead, 重新 spawn

## Team 状态不一致

1. `TeamDelete(team_name="pr-review-team")`
2. `TeamCreate(team_name="pr-review-team")` 重新创建全部 members
3. 所有 agent 重新握手

## 报告缺失

1. `skills/vibe-team-review/scripts/agent-event.sh <agent>` 查看事件列表
2. 无 `agent_report` 事件 -> 检查 pane 诊断
3. 有 `agent_report` 但 agent-report.sh 无输出 -> 检查 jq filter
