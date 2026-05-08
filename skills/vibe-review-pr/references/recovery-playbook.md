# Recovery Playbook

恢复边界只有一条原则：**不要手工伪造或篡改 team 内部状态**。

补充硬规则：

- TeamDelete 不是恢复工具
- 不发送 shutdown 指令试图"清空 teammates 后重建"
- 当前会话 team 无法安全复用时，唯一合法恢复是退出会话重建

## 已有 Team 优先复用

判断顺序：当前会话已持有 `pr-review-team` → team 配置可读 → teammates 可通过 inbox / config 追踪。三项都正常 → 直接复用，跳过 TeamCreate。仅在确认 team 缺席时才调用 `TeamCreate(team_name="pr-review-team")`。

## TeamCreate 与 Agent 状态不一致

现象：`TeamCreate` 报 `Already leading team "pr-review-team"`；或 `Agent` 报 `Team "pr-review-team" does not exist`。

处理：停止当前轮 → 退出 Claude Code 会话 → 重进 → 从 Step 1 开始，先判断已有 team 是否可复用，确认缺席才 TeamCreate。

`Already leading...` 优先解释为"当前会话已有 team"，不是清理信号。**不要**在当前会话尝试"先删后建"，**不要**手工建 `~/.claude/teams/pr-review-team/` 或写 `config.json`。

## TeamDelete 后 UI 残留

仅适用于 Step 10 已成功执行过 TeamDelete 之后。session JSONL 是 append-only，TeamDelete 不抹掉历史 `teamName`。处理：接受 UI 残留 → 退出会话 → 重进。

**不要**手工编辑 `*.jsonl`、不要为残留再次 TeamDelete。

## Phase 2 agent 缺失或超时

记录缺失 agent 名称 → 最终报告标"审查不完整" → 不替缺失 agent 推断立场 → 需要时人工决定是否重跑。

## 消息路由错误（Claude Code 已知 bug #40166 / #39651）

现象：teammate-message 的 PR 编号或内容与实际不匹配，但 agent session 文件中存在正确报告。

处理：

1. 验证消息中的 PR 编号；不匹配立即停止
2. 定位 session 文件：

   ```bash
   cat ~/.claude/teams/pr-review-team/config.json | jq '.members[] | select(.name=="<agent_name>")'
   cat ~/.claude/projects/.../<sessionId>.jsonl | grep -A 10 "PR #"
   ```

3. 在最终报告如实标注："消息路由错误，正确报告来自 session 文件 `<path>` 而非 teammate-message，引用 #40166 / #39651"

正确示例：

```
⚠️ 消息路由错误：架构审查员 teammate-message 显示 PR #690，但实际审查的是 PR #702。
已从 session 文件 3515319b-...jsonl 定位正确报告。以下内容来自 session 文件。
```

禁止：用错误消息作审查依据 / 假装 teammate-message 正常 / 不说明来源直接使用 session 内容。

## 背景报告未送达

优先级：检查 team inbox / teammate-message → SendMessage 请求 context-researcher 补发 → 仍无法获取则停止进入 Phase 2。**不要**让 Phase 2 在缺 `phase_1_output` 时继续。

## 唯一合法的终止方式

让 Team 状态消失只有两条路径：

1. **正常结束**：Step 10 用户确认 end → 一次 `TeamDelete`
2. **异常恢复**：退出 Claude Code 会话 → 重进新会话

任何在 Claude Code 之外手工触碰 `~/.claude/teams/` / `*.jsonl` / `tmux kill-pane` 的操作都属于错误恢复。
