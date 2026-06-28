---
title: 配置标准
author: Claude Sonnet 4.6
created_at: 2026-03-22
category: standards
status: active
version: 1.0
related_docs:
  - config/v3/settings.yaml
  - config/v3/models.json
  - docs/standards/github-code-review-standard.md
---

# 配置标准

## 概述

Vibe Center 使用 `config/v3/settings.yaml` 作为核心配置文件。本项目遵循 **V3 优先原则**：所有 V3 路径下的配置（`config/v3/`）均优先于 legacy V2 配置。

本文档说明各配置项的作用和使用场景，具体数值请参考配置文件本身。

---

## 配置项说明

### 1. code_limits - 代码量控制

**作用**：定义核心代码范围和代码量限制。

**使用位置**：
- `code_paths`：定义核心代码路径，用于 LOC 检查与 review scope 识别
- `scripts_paths`：脚本路径
- `test_paths`：测试路径
- `single_file_loc` / `total_file_loc`：代码量限制，用于 pre-push 与 CI 的 LOC 检查

---

### 2. review_scope - 审核范围

**作用**：定义关键路径和公开 API，用于 review 关注点识别。

**使用位置**：
- `inspect base` 命令：识别哪些改动属于关键路径或公开 API（Review Kernel 命中）
- Review Kernel 分类：命中关键路径影响 review 深度（focused/repeated）

**设计原则**：
- 只标记真正核心的文件（核心流程、关键基础设施）
- 避免过度标记（不要标记整个目录如 `services/`）

---

### 3. review - Review 配置

**作用**：配置 review agent 的行为。

**使用位置**：
- `review base` / `review pr` 命令：调用 codeagent-wrapper
- `agent_config`：指定 agent 类型和参数
- `output_format`：定义 VERDICT 格式契约
- `review_task`：提供 review 任务指引
- `review_prompt`：自定义 prompt 前缀

### 3.1 agent / backend / model 解析规则

**适用范围**：`review.agent_config`、`plan.agent_config`、`run.agent_config`，以及 orchestra 的角色配置（如 `orchestra.assignee_dispatch`、`orchestra.governance`、`orchestra.supervisor_handoff`）。

**标准语义**：
- 允许同时配置 `agent` 和 `backend/model`
- 如果同时配置，`agent` 优先
- 允许只配置 `backend/model`
- `model` 不应单独理解，必须结合当前解析链路判断是否生效

**通用 plan/run/review 链路**：
- `agent` 表示 preset 名称，具体映射由 `config/v3/models.json` 决定
- 只配置 `backend/model` 时，走 backend 直连模式
- 同时配置 `agent` 和 `backend/model` 时，执行入口仍以 `agent` 为准

**orchestra 角色链路**：
- manager / governance / supervisor 等角色也支持 preset 模式和 backend 直连模式
- 同时配置 `agent` 和 `backend/model` 时，执行入口仍以 `agent` 为准
- 但 orchestra resolver 会先把 preset 解析成有效 backend/model，因此额外配置的 `model` 仍可能影响最终模型选择

**使用建议**：
- 想表达“使用某个 preset”时，优先配置 `agent`
- 想绕过 preset 直接指定后端时，只配置 `backend/model`
- 不要把 `backend/model` 误认为一定只是注释字段，是否生效取决于具体解析链路

---

### 4. quality - 质量标准

**作用**：定义测试覆盖率要求。

**使用位置**：
- 未来用于 CI/CD 质量门禁
- 当前作为质量指标

---

## 配置原则

1. **职责分离**：
   - `code_limits.code_paths`：定义核心代码范围
   - `review_scope`：定义重点关注区域

2. **配置可调**：所有阈值都在配置文件中，可按需调整

---

## 相关文档

- [配置文件](../../config/v3/settings.yaml) - 查看具体配置值
- [GitHub 智能代码审查系统](./github-code-review-standard.md)
- [Common Rules And Tools](../../supervisor/policies/common.md)
