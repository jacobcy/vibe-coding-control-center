---
task_id: "2026-03-16-orchestra-integration"
document_type: task-readme
title: "Orchestra 调度器设计：任务板驱动的自主 Implementation Run"
current_layer: prd
status: active
author: "Kiro"
created: "2026-03-16"
last_updated: "2026-03-24"
related_docs:
  - SOUL.md
  - CLAUDE.md
  - STRUCTURE.md
  - docs/standards/glossary.md
  - src/vibe3/models/orchestration.py
  - src/vibe3/services/label_service.py
---

# Task: Orchestra 调度器设计

## 概述

**Orchestra** 是 Vibe Center v3 的调度器子系统，负责从任务板（GitHub Issues）拉取任务并自动分发给 Agent 执行。

## 当前状态

- 层级: PRD（需求分析层）→ Spec（规范层）
- 状态: **active** - 准备实现
- 最后更新: 2026-03-24

## 已完成基础

### PR #236 状态机核心

| 组件 | 文件 | 状态 |
|------|------|------|
| 状态枚举 | `src/vibe3/models/orchestration.py` | ✅ |
| 状态迁移规则 | `src/vibe3/models/orchestration.py` | ✅ |
| LabelService API | `src/vibe3/services/label_service.py` | ✅ |
| GitHub Actions | `.github/workflows/issue-state-sync.yml` | ✅ |

### 状态迁移图

```
ready → claimed → in-progress → review → merge-ready → done
                    ↓
               blocked / handoff
```

## 文档导航

### PRD / 需求分析
- [prd-orchestra-integration.md](prd-orchestra-integration.md) - v2 设计

### Spec / 规范（待创建）
- [ ] spec-serve-command.md - `vibe3 serve` 命令规范
- [ ] spec-state-triggers.md - 状态触发映射

### 已完成任务
- [github-issue-draft.md](github-issue-draft.md) - 初始 issue 草稿

## 实现计划

### Phase 1: 核心调度（本周）

```
src/vibe3/orchestra/
├── __init__.py
├── serve.py          # vibe3 serve 命令
├── poller.py         # GitHub 标签轮询
├── router.py         # 状态变化路由
├── dispatcher.py     # 命令调度执行
└── config.py         # Orchestra 配置
```

**目标**：
- `vibe3 serve` 后台服务
- 监听 GitHub 标签变化
- 触发 plan/run/review 命令

### Phase 2: 集成测试（下周）

- 单元测试覆盖率 >= 80%
- 端到端流程测试
- 文档更新

### Phase 3: 主控 Agent（后续）

- 多 agent 协调
- 错误恢复机制
- 监控面板

## 关键约束

1. **状态机已就绪** - 使用 `LabelService` API
2. **简化架构** - 先实现核心调度，后续再考虑主控 agent
3. **增量开发** - 基于现有 plan/run/review 命令
4. **幂等性** - 相同状态变化不重复执行
5. **可观测性** - 所有操作写入 handoff.db

## 快速开始

```bash
# 启动 serve 服务
vibe3 serve --interval 60

# 创建 issue 并添加标签
gh issue create --title "feat: new feature" --body "..."
gh issue edit 42 --add-label "state/ready"

# serve 自动检测并触发:
#   ready → plan
#   claimed → run
#   review → review
```