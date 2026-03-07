---
title: "Issue #36 解决方案：GitHub Projects 与 Vibe 任务系统整合"
date: "2026-03-05"
status: "draft"
source_issue: "https://github.com/jacobcy/vibe-coding-control-center/issues/36"
related_issues:
  - "https://github.com/jacobcy/vibe-coding-control-center/issues/34"
  - "https://github.com/jacobcy/vibe-coding-control-center/issues/35"
---

# Issue #36 解决方案（讨论稿）

## 1. 目标与非目标

### 1.1 目标
- 建立 `Roadmap ↔ Task ↔ Issue/Project` 的稳定映射，避免重复建模。
- 明确职责分层：`Issue` 负责需求讨论入口，`roadmap` 负责全景排布与优先级，`orchestrator` 负责设计/测试/代码/提交执行编排，`supervisor` 负责每道防线把控。
- 让 `vibe task sync` 成为 roadmap 的 GitHub 数据适配器：只负责拉取候选输入（兼容当前 OpenSpec 同步）。
- 让执行阶段关键状态可由 orchestrator/supervisor 流程回写到 GitHub（Issue 状态、标签、Project Stage）。
- 与 #34（Issue 同步）和 #35（save 自动关联）形成一条完整链路。

### 1.2 非目标
- 不重构现有 `flow` 全流程，也不一次性实现全部 PRD→Spec→Test→Code→Audit 细粒度自动推断。
- 不改变当前 `registry/worktrees` 的主存储位置和写入入口（仍由 Shell API 负责）。
- 不引入数据库或后台常驻服务。

## 2. 现状事实（基于当前代码）

- `vibe task sync` 目前只同步 OpenSpec（`lib/task_actions.sh:_vibe_task_sync`）。
- `task` 展示层已支持 `framework/source_path`（`lib/task_render.sh`），可扩展为 GitHub 来源。
- `flow` 已依赖 `gh` 做 PR 查询（`lib/flow.sh`），具备接入 GitHub API 的基础前提。
- 现有测试已覆盖 OpenSpec 同步基线（`tests/test_task_sync.bats`）。

## 3. 方案对比

### 方案 A：Task 完全映射为 Issue（强绑定）
- 优点：认知简单，GitHub 生态一致。
- 缺点：本地离线与临时任务能力下降；迁移成本高。

### 方案 B：Task 完全独立，Issue 仅外部镜像（弱绑定）
- 优点：实现最轻。
- 缺点：人工同步负担高，难满足 #34/#35/#36 的自动化诉求。

### 方案 C（推荐）：混合模式（Task 为本地真源，Issue/Project 为协作镜像）
- 优点：兼顾本地执行效率与 GitHub 协作可见性；渐进迁移风险低。
- 缺点：需要定义冲突处理和幂等规则。

**推荐结论：采用方案 C。**

### 3.1 角色定位（本方案基线）
- `Issue`：需求讨论与上下文沉淀入口，不承担执行编排职责。
- `roadmap`：全景决策中枢，维护整体计划排布（Now/Next/Later/Blocked/Exploration）并给出下一步。
- `orchestrator`：执行编排器，负责把被批准事项推进到设计、测试、代码与提交。
- `supervisor`：治理与审计防线，逐关拦截越界、缺测试、缺验证、缺证据等风险。
- `task sync`：roadmap 的 GitHub 输入适配器，不直接把 Issue 变成 Task。

## 4. 推荐设计

## 4.1 数据模型扩展（最小增量）
新增 roadmap 聚合数据（可落在本地 JSON，如 `registry.json.roadmap[]`），Task 只承接 `Now` 事项：

```json
{
  "item_id": "rm-20260305-001",
  "title": "Improve task sync for roadmap",
  "bucket": "next",
  "priority_score": 78,
  "task_ref": null,
  "source": {
    "provider": "github",
    "repo": "owner/repo",
    "issue_number": 123,
    "issue_node_id": "I_kw..."
  }
}
```

说明：
- roadmap 层维护全景排布，不等于 task 列表。
- `task_ref` 仅在事项进入 `Now` 并被执行编排后才填充。
- GitHub/Linear/本地 JSON 都可以成为 `source.provider`。

## 4.2 状态映射规则

### Roadmap.bucket ↔ GitHub Project 列（建议）
- `now` → In Progress
- `next` → Next
- `later` → Backlog
- `blocked` → Blocked
- `exploration` → Discovery

### 已绑定 Task.status ↔ GitHub Issue
- `todo/in_progress/review/blocked` → Issue 保持 `open`
- `completed/archived/done/skipped` → Issue `closed`

## 4.3 同步方向与冲突策略

默认 `vibe task sync --provider github --direction pull`：
- Pull（GitHub→本地）：
  - 新 open issue（带 `vibe-task` 标签）拉取为 roadmap 候选输入。
  - roadmap 统一排布后，仅 `Now` 事项进入 task 创建/绑定流程。
  - 已绑定 issue 的标题、关闭状态同步到本地。
- `task sync` 不承担 push 职责；状态回写由 roadmap/orchestrator 的后续流程负责。

冲突规则：
1. `Issue closed` 优先级最高，强制本地进入 `completed`（或 `archived`）。
2. 标题默认 GitHub 优先（协作面更一致）。
3. 其他字段用 `updated_at` 最近写入优先。
4. `--dry-run` 仅输出差异，不落库不回写。

