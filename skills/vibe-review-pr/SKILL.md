---
name: vibe-review-pr
description: |
  Use only in Claude Code environments with Agent Teams enabled when the user wants
  a comprehensive PR review using the multi-agent team workflow.
---

# Vibe PR Review

`vibe-review-pr` 是 Claude Code Agent Teams 专用 PR 审查入口。Phase 0 完成环境和 Team 准备，Phase 1-5 各是一个 Backlog Task。下游 agent 通过 prompt 注入获取前序报告。

## When to Use

仅在以下条件**全部**满足时使用：

- host 为 Claude Code
- `TMUX` 已设置
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- 工具面提供 TeamCreate / Agent / SendMessage

任一缺失 -> 立即停止，按文件范围回退到单 agent 审查。

## File Map

| 文件 | 职责 |
|------|------|
| `SKILL.md` | 生命周期、phase 契约、握手协议、硬边界 |
| `references/execution-reference.md` | 消息样例与等待策略 |
| `references/recovery-playbook.md` | 故障恢复路径 |
| `references/debug-guide.md` | pane 可见性、agent 执行过程查看、model 参数核查、PR 编号路由诊断 |
| `runtime/agents.sh` | Agent 注册表（名称 + 类型映射） |
| `.claude/agents/pr-*.md` | Teammate 项目特定职责定义 |

## Agent 定义

| agent | agent_type | Phase | 需要读取 |
|-------|-----------|-------|---------|
| context-researcher | pr-context-researcher | 1 | (无) — 独立调研 |
| code-analyst | pr-code-analyst | 2 | `scripts/agent-report.sh context-researcher` |
| architect-reviewer | pr-architect-reviewer | 2 | `scripts/agent-report.sh context-researcher` |
| security-reviewer | pr-security-reviewer | 2 | `scripts/agent-report.sh context-researcher` |
| fix-executor | pr-fix-executor | 5 | Phase 4 结论中提取的修复指令（lead 直接写入 prompt） |

> **codex 是外部 plugin**，通过 `codex:rescue` skill 调用，不是 teammate。不在 agents.sh 中。能跑脚本读 inbox，但不能收 SendMessage。输出由 skill 调用直接返回给 lead。

真源文件：`skills/vibe-review-pr/runtime/agents.sh`

## Shell 脚本

| 脚本 | 用途 |
|------|------|
| `scripts/agent-exist.sh` | 检查 agent 存在性（definition/inbox/pane/alive） |
| `scripts/agent-event.sh` | 列出 agent 事件（标题+时间） |
| `scripts/agent-report.sh` | 提取 agent 报告全文 |

## 握手协议（简化版）

> **核心原则**：所有 agent 必须先完成握手，才能接收正式任务。握手是**有方向、有时序**的，不是双方同时各说一次"已就绪"。

### 握手流程

1. **Phase 0**: team-lead 先执行 `ToolSearch(query="select:SendMessage")` 加载 SendMessage
2. **spawn agent**: prompt 只包含握手准备，不包含具体任务
3. **team-lead 发送握手**: `SendMessage(to=<agent>, summary="握手信号", message="【lead_ready】")`
4. **agent 回复**: 等待 `【lead_ready】` → 执行 ToolSearch → 发送 `【agent_ready】已就绪`
5. **team-lead 下发任务**: 收到 `【agent_ready】` 后，立即发送正式任务（含 PR 编号、具体指令）

### 握手约束

**team-lead 必须**：
- spawn 后立即发送 `【lead_ready】`
- 收到 `【agent_ready】` 后，**立即**发送正式任务（fresh spawn 不得先进入 idle）
- 超时未收到 → 重试（最多 3 次，每次 30s）→ 标记 blocked

**team-lead 禁止**：
- spawn 后不发 `【lead_ready】`，假设 agent 会自动执行
- 未收到 `【agent_ready】` 就给该 agent 分配工作
- 对 fresh spawn 且刚回复"【agent_ready】已就绪"的 agent 发送"保持空闲 / 等待新 PR"

### 握手失败处理

- 超时 3 次 → 标记 agent 为 blocked
- 使用 `scripts/agent-exist.sh <agent>` 诊断状态
- 使用 `scripts/agent-event.sh <agent>` 查看事件
- 详细恢复路径见 `references/recovery-playbook.md`
- 常见诊断问题见 `references/debug-guide.md`

## 阻塞处理

### Team-lead 遇到错误

**调试阶段硬规则（强制）**：

