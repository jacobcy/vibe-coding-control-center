# Recovery Playbook

本文件定义 `vibe-review-pr` 的恢复边界。原则只有一条：**不要手工伪造或篡改 team 内部状态**。

补充硬规则：

- 不要把 `TeamDelete` 当作恢复工具
- 不要发送 shutdown 指令试图“清空 teammates 后重建”
- 若当前会话里的 team 无法安全复用，唯一合法恢复是退出当前会话并重建

## 已有 Team，优先判断是否可复用

在当前会话开始审查后、判断 PR 类型之前，先不要默认重复调用 TeamCreate。

判断顺序：

1. 当前会话是否已经持有 `pr-review-team`
2. team 配置是否可读
3. teammates 是否仍可通过 inbox / config 追踪

如果以上都正常：

- 直接复用已有 team
- 跳过 TeamCreate
- 继续进入 PR 类型判断与后续流程

只有在确认 team 缺席时，才调用 `TeamCreate(team_name="pr-review-team")`。

## TeamCreate 与 Agent 状态不一致

现象：

- `TeamCreate` 报 `Already leading team "pr-review-team"`
- `Agent` 报 `Team "pr-review-team" does not exist`

处理：

1. 停止当前审查轮
2. 不继续 spawn / SendMessage / shutdown
3. 退出当前 Claude Code 会话
4. 重新进入后从 Step 1 环境检查重新开始
5. 重新判断目标 PR 是否需要多人流程
6. 先判断已有 team 是否可复用
7. 如新会话中确认 team 缺席，只通过 `TeamCreate(team_name="pr-review-team")` 创建

注意：

- 不要在当前会话里尝试“先删 team 再建”
- `Already leading...` 优先解释为“当前会话已有 team”，不是清理信号

禁止：

- 手工创建 `~/.claude/teams/pr-review-team/`
- 手工写 `config.json`

## TeamDelete 后 UI 残留

本节只适用于 **Step 10 已经得到人类确认并成功执行过 TeamDelete** 之后。

现象：

- `~/.claude/teams/` 已删
- tmux panes 已杀死
- UI 仍显示 teammates running

原因：

- session JSONL 是 append-only
- TeamDelete 不会抹掉历史 `teamName`

处理：

1. 接受 UI 历史显示可能暂时残留
2. 退出当前会话
3. 重新进入新会话

禁止：

- 手工编辑 `~/.claude/projects/.../*.jsonl`
- 期待 TeamDelete 立刻清除 UI 历史显示
- 为了 UI 残留再次调用 TeamDelete

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

1. 仅在 Step 10 且得到人类确认时调用 TeamDelete
2. 通过重启会话消除 UI 残留
