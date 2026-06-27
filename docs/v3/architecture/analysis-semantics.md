# Inspect 分析语义

> **Updated**: 2026-06-28 - Issue #3215 快照子系统退役

本文档说明 Vibe 3.0 中 `inspect` 分析工具的职责和语义。

## 概述

`inspect` 是 Vibe 3.0 的核心分析能力，服务于 `review` 流程，提供单次改动的语义分析。

## Inspect（单次改动分析）

### 职责

- **changed_symbols**: 改动涉及的符号列表（函数、类、方法）
- **风险评分**: 基于 symbols 的风险等级评估
- **函数级影响分析**: 调用链路追踪、依赖关系分析

### 入口

```bash
vibe3 inspect base        # 分析当前分支与 base 的差异
vibe3 inspect uncommit    # 分析未提交的改动
vibe3 inspect symbols     # 查找符号引用
vibe3 inspect files       # 统计文件形状
```

### 消费方

- `review base`: 消费 `inspect base` 输出
- `review pr`: 消费 `inspect pr` 输出

## Review 中的消费契约

`review base` 和 `review pr` 的输入契约不同：

### review base

```python
ReviewRequest(
    changed_symbols=inspect_output.changed_symbols,  # ← inspect 输出
    ...
)
```

- 使用 `inspect` 输出
- Base review 分析当前分支相对于 base 的所有提交累积

### review pr

```python
ReviewRequest(
    changed_symbols=inspect_output.changed_symbols,  # ← inspect 输出
    ...
)
```

- 使用 `inspect` 输出
- PR diff 已隐含结构变化（新增文件、删除文件等）

## 参考实现

源代码位置：

- `src/vibe3/roles/review.py`: `build_base_review_request`, `build_pr_review_request`
- `src/vibe3/analysis/git_diff_summary.py`: Git diff 分析实现

---

**维护者**: Vibe Team