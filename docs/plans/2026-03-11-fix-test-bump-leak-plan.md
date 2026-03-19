---
document_type: plan
title: fix test bump leak
status: proposed
author: Codex GPT-5
created: 2026-03-11
related_docs:
  - tests/flow/test_flow_pr_review.bats
  - lib/flow_pr.sh
  - .agent/context/task.md
---

# Goal

让 `tests/flow/test_flow_pr_review.bats` 中与 `_flow_pr` 相关的用例在隔离目录内运行，避免 `scripts/hooks/bump.sh` 副作用泄漏到仓库根目录。

# Non-Goals

- 不重写 `_flow_pr` 的整体发布流程
- 不修改无关 PR base 逻辑

# Tech Stack

- Bats
- Zsh shell CLI

# Step Tasks

1. 审计 `tests/flow/test_flow_pr_review.bats` 中会触发 bump 的用例，确认是否仍在仓库根目录执行。
2. 先写或调整失败测试，固定“测试不得污染仓库根目录”的行为。
3. 在测试侧引入 fixture / `mktemp -d` / `cd "$fixture"` 隔离，必要时只最小补充实现侧防护。
4. 运行 `bats tests/flow/test_flow_pr_review.bats` 验证全绿。

# Files To Modify

- `tests/flow/test_flow_pr_review.bats`
- `lib/flow_pr.sh`（仅在测试隔离不足时）

# Test Command

```bash
bats tests/flow/test_flow_pr_review.bats
```

# Expected Result

- bump 相关测试仅污染 fixture
- 仓库根目录不再残留 `VERSION` / `CHANGELOG.md` 副作用

# Change Summary

- Modified: 1-2 files
- Approximate lines: 10-40
