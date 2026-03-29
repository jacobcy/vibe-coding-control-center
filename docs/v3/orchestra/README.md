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

**Orchestra** 是 Vibe Center v3 的 self-hosted 调度子系统。
目标是让 GitHub 事件触发本地 agent 执行，并在无人值守场景下先实现最小闭环。

## 当前状态

- 层级: Implementation（已落地最小能力）
- 状态: **active**
- 最后更新: 2026-03-29

## 本版已实现（MVP）

### 1) Self-hosted 事件服务

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
- 心跳会对当前已分配 issue 做重检（依赖/flow 存在性），避免漏调度。

代码参考：
- `src/vibe3/orchestra/services/assignee_dispatch.py`
- `src/vibe3/orchestra/dependency_checker.py`
- `src/vibe3/orchestra/dispatcher.py`

### 3) PR reviewer 触发 review

- 触发事件：`pull_request/review_requested`、`pull_request/ready_for_review`。
- 触发条件：requested reviewer 命中 `manager_usernames`。
- 执行动作：调度 `vibe3 review pr <pr_number>`。

代码参考：
- `src/vibe3/orchestra/services/pr_review_dispatch.py`
- `src/vibe3/orchestra/dispatcher.py`

## 文档导航

- [prd-orchestra-integration.md](prd-orchestra-integration.md) - 当前 PRD（含本版边界）
- [github-issue-draft.md](github-issue-draft.md) - follow-up issue 拆分草稿
- [debug-reviewer-webhook.md](debug-reviewer-webhook.md) - reviewer webhook 调试与验收手册

## 快速开始

```bash
# 启动 orchestra（self-hosted）
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
