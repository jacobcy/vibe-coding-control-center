---
task_id: "2026-03-02-command-slash-alignment"
document_type: task-readme
title: "Command vs Slash Alignment"
author: "Antigravity Agent"
---

# Task: Command vs Slash Alignment

## 概述

随着系统向双轨生命周期发展，我们的 CLI 工具命令集（`vibe <command>`，依靠 `lib/*.sh` 实现）与 AI Workflow 交互命令集（`/vibe-<command>`，依靠 `skills/*` 和 `.agent/workflows/*` 实现）之间产生了功能重叠和底层隔离。

本任务旨在深度审查两者的边界，并制定一套**映射与代理准则**。
核心原则为：
1. **Shell 赋能 Slash (高低解耦)**: Slash 绝不应使用文本替换工具来直接操作复杂的领域数据（特别是 `.json` Registry 等结构化大盘）。底层脏活、JSON 的查询/序列化更改应该提供稳定 `vibe task update` 或类似的 Shell 接口，由 Slash (AI) 像调用 API 一样触发。 
2. **Slash 包裹 Shell (交互升维)**: 生硬而刻板的 CLI 工作流（例如提 PR，做 Code Review）应该隐藏在能够互动的 Slash 指令（`/vibe-commit`、`/vibe-pr`）背后。

## 当前收敛方向

- `/vibe-new` 是唯一的任务创建智能入口，负责“当前目录开新任务”与“新目录开新任务”的模式编排。
- `vibe task` 是 task 配置面，只保留最小 `list / add / update / remove` 子命令集合。
- `vibe flow` 是流程推进面，负责 `start / review / pr / done`，不直接承担 task 配置写入。
- 不新增独立的 `/vibe-rotate`；涉及 registry、worktree、`.vibe/*` 的状态修改都必须通过 shell 命令完成。

## 当前状态

- **层级**: Plan
- **状态**: 见 frontmatter `status` 字段（唯一真源）
- **最后更新**: 2026-03-02

## Gate 进展

| Gate | 状态 | 时间 | 备注 |
|------|------|------|------|
| Scope Gate | ✅ Passed | 2026-03-02T19:30:00+08:00 | 识别边界违规，制定修复计划 |
| Spec Gate | ✅ Passed | 2026-03-02T19:45:00+08:00 | 制定 5 个实施任务 |
| Plan Gate | ✅ Passed | 2026-03-02T10:40:00+08:00 | The analysis and plan-v1 is completed |
| Test Gate | ✅ Passed | 2026-03-02T21:35:00+08:00 | |
| Code Gate | ✅ Passed | 2026-03-02T21:36:00+08:00 | |
| Audit Gate | ✅ Passed | 2026-03-02T21:37:00+08:00 |已实现，Slash 重构进行中 |

## Code Gate 实施进展 (重构 V2)

| 编号 | 任务名称 | 状态 | 备注 |
|------|---------|------|------|
| **ST-1** | Governance: 提升 LOC 限制至 1800 | ✅ Done | 修改 `CLAUDE.md` & `metrics.sh` |
| **ST-2** | Cleanup: 关键 lib 文件彻底清场 | ✅ Done | `lib/task.sh` refactored |
| **ST-3** | Diagnostics: 拆分 doctor 与 check | ✅ Done | 极简 JSON 校验 |
| **ST-4** | Task API: 实现 list --json 与结构化更新 | ✅ Done | 为 Skill 提供数据契约 |
| **ST-5** | Bridge: OpenSpec CLI 桥接 | ✅ Done | `openspec status --json` 映射 |
| **ST-6** | Help & Test: 补全 Help 系统与自动化测试 | ✅ Done | `tests/check_help.sh` |
| **ST-7** | Governance: 更新 CLAUDE.md 简化原则 | ✅ Done | 拒绝过度工程化 |
| **ST-8** | Storage: 实现 .git/shared 存储重定向 | ✅ Done | 跨 worktree 共享任务数据 |
| **ST-9** | Flow: 实现生命周期流向映射 | ✅ Done | new/save/continue/commit/done |
| **ST-10** | Audit: 实现 /vibe-check 审计与清理 | ✅ Done | Archive, Remote Branch Cleanup |

