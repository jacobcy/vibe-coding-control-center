---
document_type: plan
title: Phase 05 - Polish & Cleanup
status: draft
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-16
related_docs:
  - docs/v3/handoff/v3-rewrite-plan.md
  - docs/v3/infrastructure/02-architecture.md
  - docs/v3/infrastructure/03-coding-standards.md
  - docs/v3/infrastructure/04-test-standards.md
---

# Phase 05: Polish & Cleanup

**Goal**: Optimize performance, remove technical debt, and ensure final production readiness.

## 1. 架构约束

见 [01-command-and-skeleton.md](01-command-and-skeleton.md) §通用架构约束

## 2. Context Anchor (Optional)
If you require more than technical scope, refer to the [Vibe 3.0 Master Plan](v3-rewrite-plan.md).

## 3. Pre-requisites (Executor Entry)
- [ ] All feature domains (Flow, Task, PR, Handoff) report functionally complete.
- [ ] No critical regressions in terminal output.
- [ ] Phase 04 cutover completed successfully.

## 4. Technical Health

- **Code Cleanup**: Remove all `TODO` comments, `print()` debugging statements, and unused imports.
- **Refactoring**: Consolidate redundant logic identified during Phase 1-4 implementations.
- **Linting**: Run `black`, `ruff`, and `mypy --strict` on the entire `src/` directory.

## 5. Performance & Quality

- **Execution Timing**: Ensure `vibe3 flow status` (locally) completes in under 1.0 seconds.
- **Error Handling**: Verify that all domain managers have comprehensive try-except blocks that log errors with context.
- **Logging Audit**: Ensure logs are succinct but sufficient for another Agent to debug a failure.

## 6. Success Criteria (Technical)

- [ ] All `src/` modules pass strict linting/typing with zero errors.
- [ ] Average command execution time for local-only operations is < 1s.
- [ ] No temporary files or debug artifacts remain in the workspace.
- [ ] Comprehensive smoke test suite in `tests3/` passes with 100% success.

## 7. Development Notes

### 5.1 代码重构模式
**参考**: Phase 02 中 `flow.py` 的重构经验（从 ~160 行减少到 96 行）

**重构步骤**：
1. **识别 UI 逻辑**：查找所有 `print()` 和 Rich Table 调用
2. **提取到 UI 层**：创建 `ui/flow_ui.py` 等模块
3. **简化 Command 层**：只保留参数解析和 Service 调用
4. **验证功能**：运行所有命令确保输出正确

**常见问题**：
- ❌ Command 层包含业务逻辑（如数据转换）
- ❌ Service 层包含 UI 逻辑（如颜色标注）
- ❌ 使用 `print()` 而非 `logger` 或 `rich`

**解决方案**：
- 使用 `rich.print()` 进行用户输出
- 使用 `loguru.logger` 记录调试信息
- UI 层函数命名规范：`render_<action>()`

### 5.2 Line Count 优化技巧
**经验教训**：
- ✅ 合并多行参数定义为单行（使用 typer）
- ✅ 移除不必要的空行（但保持可读性）
- ✅ 提取重复的错误处理逻辑到 UI 层

**示例**：
```python
# ❌ 多行定义（占用 4 行）
status_filter: Annotated[
    Optional[str],
    typer.Option("--status", help="Filter by status"),
] = None,

# ✅ 单行定义（占用 1 行）
status_filter: Annotated[Optional[str], typer.Option("--status", help="Filter by status")] = None,
```

### 5.3 Type Safety 检查
**参考**: [03-coding-standards.md](../implementation/03-coding-standards.md) § "Type Safety"

**必须通过**：
```bash
mypy --strict src/vibe3/
```

**常见类型错误**：
- ❌ 缺少返回类型注解
- ❌ 使用 `Any` 类型
- ❌ Optional 类型未处理 None 情况

**修复模式**：
```python
# ❌ 错误：缺少类型注解
def get_flow(branch):
    return self.store.get_flow_state(branch)

# ✅ 正确：完整类型注解
def get_flow(self, branch: str) -> FlowState | None:
    flow_data = self.store.get_flow_state(branch)
    if not flow_data:
        return None
    return FlowState(**flow_data)
```

### 5.4 Linting 配置
**工具链**：
```bash
# 格式化代码
black src/vibe3/

# Lint 检查
ruff check src/vibe3/

# 类型检查
mypy --strict src/vibe3/
```

**配置文件**（`pyproject.toml`）：
```toml
[tool.black]
line-length = 100
target-version = ['py39']

[tool.ruff]
select = ["E", "F", "I", "N", "W"]
ignore = ["E501"]  # line too long

[tool.mypy]
python_version = "3.9"
strict = true
warn_return_any = true
```

### 5.5 Performance 优化
**参考**: [2026-03-13-vibe3-parallel-rebuild-design.md](../../plans/2026-03-13-vibe3-parallel-rebuild-design.md) § "性能规格"

**优化要点**：
- ✅ 使用 SQLite 连接池（避免频繁开关）
- ✅ 批量查询代替多次单条查询
- ✅ 延迟加载非必需数据（如 PR 状态）

**性能测试**：
```bash
# 测试命令执行时间
time vibe3 flow status
time vibe3 flow list
time vibe3 task list
```

**预期结果**：
- `flow status`: < 500ms
- `flow list`: < 2s (100 个 flow)

### 5.6 Error Message 审查
**标准格式**：
```
✗ Failed to <action>: <error-message>

Recovery: <suggested-action>
```

**审查要点**：
- ✅ 所有错误消息包含恢复建议
- ✅ 不暴露内部实现细节（如 SQL 错误）
- ✅ 使用 Rich 颜色标注（`[red]`, `[yellow]`）

**示例**：
```python
# ❌ 错误：内部错误暴露
print(f"Database error: {e}")

# ✅ 正确：用户友好的错误消息
render_error(f"Failed to create flow: {e}")
print("Recovery: Check if .git/vibe3/ directory exists and is writable")
```

### 5.7 Testing Coverage 验证

**工具**：
```bash
# 运行测试并生成覆盖率报告
uv run pytest tests/ --cov=src/vibe3 --cov-report=html
```

**测试标准**: 见 [04-test-standards.md](../infrastructure/04-test-standards.md)

### 5.8 Documentation 完整性检查
**必须文档化**：
- 所有 Public API（函数、类）
- 所有命令的使用说明（`--help`）
- 所有架构决策（在 `docs/v3/` 中）

**文档格式**：
```python
def create_flow(self, slug: str, branch: str, task_id: str | None = None) -> FlowState:
    """Create a new flow.

    Args:
        slug: Flow name/slug
        branch: Git branch name
        task_id: Optional task ID to bind

    Returns:
        Created flow state

    Raises:
        RuntimeError: If flow creation fails
    """
```

## 6. Handoff for Final Reviewer
- [ ] Provide a summary of the 5 layers' final file paths.
- [ ] Ensure `v3-rewrite-plan.md` Checklist is fully marked based on technical evidence.