Team-lead 执行过程中遇到**任何错误或异常**，必须立即 `stop()`：

- 工具调用返回错误（不管原因）
- 收到下游 agent 的【agent_blocked】标记
- 脚本执行返回非零退出码
- 任何未预期的行为

**核心原则**：调试阶段宁可过度谨慎，不可遗漏异常。

**stop() 定义**：
1. **立即停止所有操作**：不再执行任何后续工具调用
2. **停止创建**：不再创建 backlog task、不再 spawn agent、不再激活 phase
3. **说明阻塞原因**：输出明确的错误信息和当前状态
4. **等待反馈**：等待用户明确指示才能继续

**禁止**：
- ❌ 修复错误后立即继续执行
- ❌ 自行判断"理解了应该继续"
- ❌ 只发送警告而不停止
- ❌ 假设用户只是想暂停思考一下

**恢复条件**：
- ✅ 用户明确指示："继续" / "resume" / "go ahead"
- ❌ 不得自行恢复

**示例**：
```
错误: TaskCreate 参数缺失 subject
↓
stop() → 输出错误原因 → 等待用户指示
↓
用户: "继续修复"
↓
修复参数 → 重新执行
```

### 下游 Agent 遇到错误

Agent 执行过程中遇到**任何错误**，必须立即发送 `【agent_blocked】` 并停止当前任务：

- 工具调用返回错误（不管原因）
- 脚本执行返回非零退出码
- 任何未预期的行为

```
【agent_blocked】脚本 agent-report.sh 执行失败：agent xxx not defined
```

**Lead 收到 `【agent_blocked】` 后**：
1. 立即 `stop()` 停止当前 Phase 流程
2. `agent-event.sh <agent>` 查看事件上下文
3. `agent-exist.sh <agent>` 诊断状态
4. 输出阻塞原因，等待用户指示

**禁止**: lead 不得跳过 `agent_blocked` 继续推进 Phase。

---

# Phase 0: 准备

> Phase 0 是 team-lead 内联操作，不需要 Backlog Task。

## Steps

### Step 1: 环境检查

检查 tmux / Agent Teams / TeamCreate / ToolSearch / SendMessage 可用性。任一缺失 -> 立即停止。

### Step 2: Team 创建或复用

1. `TeamCreate(team_name="pr-review-team")` — 若 already exists 则跳过创建
2. 对已有 members（除 team-lead）逐个握手存活检测：
   - `SendMessage(to=member, summary="握手检测", message="【lead_ready】")`
   - 收到 `【agent_ready】` -> 存活，可复用
   - 超时 3 次（各 30s）-> 标记 dead
3. 全死 -> TeamDelete -> TeamCreate 重建
4. 部分存活 -> 复用存活者，缺失的在对应 Phase 用 `Agent(name="agent_name")` spawn

> TeamCreate 后才能 TaskCreate，否则 task 不关联 team

### Step 3: team-lead 自身 ToolSearch

`ToolSearch(query="select:SendMessage")` -> 失败则停止。

### Step 4: 创建完整 Backlog

**一次性创建** = 在一个消息中提交 5 个独立的 TaskCreate 调用，每个调用都必须包含完整参数。

**创建前强制验证**（执行流程，不是可选）：

在提交任何 TaskCreate 调用之前，必须先输出验证清单：

```
准备创建 5 个 TaskCreate 调用：
✓ Phase 1: subject="Phase 1: 背景调研", description="spawn context-researcher -> 等待报告 -> 标记完成", metadata={phase_order: 1, depends_on_phase: 0}
✓ Phase 2: subject="Phase 2: 专家评审", description="spawn code-analyst / architect-reviewer / security-reviewer -> 等待报告 -> 标记完成", metadata={phase_order: 2, depends_on_phase: 1}
✓ Phase 3: subject="Phase 3: Codex 复查", description="调用 codex:rescue skill -> 等待复查结果 -> 标记完成", metadata={phase_order: 3, depends_on_phase: 2}
✓ Phase 4: subject="Phase 4: 综合判断", description="汇总 Phase 1-3 报告 -> 输出审查结论", metadata={phase_order: 4, depends_on_phase: 3}
✓ Phase 5: subject="Phase 5: 写回 + 修复", description="spawn fix-executor -> 等待报告 -> 标记完成", metadata={phase_order: 5, depends_on_phase: 4}

确认：所有 5 个调用均包含 subject + description + metadata → 提交调用
```

