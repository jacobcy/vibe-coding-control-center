# Plan: Services 拆分 + Dead Code 清理

**Issue**: #396
**Branch**: `refactor/services-decomposition`
**前置**: PR #395 已合并（analysis/ 模块和 agents/ prompt 组装器已落地）

---

## 当前状态

PR #395 已完成大部分结构拆分：

- `src/vibe3/analysis/` 已创建（15 个文件）
- `agents/` 已扩充 prompt 组装器（plan_prompt, run_prompt, review_prompt, review_pipeline_helpers）
- `tests/vibe3/analysis/` 和 `tests/vibe3/agents/` 已创建（部分覆盖）
- `services/` 已从 47 个文件降至 28 个

本 PR 完成剩余收尾工作：

---

## Task 1: 补全 tests/ 迁移

**背景**: PR #395 创建了 `tests/vibe3/analysis/`，但以下测试文件仍留在 `tests/vibe3/services/`：

需移动至 `tests/vibe3/analysis/`：
- `test_coverage_check.py`
- `test_pre_push_inspect_summary.py`
- `test_pre_push_scope.py`
- `test_pre_push_test_selector.py`
- `test_serena_service.py`
- `test_serena_service_skipped_files.py`
- `test_snapshot_diff_section.py`
- `test_snapshot_service.py`

**步骤**：
1. `git mv tests/vibe3/services/test_*.py tests/vibe3/analysis/`（逐文件）
2. 验证：`uv run pytest tests/vibe3/analysis/ -q`

---

## Task 2: Dead Code 清理（来自 PR #395 review）

### DC-1: 删除 `run_review_agent()`

- 文件: `src/vibe3/agents/review_runner.py` L65-95
- 函数已从 `__all__` 移除为宜；生产路径走 `CodeagentBackend.run()` → `run_execution_pipeline()`
- 同步删除 `tests/vibe3/services/test_agent_result.py` 中相关测试（或迁移至测 `CodeagentBackend`）

### DC-2: 删除 `ReviewAgentOptions` / `ReviewAgentResult` 别名

- 文件: `src/vibe3/models/review_runner.py` L42, L83
- 全仓库无调用方，直接删除两行

### DC-3: 评估 `AgentResult.from_completed_process()`

- 文件: `src/vibe3/models/review_runner.py` L63-75
- 生产代码无调用，若无扩展计划则删除；否则加注释标明用途

### DC-4: 删除空 `TYPE_CHECKING` 块

- 文件: `src/vibe3/models/review_runner.py` L5-8
- `if TYPE_CHECKING: pass` 无效，直接删除

**步骤**：
1. 处理 `models/review_runner.py`（DC-2, DC-3, DC-4）
2. 处理 `agents/review_runner.py`（DC-1）
3. 更新相关测试
4. 验证：`uv run mypy src/vibe3/ && uv run pytest tests/vibe3/ -q`

---

## Task 3: Bug 修复（来自 PR #395 review）

### BUG-1: 删除 `runner.py` 重复 echo

- 文件: `src/vibe3/agents/runner.py` L134
- `execute_sync()` 和 `run_execution_pipeline()` 各打一次相同消息，删除 `runner.py:134` 那行

### BUG-2: 修复 `AgentOptions` 隐式 re-export

- `src/vibe3/orchestra/config.py:9` 和 `src/vibe3/orchestra/master.py:13` 写
  `from vibe3.agents.review_runner import AgentOptions`
- `AgentOptions` 定义在 `models/review_runner`，review_runner 是隐式再导出
- 修复：将两处 import 改为 `from vibe3.models.review_runner import AgentOptions`

### BUG-3: 修复 `_build_cli_command()` sys.argv fallback

- 文件: `src/vibe3/agents/runner.py` L202
- fallback 到 `sys.argv[1:]` 前增加验证：`sys.argv[0]` 必须以 `cli.py` 或 `vibe3` 结尾
- 验证失败时抛出 `UserError`（按项目错误分类规范）

**步骤**：
1. 修复 BUG-1（单行删除）
2. 修复 BUG-2（2 处 import 替换）
3. 修复 BUG-3（增加前置验证）
4. 验证：`uv run pytest tests/vibe3/agents/ -q`

---

## Task 4: 修复 test_pr_workflow.py 警告

- 文件: `tests/vibe3/integration/test_pr_workflow.py`
- 4 个测试函数用 `return bool` 而不是 `assert`，产生 `PytestReturnNotNoneWarning`
- 修复：将 `return some_bool` 改为 `assert some_bool`

---

## 验收标准

- `uv run mypy src/vibe3` 零错误
- `uv run pytest` 全部通过，零 warning（PytestReturnNotNoneWarning 消除）
- `services/` 文件数不变（结构已在 #395 稳定）
- `tests/vibe3/services/` 不再包含属于 analysis/ 的测试文件
- 无业务逻辑改动

---

## 执行顺序

```
Task 1 (tests 迁移)  ->  Task 4 (test warning)  ->  Task 2 (dead code)  ->  Task 3 (bugs)
```

建议逐 Task 提交，保持独立 commit 便于 revert。
