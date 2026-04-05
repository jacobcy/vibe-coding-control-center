---
title: 配置标准
author: Claude Sonnet 4.6
created_at: 2026-03-22
category: standards
status: active
version: 1.0
related_docs:
  - config/settings.yaml
  - config/models.json
  - docs/standards/github-code-review-standard.md
---

# 配置标准

## 概述

Vibe Center 使用 `config/settings.yaml` 作为核心配置文件。本文档说明各配置项的作用和使用场景，具体数值请参考配置文件本身。

---

## 配置项说明

### 1. code_limits - 代码量控制

**作用**：定义核心代码范围和代码量限制。

**使用位置**：
- `code_paths`：定义核心代码路径，用于 **risk scoring 的 changed_lines 统计**
- `scripts_paths`：脚本路径，**不计入风险评分**
- `test_paths`：测试路径，**不计入风险评分**
- `single_file_loc` / `total_file_loc`：代码量限制，用于 pre-push 检查

**关键区分**：
- 只有 `code_paths` 的改动计入风险评分
- `scripts_paths` 和 `test_paths` 的改动**不计入**，避免误报

---

### 2. review_scope - 审核范围

**作用**：定义关键路径和公开 API，用于风险识别。

**使用位置**：
- `inspect base` 命令：识别哪些改动属于关键路径或公开 API
- Risk scoring：
  - `critical_path_touch = True` → 风险评分 **+2**
  - `public_api_touch = True` → 风险评分 **+2**

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
- `agent` 表示 preset 名称，具体映射由 `config/models.json` 决定
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

### 5. pr_scoring - PR 评分配置

**作用**：定义风险评分规则和阻断阈值。

#### 5.1 size_thresholds - 规模阈值

**作用**：判断 small/medium/large 的边界。

**使用位置**：
- Risk scoring：根据改动规模分配分数
- 例如：`changed_lines > 500` → xlarge（3分）

#### 5.2 weights - 分数权重

**作用**：每个维度的分数。

**使用位置**：
- Risk scoring 计算：
  ```
  score = changed_lines_score
        + changed_files_score
        + impacted_modules_score
        + critical_path_touch * 2
        + public_api_touch * 2
  ```

**Pre-push vs PR Review 区分**：
- Pre-push **不使用**：`cross_module_symbol_change`, `codex_major`, `codex_critical`
- PR review **使用所有维度**

#### 5.3 thresholds - 风险等级阈值

**作用**：定义风险等级标签（LOW/MEDIUM/HIGH/CRITICAL）。

**使用位置**：
- Risk report 显示：`Risk level: CRITICAL (score: 11/10)`
- 仅用于显示，**不影响行为**

#### 5.4 merge_gate - 阻断条件

**作用**：决定是否阻断并触发 review。

**使用位置**：
- Pre-push hook：
  - `score >= block_on_score_at_or_above` → 阻断推送，触发本地 review
  - `verdict in block_on_verdict` → 阻断推送
- PR review：
  - `score >= block_on_score_at_or_above` → 阻断合并
  - `verdict in block_on_verdict` → 阻断合并

---

## Pre-push vs PR Review 对比

| 维度 | Pre-push | PR Review |
|------|----------|-----------|
| **评估范围** | 本次推送 | 整个分支 |
| **changed_lines** | ✅ 只统计 code_paths | ✅ 只统计 code_paths |
| **critical_path_touch** | ✅ 使用 | ✅ 使用 |
| **public_api_touch** | ✅ 使用 | ✅ 使用 |
| **cross_module_symbol_change** | ❌ 不使用 | ✅ 使用 |
| **codex_major / codex_critical** | ❌ 不使用 | ✅ 使用 |
| **阻断行为** | 阻断推送，触发 review | 阻断合并 |

**设计理由**：
- Pre-push 只关注本次推送，不应过度惩罚
- PR review 关注整个分支影响，需要全面评估

---

## 配置使用示例

### Pre-push Hook 流程

```bash
git push origin task/feature-xyz
  ↓
1. 解析推送范围（只评估本次推送）
  ↓
2. 统计 changed_lines（只统计 code_paths）
  ↓
3. 识别 critical_path_touch / public_api_touch
  ↓
4. 计算风险评分（不使用 codex 维度）
  ↓
5. 如果 score >= 12：触发本地 review
```

### PR Review 流程

```bash
vibe review base origin/main
  ↓
1. 评估整个分支
  ↓
2. 统计 changed_lines（只统计 code_paths）
  ↓
3. 识别所有维度（包括 cross_module, codex）
  ↓
4. 计算风险评分（使用所有维度）
  ↓
5. 如果 score >= 12 或 verdict == "BLOCK"：阻断合并
```

---

## 配置原则

1. **职责分离**：
   - `code_limits.code_paths`：定义核心代码范围
   - `review_scope`：定义重点关注区域
   - `pr_scoring`：定义评分和阻断规则

2. **避免误报**：
   - 只统计核心代码改动
   - Pre-push 不使用 codex 维度
   - 阻断阈值设为 12（而非 9）

3. **配置可调**：所有阈值都在配置文件中，可按需调整

---

## 相关文档

- [配置文件](../../config/settings.yaml) - 查看具体配置值
- [GitHub 智能代码审查系统](./github-code-review-standard.md)
- [Common Rules And Tools](../../.agent/policies/common.md)
