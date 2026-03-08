---
document_type: plan
author: Antigravity
created: 2026-03-08
status: draft
related_docs:
  - docs/tasks/2026-03-08-roadmap-style-polish/prd-v1.md
---

# Plan: CLI Roadmap Style Polish

## 1. 目标
美化 `vibe roadmap` 的输出风格，支持状态染色和结构化展示。

## 2. 任务分解

### Phase 1: 逻辑更新
- [x] **Task 1.1**: 更新 `lib/roadmap_query.sh` 中的 `_vibe_roadmap_show` 内容。
  - 引入 `log_info`, `log_success` 等工具函数辅助。
  - 实现 `_vibe_roadmap_color_status` 内部函数。
- [x] **Task 1.2**: 更新 `_vibe_roadmap_list` 的输出，也增加简单的状态颜色标识。

### Phase 2: 全局对齐
- [x] **Task 2.1**: 检查 `vibe roadmap status` 的输出，确保其标题和汇总信息也使用了 `BOLD` 或其他样式。

## 3. 验证命令
- [ ] `bin/vibe roadmap show gh-52` (已完成的)
- [ ] `bin/vibe roadmap show gh-56` (正在做的)
- [ ] `bin/vibe roadmap list --status current`
