# vibe-review-pr runtime usage

这份文档只定义 `vibe-review-pr` 在运行时新增的两个事件与两个 shell 脚本。

目标很简单：

- `【agent_ready】` 继续保留，作为握手与通信检查事件
- `【agent_report】` 可以作为报告标记，但不是强制前提
- agent 名称和 agent type 的关系只认 `runtime/agents.sh`
- 报告提取只认 `team-lead.json`
- shell 只做核验，不做流程控制

## 真源文件

- agent 清单：`skills/vibe-review-pr/runtime/agents.sh`
- 公共函数：`skills/vibe-review-pr/scripts/lib.sh`
- ready 检查：`skills/vibe-review-pr/scripts/agent-ready.sh`
- 报告提取：`skills/vibe-review-pr/scripts/agent-report.sh`

## 定义约束

`runtime/agents.sh` 只保留 3 类信息：

1. `group`
2. `agent_name`
3. `agent_type`

其他路径全部推断：

- agent inbox: `~/.claude/teams/<group>/inboxes/<agent_name>.json`
- lead inbox: `~/.claude/teams/<group>/inboxes/team-lead.json`
- agent definition: `.claude/agents/<agent_type>.md`
- `SendMessage(to=...)`: 必须使用 `agent_name`
- `team-lead.json` 中的 `.from`: 必须等于 `agent_name`

## 事件格式

### 1. Ready 事件

保留原来的 ready 语义，不要求额外字段。

```text
【agent_ready】已就绪
```

规则：

- 发送者不需要重复写 `agent_name`
- `agent_name` 直接从 `team-lead.json` 的 `.from` 推断
- `agent_type` 通过 `runtime/agents.sh` 反查

### 2. Report 事件

推荐正式报告使用 `【agent_report】` 开头，这样最容易提取。

```text
【agent_report】

## PR #843 架构审查报告
...
```

规则：

- 事件头和正文之间建议空一行
- 如果历史消息没有 `【agent_report】`，脚本会回退提取“像报告的消息”
- “像报告”目前指：`## PR #` / `# PR #` / 包含”审查报告” / 包含”背景报告”

## 新增事件类型与验证脚本

### 事件前缀格式要求

**Prompt 层要求**：所有 agent 必须使用中文方括号 `【事件类型】`

**Shell 层兼容**：脚本同时兼容英文方括号 `[事件类型]`（处理历史数据）

### 强制事件类型

| 事件类型 | 语义 | 强制性 |
|---------|------|--------|
| `agent_ready` | 握手就绪 | **强制** |
| `agent_report` | 任务完成报告 | **强制** |

### 可选事件类型

- `agent_progress` — 进度更新
- `agent_blocked` — 任务阻塞
- `agent_handoff` — 任务交接

### agent-event.sh 通用事件提取脚本

替代特定场景的快捷入口（`agent-ready.sh`、`agent-report.sh`），支持参数化事件类型。

**用法**：

```bash
# 检查握手事件是否存在
skills/vibe-review-pr/scripts/agent-event.sh context-researcher agent_ready --latest

# 输出示例：
# event_type=agent_ready
# agent=context-researcher
# timestamp=2026-05-13T10:00:00.000Z
# content_start
# 【agent_ready】已就绪

# 提取最新报告
skills/vibe-review-pr/scripts/agent-event.sh architect-reviewer agent_report --latest

# 列出所有进度更新
skills/vibe-review-pr/scripts/agent-event.sh code-analyst agent_progress

# 检查事件不存在
skills/vibe-review-pr/scripts/agent-event.sh architect-reviewer agent_report --latest
# 输出：event_type=agent_report event_status=missing（退出码 3）
```

**输出格式**：
- 默认：列出所有匹配事件，用 `---` 分隔
- `--latest`：只输出最新事件
- 格式字段：`event_type`、`agent`、`timestamp`、`content_start`、[实际内容]

**Team-lead 验证流程**：

收到 agent idle 通知后：

```bash
# 1. 检查握手事件
skills/vibe-review-pr/scripts/agent-event.sh <agent> agent_ready --latest

# 2. 检查报告事件
skills/vibe-review-pr/scripts/agent-event.sh <agent> agent_report --latest

# 3. 如 event_status=missing → 检查 pane 诊断
tmux capture-pane -t <pane-id> -p -S -1000 | grep -E “ToolSearch|SendMessage|InputValidationError”
```

## 脚本用法

### 新增：通用事件提取脚本 agent-event.sh

以下两个脚本保留为特定场景快捷入口，推荐使用通用脚本 `agent-event.sh`：

- `agent-ready.sh` — 握手检查（等同于 `agent-event.sh <agent> agent_ready --latest`）
- `agent-report.sh` — 报告提取（等同于 `agent-event.sh <agent> agent_report --latest`）

### `agent-ready.sh`

不带参数时，列出所有定义的 agent，以及 inbox 是否存在。

```bash
skills/vibe-review-pr/scripts/agent-ready.sh
```

输出示例：

```text
group=pr-review-team
team_inbox_dir=/Users/you/.claude/teams/pr-review-team/inboxes
agent                  type                         definition inbox      status
context-researcher     pr-context-researcher       ok         ok         spawned
code-analyst           pr-code-analyst             ok         ok         spawned
architect-reviewer     pr-architect-reviewer       ok         ok         spawned
security-reviewer      pr-security-reviewer        ok         missing    not-spawned
```

检查单个 agent：

```bash
skills/vibe-review-pr/scripts/agent-ready.sh architect-reviewer
```

检查某个 agent 是否发过 ready：

```bash
skills/vibe-review-pr/scripts/agent-ready.sh architect-reviewer
```

可能输出：

```text
agent                  type                         definition inbox      status
architect-reviewer     pr-architect-reviewer       ok         ok         spawned
ready_event=found
from=architect-reviewer
timestamp=2026-05-12T13:31:07.117Z
text=【agent_ready】已就绪
```

如果没找到：

```text
ready_event=missing
```

### `agent-report.sh`

从 `team-lead.json` 提取某个 agent 的最新报告样消息。

```bash
skills/vibe-review-pr/scripts/agent-report.sh architect-reviewer
```

默认输出 metadata + 正文：

```text
agent=architect-reviewer
timestamp=2026-05-12T13:37:06.001Z
body_start

## PR #843 架构审查报告
...
```

只输出正文：

```bash
skills/vibe-review-pr/scripts/agent-report.sh architect-reviewer --body-only
```

## 推荐运行方式

### Team-lead

1. 先跑 `agent-ready.sh`
2. 确认 agent 名称、type、inbox 文件都一致
3. 发送 `【lead_ready】`
4. 用 `agent-ready.sh <agent>` 检查 ready 是否出现
5. 下发正式任务时，最好要求 agent 用 `【agent_report】` 开头发报告
6. 用 `agent-report.sh` 提取报告，不再靠猜哪条是有效报告

### Subagent

握手仍然按原协议执行，但正式报告请统一用下面格式发回 `team-lead`：

```text
【agent_report】

<你的完整报告正文>
```

## 设计边界

这些脚本解决的是：

- agent 名字是否定义清楚
- inbox 文件是否存在
- `【agent_ready】` 是否真的出现在 lead inbox
- 报告消息是否真的存在，以及如何稳定提取

这些脚本**不负责**：

- 直接推进 backlog 状态
- 自动判断 phase 是否完成
- 改写现有握手协议

也就是说：

- backlog 仍可保留
- handshake 仍可保留
- 但报告提取和 ready 检查从现在开始有 shell 真源，不再靠 lead 或 agent 口头判断