**禁止**：
- ❌ 空调用（无 subject/description 的 TaskCreate）
- ❌ 批量参数（假设一次调用创建多个 task）
- ❌ 未输出验证清单就提交调用

**正确示例（XML 格式）**：

```xml
<TaskCreate
  description="spawn context-researcher -> 等待报告 -> 标记完成"
  metadata='{"depends_on_phase": 0, "phase_order": 1}'
  subject="Phase 1: 背景调研"/>
<TaskCreate
  description="spawn code-analyst / architect-reviewer / security-reviewer -> 等待报告 -> 标记完成"
  metadata='{"depends_on_phase": 1, "phase_order": 2}'
  subject="Phase 2: 专家评审"/>
<TaskCreate
  description="调用 codex:rescue skill -> 等待复查结果 -> 标记完成"
  metadata='{"depends_on_phase": 2, "phase_order": 3}'
  subject="Phase 3: Codex 复查"/>
<TaskCreate
  description="汇总 Phase 1-3 报告 -> 输出审查结论"
  metadata='{"depends_on_phase": 3, "phase_order": 4}'
  subject="Phase 4: 综合判断"/>
<TaskCreate
  description="spawn fix-executor -> 等待报告 -> 标记完成"
  metadata='{"depends_on_phase": 4, "phase_order": 5}'
  subject="Phase 5: 写回 + 修复"/>
```

**错误处理**：
- 若 TaskCreate 返回 `InputValidationError` → 立即 `stop()`
- 仔细阅读错误信息（如"缺少 subject"、"缺少 description"）
- 检查每个 TaskCreate 是否包含所有必需参数：subject、description、metadata
- 修复后重新提交 5 个完整调用

**YAML 格式参考**（用于理解参数结构）：

Phase 1:

```yaml
- tool: TaskCreate
  params:
    subject: "Phase 1: 背景调研"
    description: "spawn context-researcher -> 等待报告 -> 标记完成"
    metadata:
      phase_order: 1
      depends_on_phase: 0
```

Phase 2:

```yaml
- tool: TaskCreate
  params:
    subject: "Phase 2: 专家评审"
    description: "spawn code-analyst / architect-reviewer / security-reviewer -> 等待报告 -> 标记完成"
    metadata:
      phase_order: 2
      depends_on_phase: 1
```

Phase 3:

```yaml
- tool: TaskCreate
  params:
    subject: "Phase 3: Codex 复查"
    description: "调用 codex:rescue skill -> 等待复查结果 -> 标记完成"
    metadata:
      phase_order: 3
      depends_on_phase: 2
```

Phase 4:

```yaml
- tool: TaskCreate
  params:
    subject: "Phase 4: 综合判断"
    description: "汇总 Phase 1-3 报告 -> 输出审查结论"
    metadata:
      phase_order: 4
      depends_on_phase: 3
```

Phase 5:

```yaml
- tool: TaskCreate
  params:
    subject: "Phase 5: 写回 + 修复"
    description: "spawn fix-executor -> 等待报告 -> 标记完成"
    metadata:
      phase_order: 5
      depends_on_phase: 4
```

### Step 5: 激活 Phase 1

`TaskUpdate(taskId=<phase-1>, status="in_progress")`

## Contracts

| 项目 | 内容 |
|------|------|
| 输入 | 无（独立执行） |
| 输出 | Team 就绪 + 全部 Phase 1-5 backlog 已创建 + Phase 1 已激活 |
| 失败处理 | 立即停止，不创建任何 backlog |

## Hard Rules

- TeamCreate 必须先于 TaskCreate
- 复用判断 = 握手结果
- 全部 Phase 1-5 task 在 Phase 0 一次性创建
- 不使用 meta-task 模式

---

# Phase 1: 背景调研

> 产出：context-researcher 结构化 PR 背景报告

## Steps

### Step 1: spawn context-researcher

spawn 时 prompt **只包含握手准备，不包含具体任务**：

```text
【第一步只能握手】
你现在不得开始调研，也不得抢先自报 ready。
等待 team-lead 发送 `【lead_ready】`。
收到 `【lead_ready】` 后，执行 ToolSearch(query="select:SendMessage", max_results=1)，
然后立刻 SendMessage(to="team-lead", message="【agent_ready】已就绪")。
在收到 team-lead 后续正式任务前，不得开始任何调研。
```

spawn:

