# Recovery Playbook

本文件定义 `vibe-review-pr` 的恢复边界。原则只有一条：**不要手工伪造或篡改 team 内部状态**。

## TeamCreate 与 Agent 状态不一致

现象：

- `TeamCreate` 报 `Already leading team "pr-review-team"`
- `Agent` 报 `Team "pr-review-team" does not exist`

处理：

1. 停止当前审查轮
2. 不继续 spawn / SendMessage
3. 退出当前 Claude Code 会话
4. 重新进入后从 Step 1 环境检查重新开始
5. 重新判断目标 PR 是否需要多人流程
6. 如仍需要，只通过 `TeamCreate(team_name="pr-review-team")` 重建

禁止：

- 手工创建 `~/.claude/teams/pr-review-team/`
- 手工写 `config.json`

## TeamDelete 后 UI 残留

现象：

- `~/.claude/teams/` 已删
- tmux panes 已杀死
- UI 仍显示 teammates running

原因：

- session JSONL 是 append-only
- TeamDelete 不会抹掉历史 `teamName`

处理：

1. 等待 teammates idle
2. 调用 TeamDelete
3. 退出当前会话
4. 重新进入新会话

禁止：

- 手工编辑 `~/.claude/projects/.../*.jsonl`
- 期待 TeamDelete 立刻清除 UI 历史显示

## Phase 2 agent 缺失或超时

处理：

1. 记录缺失的 agent 名称
2. 在最终报告中标注 `审查不完整`
3. 不替缺失 agent 推断立场
4. 需要时人工决定是否重跑该 PR

## 背景报告未送达

优先级顺序：

1. 检查 team inbox / teammate-message
2. 用 SendMessage 请求 context-researcher 补发
3. 若仍无法获取，停止进入 Phase 2

不要让 Phase 2 在没有 `phase_1_output` 的情况下继续。

## 手工清理禁令

以下都属于错误恢复：

```bash
tmux kill-pane -t %42
rm -rf ~/.claude/teams/pr-review-team
rm -rf ~/.claude/tasks/pr-review-team
```

正确做法始终是：

1. 通过 TeamDelete 清理
2. 通过重启会话消除 UI 残留
