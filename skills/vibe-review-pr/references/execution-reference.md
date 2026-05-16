# execution-reference

只展示消息样例和常用诊断命令。完整流程以 SKILL.md 为准。

## 消息样例

### idle notification

```
{"type":"idle_notification","from":"context-researcher","timestamp":"...","idleReason":"available"}
```

idle notification 是正常通知，说明 agent 正在工作。收到后运行 `agent-event.sh <agent>` 检查事件。

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

### fix-executor escalating handshake messages

fix-executor 握手使用 3 轮 escalating guidance 消息（每轮 30 秒超时）：

#### Round 1 — 初步提示

```
SendMessage(to="fix-executor", summary="握手信号未收到", message="""
We did not receive your handshake message.

You may be stuck because SendMessage is a deferred tool.
Please confirm you have executed ToolSearch to load the SendMessage schema.

Execute: ToolSearch(query='select:SendMessage', max_results=1)
""")
```

#### Round 2 — 强制指令

```
SendMessage(to="fix-executor", summary="握手信号仍未收到", message="""
Still no response.

You MUST execute the following steps:
1) ToolSearch(query='select:SendMessage', max_results=1)
2) Wait for the schema to load (look for <functions> block)
3) Then SendMessage(to='team-lead', message='【agent_ready】已就绪')
""")
```

#### Round 3 — 详细步骤 + 警告

```
SendMessage(to="fix-executor", summary="FINAL attempt", message="""
FINAL attempt to establish handshake.

Exact steps to execute NOW:
1) ToolSearch(query='select:SendMessage', max_results=1)
2) Wait for <functions> block containing SendMessage schema
3) SendMessage(to='team-lead', message='【agent_ready】已就绪')

No response after this message → you will be marked as blocked.
""")
```

> **Escalating Guidance 策略**: 从提示 → 强制 → 详细步骤，确保 agent 理解 deferred tools 必须先加载 schema 才能调用。3 轮超时后触发 `@mark_fix_executor_blocked`。

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
