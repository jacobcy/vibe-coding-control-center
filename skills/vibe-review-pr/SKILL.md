---
name: vibe-review-pr
description: |
  Use only in Claude Code environments with Agent Teams enabled when the user wants
  a comprehensive PR review using the multi-agent team workflow.
---

# Vibe PR Review Skill

## Overview

`vibe-review-pr` 是 **Claude Code Agent Teams 专用入口**。它只负责：

1. 环境检查
2. 选择执行模式
3. PR 队列排序与选择
4. 加载 team template 并创建或复用 team
5. 判断 PR 类型与检查深度
6. 驱动审查直到人类确认结束
7. 人类确认后删除 team

真实流程定义在 `.claude/team-templates/pr-review-team.yaml`。本文件只保留入口路由、阶段契约和硬边界，不再内嵌长样例。

非 Claude team 环境不要模拟本 workflow。包括 Codex 在内的非 Claude team host，统一分流：

- docs-only PR → `vibe-review-docs`
- 其他 PR → `vibe-review-code`

## When to Use

只有在以下条件同时满足时才使用本 skill：

- 当前 host 是 Claude Code
- `TMUX` 已设置
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- 当前工具面提供 TeamCreate / Agent / SendMessage / teammate-message 等 team 能力

不满足任一条件时，立即停止 team workflow，按文件范围回退到单 agent 审查。

## Must Read

开始执行前，至少读取这 3 处：

1. `.claude/team-templates/pr-review-team.yaml`
2. `.claude/agents/pr-*.md`
3. `docs/references/team-guide.md`

如需详细样例，继续读：

- `skills/vibe-review-pr/references/execution-reference.md`
- `skills/vibe-review-pr/references/recovery-playbook.md`

## Execution Flow

### Step 1: 环境检查

先检查环境，再决定是否继续 team workflow。

```bash
echo "TMUX: ${TMUX:-未设置}"
env | grep -i "CLAUDE.*TEAM" || echo "未设置"
```

Team 工具采用 deferred tools 机制时，先确认工具名可见，再用 `ToolSearch` 加载定义。若 TeamCreate / TeamDelete / SendMessage 不可用，直接回退到 `vibe-review-docs` 或 `vibe-review-code`。

### Step 2: 选择执行模式

在开始审查前先确定执行模式，除非用户已明确指定：

- `auto-fix`
- `comment-only`
- `auto-decide`
- `ask-each`（默认）

把选择保存到当前执行上下文；只有当 PR 进入多人流程时，才写入 team context 给 Phase 4 使用。

### Step 3: PR 队列排序与选择

当用户没有指定 PR 编号时，先列出 open PR，再按以下优先级排序：

1. `state/merge-ready`
2. 改动更小
3. `baseRefName == main`
4. 如范围重叠，优先审查改动更大的 PR

如果用户已明确指定 PR，直接审查该 PR，不重排。

### Step 4: 检查已有审查记录

开始前先看 PR 是否已有评论：

- 无评论：继续
- 有人类评论：询问是否完整重审
- 有 agent/bot 评论：询问是否补充审查
- 用户选择 `skip`：返回 Step 3 处理下一个 PR

### Step 5: 加载 Team Template

此步先加载配置。必须读取 `.claude/team-templates/pr-review-team.yaml`，后续所有 phase 行为都按其中的 `workflow.execution`、`agents`、`pr_classification` 执行。

### Step 6: 创建或复用 Team

在判断当前 PR 类型之前，先确保当前会话已经持有 `pr-review-team`。

先判断当前会话里是否已经存在可复用的 `pr-review-team`：

- 已存在且状态健康 → **直接复用**，跳过 TeamCreate
- 不存在 → 调用 TeamCreate 创建
- 存在但状态不一致 → **不要清理、不要关停、不要 TeamDelete**；停止当前轮次，交给人类决定是否退出并重建会话

```yaml
TeamCreate(team_name="pr-review-team", agent_type="general-purpose")
```

规则：

