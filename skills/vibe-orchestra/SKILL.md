---
name: vibe-orchestra
description: Use when the user wants to manually review issues, assign issues to managers, or check orchestra service status. Human-collaboration entrypoint for issue pool governance and service monitoring.
---

# /vibe-orchestra - Orchestra 服务监控与 Issue 治理入口

人机协作的 orchestra 服务监控和 issue pool 治理入口。

## 核心原则

- **人机协作**：提供交互式 issue 治理，不自动执行
- **基于真源**：只读 `vibe3 serve status` 和 `vibe3 task status` 输出
- **手动决策**：用户决定是否分配 assignee 或添加标签

## Scope

**两大职责**：

### 1. Service 监控
- serve 运行状态（running/stopped）
- FailedGate 检查
- error_log 分析
- heartbeat 状态
- dispatcher 状态
- 最近活动和事件

### 2. Issue Pool 治理（手动）
- 查看 assignee issue pool 状态
- 扫描候选 issue（无 assignee 的 open issues）
- 手动分配 issue 给 manager bot
- 添加治理标签（如 `orchestra-scanned`）
- 关闭明显过时的 issue

**不做**：
- 自动化 issue triage（由 `vibe scan governance -r roadmap-intake` 负责）
- 版本规划（由 `vibe-roadmap` 负责）
- RFC issues 处理（由 `vibe-task` 负责）

## Workflow

### Part 1: Service 监控

#### Step 1: 查看 serve 状态

```bash
vibe3 serve status
```

#### Step 2: 解析状态

从输出中提炼：

**运行状态**：
- Service 状态（running/stopped）
- PID 信息
- Port 绑定
- Uptime

**错误检查**：
- FailedGate 是否存在
- error_log 内容
- 系统错误

**最近活动**：
- Heartbeat 时间
- Dispatcher 状态
- 最近事件

#### Step 3: 报告问题

```text
📋 Orchestra Service 状态

运行状态
- Status: running
- PID: 12345
- Port: 8765
- Uptime: 2 hours

健康检查
- FailedGate: None ✅
- Error Log: Empty ✅
- Heartbeat: Normal ✅

最近活动
- Last Heartbeat: 2026-05-28 23:20:00
- Dispatcher: Active
- Recent Events: 3 (last hour)

建议
- Service 运行正常，无错误
```

**常见问题处理**：

**FailedGate 存在**：
```bash
vibe3 serve resume --reason "clear FailedGate"
```

**Service stopped**：
```bash
vibe3 serve start
```

### Part 2: Issue Pool 治理（手动）

#### Step 4: 查看 assignee pool 状态

```bash
vibe3 task status
```

解析输出：
- Ready queue: 待执行 issues
- Blocked queue: 阻塞 issues
- Active flows: 活跃开发流程
- Remote tasks: 远端仓库任务

#### Step 5: 扫描候选 issues

**查询候选**（无 assignee 的 open issues）：
```bash
gh issue list --state open --json number,title,assignee,labels --jq '.[] | select(.assignee == null) | select(.labels | any(.name == "orchestra-scanned") | not)'
```

**逐个审查**：
```bash
vibe3 task show <issue-number>
```

审查要点（参考 roadmap-intake 三级框架）：
- Level 0: 是否涉及 `.claude/` 或 `.codex/`（权限问题）→ 跳过并打 `roadmap/rfc`（机械阻塞，需人类；与自动 intake 一致，见 Step 6）
- Level 1: 问题是否明确？范围是否可控？
- Level 2: 架构是否仍相关？引用的代码/文档是否存在？
- Level 3: 是否过时/重复？是否有未完成工作？

#### Step 6: 手动分配 assignee

**接受 issue**：
```bash
# 分配给 manager bot
gh issue edit <issue-number> --add-assignee "@vibe-manager-agent"

# 写简短 intake 说明
gh issue comment <issue-number> --body "[governance] Intake: assigned to @vibe-manager-agent (manager-pool); scope=<bugfix/feature/refactor>."
```

**跳过 issue**：
```bash
# 打 orchestra-scanned 标签
gh issue edit <issue-number> --add-label "orchestra-scanned"

# 写跳过原因
gh issue comment <issue-number> --body "[governance suggest] Skipped: <原因>"
```