```yaml
- tool: Agent
  params:
    description: "PR 背景调研"
    name: "context-researcher"
    subagent_type: "pr-context-researcher"
    team_name: "pr-review-team"
    model: "sonnet"  # 使用 sonnet 避免 haiku extended thinking 限制
    prompt: "<上述握手 prompt>"
```

### Step 2: 主动握手等待（禁止 idle）

**禁止被动等待**：发送握手信号后不得 idle，必须使用主动轮询策略。

**主动等待流程**：

发送握手信号：`SendMessage(to="context-researcher", summary="握手信号", message="【lead_ready】")`

立即启动轮询检查（最多 30 秒，每 5 秒检查）：

```bash
for i in {1..6}; do
  sleep 5
  if skills/vibe-review-pr/scripts/agent-exist.sh context-researcher | grep -q "ready_event=found"; then
    break
  fi
done
```

**超时处理**：
- 30 秒后仍未收到 -> 重试发送握手（最多 3 次）
- 3 次超时 -> 停止并标记 blocked，等待用户指示

### Step 3: 验证握手成功 → 分配任务

1. 执行脚本验证握手成功：

```bash
skills/vibe-review-pr/scripts/agent-exist.sh context-researcher
```

**期望输出**：
```
ready_event=found
from=context-researcher
timestamp=...
text=【agent_ready】已就绪
```

**验证失败处理**：
- `ready_event=waiting` → 握手未开始，重试 Step 2（最多 3 次）
- `ready_event=missing` → 握手未完成，重试 Step 2（最多 3 次）
- `alive=inactive` → agent 已失联，重新 spawn + 握手（最多 3 次）
- 重试失败 → `stop()` 等待用户指示

2. 验证通过后，立即发送正式调研任务：

```yaml
- tool: SendMessage
  params:
    to: "context-researcher"
    summary: "PR #843 背景调研任务"
    message: |
      分析 PR #843 并产出一份结构化背景报告。

      职责：
      1. 阅读 CLAUDE.md、AGENTS.md、glossary.md、PR description、PR diff
      2. 不要修改任何文件
      3. 完成后用 SendMessage(to="team-lead", message="【agent_report】\n\n## PR #843 背景报告\n...")

      报告将保存在 team-lead.json inbox 中，后续 agent 通过 scripts/agent-report.sh context-researcher 读取。

      **脚本错误处理**：如脚本执行失败，立即发送【agent_blocked】+ 错误详情，停止执行。
```

**未验证握手成功前，不得给该 agent 分配任何工作。**

### Step 4: 主动等待报告（禁止 idle）

**禁止被动等待**：收到 idle 通知后，不得直接"等待"，必须使用主动轮询策略。

**主动等待流程**：

收到 context-researcher 的 idle 通知后，立即执行以下轮询循环：

```bash
# 第一次检查
skills/vibe-review-pr/scripts/agent-event.sh context-researcher

# 若无 agent_report，使用轮询等待（每 5 秒检查一次）
for i in {1..6}; do
  sleep 5
  skills/vibe-review-pr/scripts/agent-event.sh context-researcher
  # 检查是否有 agent_report
  if skills/vibe-review-pr/scripts/agent-exist.sh context-researcher | grep -q "agent_report"; then
    break
  fi
done
```

**等待超时处理**（30 秒后）：
- 若仍未收到报告 -> `skills/vibe-review-pr/scripts/agent-exist.sh context-researcher` 检查 alive 状态
- 若 alive=inactive -> SendMessage 要求重发或重新握手
- 若 alive=active -> 继续轮询（最多再等待 30 秒）

**处理结果**：
- 有 `agent_report` -> `scripts/agent-report.sh context-researcher` 提取报告 -> 标记 Phase 1 完成
- 无 `agent_report` 且超时 -> 重新握手或 spawn（见 recovery-playbook.md）

```yaml
- tool: TaskUpdate
  params:
    taskId: "<phase-1-task-id>"
    status: "completed"
```

### Step 5: 激活 Phase 2

`TaskUpdate(taskId=<phase-2>, status="in_progress")`

## Contracts

| 项目 | 内容 |
|------|------|
| 输入 | PR 编号 |
| 输出 | context-researcher 报告（team-lead.json 中可查） |
| 门禁 | `agent-report.sh context-researcher` 返回成功 |

## Hard Rules

- team-lead 不得自行收集上下文（gh pr view、git diff 等）
- 不得在未收到报告前激活 Phase 2

---

# Phase 2: 专家评审

> Phase 2 的三个 agent 可并行 spawn，各自独立审查

