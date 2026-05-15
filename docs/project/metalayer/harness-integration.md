---
document_type: spec
title: Harness 集成接口规范
status: draft
scope: meta-layer-integration
author: Claude Sonnet
related_docs:
  - README.md
  - metalayer-prd.md
---

# Harness 集成接口规范

本文档定义 Harness 向 Meta Layer 上报事件的接口。

## 1. 目标

在不改变现有架构的前提下，让 Harness 向 Meta Layer 提供执行信号。

## 2. 设计原则

- 不改核心架构
- 不增加复杂度
- 只增加"上报"

## 3. 必须修改的点（仅 3 处）

### 3.1 Tool 执行后

**位置**：`shell_executor`、`file_editor`、`git_provider`

**上报格式**：

```json
POST /events
{
  "type": "tool_success | tool_failed",
  "payload": {
    "tool": "...",
    "error": "...",
    "output": "..."
  }
}
```

### 3.2 Test 执行后

**上报格式**：

```json
POST /events
{
  "type": "test_passed | test_failed"
}
```

### 3.3 用户修改代码

**触发条件**：git diff 检测到文件被修改

**上报格式**：

```json
POST /events
{
  "type": "user_corrected",
  "payload": {
    "diff": "..."
  }
}
```

## 4. 可选增强

- compile error 上报
- lint error 上报
- PR review 上报

## 5. 禁止事项

**不允许在 Harness 中**：

- 写 skill 逻辑
- 写 prompt 注入
- 调用 LLM 总结经验

**Harness 只负责**：执行 + 上报

## 6. 配置

```yaml
meta_layer_url: http://localhost:3000
```

## 7. 完成标准

- [ ] 所有 tool 行为可追踪
- [ ] test 可追踪
- [ ] 用户修改可追踪
- [ ] 不影响原有功能
