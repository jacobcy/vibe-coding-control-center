# Execution Reference

承接 `SKILL.md`，提供消息样例与等待策略。SKILL.md 定义生命周期、phase 契约与质量标准；本文件只展示样例。

> **Phase 0-5结构**：Phase 0是前置条件（内联操作），Phase 1-5各是Backlog Task。Phase 0创建Phase 1 meta-task，各Phase结束时创建下一个Phase的meta-task。**不要操作teammates的idle/pane/inbox**（由运行时管理）。

## Phase 0 Step 6: TeamCreate + 创建Phase 1 meta-task

> **顺序铁律**：先 TeamCreate，后 TaskCreate。反序创建的 task 不关联 team，TaskList 永远返回空。
> **显式 PR 编号入口铁律**：`/vibe-review-pr 821` 这类入口下，team-lead 在 Step 6 不得执行 `gh pr view` / `gh pr diff` / `git diff`。PR 基本信息和 diff 首次接触者必须是 Phase 1 的 `context-researcher`。

```yaml
# 1. 创建 Team
- tool: TeamCreate
  params:
    team_name: "pr-review-team"
    description: "PR review for PR #{pr_number}"

# 2. team-lead 自身 ToolSearch（前置握手）
- tool: ToolSearch
  params:
    query: "select:SendMessage"
    max_results: 1

# 3. 创建 Phase 1 meta-task（不是直接创建Phase 1 Backlog task）
- tool: TaskCreate
  params:
    subject: "创建 Phase 1 backlog"
    description: |
      使用 references/backlog-task-templates.yaml Phase 1 模板创建完整的 Backlog task。
      创建后标记为 in_progress 并补充执行时 metadata。
    metadata:
      template_ref: "phase1"
      target_phase: 1
    owner: "team-lead"
    status: "pending"

# 4. spawn context-researcher 后，先发送 lead_ready；收到 agent_ready 后再发送正式任务
# 5. Phase 1 结束时创建 Phase 2 meta-task（或根据PR类型跳到Phase 3）
```

## Agent 握手样例（通用模式）

所有fresh spawn的agent必须先握手，适用于Phase 1的context-researcher和Phase 2的code-analyst/architect-reviewer/security-reviewer：

```yaml
# 1. spawn agent，prompt仅含握手指令
- tool: Agent
  params:
    team_name: pr-review-team
    name: <agent-name>
    subagent_type: <agent-type>
    model: <model>
    prompt: |
      【第一步只能握手】
      你现在不得开始工作，也不得抢先自报 ready。
      等待 team-lead 发送 `【lead_ready】`。
      收到 `【lead_ready】` 后，执行 ToolSearch(query="select:SendMessage", max_results=1)，
      然后立刻 SendMessage(to="team-lead", message="【agent_ready】已就绪")。
      在收到 team-lead 后续正式任务前，不得开始任何工作。
    run_in_background: true  # 仅Phase 2多agent时使用

# 2. team-lead发送lead_ready
- tool: SendMessage
  params:
    to: "<agent-name>"
    message: |
      【lead_ready】team-lead 已完成握手。
      请现在执行 ToolSearch(query="select:SendMessage", max_results=1)。
      完成后仅回复"【agent_ready】已就绪"；未完成握手前不得开始工作。

# 3. 收到agent_ready后，发送正式任务
- tool: SendMessage
  params:
    to: "<agent-name>"
    message: |
      【正式任务】
      [任务具体内容]
```

**握手约束**：
- 未收到 `agent_ready` 的agent不得分配工作
- 握手失败（超时3次）→ 标记blocked
- fresh spawn 的下一步必须是正式任务，不得发送待命指令

## 消息路由错误处理（Phase 4）

**已知bug**（#40166 / #39651）：teammate-message的PR编号可能与实际不匹配。

**诊断流程**：

```bash
# 1. 定位agent的sessionId
cat ~/.claude/teams/pr-review-team/config.json | jq '.members[] | select(.name=="<agent-name>")'

# 2. 从session文件找正确报告
cat ~/.claude/projects/.../<sessionId>.jsonl | grep -A 10 "PR #"
```

**处理**：
- 在最终报告如实标注："消息路由错误，正确报告来自session文件"
- 禁止用错误消息作审查依据

## AskUserQuestion 样例

**执行模式选择**：

```yaml
question: 请选择审核后的执行模式：1. auto-fix  2. comment-only  3. auto-decide  4. ask-each
```

**继续下一PR**：

```yaml
question: |
  PR #{pr_number} 审查完成。是否继续？
  - continue: 复用当前 Team / agents 审查下一个
  - end: TeamDelete，结束会话
```

## 会话结束流程（Phase 5后）

```python
# 1. 向所有活跃 teammates 广播 shutdown_request
for agent in ["code-analyst", "architect-reviewer", "security-reviewer", "context-researcher"]:
    SendMessage(to=agent, message={"type": "shutdown_request"})

# 2. 等待 idle 通知（通常 < 5s），然后执行 TeamDelete
TeamDelete()

# 3. 若 TeamDelete 返回 "no team found"（agents 已自行退出）
#    fallback 手动清理：
#    rm -rf ~/.claude/teams/pr-review-team ~/.claude/tasks/pr-review-team
```

---

## Backlog Task 约束补充说明

> 本章节补充 SKILL.md 的 Phase 依赖链说明，提供metadata字段详情。

### 强制约束字段

每个 Phase 的 Backlog task 必须包含以下 metadata 字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `phase_order` | integer | Phase 编号（1-5） |
| `depends_on_phase` | integer | 前一 Phase 编号 |
| `must_create_next_phase_backlog` | boolean | 强制约束标记（true） |

### 依赖链实现

- Phase 1: `depends_on_phase: 0`（第一个Backlog task）
- Phase 2-5: `addBlockedBy: ["phase-N-1-task-id"]`（串行执行）

### 未创建下一 Phase Backlog 的处理

如果 Phase N 结束时未创建 Phase N+1 的 meta-task：

1. 当前 Phase 标记为 blocked
2. 流程立即停止，不进入下一 Phase
3. 输出明确错误："Phase N 未创建 Phase N+1 meta-task，流程停止"