## Steps

### Step 1: 并行 spawn 三个 agent

spawn 时 prompt **只包含握手准备，不包含具体任务**：

```text
【第一步只能握手】
你现在不得开始审查，也不得抢先自报 ready。
等待 team-lead 发送 `【lead_ready】`。
收到 `【lead_ready】` 后，执行 ToolSearch(query="select:SendMessage", max_results=1)，
然后立刻 SendMessage(to="team-lead", message="【agent_ready】已就绪")。
在收到 team-lead 后续正式任务前，不得开始任何审查。
```

spawn:

```yaml
- tool: Agent
  params:
    description: "代码质量分析"
    name: "code-analyst"
    subagent_type: "pr-code-analyst"
    team_name: "pr-review-team"
    model: "sonnet"  # 代码分析需要强模型
    prompt: "<上述握手 prompt>"
- tool: Agent
  params:
    description: "架构审查"
    name: "architect-reviewer"
    subagent_type: "pr-architect-reviewer"
    team_name: "pr-review-team"
    model: "sonnet"
    prompt: "<上述握手 prompt>"
- tool: Agent
  params:
    description: "安全审查"
    name: "security-reviewer"
    subagent_type: "pr-security-reviewer"
    team_name: "pr-review-team"
    model: "sonnet"
    prompt: "<上述握手 prompt>"
```

### Step 2: 并行主动握手等待（禁止 idle）

**禁止被动等待**：发送握手信号后不得 idle，必须对每个 agent 使用主动轮询策略。

**并行握手流程**：

对每个 agent 执行握手（可并行发送握手信号）：

```bash
# 并行发送握手信号
SendMessage(to=code-analyst, summary="握手信号", message="【lead_ready】")
SendMessage(to=architect-reviewer, summary="握手信号", message="【lead_ready】")
SendMessage(to=security-reviewer, summary="握手信号", message="【lead_ready】")
```

发送后立即对每个 agent 启动轮询（每个 agent 独立轮询，最多 30 秒）：

```bash
# 对每个 agent 轮询检查
for agent in code-analyst architect-reviewer security-reviewer; do
  for i in {1..6}; do
    sleep 5
    if skills/vibe-review-pr/scripts/agent-exist.sh "$agent" | grep -q "ready_event=found"; then
      echo "$agent 握手成功"
      break
    fi
  done
done
```

**超时处理**：
- 30 秒后仍未收到某个 agent 的握手 -> 重试发送握手（最多 3 次）
- 3 次超时 -> 标记该 agent 为 blocked，继续处理其他 agent

### Step 3: 验证握手成功 → 分配任务

对每个 agent 执行验证（可并行）：

1. 执行脚本验证握手成功：

```bash
skills/vibe-review-pr/scripts/agent-exist.sh <agent>
```

**期望输出**：
```
ready_event=found
from=<agent>
timestamp=...
text=【agent_ready】已就绪
```

**验证失败处理**：
- `ready_event=waiting/missing` → 重试握手（最多 3 次）
- `alive=inactive` → 重新 spawn + 握手（最多 3 次）
- 重试失败 → `stop()` 等待用户指示

2. 验证通过后，立即发送正式审查任务：

code-analyst 任务：

```yaml
- tool: SendMessage
  params:
    to: "code-analyst"
    summary: "PR #843 代码质量分析任务"
    message: |
      分析 PR #843 的代码质量和技术债。

      读取 Phase 1 背景报告：
        skills/vibe-review-pr/scripts/agent-report.sh context-researcher

      完成分析后用 SendMessage(to="team-lead", message="【agent_report】\n\n## 代码质量分析报告\n...")

      **脚本错误处理**：如脚本执行失败，立即发送【agent_blocked】+ 错误详情，停止执行。
```

architect-reviewer 任务：

```yaml
- tool: SendMessage
  params:
    to: "architect-reviewer"
    summary: "PR #843 架构审查任务"
    message: |
      审查 PR #843 的架构影响。

      读取 Phase 1 背景报告：
        skills/vibe-review-pr/scripts/agent-report.sh context-researcher

      完成审查后用 SendMessage(to="team-lead", message="【agent_report】\n\n## 架构审查报告\n...")

      **脚本错误处理**：如脚本执行失败，立即发送【agent_blocked】+ 错误详情，停止执行。
```

security-reviewer 任务：