## 4.4 命令接口建议

- `vibe task sync --provider github [--repo owner/repo] [--label vibe-task] [--project <id>] [--direction pull] [--dry-run]`
- `vibe task link <task-id> --issue <number> [--repo owner/repo]`
- `vibe task unlink <task-id> [--keep-issue]`

说明：
- `sync` 保持为唯一同步入口，避免再新增平行命令族。
- `link/unlink` 解决人工绑定与迁移场景。

## 4.5 与 #34 / #35 的一体化

- #34：通过 `sync --direction pull` 先落地。
- #35：`vibe save` 时若当前 worktree 无 task，按策略：
  - 有绑定 issue → 先经过 roadmap 决策，再创建/绑定 task
  - 无绑定 issue → 按配置可选自动建 issue（默认关闭，避免噪音）
- #36：在上述能力之上增加 Project stage 自动同步。

### 4.6 端到端主链路（统一口径）
1. 在 `Issue` 中讨论和沉淀需求。
2. `task sync` 拉取候选 Issue 供 roadmap 决策使用（不直接建 task）。
3. `roadmap` 维护全景路线图排布，并明确本窗口 `Now` 事项。
4. `orchestrator` 对 `Now` 事项执行设计→测试→代码→提交的任务编排。
5. `supervisor` 在各 Gate 执行防线校验，未通过即阻断。

## 5. 任务拆解（Execution Plan）

### Task 1：扩展 task sync 参数解析与 GitHub 拉取
- 文件：
  - 修改 `lib/task_actions.sh`
  - 修改 `lib/task_help.sh`
- 测试：
  - 新增 `tests/test_task_sync_github.bats`
- 验证命令：
  - `bats tests/test_task_sync_github.bats`
- 预期：
  - 能把带 `vibe-task` 标签的 open issue 拉入 roadmap 候选输入池。

### Task 2：实现 roadmap 候选输入池的 GitHub 元数据写入与幂等更新
- 文件：
  - 修改 `lib/task_actions.sh`
  - 修改 `lib/task_write.sh`
- 测试：
  - 扩展 `tests/test_task_sync.bats`
- 验证命令：
  - `bats tests/test_task_sync.bats`
- 预期：
  - 重复执行 sync 不产生重复候选项，候选项同步时间戳（如 `source.last_synced_at`）正常更新。

### Task 3：实现 roadmap 全景排布与 `Now` 事项物化
- 文件：
  - 修改 `lib/task_actions.sh`
  - 修改 `lib/flow.sh`（在关键节点消费 roadmap 排布结果）
- 测试：
  - 新增 `tests/test_task_roadmap_materialization.bats`
- 验证命令：
  - `bats tests/test_task_roadmap_materialization.bats`
- 预期：
  - 仅当事项进入 `Now`，候选输入才会物化为本地 task 并建立绑定。

### Task 4：Project v2 stage 同步
- 文件：
  - 修改 `lib/task_actions.sh`
  - 新增 `scripts/github-project-sync.sh`（复杂 GraphQL 操作外迁）
- 测试：
  - 新增 `tests/test_task_project_sync.bats`
- 验证命令：
  - `bats tests/test_task_project_sync.bats`
- 预期：
  - `flow_stage` 可映射并更新到 Project 字段。

### Task 5：文档与帮助更新
- 文件：
  - 修改 `docs/standards/command-standard.md`
  - 修改 `CHANGELOG.md`
- 测试：
  - 命令帮助快照检查（若已有）
- 验证命令：
  - `bin/vibe task --help`
- 预期：
  - 新参数在帮助文案中可见，行为说明完整。

## 6. 验证策略（整体）

- 单元/集成测试：
  - `bats tests/test_task_sync.bats tests/test_task_sync_github.bats tests/test_task_roadmap_materialization.bats tests/test_task_project_sync.bats`
- 手工回归：
  - `vibe task sync --provider github --dry-run`
  - `vibe task sync --provider github --direction pull`
  - `vibe flow review`（确认不影响既有 PR 审计链路）

预期输出：
- 本地出现 GitHub issue 候选输入（可供 roadmap 全景排布）。
- roadmap 输出清晰的全景视图（Now/Next/Later/Blocked/Exploration）。
- 仅 `Now` 事项在 registry 生成可执行 task 绑定。
- 已关闭 issue 在本地变为 completed/archived。

## 7. 风险与缓解

- GitHub API 限流/权限不足：
  - 缓解：启动前 `vibe_has gh` + `gh auth status` 检查，失败即 fail fast。
- Project v2 GraphQL 复杂度高：
  - 缓解：先落地 Issue 同步，再分阶段接入 Project。
- 状态枚举不一致（如 `in-progress` vs `in_progress`）：
  - 缓解：在 sync 层统一归一化映射表。

## 8. 变更规模预估

- 代码文件：6-8 个
- 新增测试：3-4 个 bats 文件
- 预计改动：
  - 新增约 `+280 ~ +420` 行
  - 修改约 `120 ~ 200` 行
  - 删除约 `20 ~ 60` 行

本次讨论产物（当前提交范围）仅新增本计划文档，不涉及源码实现。
