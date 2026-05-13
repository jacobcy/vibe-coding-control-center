# vibe-review-pr 运行时参考

这份文档定义 vibe-review-pr 的运行约束和事件规范。执行流程（Phase 0-5）以 `SKILL.md` 为准。

## 真源文件

- agent 清单：`skills/vibe-review-pr/runtime/agents.sh`
- 公共函数：`skills/vibe-review-pr/scripts/lib.sh`
- 存在性检查：`skills/vibe-review-pr/scripts/agent-exist.sh`
- 事件列表：`skills/vibe-review-pr/scripts/agent-event.sh`
- 报告提取：`skills/vibe-review-pr/scripts/agent-report.sh`

## 定义约束

`runtime/agents.sh` 只保留 3 类信息：`group`、`agent_name`、`agent_type`。所有路径全部推断：

- agent inbox: `~/.claude/teams/<group>/inboxes/<agent_name>.json`
- lead inbox: `~/.claude/teams/<group>/inboxes/team-lead.json`
- agent definition: `.claude/agents/<agent_type>.md`
- 报告归宿: `team-lead.json` 中 `.from == <agent_name>` 的消息

## 事件规格

### 事件前缀

**Prompt 层**：所有 agent 使用中文方括号 `【事件类型】`。

**Shell 层**：脚本同时兼容英文方括号 `[事件类型]`（处理历史数据）。

### 事件类型

| 事件类型 | 语义 | 强制性 |
|---------|------|--------|
| `agent_ready` | 握手就绪 | 强制 |
| `agent_report` | 任务完成报告 | 强制 |

可选事件类型：`agent_progress`、`agent_blocked`、`agent_handoff`。

### 事件格式

```
【agent_ready】已就绪
```

报告建议以 `【agent_report】` 开头：

```
【agent_report】

## PR #843 架构审查报告
...
```

## 脚本用法

### `agent-exist.sh` — 存在性检查

检查 agent 的三层存在性：definition 文件、inbox 文件、tmux pane + alive 状态。

```bash
# 列出所有 agent 状态
skills/vibe-review-pr/scripts/agent-exist.sh

# 检查单个 agent
skills/vibe-review-pr/scripts/agent-exist.sh context-researcher
```

输出包含：agent、type、definition、inbox、pane、alive、suggestion。

### `agent-event.sh` — 事件概览

列出 agent 在 team-lead inbox 中的所有事件（只看标题和时间戳，不看详情）。

```bash
# 列出所有 agent 的最新事件
skills/vibe-review-pr/scripts/agent-event.sh

# 列出某个 agent 的所有事件
skills/vibe-review-pr/scripts/agent-event.sh context-researcher
```

查看完整内容直接读 inbox JSON 文件。

### `agent-report.sh` — 报告提取

提取 agent 的完整报告内容。

```bash
# 列出所有 agent 的报告状态
skills/vibe-review-pr/scripts/agent-report.sh

# 提取单个 agent 的报告
skills/vibe-review-pr/scripts/agent-report.sh context-researcher
```

输出：agent 名 + timestamp + 完整报告正文。

## 执行模型

### 核心原则

- **不再使用 backlog 做参数传递**。backlog 不可靠，不再通过 TaskCreate/TaskUpdate 传递报告或状态。
- **下游 agent 直接读报告**。Phase 2 的 agent 读 Phase 1 报告；Phase 3 (codex) 读 Phase 1 + Phase 2 报告。team-lead 不转发。
- **Phase 0 一次创建完整 backlog**。Phase 0 结束时创建全部 Phase 1-5 的 backlog task，不再逐 Phase 增量创建。
- **不再逐 Step 更新 backlog**。backlog task 只做完成/阻塞标记，不存储报告内容。
- **报告清理**。审查完成后清理 backlog（TaskCreate 创建的全部 task）。

### Agent 读取链

```
Phase 1: context-researcher → team-lead.json (【agent_report】)
Phase 2: code-analyst       → 读 team-lead.json context-researcher 的报告
         architect-reviewer → 读 team-lead.json context-researcher 的报告
         security-reviewer  → 读 team-lead.json context-researcher 的报告
Phase 3: codex              → 读 team-lead.json Phase 1 + Phase 2 的所有报告
Phase 5: fix-executor       → 读 team-lead.json 所有审查报告
```

**读取方式**：每个 subagent 被 spawn 时，prompt 中包含前序 agent 的报告内容（team-lead 通过 `agent-report.sh` 提取后写入 prompt）。subagent 不需要自己跑脚本。

> 更精确的读取方式以 SKILL.md 各 Phase Steps 为准。上表描述的是信息流向，不是 shell 调用方式。

### Team-lead 职责

1. Phase 0: 环境检查 → 创建/复用 Team → 创建完整 backlog
2. 每个 Phase: spawn agent → 等待 `【agent_report】` → 标记完成
3. idle 处理: 跑 `agent-event.sh <agent> agent_report --latest`（或直接用 `agent-report.sh` 检查），不是人工判断
4. Phase 4: 汇总报告 → 输出结论
5. 审查完成: 清理 backlog team
6. **不转发报告**。下游 agent 在自己的 prompt 里已经有前序报告内容。

### Subagent 职责

1. 启动后发送 `【agent_ready】已完成 ToolSearch`
2. 执行任务
3. 完成后发送 `【agent_report】` + 完整报告
4. 报告直接发到 team-lead（SendMessage），这就是报告的唯一真源
