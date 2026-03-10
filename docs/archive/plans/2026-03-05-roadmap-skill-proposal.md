---
title: "Roadmap 技能方案：全景路线图规划与任务编排"
date: "2026-03-05"
status: "draft"
author: "Codex GPT-5"
related_docs:
  - docs/plans/2026-03-05-issue-36-github-projects-integration.md
  - .agent/workflows/vibe-new.md
---

# Roadmap Skill Proposal

## Goal
建立一个 `vibe-roadmap` 技能：维护“全景路线图”这个长期工件，持续聚合需求、按目标和容量排布优先级，并在任意时刻回答“我们整体计划是什么、当前在哪、下一步做什么”。

## Non-Goals
- 不替代本地 `vibe task` 执行流。
- 不把 roadmap 降级为“单 issue 的通过/拒绝器”。
- 不在技能层直接改写底层 JSON 真源（必须走 Shell API）。

## Tech Stack
- Skill 层：`skills/vibe-roadmap/SKILL.md`
- CLI/真源：`bin/vibe` + `lib/task*.sh` + `lib/flow*.sh`
- 数据适配器：GitHub Projects/Issues、Linear、本地 JSON
- 数据策略：roadmap 维护全景计划；task 负责执行落地

## 核心模型（全景）

输入：多来源需求池（Issue/Linear/本地 JSON/已有 task）+ 当前阶段约束（版本窗口、容量、风险、依赖）

输出：一个持续维护的路线图视图，而非单点审批结果。

### Roadmap 视图结构（建议）
1. `Now`：当前窗口必须推进的事项（可映射执行任务）
2. `Next`：下一窗口高优先事项（已成形但未开工）
3. `Later`：方向正确但时机未到
4. `Blocked`：受依赖阻塞，等待解锁
5. `Exploration`：信息不足、需调研

补充定位：
- `roadmap` 的本质是“全景规划 + 动态排布 + 下一步指引”。
- Issue 只是输入渠道之一，不是 roadmap 的边界。
- 单个需求的通过/延期只是全景排布中的一个动作，不是 roadmap 全部价值。

### 决策维度（最小集）
- 影响面：用户影响/稳定性风险
- 紧急性：是否阻断发布或主路径
- 成本：预估工作量与不确定性
- 依赖：是否被其他任务阻塞
- 时机：是否处于封板窗口
- 容量：当前窗口可承载工作量与并行上限

### 封板规则（你提出的关键点）
- 封板期间发现非阻断问题：默认 `NEXT`。
- 仅当问题属于“发布阻断/数据安全/严重回归”才允许 `NOW`。

## 与本地 Task 的关系

- roadmap 管全局计划；task 管具体执行。
- 只有进入 `Now` 的 roadmap 事项，才需要被编排为可执行 task。
- `task sync` 是 roadmap 的采集工具，不是 task 自动创建工具。
- 输入渠道可替换：GitHub/Linear/本地 JSON 都可接入同一 roadmap 视图。

## 建议工作流

### 流程 A：更新全景路线图
1. 采集多来源需求（GitHub/Linear/本地 JSON/已有 task）
2. 标准化字段（价值、风险、规模、依赖、目标窗口）
3. 按容量与目标完成全局排布（Now/Next/Later/Blocked/Exploration）
4. 输出路线图快照（本窗口、下窗口、阻塞项、风险项）
5. 对 `Now` 事项生成执行入口建议（task id、next step、是否 bind 当前 worktree）

### 流程 B：封板前批量审视
1. 刷新候选输入并同步当前执行状态
2. 重新评估全景路线图排布（重点看容量、阻塞、发布风险）
3. 生成“当前窗口收敛清单”和“下一窗口承接清单”

## 需要修改的文件（实施阶段）
- Create: `skills/vibe-roadmap/SKILL.md`
- Modify: `skills/vibe-skills-manager/registry.json`（注册新技能）
- Optional Modify: `AGENTS.md`（若需加入 quick start）
- Optional Modify: `docs/standards/command-standard.md`（若新增 `vibe roadmap` CLI）

## Test Command（实施后）
- `bin/vibe check`
- `jq . skills/vibe-skills-manager/registry.json`
- 手工验证：
  - 输入 GitHub/Linear/本地 JSON 三路需求 → 期望输出统一 roadmap 视图
  - 给出容量约束后重新计算 → 期望 roadmap 排布稳定更新

## Expected Result
- 能清楚看到“整体计划是什么”，而不是只看到单需求审批结果。
- roadmap 可以对多来源需求做统一排布，并持续回答“当前与下一步”。
- task 仅承接 `Now` 事项进入执行编排，避免计划层和执行层混杂。
- 封板时通过全景视图收敛，而不是靠临时逐条判断。

## Change Summary (for this discussion output only)
- Added: 本文档 1 个（约 +110~130 行）
- Modified: 0
- Removed: 0

## 建议的第一版范围（MVP）
- 先实现“全景视图聚合 + 排布”能力（支持 GitHub 或本地 JSON 任一输入源）
- 仅把 `Now` 事项转为 task 建议，不自动执行写回
- 你确认后再接入 Linear 与自动回写能力
