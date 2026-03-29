---
task_id: "2026-03-16-orchestra-integration"
document_type: task-readme
title: "Orchestra 调度器：最小可用实现与后续路线"
current_layer: implementation
status: active
author: "Kiro"
created: "2026-03-16"
last_updated: "2026-03-29"
related_docs:
  - SOUL.md
  - CLAUDE.md
  - STRUCTURE.md
  - docs/standards/glossary.md
  - src/vibe3/models/orchestration.py
  - src/vibe3/services/label_service.py
---

# Task: Orchestra 调度器（MVP）

## 概述

**Orchestra** 是 Vibe Center v3 的 self-hosted webhook 调度子系统（非 GitHub Actions self-hosted runner）。
目标是让 GitHub 事件触发本地 agent 执行，并在无人值守场景下先实现最小闭环。

边界说明：
- 本系统通过 `POST /webhook/github` 接收 GitHub 事件，再在本机执行 `vibe3` 命令。
- 本系统不负责执行 GitHub Actions job；因此不等价于 `runs-on: self-hosted` runner。

## 当前状态

- 层级: Implementation（已落地最小能力）
- 状态: **active**
- 最后更新: 2026-03-29

## 本版已实现（MVP）

### 1) Self-hosted webhook 事件服务（非 Actions runner）

- `vibe3 serve start` 启动 HTTP webhook + heartbeat。
- Webhook 接口：`POST /webhook/github`（支持 HMAC 校验）。
- 心跳兜底：`polling_interval` 默认 900 秒。

代码参考：
- `src/vibe3/orchestra/serve.py`
- `src/vibe3/orchestra/heartbeat.py`
- `src/vibe3/orchestra/webhook_handler.py`

### 2) Issue assignee 触发 manager 执行

- 触发条件：`issues/assigned` 且 assignee 在 `manager_usernames`。
- 执行动作：创建/复用 flow，检查依赖后调度 manager 执行。
- 默认策略：`assignee_dispatch.use_worktree=true`，通过 `vibe3 run --worktree ...` 触发独立临时 worktree 执行。
- 执行语义（当前真源）：
  - 不切换 `serve` 进程当前分支，避免污染守护进程工作树。
  - 优先在已存在的 issue 分支 worktree 执行；不存在则自动创建 `.worktrees/issue-<number>`。
  - 对旧分支兼容：若目标分支暂不支持 `vibe3 run --worktree`，自动降级去掉该参数继续执行。
- 心跳会对当前已分配 issue 做重检（依赖/flow 存在性），避免漏调度。

代码参考：
- `src/vibe3/orchestra/services/assignee_dispatch.py`
- `src/vibe3/orchestra/dependency_checker.py`
- `src/vibe3/orchestra/dispatcher.py`

### 3) PR reviewer 触发 review

- 触发事件：`pull_request/review_requested`、`pull_request/ready_for_review`。
- 触发条件：requested reviewer 命中 `manager_usernames`。
- 执行动作：调度 `vibe3 review pr <pr_number>`。
- 默认策略：优先复用 PR 对应已有 worktree（按 `head_branch` 匹配），不新建 worktree。
- 可选：`pr_review_dispatch.use_worktree=true` 时改为 `vibe3 review pr <pr_number> --worktree`。
- 可选异步：`pr_review_dispatch.async_mode=true` 时，调度为 `vibe3 review pr <pr_number> --async`（tmux 后台执行，不阻塞当前进程）。

代码参考：
- `src/vibe3/orchestra/services/pr_review_dispatch.py`
- `src/vibe3/orchestra/dispatcher.py`

## 事件到执行链路（当前真源）

1. GitHub 触发 issue/pr 事件并投递 webhook
2. `vibe3 serve` 接收事件并验签
3. Orchestra 根据事件类型和配置判断是否触发
4. 命中 issue assignee 规则时，触发 manager 执行链
5. 命中 pr reviewer 规则时，触发 reviewer 执行链

## 文档导航

- [prd-orchestra-integration.md](prd-orchestra-integration.md) - 当前 PRD（含本版边界）
- [github-issue-draft.md](github-issue-draft.md) - follow-up issue 拆分草稿
- [release-handoff.md](release-handoff.md) - 发布接手手册（给后续 agent）
- [debug-reviewer-webhook.md](debug-reviewer-webhook.md) - reviewer webhook 调试与验收手册

## 快速开始

```bash
# 启动 orchestra（webhook 服务）
vibe3 serve start --port 8080 --interval 900

# GitHub webhook 配置事件：
# - Issues
# - Pull requests
# - Issue comments
#
# URL:
#   http://<server>:8080/webhook/github
```

## 本版边界（明确不做）

- 不实现完整 orchestrator 智能决策（优先级重排/全局调度策略）。
- 不实现 manager 的长事务状态机与失败补偿。
- 不在本版引入新的复杂持久化队列。

以上能力进入 follow-up，按 issue 分阶段推进。