- TeamCreate 只在 `pr-review-team` 缺席时调用
- 整个审查周期最多创建一次
- 后续 PR 复用当前会话中的 `pr-review-team`
- 如果 Team 已存在，不要再次调用 TeamCreate 试探
- 如果 Team 状态异常，不要发送 shutdown 指令试图“清空后重建”
- 不要手工创建 `~/.claude/teams/pr-review-team/`
- 不要伪造 `config.json`

### Step 7: 判断 PR 类型

根据 template 中的 `pr_classification` 自动分类：

| 类型 | 处理 |
|------|------|
| `simple` | 保留已创建的 team，只执行阶段 1 |
| `refactor` | 进入多人流程 |
| `security` | 进入多人流程，且必须包含 `security-reviewer` |
| `standard` | 进入多人流程 |

检查深度规则：

- `simple`：**只执行阶段 1 检查**
- `refactor` / `security` / `standard`：**执行阶段 1 + 阶段 2 的双阶段检查**

`simple` PR 的分流规则：

- 仅文档变更 → 由 team-lead 使用 `vibe-review-docs` 完成阶段 1 检查
- 其他 → 由 team-lead 使用 `vibe-review-code` 完成阶段 1 检查

这里的“阶段 1 检查”指：

- team 已经存在
- 由 team-lead 在当前会话中执行对应单 agent skill
- 不启动 Phase 2 专项审查 agent
- 仍处于当前 team 生命周期内；完成阶段 1 后直接进入写回/继续流程

### Step 8: 执行审查流程

按 PR 类型执行：

- `simple`：只执行阶段 1 检查，由 team-lead 使用对应单 agent skill 完成
- `refactor` / `security` / `standard`：按 template 驱动 Phase 1-5

这里要明确区分：

- “两步检查”只指 **Phase 1 + Phase 2**
- Phase 3-5 是汇总、写回和收尾，不是额外检查层级
- `simple` 没有 Phase 2；它在已存在的 team 现场中完成阶段 1 后，直接进入写回/继续流程

多人流程下的阶段契约：

- Phase 1：背景调研，必须产出 `phase_1_output`
- Phase 2：专项审查，必须在**单次响应**中启动多个 Agent 调用，并用 `SendMessage` 把 `phase_1_output` 发给每个 Phase 2 agent
- Phase 3：综合判断，必须检查缺失报告、记录冲突、完成仲裁
- Phase 4：写回与改进，由 team-lead 主导；仅 `auto-fix` 路径允许额外 spawn `fix-executor`
- Phase 5：准备下一个 PR，保留 inbox / idle state / pane 信息，不做手工清理

详细 phase 样例、消息格式和等待策略见 `references/execution-reference.md`。

### Step 9: 询问是否继续

每个 PR 审查完成后，询问用户是否继续审查下一个 PR：

- `continue` → 返回 Step 3
- `end` → 进入 Step 10

### Step 10: 删除 Team

只在人类明确确认结束审查后执行：

```yaml
TeamDelete(team_name="pr-review-team")
```

如果这轮在 Step 6 之前就停止、从未创建 team，则不需要 TeamDelete。

`TeamDelete` **不是**恢复工具，不用于：

- 处理 `Already leading team "pr-review-team"`
- 解决 team 状态不一致
- 为了“重新创建 team”而先删后建

## Phase Contracts

### Phase 1

- 必须先于 Phase 2 完成
- 必须把背景报告保存为 `phase_1_output`
- 不允许只把结果打印到终端而不回传给 team-lead

### Phase 2

- 多个审查 agent 必须在同一响应中启动
- 不能跳过 `SendMessage`
- 不能让 Phase 2 在没有背景信息时盲审

### Phase 3

- 必须检查是否缺少任何审查报告
- 有冲突必须仲裁，不做机械拼接
- 缺失报告时只能标注“审查不完整”，不能替缺失 agent 脑补同意

### Phase 4

- 执行模式决定写回路径
- `comment-only` 只写 comment
- `auto-fix` 才能 spawn `fix-executor`
- 范围外问题才创建 follow-up issue

### Phase 5

- 不删除 team
- 不清空 inbox
- 不清理 tasks
- 只记录当前 PR 完成并保留可复用状态

## Guardrails

### Team 生命周期