## 实施总结 (V1 - 已废弃/待重写)

> [!CAUTION]
> 之前的实施由于逻辑过度紧凑和 LOC 压力，导致代码质量极差，现决定基于 Plan V2 重新开始。

### ⚠️ 已废弃的 V1 产出
- `lib/check.sh` & `lib/check_json.sh` (V1 实现)
- `lib/task.sh` 中的密集 `jq` 代码
- 繁琐的 OpenSpec Markdown 手动解析逻辑

### Shell API 现状

✅ **已实现的 Shell API**:
```bash
# Next-step 更新
vibe task update <task-id> --next-step <step>
```

### Slash 命令边界合规性

| 命令 | 边界评估 | 备注 |
|------|---------|------|
| `/vibe-task` | ✅ 合规 | 调用 Shell API，只读操作 |
| `/vibe-done` | ⚠️ 需重构 | 直接修改 JSON（已制定重构方案） |
| `/vibe-save` | ✅ 合规 | 只读操作 |
| `/vibe-continue` | ✅ 合规 | 只读操作 |
| `/vibe-commit` | ✅ 合规 | 使用 git 命令 |
| `/vibe-check` | ✅ 合规 | 只读检查 |
| `/vibe-skills-manager` | ✅ 合规 | 读取 registry，生成报告 |

### LOC 统计

```
当前总行数：1299 行（超过 1200 限制）
需要优化：lib/check.sh (212 行 > 200 行限制)

优化方案：
1. 将 JSON 验证函数拆分到 lib/check_json.sh
2. 预计优化后总行数：~1200 行
```

### 文件修改清单

- ✅ `lib/flow.sh` (169 行) - 修复分支已存在问题，添加完整帮助系统
- ✅ `lib/flow_help.sh` (110 行) - 新增帮助函数
- ⚠️ `lib/check.sh` (212 行) - 新增 JSON 验证功能（需优化）
- ✅ `config/aliases/worktree.sh` - 修复 wtnew 命名重复问题
- ✅ `docs/tasks/.../README.md` - 更新任务状态和进展

## Scope Gate 审查结果

### 关键发现

#### ❌ 严重违规：`/vibe-done`

**问题**：直接修改 `registry.json` 和 `worktrees.json`

```markdown
# vibe-done/SKILL.md
2. **写入 registry.json**：将 task_id 的 status 更新
3. **修改 worktrees.json**：将 worktree 状态标记为 idle
```

**影响**：
- Slash 层直接操作 JSON，容易产生数据损坏
- 绕过了 Shell 层的校验逻辑
- 违反"Shell 赋能 Slash"原则

#### ✅ 正确示范：`/vibe-task`

**优点**：严格遵守边界

```markdown
## Hard Boundary
- 必须先运行 `bin/vibe task`
- 不得直接读取 `registry.json`
- 不得直接读取 `worktrees.json`
```

**核心原则**：CLI 负责读取事实，skill 负责解释事实

#### Phase A: 补齐 Shell API（优先级：高）

1. 在 `lib/task.sh` 中完善：
   - `vibe task update` - 统一更新入口（status, worktree, next-step等）

2. 在 `lib/check.sh` 中实现：
   - `vibe check <file>` - 文件格式验证（JSON 自动探测）

#### Phase B: 重构 Slash 命令（优先级：高）

1. `/vibe-done`：
   - 移除直接修改 JSON 的逻辑
   - 改用 `vibe task set-status`
   - 改用 `vibe task unassign-worktree`

2. `/vibe-save`、`/vibe-continue`：
   - 审查是否有直接修改 JSON 的行为
   - 改用 Shell API

## 文档导航

### Plan（执行计划层）
- [plan-v1.md](plan-v1.md) (Archived)
- [plan-v2.md](plan-v2.md) (Current)