```yaml
- tool: SendMessage
  params:
    to: "security-reviewer"
    summary: "PR #843 安全审查任务"
    message: |
      审查 PR #843 的安全问题。

      读取 Phase 1 背景报告：
        skills/vibe-review-pr/scripts/agent-report.sh context-researcher

      完成审查后用 SendMessage(to="team-lead", message="【agent_report】\n\n## 安全审查报告\n...")

      **脚本错误处理**：如脚本执行失败，立即发送【agent_blocked】+ 错误详情，停止执行。
```

**未验证握手成功前，不得给该 agent 分配任何工作。**

### Step 4: 主动等待全部报告（禁止 idle）

**禁止被动等待**：不得收到 idle 通知后直接"等待"，必须使用主动轮询策略。

**主动等待流程**：

对每个 agent，收到 idle 通知后执行轮询：

```bash
# 定义轮询函数
wait_for_report() {
  local agent=$1
  local max_attempts=6  # 30 秒
  
  for i in $(seq 1 $max_attempts); do
    sleep 5
    if skills/vibe-review-pr/scripts/agent-event.sh "$agent" | grep -q "agent_report"; then
      return 0
    fi
  done
  return 1  # 超时
}

# 对每个 agent 轮询
for agent in code-analyst architect-reviewer security-reviewer; do
  wait_for_report "$agent"
  if [ $? -eq 0 ]; then
    skills/vibe-review-pr/scripts/agent-report.sh "$agent"
  else
    # 超时处理
    skills/vibe-review-pr/scripts/agent-exist.sh "$agent"
    # 根据 alive 状态决定重新握手或 spawn
  fi
done
```

**等待超时处理**（30 秒后）：
- 检查 agent alive 状态 -> 若 inactive 重新握手
- 若 active 但无报告 -> 继续轮询或停止等待指示

**处理结果**：
- 全部报告就绪 -> 标记 Phase 2 完成
- 部分超时 -> 停止并等待用户指示

```yaml
- tool: TaskUpdate
  params:
    taskId: "<phase-2-task-id>"
    status: "completed"
```

### Step 4: 激活 Phase 3

`TaskUpdate(taskId=<phase-3>, status="in_progress")`

## Contracts

| 项目 | 内容 |
|------|------|
| 输入 | Phase 1 报告 |
| 输出 | code-analyst / architect-reviewer / security-reviewer 报告 |
| 门禁 | 三个 agent 的 `agent-report.sh` 均返回成功 |

---

# Phase 3: Codex 复查

## Steps

### Step 1: 调用 codex:rescue

codex 自己通过脚本读取前序报告（和 Phase 2 agent 一样），输出由 skill 调用直接返回给 lead：

```yaml
- tool: Skill
  params:
    skill: codex:rescue
    args: |
      复查 PR #<number> 的全部审查报告，给出第三方独立评估。

      读取 Phase 1 背景报告：
        skills/vibe-review-pr/scripts/agent-report.sh context-researcher

      读取 Phase 2 专家评审：
        skills/vibe-review-pr/scripts/agent-report.sh code-analyst
        skills/vibe-review-pr/scripts/agent-report.sh architect-reviewer
        skills/vibe-review-pr/scripts/agent-report.sh security-reviewer

      重点关注：是否有遗漏、结论是否一致、建议是否可行。
      给出综合评估意见。
```

> codex 是外部 plugin，不是 teammate。能跑脚本读 inbox，但不能收 SendMessage。输出由 skill 调用直接返回给 lead。

**Fallback**: 若 codex:rescue 不可用（plugin 未安装或调用失败），team-lead 可自行执行复查逻辑：
1. 读取 Phase 1 背景报告 + Phase 2 三份专家报告
2. 基于 team-lead 自身的推理能力进行第三方独立评估
3. 重点关注遗漏、结论一致性、建议可行性
4. 直接进入 Phase 4 综合判断

### Step 2: 收到 codex 复查结果 -> 激活 Phase 4

标记 Phase 3 完成，激活 Phase 4。

## Contracts

| 项目 | 内容 |
|------|------|
| 输入 | Phase 1 + Phase 2 报告 |
| 输出 | codex 复查报告 |

---

# Phase 4: 综合判断

> team-lead 内联操作，汇总所有报告做最终决策

## Steps

### Step 1: 提取所有报告

```bash
for agent in context-researcher code-analyst architect-reviewer security-reviewer; do
  skills/vibe-review-pr/scripts/agent-report.sh "$agent"
done
```

