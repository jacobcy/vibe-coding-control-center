---
document_type: plan
title: fix flow pr bump atomic
status: proposed
author: Codex GPT-5
created: 2026-03-11
related_docs:
  - lib/flow_pr.sh
  - tests/flow/test_flow_pr_review.bats
---

# Goal

把 `lib/flow_pr.sh` 中 bump、`git add`、`git commit` 的发布链路收紧为原子操作，避免 commit 失败时留下半完成现场。

# Non-Goals

- 不重做 PR 创建入口
- 不修改 GitHub CLI / web 模式选择语义

# Tech Stack

- Zsh shell CLI
- Bats

# Step Tasks

1. 审计 `_flow_pr` 中 bump 后的文件暂存与提交顺序，明确失败路径。
2. 先补失败测试，覆盖 commit 失败时不得静默吞错、不得遗留半完成状态。
3. 最小修改 `lib/flow_pr.sh`，让 bump 链路在失败时立即返回非零并停止后续 PR 创建。
4. 运行针对性测试和 `tests/flow/test_flow_pr_review.bats` 回归。

# Files To Modify

- `lib/flow_pr.sh`
- `tests/flow/test_flow_pr_review.bats`

# Test Command

```bash
bats tests/flow/test_flow_pr_review.bats
```

# Expected Result

- commit 失败时 `_flow_pr` 返回错误
- 不再出现“bump 已落盘但发布链路继续前进”的半成功状态

# Change Summary

- Modified: 2 files
- Approximate lines: 15-50
