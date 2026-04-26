# Inspect 与 Snapshot 互补边界

> **Updated**: 2026-04-20 - Issue #323 收尾文档化

本文档说明 Vibe 3.0 中 `inspect` 和 `snapshot` 两个分析工具的职责边界和互补关系。

## 概述

`inspect` 和 `snapshot` 是两个独立的分析能力，服务于 `review` 流程，但职责不同：

- **inspect**: 单次改动的语义分析（符号级、函数级）
- **snapshot**: 结构基线的对比分析（文件级、模块级）

两者互补而非替代，共同为 `review` 提供影响评估输入。

## Inspect（单次改动分析）

### 职责

- **changed_symbols**: 改动涉及的符号列表（函数、类、方法）
- **风险评分**: 基于 symbols 的风险等级评估
- **函数级影响分析**: 调用链路追踪、依赖关系分析

### 入口

```bash
vibe3 inspect base        # 分析当前分支与 base 的差异
vibe3 inspect commit SHA  # 分析单个提交
vibe3 inspect pr NUMBER   # 分析 PR 改动
```

### 消费方

- `review base`: 消费 `inspect base` 输出
- `review pr`: 消费 `inspect pr` 输出

**两者都消费 inspect 输出**。

## Snapshot（结构基线对比）

### 职责

- **文件/模块变化**: 文件级结构变化（新增、删除、重命名）
- **依赖变化**: import 关系变化、依赖漂移检测
- **基线对比**: 与历史基线的结构对比

### 入口

```bash
vibe3 snapshot build      # 构建结构基线
vibe3 snapshot diff       # 对比当前与基线
vibe3 snapshot show       # 显示基线内容
```

### 消费方

- `review base`: 消费 `snapshot diff` 输出

**仅 base review 使用 snapshot**。

## Review 中的消费契约

`review base` 和 `review pr` 的输入契约不同：

### review base

```python
ReviewRequest(
    changed_symbols=inspect_output.changed_symbols,  # ← inspect 输出
    structure_diff=snapshot_output.structure_diff,   # ← snapshot 输出
    ...
)
```

- 同时使用 `inspect` 和 `snapshot`
- Base review 需要结构基线对比，因为 base 分支可能已有多次提交累积

### review pr

```python
ReviewRequest(
    changed_symbols=inspect_output.changed_symbols,  # ← inspect 输出
    structure_diff=None,                              # ← 不使用 snapshot
    ...
)
```

- 仅使用 `inspect` 输出
- PR diff 已隐含结构变化（新增文件、删除文件等），不需要额外的 snapshot

## 为什么 review pr 不使用 snapshot

PR review 不使用 snapshot 的原因：

1. **PR diff 已包含结构信息**: GitHub PR diff 直接展示文件变化（新增、删除、修改）
2. **单一提交范围**: PR 通常对应一个清晰的提交范围，结构变化明确
3. **避免冗余**: snapshot 的结构对比在 PR 场景下与 inspect 的分析重叠

Base review 需要 snapshot 的原因：

1. **多提交累积**: base review 分析的是当前分支相对于 base 的所有提交累积
2. **结构漂移检测**: 长期分支可能产生结构漂移（文件拆分、模块重组）
3. **历史基线对比**: 需要与历史结构基线对比，捕捉隐性的架构变化

## 参考实现

源代码位置：

- `src/vibe3/roles/review.py`: `build_base_review_request`, `build_pr_review_request`
- `src/vibe3/services/inspect_service.py`: inspect 实现
- `src/vibe3/services/snapshot_service.py`: snapshot 实现

---

**维护者**: Vibe Team