> codex 复查结果已在 Phase 3 由 skill 调用直接返回，不在 inbox 中。

### Step 2: 输出审查结论

基于所有报告 + 执行模式（auto-fix / ask-each / comment-only），决定：

- 批准: 无阻塞问题
- 修复: 有阻塞问题 + auto-fix -> 激活 Phase 5
- 评论: 有问题但不可自动修复 -> 输出评论，不激活 Phase 5

### Step 3: 按决策行动

auto-fix 且有阻塞问题 — 先提取可修复项，再激活 Phase 5:

```yaml
# 从 Phase 1/2/3 报告中提取具体修复点，整理为修复指令
- tool: TaskUpdate
  params:
    taskId: "<phase-4-task-id>"
    status: "completed"

- tool: TaskUpdate
  params:
    taskId: "<phase-5-task-id>"
    status: "in_progress"
```

**修复指令格式**（Phase 4 产出，写入 Phase 5 prompt）：

```text
## 修复指令

基于 Phase 1-3 审查结论，以下问题可在当前 PR 范围内修复：

1. [具体问题] — 来源: [agent 名] — 修复方式: [具体操作]
2. ...

不可自动修复的问题（已转 follow-up issue / PR comment）：
- [问题] — 原因: [为何不可自动修复]
```

否则标记 Phase 5 为 skipped。

## Contracts

| 项目 | 内容 |
|------|------|
| 输入 | Phase 1/2/3 全部报告 |
| 输出 | 审查结论 + 修复行动 |

---

# Phase 5: 写回 + 修复

> 仅 auto-fix 模式且存在阻塞问题时进入

## Steps

### Step 1: spawn fix-executor

spawn 时 prompt **只包含握手准备，不包含具体任务**：

```text
【第一步只能握手】
你现在不得开始修复，也不得抢先自报 ready。
等待 team-lead 发送 `【lead_ready】`。
收到 `【lead_ready】` 后，执行 ToolSearch(query="select:SendMessage", max_results=1)，
然后立刻 SendMessage(to="team-lead", message="【agent_ready】已就绪")。
在收到 team-lead 后续正式任务前，不得开始任何修复工作。
```

spawn:

```yaml
- tool: Agent
  params:
    description: "修复执行"
    name: "fix-executor"
    subagent_type: "pr-fix-executor"
    team_name: "pr-review-team"
    model: "sonnet"
    prompt: "<上述握手 prompt>"
```

### Step 2: 主动握手等待（禁止 idle）

**禁止被动等待**：发送握手信号后不得 idle，必须使用主动轮询策略。

**主动等待流程**：

发送握手信号：`SendMessage(to="fix-executor", summary="握手信号", message="【lead_ready】")`

立即启动轮询检查（最多 30 秒，每 5 秒检查）：

```bash
for i in {1..6}; do
  sleep 5
  if skills/vibe-review-pr/scripts/agent-exist.sh fix-executor | grep -q "ready_event=found"; then
    break
  fi
done
```

**超时处理**：
- 30 秒后仍未收到 -> 重试发送握手（最多 3 次）
- 3 次超时 -> 停止并标记 blocked，等待用户指示

### Step 3: 验证握手成功 → 分配任务

1. 执行脚本验证握手成功：

```bash
skills/vibe-review-pr/scripts/agent-exist.sh fix-executor
```

**期望输出**：
```
ready_event=found
from=fix-executor
timestamp=...
text=【agent_ready】已就绪
```

**验证失败处理**：
- `ready_event=waiting/missing` → 重试握手（最多 3 次）
- `alive=inactive` → 重新 spawn + 握手（最多 3 次）
- 重试失败 → `stop()` 等待用户指示

2. 验证通过后，立即发送正式修复任务：

```yaml
- tool: SendMessage
  params:
    to: "fix-executor"
    summary: "PR #843 修复任务"
    message: |
      根据 team-lead 提供的修复指令修复 PR #843。

      修复指令：
      <Phase 4 产出的具体修复点列表，逐条包含问题描述、来源 agent、修复方式>

      职责：
      1. 按修复指令逐条执行修复
      2. 不要自行扩大修复范围
      3. 完成后用 SendMessage(to="team-lead", message="【agent_report】\n\n## 修复报告\n...")

      **脚本错误处理**：如脚本执行失败，立即发送【agent_blocked】+ 错误详情，停止执行。
```

**未验证握手成功前，不得给该 agent 分配任何工作。**

### Step 4: 主动等待修复报告（禁止 idle）

