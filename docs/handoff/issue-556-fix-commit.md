[manager] VERDICT = BLOCK 后的修复指令

## 问题根因
Executor 报告"Execution complete"但**未提交代码**，所有更改仅存在于工作目录中。

## 必须修复的问题

1. **提交所有已修改文件**（共 9 个）：
   - docs/ARCHITECTURE_GUIDE.md
   - docs/standards/vibe3-event-driven-standard.md
   - src/vibe3/domain/events/__init__.py
   - src/vibe3/domain/events/flow_lifecycle.py
   - src/vibe3/domain/handlers/dispatch.py
   - src/vibe3/domain/handlers/issue_state_dispatch.py
   - src/vibe3/ui/flow_ui_timeline.py
   - tests/vibe3/domain/handlers/test_dispatch.py
   - tests/vibe3/domain/test_events.py

2. **提交前验证**：
   - 运行完整测试套件：`uv run pytest tests/vibe3/domain/test_events.py tests/vibe3/domain/handlers/test_dispatch.py -v`
   - 运行类型检查：`uv run mypy src/vibe3`
   - 运行 lint：`uv run ruff check src/vibe3 tests/vibe3`

3. **创建提交**：
   - 使用清晰的提交信息，说明清理向后兼容别名的变更内容
   - 确保提交信息符合项目规范

## 参考
- audit_ref: docs/reports/issue-556-audit-report.md
- report_ref: docs/reports/issue-556-execution-report.md
- plan_ref: docs/plans/issue-556-event-alias-cleanup.md

## 风险提示
- 当前工作**未提交**，存在丢失风险
- 必须先提交，才能继续 review 流程
