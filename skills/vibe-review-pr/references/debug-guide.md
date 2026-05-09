# PR Review Team Debug Guide

> 背景：issue #787（agent pane 不实时 + model 参数错位）的调试方法汇总。

## Pane 可见性说明（非 bug）

v2.1.32+ 的实际行为（经实验验证）：

- **工具调用期间**：pane 实时显示工具调用与输出（Bash、Read 等）
- **深度思考/processing 期间**：pane 显示 "Accomplishing…" 状态行，不显示内部推理
- **idle 后**：pane 保留完整执行历史，可用 capture-pane 导出
- 结果通过 teammate-message 正常返回，不受影响

split pane 模式由 `teammateMode` 控制，默认 `"auto"`（tmux 内自动启用）。无需修改 settings.json。

## 查看 Agent 执行过程

### 方法 1：捕获 pane 历史（agent idle 后最有效）

```bash
# 列出所有 pane
tmux list-panes -a

# 捕获指定 pane（最近 1000 行）
tmux capture-pane -t <pane-id> -p -S -1000
# 例：tmux capture-pane -t calm-oak-nx0e:0.1 -p -S -1000
```

### 方法 2：查看 session JSONL（最完整）

```bash
# 找最近 30 分钟内的 session 文件
find ~/.claude/projects/ -name "*.jsonl" -mmin -30 | sort -t/ -k8 | tail -5

# 查看某个 agent 的 session（需 jq）
cat <session-file>.jsonl | jq -r 'select(.type=="text") | .content' | head -100
```

### 方法 3：查看 agent 收件箱（确认 prompt 是否正确送达）

```bash
# 查看 team 配置与 members
cat ~/.claude/teams/pr-review-team/config.json | python3 -m json.tool

# 查看特定 agent inbox
cat ~/.claude/teams/pr-review-team/inboxes/architect-reviewer.json 2>/dev/null
```

### 方法 4：查看 tool-results 文件

```bash
# 路径结构：~/.claude/projects/<project>/<session-id>/tool-results/
# 按时间列出最新工具输出
ls -lht ~/.claude/projects/*/*/tool-results/*.txt 2>/dev/null | head -20
```

## SendMessage 是 Deferred Tool

teammate 在发送消息前必须先加载工具 schema，否则调用会报 InputValidationError：

```python
# 正确做法：先 ToolSearch 再 SendMessage
ToolSearch(query="select:SendMessage")
SendMessage(to="team-lead", message="...", summary="...")
```

如果 teammate 迟迟没有发送报告，可能是卡在 ToolSearch 步骤。检查方法：
```bash
tmux capture-pane -t <pane-id> -p | grep -E "ToolSearch|SendMessage|deferred"
```

## Model 参数核查

agent 定义文件中的 `model` 字段（`opus`/`sonnet`）会被 teammate 模式遵守，但 skill 层 `Agent(model="sonnet")` 硬编码会覆盖配置。

```bash
# 确认 agent 定义文件的 model 设置
grep -n "^model:" .claude/agents/pr-*.md

# 确认 spawn 时实际使用的 model（从 session JSONL）
cat <session-file>.jsonl | jq -r 'select(.model != null) | .model' | head -5
```

## PR 编号路由核查（issue #787 问题 3）

agent 内部执行的 PR 编号可能与 prompt 指定的不一致（已知 bug）：

```bash
# 检查 agent 实际查询的 PR 编号
tmux capture-pane -t <pane-id> -p -S -1000 | grep -E "PR #[0-9]+"

# 对比 inbox 中的 prompt（应与实际执行一致）
cat ~/.claude/teams/pr-review-team/inboxes/architect-reviewer.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
msgs = data if isinstance(data, list) else data.get('messages', [])
for m in msgs[-3:]:
    print(m.get('text', m.get('content', ''))[:200])
    print('---')
"
```

## 常用一键诊断

```bash
# 当前 team 状态
cat ~/.claude/teams/pr-review-team/config.json 2>/dev/null | python3 -c "
import json, sys
d = json.load(sys.stdin)
for m in d.get('members', []):
    print(f\"{m['name']}: {m.get('agentType','?')} | active={m.get('isActive','?')} | pane={m.get('tmuxPane','?')}\")
" 2>/dev/null || echo "no active team"

# 最近 agent session 文件
find ~/.claude/projects/ -name "*.jsonl" -mmin -60 2>/dev/null | wc -l
```