**禁止被动等待**：不得 idle，必须使用主动轮询策略。

**主动等待流程**：

收到 fix-executor 的 idle 通知后，执行轮询：

```bash
# 第一次检查
skills/vibe-review-pr/scripts/agent-event.sh fix-executor

# 若无 agent_report，轮询等待（每 5 秒，最多 30 秒）
for i in {1..6}; do
  sleep 5
  skills/vibe-review-pr/scripts/agent-event.sh fix-executor
  if skills/vibe-review-pr/scripts/agent-exist.sh fix-executor | grep -q "agent_report"; then
    break
  fi
done
```

**等待超时处理**：
- 30 秒后仍未收到 -> `agent-exist.sh` 检查 alive 状态
- 若 inactive -> 重新握手
- 若 active -> 继续轮询或停止等待指示

**处理结果**：
- 有 `agent_report` -> `agent-report.sh fix-executor` 提取报告 -> 进入 Step 5
- 无报告且超时 -> 停止并等待用户指示

### Step 5: 修复完成

标记 Phase 5 完成 -> 清理。

## Contracts

| 项目 | 内容 |
|------|------|
| 输入 | Phase 4 结论中的修复指令（lead 直接写入 prompt） |
| 输出 | 修复提交 + 修复报告 |

---

# 清理

审查流程完成后:

1. `TaskUpdate` 标记所有未完成 task 为 skipped
2. `TeamDelete(team_name="pr-review-team")` 清理 team

---

# [附录 A] Shell 脚本速查

```bash
# Agent 存在性
scripts/agent-exist.sh                 # 全部状态
scripts/agent-exist.sh code-analyst    # 单个状态

# Agent 事件
scripts/agent-event.sh                  # 全部最新事件
scripts/agent-event.sh code-analyst     # 单个事件列表

# 报告提取
scripts/agent-report.sh                 # 全部报告状态
scripts/agent-report.sh code-analyst    # 完整报告正文
```

# [附录 B] 主动等待策略（禁止 idle）

**核心原则**：idle notification 是系统通知，但 team-lead 不得被动等待，必须使用主动轮询策略。

**禁止行为**：
- ❌ 收到 idle 通知后直接"等待"不做任何操作
- ❌ 假设 agent 会自动完成
- ❌ 只输出"等待..."然后停止

**强制行为**：
- ✅ 收到 idle 通知后立即执行脚本检查
- ✅ 使用轮询循环主动检查状态（每 5 秒）
- ✅ 超时后主动采取行动（重新握手、spawn、或停止等待指示）

**主动等待流程**：

收到 idle 通知后：

```bash
# Step 1: 立即检查事件
skills/vibe-review-pr/scripts/agent-event.sh <agent>

# Step 2: 若有 agent_report → 提取报告
if skills/vibe-review-pr/scripts/agent-event.sh <agent> | grep -q "agent_report"; then
  skills/vibe-review-pr/scripts/agent-report.sh <agent>
  # 处理报告
fi

# Step 3: 若无 agent_report，启动轮询（最多 30 秒）
for i in {1..6}; do
  sleep 5
  skills/vibe-review-pr/scripts/agent-event.sh <agent>
  if skills/vibe-review-pr/scripts/agent-exist.sh <agent> | grep -q "agent_report"; then
    skills/vibe-review-pr/scripts/agent-report.sh <agent>
    break
  fi
done

# Step 4: 超时处理（30 秒后仍未收到）
if [ $? -ne 0 ]; then
  skills/vibe-review-pr/scripts/agent-exist.sh <agent>
  # 根据 alive 状态采取行动
fi
```

**超时决策树**：

```
超时 (30s 无报告)
  ↓
agent-exist.sh <agent>
  ↓
alive=inactive → SendMessage 要求重发或重新握手
alive=active → 继续轮询（再 30s）或停止等待用户指示
alive=idle → 检查最后一次事件，判断是否需要重新握手
```

详细消息样例见 `references/execution-reference.md`。

# [附录 C] 恢复

Agent 失联:

1. `scripts/agent-exist.sh <agent>` 诊断
2. `SendMessage(to=<agent>, summary="握手测试", message="【lead_ready】")` 测试握手
3. 3 次超时 -> 重新 `Agent(name=<agent>, subagent_type=pr-<agent>, team_name="pr-review-team")` spawn

详细恢复流程见 `references/recovery-playbook.md`。
常见诊断问题见 `references/debug-guide.md`。
