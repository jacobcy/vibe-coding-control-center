---
document_type: plan
author: GPT-5 Codex
created: 2026-03-08
status: draft
related_docs:
  - docs/tasks/2026-03-08-roadmap-style-polish/prd-v1.md
  - docs/tasks/2026-03-08-create-issue-workflow/prd-v1.md
  - docs/standards/doc-quality-standards.md
---

# Plan: PR 74 Minimal Fixes

## Goal
修复 PR 74 中已复现的行为回归和文档契约不一致问题，使其恢复可发布状态。

## Non-goals
- 不扩展 roadmap 新功能
- 不重做 issue workflow 设计
- 不处理与本 PR 无关的 ShellCheck warning 或 Serena 配置问题

## Tech Stack
- Zsh CLI
- Bats
- ShellCheck

## Tasks
1. 为 roadmap 文本输出补充/复用失败用例，锁定“非 TTY 不应输出 ANSI 转义序列”的契约。
2. 在 `lib/roadmap_query.sh` 中实现最小颜色门控，保持交互输出可读，同时不污染管道和测试输出。
3. 修正文档与 skill：
   - 统一 `/vibe-issue` 的入口描述
   - 明确 `vibe-task` label 为 roadmap sync 的必需前提
   - 修复无效 `related_docs` 路径和不合规 `author`
4. 运行针对性测试和 lint，确认修复结果。

## Files To Modify
- `docs/plans/2026-03-08-pr-74-minimal-fixes.md`
- `lib/roadmap_query.sh`
- `tests/test_roadmap.bats`
- `.agent/workflows/vibe-issue.md`
- `skills/vibe-issue/SKILL.md`

## Test Commands
- `bats tests/test_roadmap.bats tests/test_vibe.bats`
- `bash scripts/lint.sh`

## Expected Result
- `roadmap status/list/show` 在非 TTY 下不输出 ANSI 转义序列
- 现有 roadmap/vibe 测试恢复通过
- `vibe-issue` 文档和 skill 对入口与 roadmap sync 前提保持一致
- 新增/修改文档满足当前 frontmatter 规范

## Change Summary
- 预计修改 5 个文件
- 预计新增/修改约 50-90 行
- 不删除任何命令或子系统