- 环境检查必须在 TeamCreate 之前
- Team 在当前审查会话开始后先创建或复用，再判断 PR 类型
- 已存在的健康 Team 必须优先复用
- Team 整个周期最多创建一次、最多删除一次
- `simple` 与复杂 PR 共用同一个 team 生命周期
- Step 10 之外不得调用 TeamDelete
- 当前会话若无法安全复用现有 Team，唯一合法恢复是退出并重建会话

### 边界

- 不要在 Codex 或其他非 Claude team host 中模拟这个 workflow
- 不要绕过 `.claude/team-templates/pr-review-team.yaml` 自创 phase 顺序
- 不要手工修改 `~/.claude/projects/.../*.jsonl`
- 不要手工 `rm -rf ~/.claude/teams/pr-review-team`
- 不要手工 `tmux kill-pane` 代替 TeamDelete
- 不要为恢复目的发送 teammate shutdown 指令
- 不要把 TeamDelete 当作“清场后重建”的恢复手段

### 质量控制

- 关键结论必须有证据，不接受“已合并”“CI 通过”“无漏洞”这类无证据结论
- Phase 2 的背景传递是硬要求，不是建议项
- team-lead 必须做差异仲裁，不能只汇总 teammate 原话

## Common Mistakes

### 过早创建 Team

错误：环境一通过就 `TeamCreate`。  
正确：先加载 template，再创建或复用 team，然后才判断当前 PR 类型。

### 已有 Team 仍重复创建

错误：看到多人流程 PR 就再次 `TeamCreate`。  
正确：先检查 `pr-review-team` 是否已存在且健康；存在就直接复用。

### simple PR 误入多人流程

错误：把 `simple` 理解成“不创建 team”。  
正确：`simple` 也在已创建的 team 现场中执行，只是不进入 Phase 2，且阶段 1 由 `vibe-review-docs` 或 `vibe-review-code` 完成。

### 把双阶段检查套到所有 PR

错误：不区分复杂度，默认所有 PR 都做 Phase 1 + Phase 2。  
正确：只有 `refactor` / `security` / `standard` 才做双阶段检查；`simple` 只做阶段 1。

### 忘记发送 Phase 1 背景

错误：Phase 2 agent 启动后直接开审。  
正确：必须 `SendMessage` 把 `phase_1_output` 发给每个 Phase 2 agent。

### 手工修状态

错误：手工建 team 目录、改 `config.json`、改 session JSONL。  
正确：结束会话，重进后重新走 Step 1-7。

### 把 TeamDelete 当恢复工具

错误：`Already leading...` 后尝试 TeamDelete、shutdown teammates、再 TeamCreate。  
正确：先检查并复用现有 team；若状态异常，停止当前轮次，由人类退出并重建会话。

### Phase 5 手工清理

错误：清空 inbox、删除 tasks、手工杀 pane。  
正确：保留状态给下一个 PR，最终只通过 TeamDelete 清理。

## Recovery

以下情况不要在主文件中临场发明 workaround，直接按恢复手册处理：

- `TeamCreate` 与 `Agent spawn` 状态不一致
- 已有 `pr-review-team` 但需要确认是否可直接复用
- TeamDelete 后 UI 仍显示 teammates running
- 部分审查 agent 超时或缺失
- 背景报告未送达 team-lead

恢复步骤见 `skills/vibe-review-pr/references/recovery-playbook.md`。

## File Map

| 文件 | 职责 |
|------|------|
| `skills/vibe-review-pr/SKILL.md` | 主入口：路由、阶段契约、硬边界 |
| `skills/vibe-review-pr/references/execution-reference.md` | 详细 phase 样例和消息格式 |
| `skills/vibe-review-pr/references/recovery-playbook.md` | 故障恢复与清理边界 |
| `.claude/team-templates/pr-review-team.yaml` | 团队配置和执行真源 |
| `.claude/agents/pr-*.md` | 各 teammate 的项目特定职责 |
| `docs/references/team-guide.md` | Team 功能通用背景 |

## Usage

```text
/vibe-review-pr 604
```

或：

```text
用 vibe-review-pr 审查 PR #604
```