**跳过 Level 0（`.claude/`/`.codex/` 机械阻塞）**：除 `orchestra-scanned` 外**直接打 `roadmap/rfc`**（与 roadmap-intake 的机械例外一致）。Level 0 issue 无 assignee，pool 扫不到；只有 `roadmap/rfc` 能命中 task-status Rule 1 被 `/vibe-task` surface，否则永久隐藏。
```bash
gh issue edit <issue-number> --add-label "orchestra-scanned" --add-label "roadmap/rfc"
gh issue comment <issue-number> --body "[governance suggest] Skipped: 涉及 .claude/.codex 权限配置，机械阻塞需人类决策（已打 roadmap/rfc 供 /vibe-task surface）"
```

**关闭过时 issue**：
```bash
gh issue close <issue-number> --comment "关闭理由：<具体理由>"
```

## 交互式决策流程

**用户主导**：
1. 用户询问："帮我看看有哪些 issue 可以分配"
2. Agent 扫描候选 issues 并展示
3. 用户选择："issue #123 看起来可以分配"
4. Agent 执行三级审查并报告："issue #123 通过三级审查，建议分配给 vibe-manager-agent"
5. 用户确认："好的，分配吧"
6. Agent 执行分配并写 comment

**不自动执行**：
- ❌ 不主动触发 governance scan
- ❌ 不批量处理所有 issues
- ❌ 不绕过用户确认直接分配

## 与其他 Skills 的区别

| Skill | 职责 | 触发方式 | 自动化程度 |
|-------|------|---------|-----------|
| **vibe-orchestra** | Service 监控 + 手动 issue 治理 | 交互式 | 人机协作 |
| **vibe scan governance -r roadmap-intake** | 自动化 issue triage | 定时/手动触发 | 全自动 |
| **vibe-task** | Task/flow 状态查看 | 只读查询 | - |
| **vibe-roadmap** | 版本规划和 backlog triage | 交互式 | 人机协作 |
| **vibe-debug-serve** | 深度调试 service 问题 | 交互式 | 人机协作 |

**与 roadmap-intake 的关键区别**：
- `roadmap-intake`：自动化扫描 + 批量处理 + 最小动作
- `vibe-orchestra`：手动扫描 + 单个处理 + 用户确认

## 使用场景

### 场景 1: 检查 serve 健康状态
```
用户: vibe-orchestra
Agent: 
  1. 运行 vibe3 serve status
  2. 解析并展示运行状态、错误、活动
  3. 如有 FailedGate，建议清除方法
```

### 场景 2: 手动分配 issue
```
用户: 帮我看看 issue pool 里有哪些可以分配的 issue
Agent:
  1. 运行 vibe3 task status 查看 pool 状态
  2. 扫描无 assignee 的 open issues
  3. 展示候选列表（标题、简要描述）
  4. 等待用户选择

用户: issue #123 看起来不错，帮我审查一下
Agent:
  1. 运行 vibe3 task show 123
  2. 执行三级审查（Level 0-3）
  3. 报告审查结果："通过三级审查，建议分配"

用户: 好的，分配吧
Agent:
  1. 执行 gh issue edit 123 --add-assignee "@vibe-manager-agent"
  2. 写 [governance] comment
  3. 确认完成
```

### 场景 3: 跳过不适合的 issue
```
用户: issue #456 看起来有问题
Agent:
  1. 运行 vibe3 task show 456
  2. 发现 Level 0 检查失败（涉及 .claude/ 目录）
  3. 建议："跳过，涉及权限配置，打 orchestra-scanned + roadmap/rfc（机械阻塞，需人类）"

用户: 确认跳过
Agent:
  1. 执行 gh issue edit 456 --add-label "orchestra-scanned" --add-label "roadmap/rfc"
  2. 写 [governance suggest] comment 说明原因
  3. 确认完成（roadmap/rfc 让 /vibe-task 后续可 surface 给人类）
```

## Stop Point

完成以下之一后停止：
- Service 状态报告完成
- Issue 分配或跳过完成
- 用户明确结束对话

**不进入**：
- 自动化批量处理
- Plan/run/review 执行链
- Roadmap 版本规划